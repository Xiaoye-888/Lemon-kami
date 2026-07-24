import base64

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
import routes_auth
import routes_commercial
import routes_merchant
import routes_user
from auth_utils import hash_password
from main import app as fastapi_app
from models import (
    AdminUser,
    App,
    Device,
    EndUser,
    Kami,
    KamiDeviceBinding,
    KamiSpec,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaType,
)


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


def test_manual_recharge_order_review_credits_issue_quota_and_transactions():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

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

        orders_response = client.get("/api/v1/admin/commercial/recharge-orders")
        assert orders_response.status_code == 200
        assert orders_response.json()["data"]["items"][0]["order_no"] == order_data["order_no"]

        approve_response = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{order_data['order_no']}/approve",
            json={"remark": "到账确认"},
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["data"]["status"] == "approved"

        duplicate_response = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{order_data['order_no']}/approve",
            json={"remark": "duplicate click"},
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
        session.add(merchant)
        session.add(other_merchant)
        session.add(usage_user)
        session.add(app)
        session.add(other_app)
        session.commit()
        session.refresh(merchant)
        session.refresh(other_merchant)
        session.refresh(usage_user)
        app.owner_user_id = merchant.id
        other_app.owner_user_id = other_merchant.id
        session.add(app)
        session.add(other_app)
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
        assert [item["uuid"] for item in merchant_items] == ["device-owned-1"]
        assert merchant_items[0]["card_source"] == "merchant_issued"
        assert merchant_items[0]["app_source"] == "merchant_self_owned"
        assert merchant_items[0]["issuing_user"]["username"] == "device-merchant"
        assert merchant_items[0]["owning_user"]["username"] == "device-merchant"

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
