import base64
import json
from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
import commercial_service
import routes_auth
import routes_commercial
import routes_merchant
import routes_user
from auth_utils import hash_password
from device_management_service import group_device_payloads_by_kami
from main import app as fastapi_app
from models import (
    AdminUser,
    App,
    AppNotice,
    Device,
    DeviceIpRisk,
    EndUser,
    EventLog,
    Kami,
    KamiBatch,
    KamiDeviceBinding,
    KamiStatus,
    KamiType,
    RechargeChannel,
    RechargeBonusRule,
    RechargeMode,
    RechargeOrder,
    RechargeOrderStatus,
    RechargeOption,
    RechargePaymentChannel,
    KamiSpec,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaTransactionType,
    UserQuotaType,
    get_now_naive,
)
from user_quota_service import issue_user_kamis


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def override_session_factory(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    return override_session


def override_admin_user():
    return {"sub": "admin", "user_id": 1, "is_admin": True}


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


CONFIRM_CHANGE_RECHARGE_CONFIG = "确认修改充值配置"
CONFIRM_DELETE_PAYMENT_QRCODE = "确认删除二维码"
CONFIRM_APPROVE_RECHARGE_ORDER = "确认审核入账"
CONFIRM_EXPIRE_RECHARGE_ORDER = "确认关闭订单"
CONFIRM_CLEANUP_PROOF_FILES = "确认清理凭证"
CONFIRM_DELETE_MERCHANT = "确认删除用户"
CONFIRM_DELETE_APP = "确认删除应用"


CONFIRM_CHANGE_ISSUE_PRICING = "确认修改发卡额度"


def seed_admin_and_merchant(session: Session) -> tuple[AdminUser, EndUser]:
    admin = AdminUser(
        username="admin",
        password_hash=hash_password("admin-pass"),
        is_admin=True,
        status=1,
    )
    merchant = EndUser(
        username="merchant-a",
        password_hash=hash_password("merchant-pass"),
        status=1,
    )
    session.add(admin)
    session.add(merchant)
    session.commit()
    session.refresh(admin)
    session.refresh(merchant)
    return admin, merchant


def test_shared_login_routes_admin_and_merchant_roles():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_auth.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)

    try:
        admin_response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-pass"},
        )
        assert admin_response.status_code == 200
        admin_data = admin_response.json()
        assert admin_data["success"] is True
        assert admin_data["role"] == "admin"
        assert admin_data["redirect"] == "/admin/dashboard"
        assert admin_data["user_info"]["username"] == "admin"

        merchant_response = client.post(
            "/api/v1/auth/login",
            json={"username": "merchant-a", "password": "merchant-pass"},
        )
        assert merchant_response.status_code == 200
        merchant_data = merchant_response.json()
        assert merchant_data["success"] is True
        assert merchant_data["role"] == "merchant"
        assert merchant_data["redirect"] == "/merchant/dashboard"
        assert merchant_data["user_info"]["username"] == "merchant-a"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_shared_register_creates_merchant_and_blocks_application_user_console_access():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_auth.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        admin = AdminUser(
            username="taken-admin",
            password_hash=hash_password("admin-pass"),
            is_admin=True,
            status=1,
        )
        app = App(
            app_id="app_usage",
            name="Usage App",
            app_secret="secret-usage",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        application_user = EndUser(
            app_id="app_usage",
            username="usage-user",
            password_hash=hash_password("usage-pass"),
            status=1,
        )
        session.add(admin)
        session.add(app)
        session.add(application_user)
        session.commit()
        session.refresh(application_user)
        application_user_token = routes_user.create_user_access_token(application_user)

    try:
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "merchant-new",
                "password": "merchant-pass",
                "email": "merchant@example.com",
                "phone": "13800000000",
            },
        )
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert register_data["success"] is True
        assert register_data["role"] == "merchant"
        assert register_data["redirect"] == "/merchant/dashboard"
        assert register_data["user_info"]["username"] == "merchant-new"
        assert register_data["user_info"]["app_id"] is None

        with Session(engine) as session:
            merchant = session.exec(
                select(EndUser).where(EndUser.username == "merchant-new")
            ).one()
            assert merchant.app_id is None

        duplicate_admin_response = client.post(
            "/api/v1/auth/register",
            json={"username": "taken-admin", "password": "merchant-pass"},
        )
        assert duplicate_admin_response.status_code == 400

        application_login_response = client.post(
            "/api/v1/auth/login",
            json={"username": "usage-user", "password": "usage-pass"},
        )
        assert application_login_response.status_code == 403

        merchant_api_response = client.get(
            "/api/v1/merchant/quotas",
            headers=auth_headers(application_user_token),
        )
        assert merchant_api_response.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_profile_update_syncs_visible_profile_and_cached_relations():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        owned_app = App(
            app_id="app_profile_owned",
            name="Profile Owned App",
            app_secret="secret-owned",
            rsa_public_key="public-owned",
            rsa_private_key="private-owned",
            created_by=merchant.username,
            owner_user_id=merchant.id,
            status=1,
        )
        authorized_app = App(
            app_id="app_profile_authorized",
            name="Profile Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public-authorized",
            rsa_private_key="private-authorized",
            created_by="admin",
            status=1,
        )
        session.add_all(
            [
                owned_app,
                authorized_app,
                UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=12),
                UserAppAuthorization(
                    app_id=authorized_app.app_id,
                    user_id=merchant.id,
                    username=merchant.username,
                    granted_by="admin",
                ),
            ]
        )
        session.commit()
        session.refresh(merchant)
        merchant_id = merchant.id
        token = routes_user.create_user_access_token(merchant)

    try:
        update_response = client.put(
            "/api/v1/merchant/me",
            headers=auth_headers(token),
            json={
                "username": "merchant-renamed",
                "email": "merchant@example.com",
                "phone": "13800000000",
            },
        )
        assert update_response.status_code == 200
        update_data = update_response.json()["data"]
        assert update_data["username"] == "merchant-renamed"
        assert update_data["email"] == "merchant@example.com"
        assert update_data["phone"] == "13800000000"

        me_response = client.get("/api/v1/merchant/me", headers=auth_headers(token))
        assert me_response.status_code == 200
        assert me_response.json()["data"]["username"] == "merchant-renamed"

        with Session(engine) as session:
            updated_merchant = session.get(EndUser, merchant_id)
            assert updated_merchant is not None
            assert updated_merchant.username == "merchant-renamed"
            assert updated_merchant.email == "merchant@example.com"
            assert updated_merchant.phone == "13800000000"

            owned_app_row = session.exec(
                select(App).where(App.app_id == owned_app.app_id)
            ).one()
            assert owned_app_row.created_by == "merchant-renamed"

            quota_account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            assert quota_account.username == "merchant-renamed"

            authorization = session.exec(
                select(UserAppAuthorization).where(UserAppAuthorization.app_id == authorized_app.app_id)
            ).one()
            assert authorization.username == "merchant-renamed"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_and_merchant_account_profile_password_and_avatar_routes_round_trip():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_auth.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        admin = AdminUser(username="admin-route", password_hash=hash_password("admin-pass"), is_admin=True, status=1)
        merchant = EndUser(username="merchant-route", password_hash=hash_password("merchant-pass"), status=1)
        session.add_all([admin, merchant])
        session.commit()
        session.refresh(admin)
        session.refresh(merchant)

    admin_token = routes_admin.create_access_token({"sub": admin.username, "user_id": admin.id, "is_admin": True})
    merchant_token = routes_user.create_user_access_token(merchant)

    try:
        admin_me = client.get("/api/v1/admin/me", headers=auth_headers(admin_token))
        assert admin_me.status_code == 200
        assert admin_me.json()["data"]["role"] == "admin"
        assert admin_me.json()["data"]["avatar_url"] is None

        password_reject = client.put(
            "/api/v1/admin/me/password",
            headers=auth_headers(admin_token),
            json={"old_password": "wrong-pass", "new_password": "new-admin-pass"},
        )
        assert password_reject.status_code == 400

        password_update = client.put(
            "/api/v1/admin/me/password",
            headers=auth_headers(admin_token),
            json={"old_password": "admin-pass", "new_password": "new-admin-pass"},
        )
        assert password_update.status_code == 200

        relogin = client.post(
            "/api/v1/auth/login",
            json={"username": "admin-route", "password": "new-admin-pass"},
        )
        assert relogin.status_code == 200
        assert relogin.json()["user_info"]["avatar_url"] is None

        merchant_avatar = client.post(
            "/api/v1/merchant/me/avatar",
            headers=auth_headers(merchant_token),
            files={"avatar_file": ("avatar.png", b"fake-png-data", "image/png")},
        )
        assert merchant_avatar.status_code == 200
        avatar_url = merchant_avatar.json()["data"]["avatar_url"]
        assert avatar_url.startswith("/api/v1/profile/avatars/")

        served_avatar = client.get(avatar_url)
        assert served_avatar.status_code == 200
        assert served_avatar.headers["content-type"].startswith("image/png")

        merchant_me = client.get("/api/v1/merchant/me", headers=auth_headers(merchant_token))
        assert merchant_me.status_code == 200
        assert merchant_me.json()["data"]["role"] == "merchant"
        assert merchant_me.json()["data"]["avatar_url"] == avatar_url
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_application_users_and_commercial_merchants_are_listed_separately():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        app = App(
            app_id="app_usage",
            name="Usage App",
            app_secret="secret-usage",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        merchant = EndUser(username="merchant-only", password_hash=hash_password("secret123"), status=1)
        usage_user = EndUser(
            app_id="app_usage",
            username="usage-only",
            password_hash=hash_password("secret123"),
            status=1,
        )
        session.add(app)
        session.add(merchant)
        session.add(usage_user)
        session.commit()

    try:
        end_users_response = client.get("/api/v1/admin/end-users")
        assert end_users_response.status_code == 200
        end_user_items = end_users_response.json()["data"]["items"]
        assert [item["username"] for item in end_user_items] == ["usage-only"]

        stats_response = client.get("/api/v1/admin/end-users/stats")
        assert stats_response.status_code == 200
        assert stats_response.json()["data"]["total"] == 1

        merchants_response = client.get("/api/v1/admin/commercial/merchants")
        assert merchants_response.status_code == 200
        merchant_items = merchants_response.json()["data"]["items"]
        assert [item["username"] for item in merchant_items] == ["merchant-only"]
        assert merchant_items[0]["app_id"] is None
        assert "app_create_balance" not in merchant_items[0]
        assert "recharge_balance" not in merchant_items[0]
        assert "kami_issue_balance" in merchant_items[0]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_commercial_merchant_detail_aggregates_apps_authorizations_and_usage_users():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="detail-merchant", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="detail-other", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        self_app = App(
            app_id="app_detail_self",
            name="Detail Self",
            app_secret="secret-self",
            rsa_public_key="public-self",
            rsa_private_key="private-self",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        authorized_app = App(
            app_id="app_detail_authorized",
            name="Detail Authorized",
            app_secret="secret-authorized",
            rsa_public_key="public-authorized",
            rsa_private_key="private-authorized",
            created_by="admin",
        )
        usage_user = EndUser(
            app_id=self_app.app_id,
            username="detail-usage",
            password_hash=hash_password("secret123"),
            status=1,
        )
        session.add_all([self_app, authorized_app, usage_user])
        session.add(
            UserAppAuthorization(
                app_id=authorized_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=9))
        session.commit()
        merchant_id = merchant.id

    try:
        response = client.get(f"/api/v1/admin/commercial/merchants/{merchant_id}/detail")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["profile"]["username"] == "detail-merchant"
        assert data["quota"]["kami_issue_balance"] == 9
        assert [item["app_id"] for item in data["self_owned_apps"]] == ["app_detail_self"]
        assert [item["app_id"] for item in data["authorized_apps"]] == ["app_detail_authorized"]
        assert [item["username"] for item in data["usage_users"]] == ["detail-usage"]
        assert data["self_owned_apps"][0]["can_generate_kamis"] is True
        assert data["authorized_apps"][0]["can_manage_batches"] is True
        assert "app_secret" not in response.text
        assert "rsa_private_key" not in response.text
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_apps_owner_scope_admin_excludes_merchant_self_owned_apps():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="merchant-owner", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        session.add_all(
            [
                App(
                    app_id="app_admin_owned",
                    name="Admin Owned",
                    app_secret="s1",
                    rsa_public_key="public-admin",
                    rsa_private_key="private-admin",
                    created_by="admin",
                ),
                App(
                    app_id="app_merchant_owned",
                    name="Merchant Owned",
                    app_secret="s2",
                    rsa_public_key="public-merchant",
                    rsa_private_key="private-merchant",
                    created_by=merchant.username,
                    owner_user_id=merchant.id,
                ),
            ]
        )
        session.commit()

    try:
        scoped = client.get("/api/v1/admin/apps?owner_scope=admin")
        assert scoped.status_code == 200
        scoped_ids = [item["app_id"] for item in scoped.json()["data"]]
        assert scoped_ids == ["app_admin_owned"]

        unscoped = client.get("/api/v1/admin/apps")
        assert unscoped.status_code == 200
        all_ids = {item["app_id"] for item in unscoped.json()["data"]}
        assert {"app_admin_owned", "app_merchant_owned"}.issubset(all_ids)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_commercial_merchant_delete_self_owned_app_requires_confirmation_and_scope():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="delete-app-merchant", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="other-delete-app-merchant", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        session.refresh(other)
        session.add_all(
            [
                App(
                    app_id="app_delete_owned",
                    name="Delete Owned",
                    app_secret="secret-owned",
                    rsa_public_key="public-owned",
                    rsa_private_key="private-owned",
                    created_by=merchant.username,
                    owner_user_id=merchant.id,
                ),
                App(
                    app_id="app_delete_other",
                    name="Delete Other",
                    app_secret="secret-other",
                    rsa_public_key="public-other",
                    rsa_private_key="private-other",
                    created_by=other.username,
                    owner_user_id=other.id,
                ),
            ]
        )
        session.commit()
        merchant_id = merchant.id

    try:
        missing_confirm = client.delete(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_delete_owned"
        )
        assert missing_confirm.status_code == 400

        wrong_scope = client.delete(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_delete_other",
            params={"confirm_text": CONFIRM_DELETE_APP},
        )
        assert wrong_scope.status_code == 404

        deleted = client.delete(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_delete_owned",
            params={"confirm_text": CONFIRM_DELETE_APP},
        )
        assert deleted.status_code == 200

        with Session(engine) as session:
            assert session.exec(select(App).where(App.app_id == "app_delete_owned")).first() is None
            assert session.exec(select(App).where(App.app_id == "app_delete_other")).first() is not None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_commercial_merchant_batch_scope_generates_as_target_issuer():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="scoped-issuer", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="other-issuer", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        session.refresh(other)

        admin_app = App(
            app_id="app_scoped_admin",
            name="Scoped Admin App",
            app_secret="s1",
            rsa_public_key="public-admin",
            rsa_private_key="private-admin",
            created_by="admin",
        )
        self_app = App(
            app_id="app_scoped_self",
            name="Scoped Self App",
            app_secret="s2",
            rsa_public_key="public-self",
            rsa_private_key="private-self",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        other_app = App(
            app_id="app_scoped_other",
            name="Other Self App",
            app_secret="s3",
            rsa_public_key="public-other",
            rsa_private_key="private-other",
            created_by=other.username,
            owner_user_id=other.id,
        )
        session.add_all([admin_app, self_app, other_app])
        session.add(
            UserAppAuthorization(
                app_id=admin_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=5))
        session.add(UserQuotaAccount(user_id=other.id, username=other.username, kami_issue_balance=5))
        session.commit()

        spec = KamiSpec(
            app_id=admin_app.app_id,
            spec_key="scoped-points",
            spec_name="Scoped Points",
            kami_type="points",
            points_amount=100,
            status=1,
        )
        self_spec = KamiSpec(
            app_id=self_app.app_id,
            spec_key="self-points",
            spec_name="Self Points",
            kami_type="points",
            points_amount=50,
            status=1,
        )
        session.add_all([spec, self_spec])
        session.commit()
        session.refresh(spec)

        issue_user_kamis(
            session,
            other,
            admin_app,
            spec_id=spec.id,
            kami_type="points",
            count=1,
            unit_cost=1,
            batch_no="OTHER-ISSUER-BATCH",
            points_amount=100,
        )
        session.commit()
        merchant_id = merchant.id
        spec_id = spec.id

    try:
        apps_response = client.get(f"/api/v1/admin/commercial/merchants/{merchant_id}/batch-apps")
        assert apps_response.status_code == 200
        app_ids = [item["app_id"] for item in apps_response.json()["data"]]
        assert app_ids == ["app_scoped_self", "app_scoped_admin"]
        assert "app_scoped_other" not in app_ids

        specs_response = client.get(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_scoped_admin/specs"
        )
        assert specs_response.status_code == 200
        scoped_spec = specs_response.json()["data"]["items"][0]
        assert scoped_spec["id"] == spec_id
        assert scoped_spec["total_count"] == 0
        assert scoped_spec["batch_count"] == 0

        preview = client.post(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_scoped_admin/kamis/preview",
            json={"spec_id": spec_id, "count": 2},
        )
        assert preview.status_code == 200
        assert preview.json()["data"]["balance_before"] == 5
        assert preview.json()["data"]["balance_after"] == 3

        issue = client.post(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_scoped_admin/kamis/batch",
            json={
                "spec_id": spec_id,
                "count": 2,
                "batch_no": "ADMIN-SCOPED-ISSUE",
                "code_length": 8,
                "charset": "upper_numeric",
            },
        )
        assert issue.status_code == 200
        assert issue.json()["data"]["count"] == 2

        batches = client.get(f"/api/v1/admin/commercial/merchants/{merchant_id}/apps/app_scoped_admin/batches")
        assert batches.status_code == 200
        batch_nos = [item["batch_no"] for item in batches.json()["data"]]
        assert batch_nos == ["ADMIN-SCOPED-ISSUE"]

        with Session(engine) as session:
            cards = session.exec(select(Kami).where(Kami.batch_no == "ADMIN-SCOPED-ISSUE")).all()
            assert len(cards) == 2
            assert {card.created_by_user_id for card in cards} == {merchant_id}
            account = session.exec(select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)).one()
            assert account.kami_issue_balance == 3
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_scoped_merchant_kami_delete_refund_records_admin_operator():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="scoped-delete-issuer", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)

        app = App(
            app_id="app_scoped_delete_refund",
            name="Scoped Delete Refund",
            app_secret="secret",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        session.add(app)
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=20))
        session.commit()

        issue_user_kamis(
            session,
            merchant,
            app,
            kami_type="points",
            count=2,
            unit_cost=4,
            batch_no="ADMIN-DELETE-REFUND",
            points_amount=100,
        )
        session.commit()
        codes = session.exec(
            select(Kami.kami_code).where(
                Kami.app_id == app.app_id,
                Kami.batch_no == "ADMIN-DELETE-REFUND",
            )
        ).all()
        merchant_id = merchant.id

    try:
        response = client.post(
            f"/api/v1/admin/commercial/merchants/{merchant_id}/kamis/delete",
            json={"app_id": "app_scoped_delete_refund", "kami_codes": codes},
        )
        assert response.status_code == 200

        with Session(engine) as session:
            refund_transactions = session.exec(
                select(UserQuotaTransaction)
                .where(
                    UserQuotaTransaction.user_id == merchant_id,
                    UserQuotaTransaction.transaction_type == UserQuotaTransactionType.refund,
                )
                .order_by(UserQuotaTransaction.id)
            ).all()
            assert [tx.amount for tx in refund_transactions] == [4, 4]
            assert {tx.operator for tx in refund_transactions} == {"admin"}
            metadata = [json.loads(tx.metadata_json) for tx in refund_transactions]
            assert {item["admin_scoped_merchant_id"] for item in metadata} == {merchant_id}
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_end_users_default_and_app_filter_exclude_merchant_owned_app_users():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="app-user-owner", password_hash=hash_password("secret123"), status=1)
        admin_app = App(
            app_id="app_admin_users_only",
            name="Admin Users Only",
            app_secret="secret-admin",
            rsa_public_key="public-admin",
            rsa_private_key="private-admin",
            created_by="admin",
        )
        session.add(merchant)
        session.add(admin_app)
        session.commit()
        session.refresh(merchant)
        merchant_app = App(
            app_id="app_merchant_users_hidden",
            name="Merchant Users Hidden",
            app_secret="secret-merchant",
            rsa_public_key="public-merchant",
            rsa_private_key="private-merchant",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        session.add(merchant_app)
        session.add_all(
            [
                EndUser(app_id=admin_app.app_id, username="admin-app-user", password_hash="secret123", status=1),
                EndUser(app_id=merchant_app.app_id, username="merchant-app-user", password_hash="secret123", status=1),
            ]
        )
        session.commit()

    try:
        default_response = client.get("/api/v1/admin/end-users")
        assert default_response.status_code == 200
        usernames = [item["username"] for item in default_response.json()["data"]["items"]]
        assert usernames == ["admin-app-user"]

        merchant_app_response = client.get(
            "/api/v1/admin/end-users",
            params={"app_id": "app_merchant_users_hidden"},
        )
        assert merchant_app_response.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()


def test_manual_recharge_order_review_credits_issue_quota_and_transactions(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", tmp_path / "uploads" / "commercial")

    fastapi_app.dependency_overrides[routes_auth.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        merchant_token = routes_user.create_user_access_token(merchant)
        merchant_id = merchant.id

    proof_image = "data:image/png;base64," + base64.b64encode(b"fake-png").decode("ascii")

    try:
        channel_response = client.post(
            "/api/v1/admin/commercial/payment-channels",
            json={
                "channel": "wechat",
                "display_name": "微信收款",
                "qr_code_url": "https://example.com/wechat.png",
                "enabled": True,
                "sort_order": 1,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert channel_response.status_code == 200

        bonus_response = client.post(
            "/api/v1/admin/commercial/recharge-bonus-rules",
            json={
                "threshold_amount": 300,
                "bonus_quota": 50,
                "enabled": True,
                "sort_order": 1,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert bonus_response.status_code == 200

        preview_response = client.post(
            "/api/v1/merchant/recharge/preview",
            headers=auth_headers(merchant_token),
            json={"amount": 350, "mode": "custom"},
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()["data"]
        assert preview_data["base_quota"] == 350
        assert preview_data["bonus_quota"] == 50
        assert preview_data["credit_quota"] == 400

        order_response = client.post(
            "/api/v1/merchant/recharge/orders",
            headers=auth_headers(merchant_token),
            json={
                "amount": 350,
                "mode": "custom",
                "channel": "wechat",
                "remark": "paid from merchant console",
                "proof_image_data_url": proof_image,
            },
        )
        assert order_response.status_code == 200
        order_data = order_response.json()["data"]
        assert order_data["status"] == "pending_review"
        assert order_data["credit_quota"] == 400
        assert order_data["order_no"].startswith("RC")
        assert "payment_snapshot" not in order_data
        assert "preview_snapshot" not in order_data

        orders_response = client.get("/api/v1/admin/commercial/recharge-orders")
        assert orders_response.status_code == 200
        order_item = orders_response.json()["data"]["items"][0]
        assert order_item["order_no"] == order_data["order_no"]
        assert "payment_snapshot" not in order_item
        assert "preview_snapshot" not in order_item

        approve_response = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{order_data['order_no']}/approve",
            json={"remark": "到账确认", "confirm_text": CONFIRM_APPROVE_RECHARGE_ORDER},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["data"]["status"] == "approved"

        duplicate_response = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{order_data['order_no']}/approve",
            json={"remark": "duplicate click", "confirm_text": CONFIRM_APPROVE_RECHARGE_ORDER},
        )
        assert duplicate_response.status_code == 400

        quota_response = client.get(
            "/api/v1/merchant/quotas",
            headers=auth_headers(merchant_token),
        )
        assert quota_response.status_code == 200
        assert quota_response.json()["data"]["kami_issue_balance"] == 400

        tx_response = client.get(
            "/api/v1/merchant/quota-transactions",
            headers=auth_headers(merchant_token),
        )
        assert tx_response.status_code == 200
        tx_item = tx_response.json()["data"]["items"][0]
        assert tx_item["transaction_type"] == "grant"
        assert tx_item["quota_type"] == "kami_issue"
        assert tx_item["display_scene"] == "充值入账"
        assert tx_item["display_direction"] == "入账"
        assert tx_item["display_quota_type"] == "发卡额度"
        assert tx_item["display_subject"].startswith("充值订单")
        assert tx_item["short_transaction_no"].startswith("UQ-")
        assert tx_item["amount"] == 400
        assert tx_item["biz_id"] == f"recharge_order:{order_data['order_no']}"

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            assert account.kami_issue_balance == 400
            transactions = session.exec(select(UserQuotaTransaction)).all()
            assert len([tx for tx in transactions if tx.biz_id == f"recharge_order:{order_data['order_no']}"]) == 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_can_delete_unused_recharge_config_and_archives_used_rows():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        merchant_id = merchant.id

    try:
        unused_option_response = client.post(
            "/api/v1/admin/commercial/recharge-options",
            json={
                "amount": 50,
                "credit_quota": 60,
                "enabled": True,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert unused_option_response.status_code == 200
        unused_option_id = unused_option_response.json()["data"]["id"]

        delete_unused_option = client.delete(
            f"/api/v1/admin/commercial/recharge-options/{unused_option_id}",
            params={"confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG},
        )
        assert delete_unused_option.status_code == 200
        assert delete_unused_option.json()["data"] == {
            "id": unused_option_id,
            "deleted": True,
            "archived": False,
        }

        with Session(engine) as session:
            assert session.get(RechargeOption, unused_option_id) is None

        used_option_response = client.post(
            "/api/v1/admin/commercial/recharge-options",
            json={
                "amount": 80,
                "credit_quota": 100,
                "enabled": True,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert used_option_response.status_code == 200
        used_option_id = used_option_response.json()["data"]["id"]
        with Session(engine) as session:
            session.add(
                RechargeOrder(
                    order_no="RC_USED_OPTION",
                    user_id=merchant_id,
                    username="merchant-a",
                    mode=RechargeMode.fixed,
                    channel=RechargeChannel.wechat,
                    amount_cents=8000,
                    base_quota=100,
                    bonus_quota=0,
                    credit_quota=100,
                    option_id=used_option_id,
                    status=RechargeOrderStatus.pending_review,
                )
            )
            session.commit()

        archive_used_option = client.delete(
            f"/api/v1/admin/commercial/recharge-options/{used_option_id}",
            params={"confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG},
        )
        assert archive_used_option.status_code == 200
        assert archive_used_option.json()["data"] == {
            "id": used_option_id,
            "deleted": False,
            "archived": True,
        }
        with Session(engine) as session:
            archived_option = session.get(RechargeOption, used_option_id)
            assert archived_option is not None
            assert archived_option.enabled is False

        unused_rule_response = client.post(
            "/api/v1/admin/commercial/recharge-bonus-rules",
            json={
                "threshold_amount": 300,
                "bonus_quota": 50,
                "enabled": True,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert unused_rule_response.status_code == 200
        unused_rule_id = unused_rule_response.json()["data"]["id"]
        delete_unused_rule = client.delete(
            f"/api/v1/admin/commercial/recharge-bonus-rules/{unused_rule_id}",
            params={"confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG},
        )
        assert delete_unused_rule.status_code == 200
        assert delete_unused_rule.json()["data"] == {
            "id": unused_rule_id,
            "deleted": True,
            "archived": False,
        }

        used_rule_response = client.post(
            "/api/v1/admin/commercial/recharge-bonus-rules",
            json={
                "threshold_amount": 500,
                "bonus_quota": 90,
                "enabled": True,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert used_rule_response.status_code == 200
        used_rule_id = used_rule_response.json()["data"]["id"]
        with Session(engine) as session:
            session.add(
                RechargeOrder(
                    order_no="RC_USED_RULE",
                    user_id=merchant_id,
                    username="merchant-a",
                    mode=RechargeMode.custom,
                    channel=RechargeChannel.wechat,
                    amount_cents=50000,
                    base_quota=500,
                    bonus_quota=90,
                    credit_quota=590,
                    bonus_rule_id=used_rule_id,
                    status=RechargeOrderStatus.pending_review,
                )
            )
            session.commit()

        archive_used_rule = client.delete(
            f"/api/v1/admin/commercial/recharge-bonus-rules/{used_rule_id}",
            params={"confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG},
        )
        assert archive_used_rule.status_code == 200
        assert archive_used_rule.json()["data"] == {
            "id": used_rule_id,
            "deleted": False,
            "archived": True,
        }
        with Session(engine) as session:
            archived_rule = session.get(RechargeBonusRule, used_rule_id)
            assert archived_rule is not None
            assert archived_rule.enabled is False
    finally:
        fastapi_app.dependency_overrides.clear()


def test_recharge_orders_can_be_canceled_and_expired_before_review():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        merchant_token = routes_user.create_user_access_token(merchant)

    try:
        channel_response = client.post(
            "/api/v1/admin/commercial/payment-channels",
            json={
                "channel": "wechat",
                "display_name": "Wechat",
                "enabled": True,
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert channel_response.status_code == 200

        first_order_response = client.post(
            "/api/v1/merchant/recharge/orders",
            headers=auth_headers(merchant_token),
            json={"amount": 20, "mode": "custom", "channel": "wechat"},
        )
        assert first_order_response.status_code == 200
        first_order_no = first_order_response.json()["data"]["order_no"]

        cancel_response = client.post(
            f"/api/v1/merchant/recharge/orders/{first_order_no}/cancel",
            headers=auth_headers(merchant_token),
            json={"remark": "merchant changed mind"},
        )
        assert cancel_response.status_code == 200
        assert cancel_response.json()["data"]["status"] == "canceled"

        approve_canceled = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{first_order_no}/approve",
            json={"remark": "must not approve", "confirm_text": CONFIRM_APPROVE_RECHARGE_ORDER},
        )
        assert approve_canceled.status_code == 400

        second_order_response = client.post(
            "/api/v1/merchant/recharge/orders",
            headers=auth_headers(merchant_token),
            json={"amount": 30, "mode": "custom", "channel": "wechat"},
        )
        assert second_order_response.status_code == 200
        second_order_no = second_order_response.json()["data"]["order_no"]

        expire_response = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{second_order_no}/expire",
            json={"remark": "manual timeout", "confirm_text": CONFIRM_EXPIRE_RECHARGE_ORDER},
        )
        assert expire_response.status_code == 200
        assert expire_response.json()["data"]["status"] == "expired"

        cancel_expired = client.post(
            f"/api/v1/merchant/recharge/orders/{second_order_no}/cancel",
            headers=auth_headers(merchant_token),
            json={"remark": "too late"},
        )
        assert cancel_expired.status_code == 400

        approve_expired = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{second_order_no}/approve",
            json={"remark": "must not approve", "confirm_text": CONFIRM_APPROVE_RECHARGE_ORDER},
        )
        assert approve_expired.status_code == 400

        canceled_list = client.get("/api/v1/admin/commercial/recharge-orders?status=canceled")
        assert canceled_list.status_code == 200
        assert canceled_list.json()["data"]["items"][0]["order_no"] == first_order_no

        expired_list = client.get("/api/v1/admin/commercial/recharge-orders?status=expired")
        assert expired_list.status_code == 200
        assert expired_list.json()["data"]["items"][0]["order_no"] == second_order_no
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_cleanup_recharge_proofs_removes_only_terminal_old_files(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    upload_root = tmp_path / "uploads" / "commercial"
    proof_dir = upload_root / "proofs"
    proof_dir.mkdir(parents=True)
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    old_time = get_now_naive() - timedelta(days=40)
    new_time = get_now_naive() - timedelta(days=5)
    terminal_path = proof_dir / "terminal.png"
    pending_path = proof_dir / "pending.png"
    new_path = proof_dir / "new.png"
    terminal_path.write_bytes(b"terminal-proof")
    pending_path.write_bytes(b"pending-proof")
    new_path.write_bytes(b"new-proof")

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        for order_no, status, proof_path, created_at in [
            ("RC_OLD_TERMINAL", RechargeOrderStatus.approved, terminal_path, old_time),
            ("RC_OLD_PENDING", RechargeOrderStatus.pending_review, pending_path, old_time),
            ("RC_NEW_TERMINAL", RechargeOrderStatus.approved, new_path, new_time),
        ]:
            session.add(
                RechargeOrder(
                    order_no=order_no,
                    user_id=merchant.id,
                    username=merchant.username,
                    mode=RechargeMode.custom,
                    channel=RechargeChannel.wechat,
                    amount_cents=1000,
                    base_quota=10,
                    bonus_quota=0,
                    credit_quota=10,
                    status=status,
                    proof_file_path=proof_path.as_posix(),
                    proof_file_name=proof_path.name,
                    proof_content_type="image/png",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
        session.commit()

    try:
        dry_run_response = client.post(
            "/api/v1/admin/commercial/recharge-proofs/cleanup",
            json={"older_than_days": 30, "dry_run": True},
        )
        assert dry_run_response.status_code == 200
        assert dry_run_response.json()["data"]["matched_orders"] == 1
        assert terminal_path.exists()

        cleanup_response = client.post(
            "/api/v1/admin/commercial/recharge-proofs/cleanup",
            json={
                "older_than_days": 30,
                "dry_run": False,
                "confirm_text": CONFIRM_CLEANUP_PROOF_FILES,
            },
        )
        assert cleanup_response.status_code == 200
        data = cleanup_response.json()["data"]
        assert data["matched_orders"] == 1
        assert data["deleted_proofs"] == 1
        assert not terminal_path.exists()
        assert pending_path.exists()
        assert new_path.exists()

        with Session(engine) as session:
            old_terminal = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "RC_OLD_TERMINAL")
            ).one()
            old_pending = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "RC_OLD_PENDING")
            ).one()
            assert old_terminal.proof_file_path is None
            assert old_terminal.proof_file_name is None
            assert old_terminal.proof_content_type is None
            assert old_pending.proof_file_path == pending_path.as_posix()
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_authorized_app_issue_requires_existing_spec_and_hides_secrets():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        user = EndUser(username="spec-issuer", password_hash=hash_password("secret123"), status=1)
        app = App(
            app_id="app_shared",
            name="Shared App",
            app_secret="secret-shared",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        session.add(user)
        session.add(app)
        session.commit()
        session.refresh(user)
        spec = KamiSpec(
            app_id="app_shared",
            spec_key="points-100",
            spec_name="100积分",
            kami_type="points",
            points_amount=100,
            status=1,
        )
        session.add(spec)
        session.add(
            UserAppAuthorization(
                app_id="app_shared",
                user_id=user.id,
                username=user.username,
                granted_by="admin",
            )
        )
        quota_account = UserQuotaAccount(user_id=user.id, username=user.username, kami_issue_balance=3)
        session.add(quota_account)
        session.commit()
        session.refresh(spec)
        token = routes_user.create_user_access_token(user)
        spec_id = spec.id
        user_id = user.id

    try:
        apps_response = client.get("/api/v1/merchant/apps", headers=auth_headers(token))
        assert apps_response.status_code == 200
        shared_app = apps_response.json()["data"][0]
        assert shared_app["app_id"] == "app_shared"
        assert shared_app["is_owned"] is False
        assert "app_secret" not in shared_app
        assert "rsa_private_key" not in shared_app

        invalid_issue_response = client.post(
            "/api/v1/merchant/apps/app_shared/kamis/batch",
            headers=auth_headers(token),
            json={"kami_type": "points", "count": 1, "points_amount": 200, "batch_no": "BAD-001"},
        )
        assert invalid_issue_response.status_code == 400
        assert "spec_id" in invalid_issue_response.json()["detail"]

        issue_response = client.post(
            "/api/v1/merchant/apps/app_shared/kamis/batch",
            headers=auth_headers(token),
            json={"spec_id": spec_id, "count": 2, "batch_no": "GOOD-001", "code_length": 8},
        )
        assert issue_response.status_code == 200
        issue_data = issue_response.json()["data"]
        assert issue_data["count"] == 2
        assert issue_data["spec_id"] == spec_id
        assert issue_data["quota"]["amount"] == 2

        with Session(engine) as session:
            rows = session.exec(
                select(Kami).where(Kami.created_by_user_id == user_id, Kami.batch_no == "GOOD-001")
            ).all()
            assert len(rows) == 2
            assert all(row.spec_id == spec_id for row in rows)
            assert all(row.points_amount == 100 for row in rows)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_authorized_app_batches_are_issuer_scoped_not_synced_from_admin():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="authorized-batch-issuer", password_hash=hash_password("secret123"), status=1)
        app = App(
            app_id="app_authorized_batch_scope",
            name="Authorized Batch Scope",
            app_secret="secret-authorized-scope",
            rsa_public_key="public-authorized-scope",
            rsa_private_key="private-authorized-scope",
            created_by="admin",
        )
        session.add_all([merchant, app])
        session.commit()
        session.refresh(merchant)
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="points-100-shared",
            spec_name="Shared 100 Points",
            spec_group="common",
            kami_type="points",
            points_amount=100,
            status=1,
        )
        session.add_all(
            [
                spec,
                UserAppAuthorization(
                    app_id=app.app_id,
                    user_id=merchant.id,
                    username=merchant.username,
                    granted_by="admin",
                ),
                UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=10),
            ]
        )
        session.commit()
        session.refresh(spec)
        admin_batch = KamiBatch(
            spec_id=spec.id,
            app_id=app.app_id,
            batch_no="ADMIN-SHOULD-NOT-SYNC",
            kami_type="points",
            points_amount=100,
            status=1,
        )
        session.add(admin_batch)
        session.commit()
        session.refresh(admin_batch)
        session.add(
            Kami(
                spec_id=spec.id,
                app_id=app.app_id,
                kami_code="ADMIN-SCOPE-001",
                kami_type="points",
                status="unused",
                batch_no=admin_batch.batch_no,
                points_amount=100,
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)
        spec_id = spec.id
        admin_batch_id = admin_batch.id

    try:
        empty_spec_batches = client.get(
            f"/api/v1/merchant/kami-specs/{spec_id}/batches",
            headers=auth_headers(token),
        )
        assert empty_spec_batches.status_code == 200
        assert empty_spec_batches.json()["items"] == []

        empty_app_batches = client.get(
            "/api/v1/merchant/apps/app_authorized_batch_scope/batches",
            headers=auth_headers(token),
        )
        assert empty_app_batches.status_code == 200
        assert empty_app_batches.json()["items"] == []

        hidden_admin_batch = client.get(
            f"/api/v1/merchant/batches/{admin_batch_id}/kamis",
            headers=auth_headers(token),
        )
        assert hidden_admin_batch.status_code == 404

        issue_response = client.post(
            "/api/v1/merchant/apps/app_authorized_batch_scope/kamis/batch",
            headers=auth_headers(token),
            json={"spec_id": spec_id, "count": 2, "batch_no": "MERCHANT-ONLY-BATCH", "code_length": 8},
        )
        assert issue_response.status_code == 200

        spec_batches = client.get(
            f"/api/v1/merchant/kami-specs/{spec_id}/batches",
            headers=auth_headers(token),
        )
        assert spec_batches.status_code == 200
        spec_items = spec_batches.json()["items"]
        assert [item["batch_no"] for item in spec_items] == ["MERCHANT-ONLY-BATCH"]
        assert spec_items[0]["source"] == "admin_authorized"
        assert spec_items[0]["batch_source"] == "merchant_issued"
        assert spec_items[0]["can_edit"] is True
        assert spec_items[0]["can_append"] is True

        app_batches = client.get(
            "/api/v1/merchant/apps/app_authorized_batch_scope/batches",
            headers=auth_headers(token),
        )
        assert app_batches.status_code == 200
        app_items = app_batches.json()["items"]
        assert [item["batch_no"] for item in app_items] == ["MERCHANT-ONLY-BATCH"]

        visible_cards = client.get(
            f"/api/v1/merchant/batches/{app_items[0]['id']}/kamis",
            headers=auth_headers(token),
        )
        assert visible_cards.status_code == 200
        assert visible_cards.json()["total"] == 2

        still_hidden_admin_batch = client.get(
            f"/api/v1/merchant/batches/{admin_batch_id}/kamis",
            headers=auth_headers(token),
        )
        assert still_hidden_admin_batch.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_issue_batch_persists_admin_grade_code_generation_options():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="code-option-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_code_options",
            name="Code Options",
            app_secret="secret-code",
            rsa_public_key="public-code",
            rsa_private_key="private-code",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="points-66",
            spec_name="66积分",
            kami_type="points",
            points_amount=66,
            status=1,
        )
        session.add_all([app, spec, UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=5)])
        session.commit()
        session.refresh(spec)
        token = routes_user.create_user_access_token(merchant)

    try:
        issue = client.post(
            "/api/v1/merchant/apps/app_code_options/kamis/batch",
            headers=auth_headers(token),
            json={
                "spec_id": spec.id,
                "count": 1,
                "batch_no": "CODE-OPTIONS-001",
                "code_prefix": "VIP-",
                "code_length": 10,
                "charset": "upper_numeric",
                "code_valid_days": 7,
            },
        )
        assert issue.status_code == 200

        with Session(engine) as session:
            batch = session.exec(select(KamiBatch).where(KamiBatch.batch_no == "CODE-OPTIONS-001")).one()
            kami = session.exec(select(Kami).where(Kami.batch_no == "CODE-OPTIONS-001")).one()
            assert batch.code_prefix == "VIP-"
            assert batch.code_length == 10
            assert batch.charset == "upper_numeric"
            assert batch.code_valid_days == 7
            assert kami.code_prefix == "VIP-"
            assert kami.code_length == 10
            assert kami.charset == "upper_numeric"
            assert kami.code_valid_days == 7
            assert kami.code_expires_at is not None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_batch_lists_expose_admin_grade_generation_policy_and_permission_fields():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    now = get_now_naive()
    with Session(engine) as session:
        merchant = EndUser(username="batch-contract-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_batch_contract",
            name="Batch Contract",
            app_secret="secret-batch-contract",
            rsa_public_key="public-batch-contract",
            rsa_private_key="private-batch-contract",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="points-128-user-bind",
            spec_name="128积分 / 用户绑定",
            spec_group="custom",
            kami_type="points",
            points_amount=128,
            points_valid_days=30,
            machine_bind_mode="one_card_multi_device",
            max_bind_devices=3,
            authorization_owner="user",
            user_bind_mode="required",
            status=1,
            remark="contract spec",
        )
        session.add_all([app, spec])
        session.commit()
        session.refresh(spec)
        batch = KamiBatch(
            spec_id=spec.id,
            app_id=app.app_id,
            batch_no="CONTRACT-001",
            kami_type="points",
            points_amount=128,
            points_valid_days=30,
            code_prefix="VIP-",
            code_length=12,
            charset="upper_numeric",
            code_valid_days=14,
            machine_bind_mode="one_card_multi_device",
            max_bind_devices=3,
            authorization_owner="user",
            user_bind_mode="required",
            status=1,
            remark="contract batch",
            created_at=now,
            updated_at=now,
        )
        session.add(batch)
        session.add(
            Kami(
                spec_id=spec.id,
                app_id=app.app_id,
                kami_code="VIP-CONTRACT01",
                kami_type="points",
                status="unused",
                batch_no=batch.batch_no,
                points_amount=128,
                points_valid_days=30,
                code_prefix="VIP-",
                code_length=12,
                charset="upper_numeric",
                code_valid_days=14,
                machine_bind_mode="one_card_multi_device",
                max_bind_devices=3,
                authorization_owner="user",
                user_bind_mode="required",
                created_by_user_id=merchant.id,
            )
        )
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=10))
        session.commit()
        token = routes_user.create_user_access_token(merchant)
        spec_id = spec.id

    try:
        spec_batches = client.get(
            f"/api/v1/merchant/kami-specs/{spec_id}/batches",
            headers=auth_headers(token),
        )
        assert spec_batches.status_code == 200
        spec_item = spec_batches.json()["data"]["items"][0]

        app_batches = client.get(
            "/api/v1/merchant/apps/app_batch_contract/batches",
            headers=auth_headers(token),
        )
        assert app_batches.status_code == 200
        app_item = app_batches.json()["items"][0]

        for item in (spec_item, app_item):
            assert item["batch_no"] == "CONTRACT-001"
            assert item["spec_name"] == "128积分 / 用户绑定"
            assert item["points_amount"] == 128
            assert item["points_valid_days"] == 30
            assert item["code_prefix"] == "VIP-"
            assert item["code_length"] == 12
            assert item["charset"] == "upper_numeric"
            assert item["code_valid_days"] == 14
            assert item["machine_bind_mode"] == "one_card_multi_device"
            assert item["max_bind_devices"] == 3
            assert item["authorization_owner"] == "user"
            assert item["user_bind_mode"] == "required"
            assert item["status"] == 1
            assert item["remark"] == "contract batch"
            assert item["can_manage"] is True
            assert item["source"] == "self_owned"
            assert item["created_at"]
            assert item["updated_at"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_kami_list_and_export_can_be_scoped_to_spec_detail():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="export-scope-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_export_scope",
            name="Export Scope",
            app_secret="secret-export-scope",
            rsa_public_key="public-export-scope",
            rsa_private_key="private-export-scope",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec_a = KamiSpec(
            app_id=app.app_id,
            spec_key="points-10-export",
            spec_name="10积分",
            spec_group="custom",
            kami_type="points",
            points_amount=10,
            status=1,
        )
        spec_b = KamiSpec(
            app_id=app.app_id,
            spec_key="points-20-export",
            spec_name="20积分",
            spec_group="custom",
            kami_type="points",
            points_amount=20,
            status=1,
        )
        session.add_all([app, spec_a, spec_b])
        session.commit()
        session.refresh(spec_a)
        session.refresh(spec_b)
        session.add_all(
            [
                Kami(
                    spec_id=spec_a.id,
                    app_id=app.app_id,
                    kami_code="EXPORT-SPEC-A",
                    kami_type="points",
                    status="unused",
                    batch_no="EXPORT-A",
                    points_amount=10,
                    created_by_user_id=merchant.id,
                ),
                Kami(
                    spec_id=spec_b.id,
                    app_id=app.app_id,
                    kami_code="EXPORT-SPEC-B",
                    kami_type="points",
                    status="unused",
                    batch_no="EXPORT-B",
                    points_amount=20,
                    created_by_user_id=merchant.id,
                ),
            ]
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)
        spec_id = spec_a.id

    try:
        list_response = client.get(
            "/api/v1/merchant/kamis",
            headers=auth_headers(token),
            params={"app_id": "app_export_scope", "spec_id": spec_id},
        )
        assert list_response.status_code == 200
        assert [item["kami_code"] for item in list_response.json()["data"]["items"]] == ["EXPORT-SPEC-A"]

        export_response = client.get(
            "/api/v1/merchant/kamis/export",
            headers=auth_headers(token),
            params={"app_id": "app_export_scope", "spec_id": spec_id},
        )
        assert export_response.status_code == 200
        csv_text = export_response.content.decode("utf-8-sig")
        assert "EXPORT-SPEC-A" in csv_text
        assert "EXPORT-SPEC-B" not in csv_text
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_batch_update_append_and_delete_guard_follow_admin_grade_contract():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    now = get_now_naive()
    with Session(engine) as session:
        merchant = EndUser(username="batch-edit-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_batch_edit",
            name="Batch Edit",
            app_secret="secret-batch-edit",
            rsa_public_key="public-batch-edit",
            rsa_private_key="private-batch-edit",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="points-88-edit",
            spec_name="88积分 / 编辑",
            spec_group="custom",
            kami_type="points",
            points_amount=88,
            points_valid_days=15,
            machine_bind_mode="one_card_one_device",
            max_bind_devices=1,
            authorization_owner="device",
            user_bind_mode="none",
            status=1,
        )
        session.add_all([app, spec, UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=10)])
        session.commit()
        session.refresh(spec)
        batch = KamiBatch(
            spec_id=spec.id,
            app_id=app.app_id,
            batch_no="EDIT-001",
            kami_type="points",
            points_amount=88,
            points_valid_days=15,
            code_prefix="VIP-",
            code_length=10,
            charset="upper_numeric",
            code_valid_days=7,
            machine_bind_mode="one_card_one_device",
            max_bind_devices=1,
            authorization_owner="device",
            user_bind_mode="none",
            status=1,
            remark="edit batch",
            created_at=now,
            updated_at=now,
        )
        session.add(batch)
        session.add(
            Kami(
                spec_id=spec.id,
                app_id=app.app_id,
                kami_code="VIP-EDIT0001",
                kami_type="points",
                status="unused",
                batch_no=batch.batch_no,
                points_amount=88,
                points_valid_days=15,
                code_prefix="VIP-",
                code_length=10,
                charset="upper_numeric",
                code_valid_days=7,
                machine_bind_mode="one_card_one_device",
                max_bind_devices=1,
                authorization_owner="device",
                user_bind_mode="none",
                created_by_user_id=merchant.id,
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)
        batch_id = batch.id

    try:
        update = client.put(
            f"/api/v1/merchant/batches/{batch_id}",
            headers=auth_headers(token),
            json={
                "batch_no": "EDIT-RENAMED",
                "remark": "updated batch",
                "code_valid_days": 14,
            },
        )
        assert update.status_code == 200
        update_data = update.json()["data"]
        assert update_data["batch_no"] == "EDIT-RENAMED"
        assert update_data["remark"] == "updated batch"
        assert update_data["code_valid_days"] == 14
        assert update_data["can_manage"] is True

        append = client.post(
            f"/api/v1/merchant/batches/{batch_id}/append",
            headers=auth_headers(token),
            json={
                "count": 2,
                "code_prefix": "VIP-",
                "code_length": 10,
                "charset": "upper_numeric",
                "code_valid_days": 5,
            },
        )
        assert append.status_code == 200
        append_data = append.json()["data"]
        assert append_data["count"] == 2
        assert append_data["batch_no"] == "EDIT-RENAMED"

        delete = client.delete(
            f"/api/v1/merchant/batches/{batch_id}",
            headers=auth_headers(token),
        )
        assert delete.status_code == 400

        with Session(engine) as session:
            batch_row = session.get(KamiBatch, batch_id)
            assert batch_row.batch_no == "EDIT-RENAMED"
            kamis = session.exec(select(Kami).where(Kami.app_id == app.app_id, Kami.batch_no == "EDIT-RENAMED")).all()
            assert len(kamis) == 3
            assert any(kami.code_valid_days == 5 for kami in kamis)
            assert any(kami.code_expires_at is not None for kami in kamis)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_can_create_self_owned_app_without_hidden_app_create_quota():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="self-app-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        merchant_token = routes_user.create_user_access_token(merchant)
        merchant_id = merchant.id

    try:
        response = client.post(
            "/api/v1/merchant/apps",
            headers=auth_headers(merchant_token),
            json={"name": "Merchant Self App"},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["is_owned"] is True
        assert data["quota"]["quota_type"] == "app_create"
        assert data["quota"]["amount"] == 0

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            assert account.app_create_balance == 0
            assert account.kami_issue_balance == 0
            app_create_transactions = session.exec(
                select(UserQuotaTransaction).where(
                    UserQuotaTransaction.user_id == merchant_id,
                    UserQuotaTransaction.quota_type == UserQuotaType.app_create,
                )
            ).all()
            assert app_create_transactions == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_dashboard_aggregates_workbench_data_for_visible_resources():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="dashboard-issuer", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="other-dashboard-issuer", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        session.refresh(other)
        self_app = App(
            app_id="app_dashboard_self",
            name="Dashboard Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
            status=1,
        )
        authorized_app = App(
            app_id="app_dashboard_authorized",
            name="Dashboard Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
            status=1,
        )
        other_app = App(
            app_id="app_dashboard_other",
            name="Dashboard Other App",
            app_secret="secret-other",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=other.username,
            owner_user_id=other.id,
            status=1,
        )
        session.add_all([self_app, authorized_app, other_app])
        session.add(UserAppAuthorization(app_id=authorized_app.app_id, user_id=merchant.id, username=merchant.username, granted_by="admin"))
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=7, total_kami_issue_granted=12))
        session.add(
            RechargeOrder(
                order_no="RC_DASHBOARD_001",
                user_id=merchant.id,
                username=merchant.username,
                amount_cents=1000,
                credit_quota=10,
                channel=RechargeChannel.wechat,
                mode=RechargeMode.fixed,
                status=RechargeOrderStatus.pending_review,
            )
        )
        session.add(AppNotice(app_id=self_app.app_id, title="额度维护通知", content="请关注额度", level="important", enabled=True))
        session.add(AppNotice(app_id=other_app.app_id, title="其他用户通知", content="不可见", level="important", enabled=True))
        batch = KamiBatch(
            app_id=self_app.app_id,
            batch_no="DASH-BATCH-001",
            kami_type="points",
            points_amount=100,
        )
        session.add(batch)
        session.commit()
        session.add_all(
            [
                Kami(
                    app_id=self_app.app_id,
                    kami_code="DASH-CARD-001",
                    kami_type="points",
                    batch_no=batch.batch_no,
                    points_amount=100,
                    created_by_user_id=merchant.id,
                ),
                Kami(
                    app_id=other_app.app_id,
                    kami_code="OTHER-DASH-CARD-001",
                    kami_type="points",
                    batch_no="OTHER-DASH",
                    points_amount=100,
                    created_by_user_id=other.id,
                ),
            ]
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        response = client.get("/api/v1/merchant/dashboard", headers=auth_headers(token))

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["quota"]["balance"] == 7
        assert data["quota"]["total_granted"] == 12
        assert data["apps"]["total"] == 2
        assert data["apps"]["self_owned"] == 1
        assert data["apps"]["authorized"] == 1
        assert data["orders"]["pending_review"] == 1
        assert data["cards"]["total"] == 1
        assert [item["title"] for item in data["notifications"]] == ["额度维护通知"]
        assert data["recent_batches"][0]["batch_no"] == "DASH-BATCH-001"
        assert data["recent_orders"][0]["order_no"] == "RC_DASHBOARD_001"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_self_owned_specs_are_manageable_and_authorized_specs_are_read_only():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="spec-manager", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="other-spec-manager", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        session.refresh(other)
        self_app = App(
            app_id="app_spec_self",
            name="Spec Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        authorized_app = App(
            app_id="app_spec_authorized",
            name="Spec Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        other_app = App(
            app_id="app_spec_other",
            name="Spec Other App",
            app_secret="secret-other",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=other.username,
            owner_user_id=other.id,
        )
        session.add_all([self_app, authorized_app, other_app])
        session.add(UserAppAuthorization(app_id=authorized_app.app_id, user_id=merchant.id, username=merchant.username, granted_by="admin"))
        session.add_all(
            [
                KamiSpec(app_id=authorized_app.app_id, spec_key="enabled", spec_name="Enabled Spec", kami_type="points", points_amount=100, status=1),
                KamiSpec(app_id=authorized_app.app_id, spec_key="disabled", spec_name="Disabled Spec", kami_type="points", points_amount=200, status=0),
            ]
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    spec_payload = {
        "kami_type": "points",
        "points_amount": 88,
        "points_valid_days": 30,
        "machine_bind_mode": "one_card_multi_device",
        "max_bind_devices": 2,
        "authorization_owner": "device",
        "user_bind_mode": "none",
        "remark": "self owned spec",
    }

    try:
        created = client.post(
            "/api/v1/merchant/apps/app_spec_self/specs",
            headers=auth_headers(token),
            json=spec_payload,
        )
        assert created.status_code == 200
        created_spec = created.json()["data"]
        assert created_spec["app_id"] == "app_spec_self"
        assert created_spec["points_amount"] == 88
        assert created_spec["is_editable"] is True
        assert created_spec["batch_count"] == 0
        spec_id = created_spec["id"]

        listed_self = client.get("/api/v1/merchant/apps/app_spec_self/specs", headers=auth_headers(token))
        assert listed_self.status_code == 200
        assert listed_self.json()["data"]["total"] == 1
        assert listed_self.json()["data"]["items"][0]["is_editable"] is True
        assert listed_self.json()["data"]["items"][0]["capabilities"]["can_edit"] is True
        assert listed_self.json()["data"]["items"][0]["capabilities"]["can_delete"] is True

        updated = client.put(
            f"/api/v1/merchant/apps/app_spec_self/specs/{spec_id}",
            headers=auth_headers(token),
            json={"status": 0, "sort_order": 5, "remark": "paused"},
        )
        assert updated.status_code == 200
        assert updated.json()["data"]["status"] == 0
        assert updated.json()["data"]["sort_order"] == 5

        deleted = client.delete(f"/api/v1/merchant/apps/app_spec_self/specs/{spec_id}", headers=auth_headers(token))
        assert deleted.status_code == 200

        blocking_spec = KamiSpec(
            app_id="app_spec_self",
            spec_key="blocking",
            spec_name="Blocking Spec",
            kami_type=KamiType.points,
            points_amount=66,
            status=1,
        )
        session.add(blocking_spec)
        session.commit()
        session.refresh(blocking_spec)
        session.add(
            Kami(
                app_id="app_spec_self",
                spec_id=blocking_spec.id,
                kami_code="BLOCK-001",
                kami_type=KamiType.points,
                status=KamiStatus.unused,
                created_by_user_id=merchant.id,
            )
        )
        session.commit()

        blocked_list = client.get("/api/v1/merchant/apps/app_spec_self/specs", headers=auth_headers(token))
        assert blocked_list.status_code == 200
        blocked_items = blocked_list.json()["data"]["items"]
        blocked_item = next(item for item in blocked_items if item["id"] == blocking_spec.id)
        assert blocked_item["capabilities"]["can_delete"] is False

        blocked_delete = client.delete(
            f"/api/v1/merchant/apps/app_spec_self/specs/{blocking_spec.id}",
            headers=auth_headers(token),
        )
        assert blocked_delete.status_code == 400
        assert blocked_delete.json()["detail"] == "规格下仍有批次或卡密，无法删除"

        authorized_list = client.get("/api/v1/merchant/apps/app_spec_authorized/specs", headers=auth_headers(token))
        assert authorized_list.status_code == 200
        authorized_items = authorized_list.json()["data"]["items"]
        assert [item["spec_name"] for item in authorized_items] == ["Enabled Spec"]
        assert authorized_items[0]["is_editable"] is False
        assert authorized_items[0]["capabilities"]["can_edit"] is False
        assert authorized_items[0]["capabilities"]["can_delete"] is False

        filtered_authorized = client.get(
            "/api/v1/merchant/apps/app_spec_authorized/specs",
            headers=auth_headers(token),
            params={"kami_type": "points", "keyword": "Enabled"},
        )
        assert filtered_authorized.status_code == 200
        assert filtered_authorized.json()["data"]["total"] == 1

        hidden_inactive = client.get(
            "/api/v1/merchant/apps/app_spec_authorized/specs",
            headers=auth_headers(token),
            params={"keyword": "Disabled"},
        )
        assert hidden_inactive.status_code == 200
        assert hidden_inactive.json()["data"]["total"] == 0

        forbidden_create = client.post(
            "/api/v1/merchant/apps/app_spec_authorized/specs",
            headers=auth_headers(token),
            json=spec_payload,
        )
        assert forbidden_create.status_code == 403

        forbidden_other = client.post(
            "/api/v1/merchant/apps/app_spec_other/specs",
            headers=auth_headers(token),
            json=spec_payload,
        )
        assert forbidden_other.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_app_detail_and_interface_management_follow_ownership_boundaries():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="app-workbench-merchant", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="app-workbench-other", password_hash=hash_password("secret123"), status=1)
        session.add_all([merchant, other])
        session.commit()
        session.refresh(merchant)
        session.refresh(other)
        self_app = App(
            app_id="app_workbench_self",
            name="Workbench Self App",
            app_secret="secret-self",
            rsa_public_key="public-self",
            rsa_private_key="private-self",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        authorized_app = App(
            app_id="app_workbench_authorized",
            name="Workbench Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public-authorized",
            rsa_private_key="private-authorized",
            created_by="admin",
        )
        session.add_all([self_app, authorized_app])
        session.add(
            UserAppAuthorization(
                app_id=authorized_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        self_detail = client.get(
            "/api/v1/merchant/apps/app_workbench_self",
            headers=auth_headers(token),
        )
        assert self_detail.status_code == 200
        self_data = self_detail.json()["data"]
        assert self_data["is_owned"] is True
        assert self_data["app_secret"] == "secret-self"
        assert self_data["rsa_public_key"] == "public-self"
        assert self_data["capabilities"]["can_rename"] is True
        assert self_data["capabilities"]["can_delete"] is True
        assert self_data["capabilities"]["can_manage_interfaces"] is True
        assert self_data["capabilities"]["can_manage_specs"] is True
        assert self_data["capabilities"]["can_generate_batches"] is True

        authorized_detail = client.get(
            "/api/v1/merchant/apps/app_workbench_authorized",
            headers=auth_headers(token),
        )
        assert authorized_detail.status_code == 200
        authorized_data = authorized_detail.json()["data"]
        assert authorized_data["is_owned"] is False
        assert authorized_data["source"] == "admin_authorized"
        assert "app_secret" not in authorized_data
        assert "rsa_public_key" not in authorized_data
        assert authorized_data["capabilities"]["can_rename"] is False
        assert authorized_data["capabilities"]["can_delete"] is False
        assert authorized_data["capabilities"]["can_manage_interfaces"] is False
        assert authorized_data["capabilities"]["can_manage_specs"] is False
        assert authorized_data["capabilities"]["can_generate_batches"] is True

        authorized_rename = client.put(
            "/api/v1/merchant/apps/app_workbench_authorized",
            headers=auth_headers(token),
            json={"name": "Not Allowed"},
        )
        assert authorized_rename.status_code == 403

        authorized_delete = client.delete(
            "/api/v1/merchant/apps/app_workbench_authorized",
            headers=auth_headers(token),
        )
        assert authorized_delete.status_code == 403

        self_interfaces = client.get(
            "/api/v1/merchant/apps/app_workbench_self/interfaces",
            headers=auth_headers(token),
        )
        assert self_interfaces.status_code == 200
        self_interface_items = self_interfaces.json()["data"]
        assert self_interface_items
        first_interface_id = self_interface_items[0]["interface_id"]

        self_interface_update = client.put(
            f"/api/v1/merchant/apps/app_workbench_self/interfaces/{first_interface_id}",
            headers=auth_headers(token),
            json={
                "enabled": True,
                "quota_limit": 12,
                "expires_at": "2026-08-01T00:00:00",
                "remark": "merchant config",
                "config": {"release_on_logout": True},
            },
        )
        assert self_interface_update.status_code == 200
        assert self_interface_update.json()["data"]["configured"] is True

        authorized_interfaces = client.get(
            "/api/v1/merchant/apps/app_workbench_authorized/interfaces",
            headers=auth_headers(token),
        )
        assert authorized_interfaces.status_code == 200
        authorized_interface_items = authorized_interfaces.json()["data"]
        assert authorized_interface_items
        authorized_first_interface_id = authorized_interface_items[0]["interface_id"]

        forbidden_interface_update = client.put(
            f"/api/v1/merchant/apps/app_workbench_authorized/interfaces/{authorized_first_interface_id}",
            headers=auth_headers(token),
            json={
                "enabled": True,
                "quota_limit": 12,
                "expires_at": "2026-08-01T00:00:00",
                "remark": "should not save",
                "config": {"release_on_logout": True},
            },
        )
        assert forbidden_interface_update.status_code == 403

        self_rename = client.put(
            "/api/v1/merchant/apps/app_workbench_self",
            headers=auth_headers(token),
            json={"name": "Workbench Self App Renamed"},
        )
        assert self_rename.status_code == 200
        assert self_rename.json()["data"]["name"] == "Workbench Self App Renamed"

        self_delete = client.delete(
            "/api/v1/merchant/apps/app_workbench_self",
            headers=auth_headers(token),
        )
        assert self_delete.status_code == 200
        assert self_delete.json()["data"]["interface_config_count"] == 1
        assert self_delete.json()["data"]["spec_count"] == 0

        missing_self = client.get(
            "/api/v1/merchant/apps/app_workbench_self",
            headers=auth_headers(token),
        )
        assert missing_self.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_app_interfaces_expose_schema_driven_config_fields():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="schema-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_schema",
            name="Schema App",
            app_secret="secret-schema",
            rsa_public_key="public-schema",
            rsa_private_key="private-schema",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        session.add(app)
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        response = client.get(
            "/api/v1/merchant/apps/app_schema/interfaces",
            headers=auth_headers(token),
        )
        assert response.status_code == 200
        items = response.json()["data"]
        by_key = {item["interface_key"]: item for item in items}

        assert "points.redeem" in by_key
        assert "sdk.verify" in by_key
        assert "sdk.unbind" in by_key
        assert "sdk.device_limit" in by_key
        assert "sdk.notice" in by_key
        assert "sdk.update_check" in by_key

        redeem_schema = by_key["points.redeem"].get("config_schema") or []
        verify_schema = by_key["sdk.verify"].get("config_schema") or []
        unbind_schema = by_key["sdk.unbind"].get("config_schema") or []
        notice_schema = by_key["sdk.notice"].get("config_schema") or []
        update_schema = by_key["sdk.update_check"].get("config_schema") or []

        assert any(field["key"] == "allow_redeem" for field in redeem_schema)
        assert any(field["key"] == "bind_user_on_redeem" for field in redeem_schema)
        assert any(field["key"] == "signature_required" for field in verify_schema)
        assert any(field["key"] == "ip_lock_enabled" for field in verify_schema)
        assert any(field["key"] == "max_unbind_count" for field in unbind_schema)
        assert any(field["key"] == "max_notice_length" for field in notice_schema)
        assert any(field["key"] == "min_supported_version_code" for field in update_schema)
        assert by_key["points.redeem"]["config_schema"] != by_key["sdk.verify"]["config_schema"]
        assert "quota_limit" not in by_key["points.redeem"]
        assert "expires_at" not in by_key["points.redeem"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_notice_and_version_management_follows_app_ownership_boundaries():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="content-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        self_app = App(
            app_id="app_content_self",
            name="Content Self",
            app_secret="secret-self",
            rsa_public_key="public-self",
            rsa_private_key="private-self",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        authorized_app = App(
            app_id="app_content_authorized",
            name="Content Authorized",
            app_secret="secret-authorized",
            rsa_public_key="public-authorized",
            rsa_private_key="private-authorized",
            created_by="admin",
        )
        session.add_all([self_app, authorized_app])
        session.add(
            UserAppAuthorization(
                app_id=authorized_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(
            AppNotice(
                app_id=authorized_app.app_id,
                title="授权应用公告",
                content="只读公告",
                created_by="admin",
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        create_notice = client.post(
            "/api/v1/merchant/apps/app_content_self/notices",
            headers=auth_headers(token),
            json={
                "title": "自建公告",
                "content": "公告内容",
                "level": "normal",
                "enabled": True,
                "popup": False,
                "show_once": True,
            },
        )
        assert create_notice.status_code == 200
        notice_id = create_notice.json()["data"]["id"]
        assert create_notice.json()["data"]["revision"] == 1

        list_notice = client.get(
            "/api/v1/merchant/apps/app_content_self/notices",
            headers=auth_headers(token),
        )
        assert list_notice.status_code == 200
        assert list_notice.json()["data"]["items"][0]["title"] == "自建公告"

        readonly_notice = client.get(
            "/api/v1/merchant/apps/app_content_authorized/notices",
            headers=auth_headers(token),
        )
        assert readonly_notice.status_code == 200
        assert readonly_notice.json()["data"]["items"][0]["title"] == "授权应用公告"

        forbidden_notice = client.post(
            "/api/v1/merchant/apps/app_content_authorized/notices",
            headers=auth_headers(token),
            json={"title": "越权", "content": "不允许", "level": "normal"},
        )
        assert forbidden_notice.status_code == 403

        update_notice = client.put(
            f"/api/v1/merchant/apps/app_content_self/notices/{notice_id}",
            headers=auth_headers(token),
            json={
                "title": "自建公告更新",
                "content": "公告内容更新",
                "level": "important",
                "enabled": True,
                "popup": True,
                "show_once": False,
            },
        )
        assert update_notice.status_code == 200
        assert update_notice.json()["data"]["revision"] == 2

        invalid_version = client.post(
            "/api/v1/merchant/apps/app_content_self/updates",
            headers=auth_headers(token),
            json={
                "platform": "windows",
                "version": "2.0.0",
                "version_code": 200,
                "title": "强制更新",
                "force_update": True,
                "status": "published",
            },
        )
        assert invalid_version.status_code == 400

        create_version = client.post(
            "/api/v1/merchant/apps/app_content_self/updates",
            headers=auth_headers(token),
            json={
                "platform": "windows",
                "version": "2.0.0",
                "version_code": 200,
                "title": "新版发布",
                "notes": "更新说明",
                "force_update": True,
                "download_url": "https://example.com/v2.exe",
                "status": "published",
            },
        )
        assert create_version.status_code == 200
        version_id = create_version.json()["data"]["id"]

        versions = client.get(
            "/api/v1/merchant/apps/app_content_self/updates",
            headers=auth_headers(token),
        )
        assert versions.status_code == 200
        assert versions.json()["data"]["items"][0]["version"] == "2.0.0"

        delete_version = client.delete(
            f"/api/v1/merchant/apps/app_content_self/updates/{version_id}",
            headers=auth_headers(token),
        )
        assert delete_version.status_code == 200

        delete_notice = client.delete(
            f"/api/v1/merchant/apps/app_content_self/notices/{notice_id}",
            headers=auth_headers(token),
        )
        assert delete_notice.status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()


def test_duplicate_merchant_issue_batch_is_rejected_without_free_cards():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="duplicate-issuer", password_hash=hash_password("secret123"), status=1)
        app = App(
            app_id="app_duplicate_issue",
            name="Duplicate Issue App",
            app_secret="secret-duplicate",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=1,
        )
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app.owner_user_id = merchant.id
        session.add(app)
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=5))
        session.commit()
        token = routes_user.create_user_access_token(merchant)
        merchant_id = merchant.id

    payload = {
        "kami_type": "points",
        "count": 2,
        "points_amount": 10,
        "batch_no": "DUP-001",
        "code_length": 8,
    }

    try:
        first_response = client.post(
            "/api/v1/merchant/apps/app_duplicate_issue/kamis/batch",
            headers=auth_headers(token),
            json=payload,
        )
        assert first_response.status_code == 200

        duplicate_response = client.post(
            "/api/v1/merchant/apps/app_duplicate_issue/kamis/batch",
            headers=auth_headers(token),
            json=payload,
        )
        assert duplicate_response.status_code == 400
        assert "batch_no" in duplicate_response.json()["detail"]

        with Session(engine) as session:
            cards = session.exec(
                select(Kami).where(
                    Kami.app_id == "app_duplicate_issue",
                    Kami.batch_no == "DUP-001",
                    Kami.created_by_user_id == merchant_id,
                )
            ).all()
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            consume_transactions = session.exec(
                select(UserQuotaTransaction).where(
                    UserQuotaTransaction.user_id == merchant_id,
                    UserQuotaTransaction.quota_type == UserQuotaType.kami_issue,
                    UserQuotaTransaction.biz_id == "kami_issue:app_duplicate_issue:DUP-001::2",
                )
            ).all()
            assert len(cards) == 2
            assert account.kami_issue_balance == 3
            assert len(consume_transactions) == 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_issue_preview_returns_cost_and_balance_without_deducting():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="preview-issuer", password_hash=hash_password("secret123"), status=1)
        other = EndUser(username="other-issuer", password_hash=hash_password("secret123"), status=1)
        self_app = App(
            app_id="app_preview_self",
            name="Preview Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
        )
        authorized_app = App(
            app_id="app_preview_authorized",
            name="Preview Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        forbidden_app = App(
            app_id="app_preview_forbidden",
            name="Preview Forbidden App",
            app_secret="secret-forbidden",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=other.username,
        )
        session.add(merchant)
        session.add(other)
        session.commit()
        session.refresh(merchant)
        session.refresh(other)
        self_app.owner_user_id = merchant.id
        forbidden_app.owner_user_id = other.id
        session.add(self_app)
        session.add(authorized_app)
        session.add(forbidden_app)
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=5))
        session.commit()
        spec = KamiSpec(
            app_id=authorized_app.app_id,
            spec_key="lifetime-device",
            spec_name="Lifetime",
            kami_type="lifetime",
            status=1,
        )
        session.add(spec)
        session.add(
            UserAppAuthorization(
                app_id=authorized_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.commit()
        session.refresh(spec)
        token = routes_user.create_user_access_token(merchant)
        merchant_id = merchant.id
        spec_id = spec.id

    try:
        preview_response = client.post(
            "/api/v1/merchant/apps/app_preview_self/kamis/preview",
            headers=auth_headers(token),
            json={"kami_type": "points", "points_amount": 10, "count": 3},
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()["data"]
        assert {
            key: preview_data[key]
            for key in ("count", "unit_cost", "total_cost", "balance_before", "balance_after", "can_issue")
        } == {
            "count": 3,
            "unit_cost": 1,
            "total_cost": 3,
            "balance_before": 5,
            "balance_after": 2,
            "can_issue": True,
        }
        assert preview_data["pricing_source"] == "default"
        assert preview_data["pricing_rule_id"] is None
        assert preview_data["pricing_rule_key"] is None

        insufficient_response = client.post(
            "/api/v1/merchant/apps/app_preview_self/kamis/preview",
            headers=auth_headers(token),
            json={"kami_type": "points", "points_amount": 10, "count": 6},
        )
        assert insufficient_response.status_code == 200
        assert insufficient_response.json()["data"]["balance_after"] == -1
        assert insufficient_response.json()["data"]["can_issue"] is False

        missing_spec_response = client.post(
            "/api/v1/merchant/apps/app_preview_authorized/kamis/preview",
            headers=auth_headers(token),
            json={"count": 1},
        )
        assert missing_spec_response.status_code == 400
        assert "spec_id" in missing_spec_response.json()["detail"]

        authorized_preview_response = client.post(
            "/api/v1/merchant/apps/app_preview_authorized/kamis/preview",
            headers=auth_headers(token),
            json={"spec_id": spec_id, "count": 2},
        )
        assert authorized_preview_response.status_code == 200
        assert authorized_preview_response.json()["data"]["total_cost"] == 2
        assert authorized_preview_response.json()["data"]["can_issue"] is True

        forbidden_response = client.post(
            "/api/v1/merchant/apps/app_preview_forbidden/kamis/preview",
            headers=auth_headers(token),
            json={"kami_type": "points", "points_amount": 10, "count": 1},
        )
        assert forbidden_response.status_code == 403

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            assert account.kami_issue_balance == 5
            assert session.exec(select(UserQuotaTransaction)).all() == []
            assert session.exec(select(Kami)).all() == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_issue_pricing_rules_drive_merchant_preview_issue_and_quota_snapshots():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="priced-issuer", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        self_app = App(
            app_id="app_priced_self",
            name="Priced Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        authorized_app = App(
            app_id="app_priced_authorized",
            name="Priced Authorized App",
            app_secret="secret-authorized",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        session.add(self_app)
        session.add(authorized_app)
        session.commit()
        spec = KamiSpec(
            app_id=authorized_app.app_id,
            spec_key="priced-lifetime",
            spec_name="Priced Lifetime",
            kami_type="lifetime",
            status=1,
        )
        session.add(spec)
        session.add(
            UserAppAuthorization(
                app_id=authorized_app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=20))
        session.commit()
        session.refresh(spec)
        token = routes_user.create_user_access_token(merchant)
        merchant_id = merchant.id
        spec_id = spec.id

    try:
        self_rule = client.post(
            "/api/v1/admin/commercial/issue-pricing/rules",
            json={
                "target_type": "user_self_app",
                "user_id": merchant_id,
                "unit_cost": 3,
                "confirm_text": CONFIRM_CHANGE_ISSUE_PRICING,
            },
        )
        assert self_rule.status_code == 200
        assert self_rule.json()["data"]["unit_cost"] == 3

        authorized_rule = client.post(
            "/api/v1/admin/commercial/issue-pricing/rules",
            json={
                "target_type": "user_authorized_spec",
                "user_id": merchant_id,
                "spec_id": spec_id,
                "unit_cost": 5,
                "confirm_text": CONFIRM_CHANGE_ISSUE_PRICING,
            },
        )
        assert authorized_rule.status_code == 200
        assert authorized_rule.json()["data"]["unit_cost"] == 5

        self_preview = client.post(
            "/api/v1/merchant/apps/app_priced_self/kamis/preview",
            headers=auth_headers(token),
            json={"kami_type": "points", "points_amount": 10, "count": 2},
        )
        assert self_preview.status_code == 200
        assert self_preview.json()["data"]["unit_cost"] == 3
        assert self_preview.json()["data"]["total_cost"] == 6
        assert self_preview.json()["data"]["pricing_source"] == "user_self_app"
        assert self_preview.json()["data"]["pricing_rule_id"] == self_rule.json()["data"]["id"]
        assert self_preview.json()["data"]["pricing_rule_key"] == self_rule.json()["data"]["rule_key"]

        self_issue = client.post(
            "/api/v1/merchant/apps/app_priced_self/kamis/batch",
            headers=auth_headers(token),
            json={
                "kami_type": "points",
                "points_amount": 10,
                "count": 2,
                "batch_no": "PRICED-SELF-001",
            },
        )
        assert self_issue.status_code == 200
        assert self_issue.json()["data"]["total_cost"] == 6
        assert self_issue.json()["data"]["pricing_source"] == "user_self_app"
        assert self_issue.json()["data"]["pricing_rule_id"] == self_rule.json()["data"]["id"]

        authorized_preview = client.post(
            "/api/v1/merchant/apps/app_priced_authorized/kamis/preview",
            headers=auth_headers(token),
            json={"spec_id": spec_id, "count": 2},
        )
        assert authorized_preview.status_code == 200
        assert authorized_preview.json()["data"]["unit_cost"] == 5
        assert authorized_preview.json()["data"]["total_cost"] == 10
        assert authorized_preview.json()["data"]["pricing_source"] == "user_authorized_spec"
        assert authorized_preview.json()["data"]["pricing_rule_id"] == authorized_rule.json()["data"]["id"]
        assert authorized_preview.json()["data"]["pricing_rule_key"] == authorized_rule.json()["data"]["rule_key"]

        authorized_issue = client.post(
            "/api/v1/merchant/apps/app_priced_authorized/kamis/batch",
            headers=auth_headers(token),
            json={"spec_id": spec_id, "count": 2, "batch_no": "PRICED-AUTH-001"},
        )
        assert authorized_issue.status_code == 200
        assert authorized_issue.json()["data"]["total_cost"] == 10
        assert authorized_issue.json()["data"]["pricing_source"] == "user_authorized_spec"
        assert authorized_issue.json()["data"]["pricing_rule_id"] == authorized_rule.json()["data"]["id"]

        self_batches = client.get(
            "/api/v1/merchant/apps/app_priced_self/batches",
            headers=auth_headers(token),
        )
        assert self_batches.status_code == 200
        self_batch = self_batches.json()["items"][0]
        assert self_batch["batch_no"] == "PRICED-SELF-001"
        assert self_batch["unit_issue_cost"] == 3
        assert self_batch["total_issue_cost"] == 6
        assert self_batch["pricing_source"] == "user_self_app"

        authorized_batches = client.get(
            "/api/v1/merchant/apps/app_priced_authorized/batches",
            headers=auth_headers(token),
        )
        assert authorized_batches.status_code == 200
        authorized_batch = authorized_batches.json()["items"][0]
        assert authorized_batch["batch_no"] == "PRICED-AUTH-001"
        assert authorized_batch["spec_name"] == "Priced Lifetime"
        assert authorized_batch["unit_issue_cost"] == 5
        assert authorized_batch["total_issue_cost"] == 10
        assert authorized_batch["pricing_source"] == "user_authorized_spec"

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            assert account.kami_issue_balance == 4
            consume_transactions = session.exec(
                select(UserQuotaTransaction)
                .where(
                    UserQuotaTransaction.user_id == merchant_id,
                    UserQuotaTransaction.transaction_type == UserQuotaTransactionType.consume,
                )
                .order_by(UserQuotaTransaction.id)
            ).all()
            assert [tx.amount for tx in consume_transactions] == [-6, -10]
            metadata = [json.loads(tx.metadata_json) for tx in consume_transactions]
            assert metadata[0]["unit_cost"] == 3
            assert metadata[0]["pricing_source"] == "user_self_app"
            assert metadata[1]["unit_cost"] == 5
            assert metadata[1]["pricing_source"] == "user_authorized_spec"
            assert metadata[1]["pricing_rule_id"] == authorized_rule.json()["data"]["id"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_can_delete_own_issued_kamis_and_refund_source_quota():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="delete-issuer", password_hash="secret123", status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)

        app = App(
            app_id="app_delete_self",
            name="Delete Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        session.add(app)
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=20))
        session.commit()
        session.refresh(app)

        issue_user_kamis(
            session,
            merchant,
            app,
            kami_type="points",
            count=2,
            unit_cost=3,
            batch_no="REFUND-001",
            points_amount=100,
        )
        issue_user_kamis(
            session,
            merchant,
            app,
            kami_type="points",
            count=1,
            unit_cost=5,
            batch_no="REFUND-001",
            points_amount=100,
            allow_existing_batch=True,
            biz_id_suffix="second",
        )
        session.commit()

        cards = session.exec(
            select(Kami)
            .where(Kami.app_id == app.app_id, Kami.created_by_user_id == merchant.id)
            .order_by(Kami.id)
        ).all()
        session.add(
            KamiDeviceBinding(
                app_id=app.app_id,
                kami_code=cards[0].kami_code,
                device_uuid="device-a",
                fingerprint="fingerprint-a",
            )
        )
        session.add(
            EventLog(
                app_id=app.app_id,
                kami_code=cards[-1].kami_code,
                event_type="verify",
                status=1,
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        delete_response = client.post(
            "/api/v1/merchant/kamis/delete",
            headers=auth_headers(token),
            json={
                "app_id": "app_delete_self",
                "kami_codes": [cards[0].kami_code, cards[-1].kami_code],
            },
        )
        assert delete_response.status_code == 200
        delete_data = delete_response.json()["data"]
        assert delete_data["deleted_count"] == 2
        assert delete_data["refunded_amount"] == 8
        assert delete_data["skipped_count"] == 0

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant.id)
            ).one()
            assert account.kami_issue_balance == 17

            remaining_cards = session.exec(
                select(Kami).where(Kami.app_id == "app_delete_self")
            ).all()
            assert len(remaining_cards) == 1
            assert remaining_cards[0].issue_quota_transaction_id is not None

            refund_transactions = session.exec(
                select(UserQuotaTransaction)
                .where(
                    UserQuotaTransaction.user_id == merchant.id,
                    UserQuotaTransaction.transaction_type == UserQuotaTransactionType.refund,
                )
                .order_by(UserQuotaTransaction.id)
            ).all()
            assert [tx.amount for tx in refund_transactions] == [3, 5]

        tx_response = client.get(
            "/api/v1/merchant/quota-transactions",
            headers=auth_headers(token),
        )
        assert tx_response.status_code == 200
        delete_tx = next(
            item for item in tx_response.json()["data"]["items"] if str(item.get("biz_id", "")).startswith("kami_delete:")
        )
        assert delete_tx["display_scene"] == "额度退回"
        assert delete_tx["display_subject"].startswith("删除卡密返还额度")
        assert "Refund deleted kami" not in tx_response.text

        with Session(engine) as session:
            assert session.exec(select(KamiDeviceBinding)).all() == []
            logs = session.exec(select(EventLog)).all()
            assert len(logs) == 1
            assert logs[0].kami_code is None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_deleting_last_issued_kami_cleans_empty_batch_and_allows_spec_delete():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="cleanup-issuer", password_hash="secret123", status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)

        app = App(
            app_id="app_cleanup_self",
            name="Cleanup Self App",
            app_secret="secret-self",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="points-cleanup",
            spec_name="Cleanup Spec",
            kami_type="points",
            points_amount=100,
            status=1,
        )
        session.add(app)
        session.add(spec)
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=10))
        session.commit()
        session.refresh(spec)

        issue_user_kamis(
            session,
            merchant,
            app,
            spec_id=spec.id,
            kami_type="points",
            count=1,
            unit_cost=3,
            batch_no="CLEAN-001",
            points_amount=100,
        )
        session.commit()

        card = session.exec(
            select(Kami).where(Kami.app_id == app.app_id, Kami.created_by_user_id == merchant.id)
        ).one()
        batch = session.exec(
            select(KamiBatch).where(KamiBatch.app_id == app.app_id, KamiBatch.batch_no == "CLEAN-001")
        ).one()
        assert batch.spec_id == spec.id
        token = routes_user.create_user_access_token(merchant)

    try:
        delete_response = client.post(
            "/api/v1/merchant/kamis/delete",
            headers=auth_headers(token),
            json={"app_id": app.app_id, "kami_codes": [card.kami_code]},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["deleted_count"] == 1

        with Session(engine) as session:
            assert (
                session.exec(
                    select(Kami).where(Kami.app_id == app.app_id, Kami.batch_no == "CLEAN-001")
                ).all()
                == []
            )
            assert (
                session.exec(
                    select(KamiBatch).where(KamiBatch.app_id == app.app_id, KamiBatch.batch_no == "CLEAN-001")
                ).all()
                == []
            )

        delete_spec = client.delete(
            f"/api/v1/merchant/apps/{app.app_id}/specs/{spec.id}",
            headers=auth_headers(token),
        )
        assert delete_spec.status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_self_owned_app_legacy_unassigned_kamis_are_visible_deletable_and_unblock_spec_delete():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="legacy-owner", password_hash="secret123", status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)

        app = App(
            app_id="app_legacy_owner",
            name="Legacy Owner App",
            app_secret="secret-owner",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        spec = KamiSpec(
            app_id=app.app_id,
            spec_key="legacy-points",
            spec_name="Legacy Points",
            kami_type=KamiType.points,
            points_amount=100,
            status=1,
        )
        account = UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=7)
        session.add_all([app, spec, account])
        session.commit()
        session.refresh(spec)
        session.refresh(account)

        tx_id = "UQ-LEGACY-CONSUME"
        session.add(
            UserQuotaTransaction(
                transaction_id=tx_id,
                account_id=account.id,
                user_id=merchant.id,
                username=merchant.username,
                quota_type=UserQuotaType.kami_issue,
                transaction_type=UserQuotaTransactionType.consume,
                amount=-2,
                balance_before=9,
                balance_after=7,
                biz_id="kami_issue:app_legacy_owner:LEGACY-BATCH:2",
                operator=merchant.username,
                metadata_json=json.dumps({"unit_cost": 2, "count": 1, "total_cost": 2}),
            )
        )
        session.add(
            KamiBatch(
                app_id=app.app_id,
                spec_id=spec.id,
                batch_no="LEGACY-BATCH",
                kami_type=KamiType.points,
                points_amount=100,
            )
        )
        session.add(
            Kami(
                app_id=app.app_id,
                spec_id=spec.id,
                kami_code="LEGACY-OWNER-001",
                kami_type=KamiType.points,
                status=KamiStatus.unused,
                batch_no="LEGACY-BATCH",
                points_amount=100,
                created_by_user_id=None,
                issue_quota_transaction_id=tx_id,
            )
        )
        session.commit()
        token = routes_user.create_user_access_token(merchant)

    try:
        spec_list = client.get(
            "/api/v1/merchant/apps/app_legacy_owner/specs",
            headers=auth_headers(token),
        )
        assert spec_list.status_code == 200
        listed_spec = spec_list.json()["data"]["items"][0]
        assert listed_spec["total_count"] == 1
        assert listed_spec["batch_count"] == 1
        assert listed_spec["capabilities"]["can_delete"] is False

        detail_kamis = client.get(
            f"/api/v1/merchant/kami-specs/{spec.id}/kamis",
            headers=auth_headers(token),
        )
        assert detail_kamis.status_code == 200
        assert [item["kami_code"] for item in detail_kamis.json()["data"]["items"]] == ["LEGACY-OWNER-001"]

        delete_response = client.post(
            "/api/v1/merchant/kamis/delete",
            headers=auth_headers(token),
            json={"app_id": app.app_id, "kami_codes": ["LEGACY-OWNER-001"]},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["data"]["deleted_count"] == 1
        assert delete_response.json()["data"]["refunded_amount"] == 2
        assert delete_response.json()["data"]["quota_balance_after"] == 9

        delete_spec = client.delete(
            f"/api/v1/merchant/apps/{app.app_id}/specs/{spec.id}",
            headers=auth_headers(token),
        )
        assert delete_spec.status_code == 200
    finally:
        fastapi_app.dependency_overrides.clear()


def test_legacy_user_management_routes_are_gone_for_merchant_accounts():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="legacy-merchant", password_hash="hash", app_id=None, status=1)
        session.add(merchant)
        app = App(
            app_id="app_legacy_admin",
            name="Legacy Admin App",
            app_secret="secret-should-not-leak",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
            status=1,
        )
        session.add(app)
        session.commit()
        session.refresh(merchant)
        spec = KamiSpec(
            app_id="app_legacy_admin",
            spec_key="vip",
            spec_name="VIP",
            kami_type="points",
            points_amount=100,
            points_valid_days=30,
            status=1,
        )
        session.add(spec)
        session.add(
            UserAppAuthorization(
                app_id="app_legacy_admin",
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=20))
        session.commit()
        merchant_token = routes_user.create_user_access_token(merchant)

    try:
        apps_response = client.get(
            "/api/v1/user/apps",
            headers=auth_headers(merchant_token),
        )
        assert apps_response.status_code == 410
        assert "secret-should-not-leak" not in apps_response.text

        issue_response = client.post(
            "/api/v1/user/apps/app_legacy_admin/kamis/batch",
            headers=auth_headers(merchant_token),
            json={
                "kami_type": "points",
                "points_amount": 999,
                "points_valid_days": 365,
                "count": 2,
                "batch_no": "LEGACY-BYPASS",
                "code_length": 8,
            },
        )
        assert issue_response.status_code == 410

        with Session(engine) as session:
            rows = session.exec(select(Kami).where(Kami.batch_no == "LEGACY-BYPASS")).all()
            assert rows == []
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.username == "legacy-merchant")
            ).one()
            assert account.kami_issue_balance == 20
    finally:
        fastapi_app.dependency_overrides.clear()


def test_application_users_cannot_use_quota_or_app_management_routes():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        app = App(
            app_id="app_usage_only",
            name="Usage Only",
            app_secret="usage-secret",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
            status=1,
        )
        user = EndUser(username="usage-only", password_hash="hash", app_id="app_usage_only", status=1)
        session.add(app)
        session.add(user)
        session.commit()
        session.refresh(user)
        user_token = routes_user.create_user_access_token(user)

    try:
        quota_response = client.get(
            "/api/v1/user/quotas",
            headers=auth_headers(user_token),
        )
        assert quota_response.status_code == 410

        apps_response = client.get(
            "/api/v1/user/apps",
            headers=auth_headers(user_token),
        )
        assert apps_response.status_code == 410

        create_response = client.post(
            "/api/v1/user/apps",
            headers=auth_headers(user_token),
            json={"name": "Unexpected App"},
        )
        assert create_response.status_code == 410
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_devices_require_admin_and_merchant_devices_are_scoped():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(username="device-merchant", password_hash=hash_password("secret123"), status=1)
        other_merchant = EndUser(username="other-device-merchant", password_hash=hash_password("secret123"), status=1)
        no_app_merchant = EndUser(username="no-app-device-merchant", password_hash=hash_password("secret123"), status=1)
        usage_user = EndUser(
            app_id="app_device_owned",
            username="usage-device-user",
            password_hash=hash_password("secret123"),
            status=1,
        )
        app = App(
            app_id="app_device_owned",
            name="Device Owned App",
            app_secret="secret-device-owned",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="device-merchant",
        )
        other_app = App(
            app_id="app_device_other",
            name="Other Device App",
            app_secret="secret-device-other",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="other-device-merchant",
        )
        authorized_app = App(
            app_id="app_device_authorized",
            name="Authorized Device App",
            app_secret="secret-device-authorized",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by="admin",
        )
        session.add(merchant)
        session.add(other_merchant)
        session.add(no_app_merchant)
        session.add(usage_user)
        session.add(app)
        session.add(other_app)
        session.add(authorized_app)
        session.commit()
        session.refresh(merchant)
        session.refresh(other_merchant)
        session.refresh(no_app_merchant)
        session.refresh(usage_user)
        app.owner_user_id = merchant.id
        other_app.owner_user_id = other_merchant.id
        session.add(app)
        session.add(other_app)
        session.add(
            UserAppAuthorization(
                app_id="app_device_authorized",
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
            )
        )
        session.add(
            Kami(
                app_id="app_device_owned",
                kami_code="DEVOWN001",
                kami_type="points",
                status="active",
                points_amount=10,
                redeemed_by_user_id=usage_user.id,
                created_by_user_id=merchant.id,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_device_owned",
                kami_code="DEVOWN001",
                device_uuid="device-owned-1",
                fingerprint="fingerprint-owned-1",
                bind_ip="203.0.113.10",
            )
        )
        session.add(Device(app_id="app_device_owned", uuid="device-owned-1", fingerprint="fingerprint-owned-1", last_ip="203.0.113.10"))
        session.add(
            Kami(
                app_id="app_device_authorized",
                kami_code="DEVAUTH001",
                kami_type="points",
                status="active",
                points_amount=10,
                created_by_user_id=merchant.id,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_device_authorized",
                kami_code="DEVAUTH001",
                device_uuid="device-authorized-1",
                fingerprint="fingerprint-authorized-1",
                bind_ip="203.0.113.12",
            )
        )
        session.add(
            Device(
                app_id="app_device_authorized",
                uuid="device-authorized-1",
                fingerprint="fingerprint-authorized-1",
                last_ip="203.0.113.12",
            )
        )
        session.add(
            Kami(
                app_id="app_device_other",
                kami_code="DEVOTH001",
                kami_type="points",
                status="active",
                points_amount=10,
                created_by_user_id=other_merchant.id,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_device_other",
                kami_code="DEVOTH001",
                device_uuid="device-other-1",
                fingerprint="fingerprint-other-1",
                bind_ip="203.0.113.11",
            )
        )
        session.add(Device(app_id="app_device_other", uuid="device-other-1", fingerprint="fingerprint-other-1", last_ip="203.0.113.11"))
        session.commit()
        merchant_token = routes_user.create_user_access_token(merchant)
        no_app_merchant_token = routes_user.create_user_access_token(no_app_merchant)
        admin_token = routes_admin.create_access_token({"sub": "admin", "user_id": 1, "is_admin": True})

    try:
        forbidden_admin_response = client.get(
            "/api/v1/admin/devices",
            headers=auth_headers(merchant_token),
        )
        assert forbidden_admin_response.status_code == 403

        forbidden_risk_response = client.put(
            "/api/v1/admin/devices/1/risk",
            headers=auth_headers(merchant_token),
            params={"risk_level": 2},
        )
        assert forbidden_risk_response.status_code == 403

        merchant_devices_response = client.get(
            "/api/v1/merchant/devices",
            headers=auth_headers(merchant_token),
        )
        assert merchant_devices_response.status_code == 200
        merchant_items = merchant_devices_response.json()["data"]["items"]
        merchant_items_by_app = {item["app_id"]: item for item in merchant_items}
        assert set(merchant_items_by_app) == {"app_device_owned", "app_device_authorized"}
        assert merchant_items_by_app["app_device_owned"]["uuid"] == "device-owned-1"
        assert merchant_items_by_app["app_device_owned"]["card_source"] == "merchant_issued"
        assert merchant_items_by_app["app_device_owned"]["app_source"] == "merchant_self_owned"
        assert merchant_items_by_app["app_device_owned"]["can_manage_risk"] is True
        assert merchant_items_by_app["app_device_owned"]["issuing_user"]["username"] == "device-merchant"
        assert merchant_items_by_app["app_device_owned"]["owning_user"]["username"] == "device-merchant"
        assert merchant_items_by_app["app_device_authorized"]["uuid"] == "device-authorized-1"
        assert merchant_items_by_app["app_device_authorized"]["app_source"] == "admin_authorized"
        assert merchant_items_by_app["app_device_authorized"]["can_manage_risk"] is False

        merchant_risk_response = client.put(
            f"/api/v1/merchant/devices/{merchant_items_by_app['app_device_owned']['id']}/risk",
            headers=auth_headers(merchant_token),
            params={"risk_level": 2},
        )
        assert merchant_risk_response.status_code == 200
        with Session(engine) as session:
            owned_device = session.exec(select(Device).where(Device.uuid == "device-owned-1")).one()
            owned_ip_risk = session.exec(
                select(DeviceIpRisk).where(
                    DeviceIpRisk.app_id == "app_device_owned",
                    DeviceIpRisk.ip_address == "203.0.113.10",
                )
            ).one()
            assert owned_device.risk_level == 2
            assert owned_ip_risk.risk_level == 2

        authorized_risk_response = client.put(
            f"/api/v1/merchant/devices/{merchant_items_by_app['app_device_authorized']['id']}/risk",
            headers=auth_headers(merchant_token),
            params={"risk_level": 2},
        )
        assert authorized_risk_response.status_code == 403
        with Session(engine) as session:
            authorized_device = session.exec(select(Device).where(Device.uuid == "device-authorized-1")).one()
            assert authorized_device.risk_level == 0

        no_app_forbidden_response = client.get(
            "/api/v1/merchant/devices",
            headers=auth_headers(no_app_merchant_token),
            params={"app_id": "app_device_owned"},
        )
        assert no_app_forbidden_response.status_code == 403

        admin_devices_response = client.get(
            "/api/v1/admin/devices",
            headers=auth_headers(admin_token),
            params={"app_id": "app_device_owned"},
        )
        assert admin_devices_response.status_code == 200
        admin_item = admin_devices_response.json()["data"]["items"][0]
        assert admin_item["uuid"] == "device-owned-1"
        assert admin_item["user_type"] == "usage_user"
        assert admin_item["card_source"] == "merchant_issued"
        assert admin_item["app_source"] == "merchant_self_owned"
        assert admin_item["issuing_user"]["username"] == "device-merchant"
        assert admin_item["owning_user"]["username"] == "device-merchant"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_device_management_groups_devices_by_kami_and_keeps_machine_details():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    first_bind_at = get_now_naive()
    with Session(engine) as session:
        merchant = EndUser(username="device-group-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        app = App(
            app_id="app_device_group",
            name="Device Group App",
            app_secret="secret-device-group",
            rsa_public_key="public",
            rsa_private_key="private",
            created_by=merchant.username,
            owner_user_id=merchant.id,
        )
        session.add(app)
        session.add(
            Kami(
                app_id="app_device_group",
                kami_code="GROUPDEV001",
                kami_type="lifetime",
                status="active",
                machine_bind_mode="no_limit",
                max_bind_devices=0,
                created_by_user_id=merchant.id,
            )
        )
        machines = [
            ("device-first", "fingerprint-first", "DESKTOP-FIRST", "Legion Y7000P IRX9", "FIRST-ID", "203.0.113.21", 0),
            ("device-second", "fingerprint-second", "DESKTOP-SECOND", "ThinkBook 14", "SECOND-ID", "203.0.113.22", 0),
            ("device-third", "fingerprint-third", "DESKTOP-THIRD", "Surface Pro", "THIRD-ID", "203.0.113.23", 0),
        ]
        for index, (uuid, fingerprint, name, model, device_id, ip, risk_level) in enumerate(machines):
            session.add(
                KamiDeviceBinding(
                    app_id="app_device_group",
                    kami_code="GROUPDEV001",
                    device_uuid=uuid,
                    fingerprint=fingerprint,
                    bind_ip=ip,
                    first_bind_at=first_bind_at + timedelta(minutes=index),
                    last_verify_at=first_bind_at + timedelta(minutes=index),
                )
            )
            session.add(
                Device(
                    app_id="app_device_group",
                    uuid=uuid,
                    fingerprint=fingerprint,
                    device_name=name,
                    device_model=model,
                    device_id=device_id,
                    last_ip=ip,
                    risk_level=risk_level,
                )
            )
        session.commit()
        merchant_token = routes_user.create_user_access_token(merchant)
        admin_token = routes_admin.create_access_token({"sub": "admin", "user_id": 1, "is_admin": True})

    try:
        admin_response = client.get(
            "/api/v1/admin/devices",
            headers=auth_headers(admin_token),
            params={"app_id": "app_device_group"},
        )
        assert admin_response.status_code == 200
        admin_items = admin_response.json()["data"]["items"]
        assert len(admin_items) == 1
        admin_item = admin_items[0]
        assert admin_item["row_type"] == "kami"
        assert admin_item["kami_code"] == "GROUPDEV001"
        assert admin_item["device_count"] == 3
        assert admin_item["device_name"] == "DESKTOP-FIRST"
        assert admin_item["device_model"] == "Legion Y7000P IRX9"
        assert admin_item["device_id"] == "FIRST-ID"
        assert admin_item["last_ip"] == "203.0.113.21"
        assert admin_item["risk_level"] == 0
        assert admin_item["machine_bind_mode"] == "no_limit"
        assert admin_item["machine_bind_mode_text"] == "不限制(2台)"
        assert admin_item["detail_device_count"] == 2
        assert [device["device_id"] for device in admin_item["device_items"]] == [
            "SECOND-ID",
            "THIRD-ID",
        ]
        assert [device["last_ip"] for device in admin_item["device_items"]] == [
            "203.0.113.22",
            "203.0.113.23",
        ]
        assert [device["risk_level"] for device in admin_item["device_items"]] == [0, 0]

        second_device = admin_item["device_items"][0]
        risk_response = client.put(
            f"/api/v1/admin/devices/{second_device['id']}/risk",
            headers=auth_headers(admin_token),
            params={"risk_level": 2},
        )
        assert risk_response.status_code == 200

        refreshed_response = client.get(
            "/api/v1/admin/devices",
            headers=auth_headers(admin_token),
            params={"app_id": "app_device_group"},
        )
        refreshed_item = refreshed_response.json()["data"]["items"][0]
        assert refreshed_item["id"] == admin_item["id"]
        assert refreshed_item["risk_level"] == 0
        assert [
            (device["device_id"], device["last_ip"], device["risk_level"])
            for device in refreshed_item["device_items"]
        ] == [
            ("SECOND-ID", "203.0.113.22", 2),
            ("THIRD-ID", "203.0.113.23", 0),
        ]

        merchant_response = client.get(
            "/api/v1/merchant/devices",
            headers=auth_headers(merchant_token),
            params={"app_id": "app_device_group", "keyword": "SECOND-ID"},
        )
        assert merchant_response.status_code == 200
        merchant_items = merchant_response.json()["data"]["items"]
        assert len(merchant_items) == 1
        assert merchant_items[0]["kami_code"] == "GROUPDEV001"
        assert merchant_items[0]["device_count"] == 3
        assert [device["device_name"] for device in merchant_items[0]["device_items"]] == [
            "DESKTOP-SECOND",
            "DESKTOP-THIRD",
        ]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_device_management_deduplicates_first_device_before_detail_split():
    payloads = [
        {
            "id": "historical:app_device_group:FIRST-ID",
            "app_id": "app_device_group",
            "kami_code": "GROUPDEV001",
            "kami_codes": ["GROUPDEV001"],
            "uuid": "FIRST-ID",
            "fingerprint": "FIRST-ID",
            "device_name": None,
            "device_model": None,
            "device_id": None,
            "last_ip": "203.0.113.21",
            "risk_level": 0,
            "risk_level_text": "正常",
            "first_bind_at": "2026-07-30T10:00:00",
            "machine_bind_mode_text": "不限制",
        },
        {
            "id": 1,
            "app_id": "app_device_group",
            "kami_code": "GROUPDEV001",
            "kami_codes": ["GROUPDEV001"],
            "uuid": "legacy-first-uuid",
            "fingerprint": "legacy-first-fingerprint",
            "device_name": "DESKTOP-FSQQCER",
            "device_model": "Legion Y7000P IRX9",
            "device_id": "FIRST-ID",
            "last_ip": "203.0.113.21",
            "risk_level": 0,
            "risk_level_text": "正常",
            "first_bind_at": "2026-07-30T10:00:00",
            "machine_bind_mode_text": "不限制",
        },
        {
            "id": 2,
            "app_id": "app_device_group",
            "kami_code": "GROUPDEV001",
            "kami_codes": ["GROUPDEV001"],
            "uuid": "SECOND-ID",
            "fingerprint": "SECOND-ID",
            "device_name": "DESKTOP-SECOND",
            "device_model": "ThinkBook 14",
            "device_id": "SECOND-ID",
            "last_ip": "203.0.113.22",
            "risk_level": 0,
            "risk_level_text": "正常",
            "first_bind_at": "2026-07-30T10:01:00",
            "machine_bind_mode_text": "不限制",
        },
    ]

    grouped = group_device_payloads_by_kami(payloads)

    assert len(grouped) == 1
    item = grouped[0]
    assert item["device_count"] == 2
    assert item["detail_device_count"] == 1
    assert item["machine_bind_mode_text"] == "不限制(1台)"
    assert item["device_name"] == "DESKTOP-FSQQCER"
    assert item["device_id"] == "FIRST-ID"
    assert [device["device_id"] for device in item["device_items"]] == ["SECOND-ID"]


def test_proof_upload_runtime_has_writable_persistent_uploads_directory():
    project_root = __import__("pathlib").Path(__file__).resolve().parents[1]
    dockerfile = (project_root / "Dockerfile").read_text(encoding="utf-8")
    prod_compose = (project_root / "docker-compose.prod.yml").read_text(encoding="utf-8")
    dev_compose = (project_root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "/app/uploads" in dockerfile
    assert "chown -R app:app /app/logs /app/uploads" in dockerfile
    assert "fastapi_uploads:/app/uploads" in prod_compose
    assert "fastapi_uploads:" in prod_compose
    assert "fastapi_uploads:/app/uploads" in dev_compose
    assert "fastapi_uploads:" in dev_compose


def test_hard_delete_merchant_removes_recharge_orders_and_proof_files(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    proof_dir = upload_root / "proofs"
    proof_dir.mkdir(parents=True)
    proof_path = proof_dir / "proof.png"
    proof_path.write_bytes(b"fake-png")
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    with Session(engine) as session:
        merchant = EndUser(username="delete-order-merchant", password_hash=hash_password("secret123"), status=1)
        session.add(merchant)
        session.commit()
        session.refresh(merchant)
        account = UserQuotaAccount(user_id=merchant.id, username=merchant.username, kami_issue_balance=10)
        session.add(account)
        session.commit()
        session.refresh(account)
        tx = UserQuotaTransaction(
            transaction_id="uq_delete_order",
            account_id=account.id,
            user_id=merchant.id,
            username=merchant.username,
            quota_type=UserQuotaType.kami_issue,
            transaction_type=UserQuotaTransactionType.grant,
            amount=10,
            balance_before=0,
            balance_after=10,
            biz_id="recharge_order:RC_DELETE_ORDER",
        )
        order = RechargeOrder(
            order_no="RC_DELETE_ORDER",
            user_id=merchant.id,
            username=merchant.username,
            mode=RechargeMode.custom,
            channel=RechargeChannel.wechat,
            amount_cents=1000,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            proof_file_path=proof_path.as_posix(),
            proof_file_name="proof.png",
            proof_content_type="image/png",
            quota_transaction_id=tx.transaction_id,
        )
        session.add(tx)
        session.add(order)
        session.commit()
        merchant_id = merchant.id

    try:
        response = client.post(
            "/api/v1/admin/end-users/delete",
            json={"user_ids": [merchant_id], "confirm_text": CONFIRM_DELETE_MERCHANT},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted_users"] == 1
        assert data["deleted_recharge_orders"] == 1
        assert data["deleted_recharge_proofs"] == 1
        assert not proof_path.exists()

        with Session(engine) as session:
            assert session.get(EndUser, merchant_id) is None
            assert session.exec(select(RechargeOrder)).all() == []
            assert session.exec(select(UserQuotaAccount)).all() == []
            assert session.exec(select(UserQuotaTransaction)).all() == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_hard_delete_merchant_requires_fixed_confirmation_text():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        merchant = EndUser(
            app_id=None,
            username="merchant_delete_confirm",
            password_hash=hash_password("pass123"),
            status=1,
        )
        session.add(merchant)
        session.commit()
        merchant_id = merchant.id

    try:
        missing_confirm = client.post(
            "/api/v1/admin/end-users/delete",
            json={"user_ids": [merchant_id]},
        )
        assert missing_confirm.status_code == 400
        assert missing_confirm.json()["detail"]["expected"] == CONFIRM_DELETE_MERCHANT

        confirmed = client.post(
            "/api/v1/admin/end-users/delete",
            json={"user_ids": [merchant_id], "confirm_text": CONFIRM_DELETE_MERCHANT},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["data"]["deleted_users"] == 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_payment_channel_upload_saves_qrcode_and_replaces_old_file(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    qr_dir = upload_root / "payment-qrcodes"
    qr_dir.mkdir(parents=True)
    old_qr = qr_dir / "wechat_old.png"
    old_qr.write_bytes(b"old-qr")
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    with Session(engine) as session:
        row = commercial_service.upsert_payment_channel(
            session,
            channel=RechargeChannel.wechat,
            display_name="Old WeChat",
            qr_code_url="/api/v1/commercial/payment-qrcodes/wechat_old.png",
            enabled=True,
            sort_order=1,
        )
        session.commit()
        assert row.id is not None

    try:
        response = client.post(
            "/api/v1/admin/commercial/payment-channels/upload",
            data={
                "channel": "wechat",
                "display_name": "WeChat Pay",
                "account_name": "receiver",
                "enabled": "true",
                "sort_order": "2",
                "remark": "new qr",
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
            files={"qr_code_file": ("wechat.png", b"new-qr", "image/png")},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["channel"] == "wechat"
        assert data["display_name"] == "WeChat Pay"
        assert data["account_name"] == "receiver"
        assert data["enabled"] is True
        assert data["sort_order"] == 2
        assert data["qr_code_url"].startswith("/api/v1/commercial/payment-qrcodes/")
        assert data["qr_code_url"].endswith(".png")

        new_qr_path = qr_dir / Path(data["qr_code_url"]).name
        assert new_qr_path.exists()
        assert new_qr_path.read_bytes() == b"new-qr"
        assert not old_qr.exists()
        served_qr_response = client.get(data["qr_code_url"])
        assert served_qr_response.status_code == 200
        assert served_qr_response.content == b"new-qr"

        with Session(engine) as session:
            saved = session.exec(
                select(RechargePaymentChannel).where(
                    RechargePaymentChannel.channel == RechargeChannel.wechat
                )
            ).one()
            assert saved.qr_code_url == data["qr_code_url"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_payment_channel_qrcode_delete_clears_url_and_removes_uploaded_file(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    qr_dir = upload_root / "payment-qrcodes"
    qr_dir.mkdir(parents=True)
    qr_path = qr_dir / "wechat_delete.png"
    qr_path.write_bytes(b"old-qr")
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    with Session(engine) as session:
        commercial_service.upsert_payment_channel(
            session,
            channel=RechargeChannel.wechat,
            display_name="WeChat Pay",
            qr_code_url="/api/v1/commercial/payment-qrcodes/wechat_delete.png",
            enabled=True,
            sort_order=1,
        )
        session.commit()

    try:
        response = client.delete(
            "/api/v1/admin/commercial/payment-channels/wechat/qrcode",
            params={"confirm_text": CONFIRM_DELETE_PAYMENT_QRCODE},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["channel"] == "wechat"
        assert data["qr_code_url"] is None
        assert data["deleted_file"] is True
        assert not qr_path.exists()

        with Session(engine) as session:
            saved = session.exec(
                select(RechargePaymentChannel).where(
                    RechargePaymentChannel.channel == RechargeChannel.wechat
                )
            ).one()
            assert saved.qr_code_url is None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_payment_channel_upload_preserves_qrcode_when_no_new_file_or_url(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    with Session(engine) as session:
        commercial_service.upsert_payment_channel(
            session,
            channel=RechargeChannel.wechat,
            display_name="WeChat Pay",
            qr_code_url="/api/v1/commercial/payment-qrcodes/wechat_saved.png",
            enabled=True,
            sort_order=1,
        )
        session.commit()

    try:
        response = client.post(
            "/api/v1/admin/commercial/payment-channels/upload",
            data={
                "channel": "wechat",
                "display_name": "WeChat Pay Updated",
                "enabled": "true",
                "sort_order": "2",
                "remark": "keep existing qr",
                "confirm_text": CONFIRM_CHANGE_RECHARGE_CONFIG,
            },
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["display_name"] == "WeChat Pay Updated"
        assert data["qr_code_url"] == "/api/v1/commercial/payment-qrcodes/wechat_saved.png"

        with Session(engine) as session:
            saved = session.exec(
                select(RechargePaymentChannel).where(
                    RechargePaymentChannel.channel == RechargeChannel.wechat
                )
            ).one()
            assert saved.qr_code_url == "/api/v1/commercial/payment-qrcodes/wechat_saved.png"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_recharge_order_upload_stores_proof_file(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        merchant_token = routes_user.create_user_access_token(merchant)
        session.add(
            RechargePaymentChannel(
                channel=RechargeChannel.wechat,
                display_name="WeChat Pay",
                qr_code_url="/api/v1/commercial/payment-qrcodes/wechat.png",
                enabled=True,
            )
        )
        session.add(
            RechargeBonusRule(
                threshold_amount_cents=30000,
                bonus_quota=50,
                enabled=True,
                sort_order=1,
            )
        )
        session.commit()

    try:
        response = client.post(
            "/api/v1/merchant/recharge/orders/upload",
            headers=auth_headers(merchant_token),
            data={
                "amount": "350",
                "mode": "custom",
                "channel": "wechat",
                "remark": "uploaded receipt",
            },
            files={"proof_file": ("receipt.webp", b"proof-bytes", "image/webp")},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "pending_review"
        assert data["base_quota"] == 350
        assert data["bonus_quota"] == 50
        assert data["credit_quota"] == 400
        assert data["has_proof"] is True
        assert data["proof_content_type"] == "image/webp"
        assert data["proof_file_name"].endswith(".webp")

        proof_path = upload_root / "proofs" / data["proof_file_name"]
        assert proof_path.exists()
        assert proof_path.read_bytes() == b"proof-bytes"

        with Session(engine) as session:
            order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == data["order_no"])
            ).one()
            assert order.proof_file_path == proof_path.as_posix()
            assert order.proof_file_name == data["proof_file_name"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_recharge_order_upload_rejects_oversized_proof(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    upload_root = tmp_path / "uploads" / "commercial"
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(commercial_service, "MAX_PROOF_BYTES", 4)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        merchant_token = routes_user.create_user_access_token(merchant)
        session.add(
            RechargePaymentChannel(
                channel=RechargeChannel.wechat,
                display_name="WeChat Pay",
                enabled=True,
            )
        )
        session.commit()

    try:
        response = client.post(
            "/api/v1/merchant/recharge/orders/upload",
            headers=auth_headers(merchant_token),
            data={"amount": "10", "mode": "custom", "channel": "wechat"},
            files={"proof_file": ("too-large.png", b"12345", "image/png")},
        )
        assert response.status_code == 400
        assert "too large" in response.json()["detail"]
        assert not (upload_root / "proofs").exists()
    finally:
        fastapi_app.dependency_overrides.clear()
