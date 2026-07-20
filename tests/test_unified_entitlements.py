from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.dialects import mysql
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateTable
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
import routes_sdk
import routes_user
from authorization_service import grant_points, grant_time, grant_times, get_or_create_authorization_account
from main import app as fastapi_app
from models import (
    ApiInterface,
    App,
    AppNotice,
    AppVersion,
    AuthorizationAccount,
    AuthorizationBenefitType,
    AuthorizationLot,
    AuthorizationOwnerMode,
    AuthorizationOwnerType,
    AuthorizationTransaction,
    AuthorizationTransactionType,
    Device,
    EndUser,
    EventLog,
    Kami,
    KamiDeviceBinding,
    KamiSpec,
    KamiStatus,
    KamiType,
    MachineBindMode,
    PointTransaction,
    PointTransactionType,
    UserBindMode,
    UserPointAccount,
    UserPointLot,
    get_now_naive,
)
from point_service import PointServiceError, consume_points, get_points_balance_summary, redeem_points_kami


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def make_engine_with_foreign_keys():
    engine = make_engine()

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_app(app_id="app_demo", name="Demo"):
    return App(
        app_id=app_id,
        name=name,
        app_secret=f"secret-{app_id}",
        rsa_public_key="public",
        rsa_private_key="private",
    )


def override_admin_user():
    return {"sub": "admin", "is_admin": True}


def override_session_factory(engine):
    def override_session():
        with Session(engine) as session:
            yield session

    return override_session


class FakeRedis:
    def __init__(self):
        self.hashes = {}

    def hgetall(self, key):
        return self.hashes.get(key, {})

    def hset(self, key, mapping):
        self.hashes[key] = dict(mapping)

    def expire(self, key, ttl):
        return True

    def delete(self, key):
        self.hashes.pop(key, None)


def test_notice_and_update_check_are_separate_sdk_surfaces():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_sdk.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add(
            AppNotice(
                app_id="app_demo",
                title="维护公告",
                content="今晚维护",
                level="important",
                enabled=True,
                popup=True,
                show_once=True,
                revision=1,
                created_by="admin",
            )
        )
        session.add(
            AppVersion(
                app_id="app_demo",
                platform="windows",
                version="1.2.0",
                version_code=120,
                title="发现新版本",
                notes="新增版本更新模块",
                force_update=False,
                download_url="https://example.com/app.exe",
                url_type="direct",
                button_text="立即下载",
                status="published",
            )
        )
        session.commit()

    try:
        notice_response = client.get("/api/v1/sdk/apps/app_demo/notice")
        assert notice_response.status_code == 200
        notice_data = notice_response.json()["data"]
        assert notice_data["notice_title"] == "维护公告"
        assert notice_data["notice"] == "今晚维护"
        assert notice_data["notice_popup"] is True
        assert "version" not in notice_data
        assert "update_url" not in notice_data
        assert "force_update" not in notice_data

        old_version_response = client.get(
            "/api/v1/sdk/apps/app_demo/updates/check",
            params={"current_version_code": 100, "platform": "windows"},
        )
        assert old_version_response.status_code == 200
        old_version_data = old_version_response.json()["data"]
        assert old_version_data["has_update"] is True
        assert old_version_data["latest_version"] == "1.2.0"
        assert old_version_data["latest_version_code"] == 120
        assert old_version_data["download_url"] == "https://example.com/app.exe"

        current_version_response = client.get(
            "/api/v1/sdk/apps/app_demo/updates/check",
            params={"current_version_code": 120, "platform": "windows"},
        )
        assert current_version_response.status_code == 200
        assert current_version_response.json()["data"] == {"has_update": False}
    finally:
        fastapi_app.dependency_overrides.clear()


def test_release_tables_use_mysql_safe_column_types():
    notice_ddl = str(CreateTable(AppNotice.__table__).compile(dialect=mysql.dialect()))
    version_ddl = str(CreateTable(AppVersion.__table__).compile(dialect=mysql.dialect()))

    assert "app_id VARCHAR(64) NOT NULL" in notice_ddl
    assert "content TEXT NOT NULL" in notice_ddl
    assert "app_id VARCHAR(64) NOT NULL" in version_ddl
    assert "notes TEXT" in version_ddl
    assert "download_url TEXT" in version_ddl


def test_admin_notice_and_version_management_records_history_and_validates_force_update():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.commit()

    try:
        notice_response = client.post(
            "/api/v1/admin/apps/app_demo/notices",
            json={
                "title": "系统公告",
                "content": "公告内容",
                "level": "normal",
                "enabled": True,
                "popup": True,
                "show_once": True,
            },
        )
        assert notice_response.status_code == 200
        assert notice_response.json()["data"]["revision"] == 1

        notices_response = client.get("/api/v1/admin/apps/app_demo/notices")
        assert notices_response.status_code == 200
        notices = notices_response.json()["data"]["items"]
        assert len(notices) == 1
        assert notices[0]["title"] == "系统公告"

        invalid_update_response = client.post(
            "/api/v1/admin/apps/app_demo/updates",
            json={
                "version": "2.0.0",
                "version_code": 200,
                "title": "强制更新",
                "notes": "必须更新",
                "force_update": True,
                "status": "published",
            },
        )
        assert invalid_update_response.status_code == 400

        update_response = client.post(
            "/api/v1/admin/apps/app_demo/updates",
            json={
                "platform": "windows",
                "version": "2.0.0",
                "version_code": 200,
                "title": "强制更新",
                "notes": "必须更新",
                "force_update": True,
                "download_url": "https://example.com/v2.exe",
                "status": "published",
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["data"]["status"] == "published"

        updates_response = client.get("/api/v1/admin/apps/app_demo/updates")
        assert updates_response.status_code == 200
        updates = updates_response.json()["data"]["items"]
        assert len(updates) == 1
        assert updates[0]["version"] == "2.0.0"
        assert updates[0]["force_update"] is True
    finally:
        fastapi_app.dependency_overrides.clear()


def test_points_redeem_credits_unified_user_app_account_and_stacks_by_app():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_app("app_a", "App A"))
        session.add(make_app("app_b", "App B"))
        user = EndUser(username="alice", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        session.add_all(
            [
                Kami(
                    app_id="app_a",
                    kami_code="POINT100A",
                    kami_type=KamiType.points,
                    status=KamiStatus.unused,
                    points_amount=100,
                    authorization_owner=AuthorizationOwnerMode.user,
                    user_bind_mode=UserBindMode.required,
                ),
                Kami(
                    app_id="app_a",
                    kami_code="POINT50A",
                    kami_type=KamiType.points,
                    status=KamiStatus.unused,
                    points_amount=50,
                    authorization_owner=AuthorizationOwnerMode.user,
                    user_bind_mode=UserBindMode.required,
                ),
                Kami(
                    app_id="app_b",
                    kami_code="POINT30B",
                    kami_type=KamiType.points,
                    status=KamiStatus.unused,
                    points_amount=30,
                    authorization_owner=AuthorizationOwnerMode.user,
                    user_bind_mode=UserBindMode.required,
                ),
            ]
        )
        session.commit()

        assert redeem_points_kami(session, user, "POINT100A")["balance"] == 100
        assert redeem_points_kami(session, user, "POINT50A")["balance"] == 150
        assert redeem_points_kami(session, user, "POINT30B")["balance"] == 30

        account_a = session.exec(
            select(AuthorizationAccount).where(
                AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
                AuthorizationAccount.user_id == user.id,
                AuthorizationAccount.app_id == "app_a",
            )
        ).first()
        account_b = session.exec(
            select(AuthorizationAccount).where(
                AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
                AuthorizationAccount.user_id == user.id,
                AuthorizationAccount.app_id == "app_b",
            )
        ).first()

        assert account_a is not None
        assert account_a.points_balance == 150
        assert account_b is not None
        assert account_b.points_balance == 30
        assert session.exec(select(PointTransaction)).all() == []
        assert session.exec(select(UserPointLot)).all() == []

        consume_result = consume_points(
            session=session,
            user_id=user.id,
            app_id="app_a",
            amount=40,
            biz_id="order-1001",
        )
        assert consume_result["balance_after"] == 110
        assert consume_result["idempotent"] is False
        assert consume_points(
            session=session,
            user_id=user.id,
            app_id="app_a",
            amount=40,
            biz_id="order-1001",
        )["idempotent"] is True

        session.refresh(account_a)
        session.refresh(account_b)
        assert account_a.points_balance == 110
        assert account_b.points_balance == 30
        assert get_points_balance_summary(session, user.id, "app_a")["balance"] == 110
        assert session.exec(select(PointTransaction)).all() == []
        assert session.exec(select(UserPointLot)).all() == []

        try:
            redeem_points_kami(session, user, "POINT100A")
        except PointServiceError as error:
            assert error.code == "already_redeemed"
        else:
            raise AssertionError("same points kami must not credit twice")

        session.refresh(account_a)
        assert account_a.points_balance == 110


def test_times_and_time_grants_stack_on_unified_account():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_app())
        user = EndUser(app_id="app_demo", username="bob", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        grant_times(session, account, 10, source_kami_code="TIMES10")
        grant_times(session, account, 20, source_kami_code="TIMES20")
        session.refresh(account)
        assert account.times_balance == 30

        now = get_now_naive()
        grant_time(session, account, days=10, source_kami_code="DAY10", now=now)
        session.refresh(account)
        first_expiry = account.time_expires_at
        grant_time(session, account, days=5, source_kami_code="DAY5", now=now + timedelta(days=1))
        session.refresh(account)

        assert first_expiry is not None
        assert account.time_expires_at == first_expiry + timedelta(days=5)


def test_authorization_account_sets_legacy_owner_key_for_existing_mysql_schema():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="owner-key-user", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        user_account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        device_account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.device.value,
            device_uuid="device-1",
            fingerprint="fingerprint-1",
        )

        assert user_account.owner_key == f"user:{user.id}"
        assert device_account.owner_key == "device:device-1"


def test_legacy_point_and_times_balances_are_visible_in_user_authorization():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="legacy", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(
            UserPointAccount(
                user_id=user.id,
                balance=90,
                total_recharged=120,
                total_consumed=30,
            )
        )
        session.add(
            UserPointLot(
                user_id=user.id,
                source_transaction_id="legacy-tx",
                app_id="app_demo",
                kami_code="LEGACYPOINTS",
                points_total=120,
                points_remaining=90,
            )
        )
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="LEGACYTIMES",
                kami_type=KamiType.times,
                status=KamiStatus.active,
                times_total=10,
                times_remaining=7,
                redeemed_by_user_id=user.id,
                authorization_owner=AuthorizationOwnerMode.user,
            )
        )
        session.commit()

        summary = get_points_balance_summary(session, user.id, "app_demo")
        assert summary["balance"] == 90
        account = session.exec(
            select(AuthorizationAccount).where(
                AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
                AuthorizationAccount.user_id == user.id,
                AuthorizationAccount.app_id == "app_demo",
            )
        ).first()
        assert account is not None
        assert account.points_balance == 90

        consume_result = consume_points(
            session=session,
            user_id=user.id,
            app_id="app_demo",
            amount=40,
            biz_id="legacy-consume",
        )
        assert consume_result["balance_after"] == 50

    try:
        response = client.get("/api/v1/admin/end-users", params={"app_id": "app_demo"})
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["username"] == "legacy"
        assert item["points_remaining"] == 50
        assert item["times_remaining"] == 7
    finally:
        fastapi_app.dependency_overrides.clear()


def test_user_points_consume_with_device_identity_creates_admin_device_row():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_user.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add(
            ApiInterface(
                name="Consume points",
                interface_key="points.consume",
                method="POST",
                path="/api/v1/user/points/consume",
                is_builtin=True,
                status=1,
            )
        )
        user = EndUser(app_id="app_demo", username="point-device", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        grant_points(session, account, 100, source_kami_code="POINT100")
        token = routes_user.create_user_access_token(user)

    try:
        response = client.post(
            "/api/v1/user/points/consume",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "test-client",
                "X-Forwarded-For": "10.0.0.8",
            },
            json={
                "app_id": "app_demo",
                "amount": 20,
                "biz_id": "device-consume-1",
                "uuid": "device-point-1",
                "fingerprint": "fingerprint-point-1",
            },
        )
        assert response.status_code == 200

        devices_response = client.get("/api/v1/admin/devices", params={"app_id": "app_demo"})
        assert devices_response.status_code == 200
        item = devices_response.json()["data"]["items"][0]
        assert item["uuid"] == "device-point-1"
        assert item["fingerprint"] == "fingerprint-point-1"
        assert item["username"] == "point-device"
        assert item["binding_relation"] == "用户授权"
        assert item["last_ip"] == "10.0.0.8"
        assert item["ip_count"] == 1
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_kamis_show_source_point_lot_remaining_instead_of_user_balance():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="source-points", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add_all(
            [
                Kami(
                    app_id="app_demo",
                    kami_code="POINT100",
                    kami_type=KamiType.points,
                    status=KamiStatus.unused,
                    points_amount=100,
                    authorization_owner=AuthorizationOwnerMode.user,
                    user_bind_mode=UserBindMode.required,
                ),
                Kami(
                    app_id="app_demo",
                    kami_code="POINT50",
                    kami_type=KamiType.points,
                    status=KamiStatus.unused,
                    points_amount=50,
                    authorization_owner=AuthorizationOwnerMode.user,
                    user_bind_mode=UserBindMode.required,
                ),
            ]
        )
        session.commit()

        redeem_points_kami(session, user, "POINT100")
        redeem_points_kami(session, user, "POINT50")
        consume_result = consume_points(
            session=session,
            user_id=user.id,
            app_id="app_demo",
            amount=20,
            biz_id="source-lot-consume",
        )
        assert consume_result["balance_after"] == 130

    try:
        response = client.get(
            "/api/v1/admin/kamis",
            params={"app_id": "app_demo", "kami_type": "points", "page_size": 10},
        )
        assert response.status_code == 200
        items = {item["kami_code"]: item for item in response.json()["data"]["items"]}

        point100 = items["POINT100"]
        assert point100["points_amount"] == 100
        assert point100["points_remaining"] == 80
        assert point100["points_redeemed"] == 20
        assert point100["point_balance"] == 130
        assert point100["device_bind_count"] == 0
        assert point100["redeemed_at"] is not None

        point50 = items["POINT50"]
        assert point50["points_amount"] == 50
        assert point50["points_remaining"] == 50
        assert point50["points_redeemed"] == 0
        assert point50["point_balance"] == 130
        assert point50["device_bind_count"] == 0
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_end_user_kamis_includes_manual_grants_without_source_kami():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="manual-grant", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        grant_points(session, account, 100)
        consume_points(
            session=session,
            user_id=user.id,
            app_id="app_demo",
            amount=30,
            biz_id="manual-grant-consume",
        )
        user_id = user.id

    try:
        response = client.get(
            f"/api/v1/admin/end-users/{user_id}/kamis",
            params={"app_id": "app_demo"},
        )
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        item = items[0]
        assert item["kami_code"] == "-"
        assert item["kami_type"] == "points"
        assert item["status"] == "active"
        assert item["binding_relation"] == "用户授权"
        assert item["points_amount"] == 100
        assert item["point_source_remaining"] == 70
        assert item["authorization_lots"][0]["amount_total"] == 100
        assert item["authorization_lots"][0]["amount_remaining"] == 70
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_end_user_kamis_includes_legacy_owner_key_accounts_without_user_id():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="legacy-owner", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        account = AuthorizationAccount(
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user,
            owner_key=f"user:{user.id}",
            username=user.username,
            points_balance=25,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        session.add(
            AuthorizationLot(
                account_id=account.id,
                benefit_type=AuthorizationBenefitType.points,
                amount_total=25,
                amount_remaining=25,
            )
        )
        session.commit()
        user_id = user.id

    try:
        response = client.get(
            f"/api/v1/admin/end-users/{user_id}/kamis",
            params={"app_id": "app_demo"},
        )
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        item = items[0]
        assert item["kami_code"] == "-"
        assert item["batch_no"] == "后台授权"
        assert item["points_amount"] == 25
        assert item["point_source_remaining"] == 25
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_delete_end_users_hard_deletes_related_records():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="delete-me", password_hash="hash")
        other_user = EndUser(app_id="app_demo", username="keep-me", password_hash="hash")
        session.add_all([user, other_user])
        session.commit()
        session.refresh(user)
        session.refresh(other_user)

        account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        grant_points(session, account, 100, source_kami_code="DELETEPOINT")
        grant_times(session, account, 5, source_kami_code="DELETETIMES")
        session.refresh(account)
        account_id = account.id

        session.add_all(
            [
                UserPointAccount(
                    user_id=user.id,
                    balance=40,
                    total_recharged=100,
                    total_consumed=60,
                ),
                UserPointLot(
                    user_id=user.id,
                    source_transaction_id="legacy-source",
                    app_id="app_demo",
                    kami_code="DELETEPOINT",
                    points_total=100,
                    points_remaining=40,
                ),
                PointTransaction(
                    transaction_id="legacy-tx",
                    user_id=user.id,
                    app_id="app_demo",
                    kami_code="DELETEPOINT",
                    transaction_type=PointTransactionType.recharge,
                    amount=100,
                    balance_before=0,
                    balance_after=100,
                    biz_id="legacy-recharge",
                ),
                Kami(
                    app_id="app_demo",
                    kami_code="DELETEPOINT",
                    kami_type=KamiType.points,
                    status=KamiStatus.active,
                    points_amount=100,
                    redeemed_by_user_id=user.id,
                    authorization_owner=AuthorizationOwnerMode.user,
                ),
                Kami(
                    app_id="app_demo",
                    kami_code="KEEPPOINT",
                    kami_type=KamiType.points,
                    status=KamiStatus.active,
                    points_amount=50,
                    redeemed_by_user_id=other_user.id,
                    authorization_owner=AuthorizationOwnerMode.user,
                ),
                KamiDeviceBinding(
                    app_id="app_demo",
                    kami_code="DELETEPOINT",
                    device_uuid="device-delete",
                    fingerprint="fingerprint-delete",
                    bind_ip="203.0.113.8",
                ),
                Device(
                    app_id="app_demo",
                    uuid="device-delete",
                    fingerprint="fingerprint-delete",
                    last_ip="203.0.113.8",
                ),
                EventLog(
                    app_id="app_demo",
                    kami_code="DELETEPOINT",
                    event_type="consume",
                    ip_address="203.0.113.8",
                    device_uuid="device-delete",
                    payload='{"user_id": %d, "username": "%s", "fingerprint": "fingerprint-delete"}'
                    % (user.id, user.username),
                    status=1,
                ),
                EventLog(
                    app_id="app_demo",
                    event_type="points_consume",
                    ip_address="203.0.113.9",
                    device_uuid="device-delete",
                    payload='{"user_id": %d, "username": "%s"}' % (user.id, user.username),
                    status=1,
                ),
                EventLog(
                    app_id="app_demo",
                    kami_code="KEEPPOINT",
                    event_type="verify",
                    status=1,
                ),
            ]
        )
        session.commit()
        user_id = user.id
        other_user_id = other_user.id
        username = user.username

    try:
        response = client.post("/api/v1/admin/end-users/delete", json={"user_ids": [user_id]})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted_users"] == 1
        assert data["deleted_kamis"] == 1

        with Session(engine) as session:
            assert session.get(EndUser, user_id) is None
            assert session.get(EndUser, other_user_id) is not None
            assert session.exec(
                select(AuthorizationAccount).where(AuthorizationAccount.user_id == user_id)
            ).all() == []
            assert session.exec(
                select(AuthorizationLot).where(AuthorizationLot.account_id == account_id)
            ).all() == []
            assert session.exec(
                select(AuthorizationTransaction).where(AuthorizationTransaction.account_id == account_id)
            ).all() == []
            assert session.exec(select(UserPointAccount).where(UserPointAccount.user_id == user_id)).all() == []
            assert session.exec(select(UserPointLot).where(UserPointLot.user_id == user_id)).all() == []
            assert session.exec(select(PointTransaction).where(PointTransaction.user_id == user_id)).all() == []
            assert session.exec(select(Kami).where(Kami.kami_code == "DELETEPOINT")).first() is None
            assert session.exec(select(Kami).where(Kami.kami_code == "KEEPPOINT")).first() is not None
            assert session.exec(
                select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == "DELETEPOINT")
            ).all() == []
            assert session.exec(
                select(EventLog).where(EventLog.kami_code == "DELETEPOINT")
            ).all() == []
            assert session.exec(
                select(Device).where(Device.uuid == "device-delete")
            ).all() == []
            remaining_payloads = [
                log.payload or ""
                for log in session.exec(select(EventLog)).all()
            ]
            assert not any(username in payload for payload in remaining_payloads)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_delete_end_users_removes_legacy_owner_key_accounts_without_user_id():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="delete-legacy", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        account = AuthorizationAccount(
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user,
            owner_key=f"username:{user.username}",
            username=user.username,
            points_balance=70,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        account_id = account.id

        session.add_all(
            [
                AuthorizationLot(
                    account_id=account.id,
                    benefit_type=AuthorizationBenefitType.points,
                    amount_total=70,
                    amount_remaining=70,
                ),
                AuthorizationTransaction(
                    transaction_id="legacy-owner-tx",
                    account_id=account.id,
                    transaction_type=AuthorizationTransactionType.grant,
                    benefit_type=AuthorizationBenefitType.points,
                    amount=70,
                    balance_after=70,
                ),
                Kami(
                    app_id="app_demo",
                    kami_code="USERLEGACY",
                    kami_type=KamiType.points,
                    status=KamiStatus.active,
                    points_amount=70,
                    bind_uuid=f"user:{user.id}",
                    authorization_owner=AuthorizationOwnerMode.user,
                ),
                EventLog(
                    app_id="app_demo",
                    kami_code="USERLEGACY",
                    event_type="verify",
                    payload='{"username": "delete-legacy"}',
                    status=1,
                ),
            ]
        )
        session.commit()
        user_id = user.id

    try:
        response = client.post("/api/v1/admin/end-users/delete", json={"user_ids": [user_id]})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted_users"] == 1
        assert data["deleted_authorization_accounts"] == 1
        assert data["deleted_kamis"] == 1

        with Session(engine) as session:
            assert session.get(EndUser, user_id) is None
            assert session.get(AuthorizationAccount, account_id) is None
            assert session.exec(
                select(AuthorizationLot).where(AuthorizationLot.account_id == account_id)
            ).all() == []
            assert session.exec(
                select(AuthorizationTransaction).where(AuthorizationTransaction.account_id == account_id)
            ).all() == []
            assert session.exec(select(Kami).where(Kami.kami_code == "USERLEGACY")).all() == []
            assert session.exec(select(EventLog).where(EventLog.kami_code == "USERLEGACY")).all() == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_delete_end_users_respects_foreign_key_delete_order():
    engine = make_engine_with_foreign_keys()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="delete-fk", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)

        account = AuthorizationAccount(
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user,
            owner_key=f"username:{user.username}",
            username=user.username,
            points_balance=70,
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        account_id = account.id

        session.add_all(
            [
                AuthorizationLot(
                    account_id=account.id,
                    benefit_type=AuthorizationBenefitType.points,
                    amount_total=70,
                    amount_remaining=70,
                ),
                AuthorizationTransaction(
                    transaction_id="fk-order-tx",
                    account_id=account.id,
                    transaction_type=AuthorizationTransactionType.grant,
                    benefit_type=AuthorizationBenefitType.points,
                    amount=70,
                    balance_after=70,
                ),
                Kami(
                    app_id="app_demo",
                    kami_code="FKORDER",
                    kami_type=KamiType.points,
                    status=KamiStatus.active,
                    points_amount=70,
                    redeemed_by_user_id=user.id,
                    authorization_owner=AuthorizationOwnerMode.user,
                ),
                KamiDeviceBinding(
                    app_id="app_demo",
                    kami_code="FKORDER",
                    device_uuid="fk-device",
                    fingerprint="fk-fingerprint",
                ),
                EventLog(
                    app_id="app_demo",
                    kami_code="FKORDER",
                    event_type="verify",
                    payload='{"username": "delete-fk"}',
                    status=1,
                ),
                Device(
                    app_id="app_demo",
                    uuid="fk-device",
                    fingerprint="fk-fingerprint",
                ),
            ]
        )
        session.commit()
        user_id = user.id

    try:
        response = client.post("/api/v1/admin/end-users/delete", json={"user_ids": [user_id]})
        assert response.status_code == 200

        with Session(engine) as session:
            assert session.get(EndUser, user_id) is None
            assert session.get(AuthorizationAccount, account_id) is None
            assert session.exec(
                select(AuthorizationLot).where(AuthorizationLot.account_id == account_id)
            ).all() == []
            assert session.exec(
                select(AuthorizationTransaction).where(AuthorizationTransaction.account_id == account_id)
            ).all() == []
            assert session.exec(select(Kami).where(Kami.kami_code == "FKORDER")).all() == []
            assert session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == "FKORDER")).all() == []
            assert session.exec(select(EventLog).where(EventLog.kami_code == "FKORDER")).all() == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_dashboard_api_call_count_excludes_admin_operations():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add_all(
            [
                EventLog(app_id="app_demo", event_type="verify", status=1),
                EventLog(app_id="app_demo", event_type="points_consume", status=1),
                EventLog(app_id="app_demo", event_type="consume", status=0),
                EventLog(app_id=None, event_type="admin_login", status=1),
                EventLog(app_id="app_demo", event_type="admin_update_app", status=1),
            ]
        )
        session.commit()

    try:
        response = client.get("/api/v1/admin/dashboard")
        assert response.status_code == 200
        integration = response.json()["data"]["integration_health"]
        assert integration["api_calls_today"] == 3
        assert "verify_success_rate" not in integration
        assert "abnormal_calls_today" not in integration
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_update_app_supports_renaming_without_changing_id():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Old Name"))
        session.commit()

    try:
        response = client.put("/api/v1/admin/apps/app_demo", params={"name": "New Name"})
        assert response.status_code == 200
        assert response.json()["data"]["name"] == "New Name"

        with Session(engine) as session:
            app = session.exec(select(App).where(App.app_id == "app_demo")).first()
            assert app is not None
            assert app.app_id == "app_demo"
            assert app.name == "New Name"
            assert app.app_secret == "secret-app_demo"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_sdk_verify_no_limit_device_authorization_links_card_device_and_admin_views():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_sdk.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    fastapi_app.dependency_overrides[routes_sdk.get_redis] = lambda: FakeRedis()
    fastapi_app.dependency_overrides[routes_sdk.get_decrypted_data] = lambda: {
        "kami": "FREEDEVICE",
        "uuid": "device-free-1",
        "fingerprint": "fingerprint-free-1",
        "_app_info": {"app_id": "app_demo", "app_secret": "secret-app_demo"},
    }
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add(
            ApiInterface(
                name="SDK Verify",
                interface_key="sdk.verify",
                path="/api/v1/sdk/verify",
                is_builtin=True,
                status=1,
            )
        )
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="FREEDEVICE",
                kami_type=KamiType.lifetime,
                status=KamiStatus.unused,
                authorization_owner=AuthorizationOwnerMode.device,
                machine_bind_mode=MachineBindMode.no_limit,
                max_bind_devices=0,
            )
        )
        session.commit()

    try:
        response = client.post("/api/v1/sdk/verify", json={})
        assert response.status_code == 200

        with Session(engine) as session:
            kami = session.exec(select(Kami).where(Kami.kami_code == "FREEDEVICE")).one()
            binding = session.exec(
                select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == "FREEDEVICE")
            ).one()
            device = session.exec(select(Device).where(Device.uuid == "device-free-1")).one()
            assert kami.status == KamiStatus.active
            assert kami.activate_time is not None
            assert kami.redeemed_at is not None
            assert kami.bind_uuid == "device-free-1"
            assert binding.device_uuid == "device-free-1"
            assert binding.fingerprint == "fingerprint-free-1"
            assert device.fingerprint == "fingerprint-free-1"

        kamis_response = client.get("/api/v1/admin/kamis", params={"app_id": "app_demo"})
        assert kamis_response.status_code == 200
        kami_item = kamis_response.json()["data"]["items"][0]
        assert kami_item["kami_code"] == "FREEDEVICE"
        assert kami_item["device_bind_count"] == 1
        assert kami_item["bound_device_uuids"] == ["device-free-1"]
        assert kami_item["redeemed_at"] is not None

        devices_response = client.get("/api/v1/admin/devices", params={"app_id": "app_demo"})
        assert devices_response.status_code == 200
        device_item = devices_response.json()["data"]["items"][0]
        assert device_item["uuid"] == "device-free-1"
        assert device_item["kami_code"] == "FREEDEVICE"
        assert device_item["kami_codes"] == ["FREEDEVICE"]
        assert device_item["binding_relation"] == "设备授权"
        assert device_item["machine_bind_mode"] == "no_limit"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_kami_views_infer_legacy_device_binding_and_redeem_time_from_kami_row():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    activated_at = get_now_naive()

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="LEGACYDEVICE",
                kami_type=KamiType.month,
                status=KamiStatus.active,
                bind_uuid="legacy-device-1",
                activate_time=activated_at,
                redeemed_at=None,
                bind_ip="10.0.0.8",
                authorization_owner=AuthorizationOwnerMode.device,
                machine_bind_mode=MachineBindMode.one_card_one_device,
                max_bind_devices=1,
            )
        )
        session.add(
            Device(
                app_id="app_demo",
                uuid="legacy-device-1",
                fingerprint="legacy-fingerprint-1",
                last_ip="10.0.0.8",
            )
        )
        session.commit()

    try:
        kamis_response = client.get("/api/v1/admin/kamis", params={"app_id": "app_demo"})
        assert kamis_response.status_code == 200
        kami_item = kamis_response.json()["data"]["items"][0]
        assert kami_item["kami_code"] == "LEGACYDEVICE"
        assert kami_item["device_bind_count"] == 1
        assert kami_item["bound_device_uuids"] == ["legacy-device-1"]
        assert kami_item["redeemed_at"] is not None

        devices_response = client.get("/api/v1/admin/devices", params={"app_id": "app_demo"})
        assert devices_response.status_code == 200
        device_item = devices_response.json()["data"]["items"][0]
        assert device_item["uuid"] == "legacy-device-1"
        assert device_item["kami_code"] == "LEGACYDEVICE"
        assert device_item["kami_codes"] == ["LEGACYDEVICE"]
        assert device_item["machine_bind_mode"] == "one_card_one_device"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_devices_infer_historical_device_authorization_without_device_row():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    activated_at = get_now_naive()

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="HISTORYDEVICE",
                kami_type=KamiType.month,
                status=KamiStatus.active,
                bind_uuid="historical-device-1",
                bind_ip="10.0.0.9",
                activate_time=activated_at,
                redeemed_at=None,
                authorization_owner=AuthorizationOwnerMode.device,
                machine_bind_mode=MachineBindMode.one_card_one_device,
                max_bind_devices=1,
            )
        )
        session.add(
            EventLog(
                app_id="app_demo",
                kami_code="HISTORYDEVICE",
                event_type="activate",
                ip_address="10.0.0.9",
                device_uuid="historical-device-1",
                status=1,
                payload='{"fingerprint": "historical-fingerprint-1"}',
            )
        )
        session.commit()

    try:
        response = client.get("/api/v1/admin/devices", params={"app_id": "app_demo"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        item = data["items"][0]
        assert item["uuid"] == "historical-device-1"
        assert item["fingerprint"] == "historical-fingerprint-1"
        assert item["last_ip"] == "10.0.0.9"
        assert item["kami_code"] == "HISTORYDEVICE"
        assert item["kami_codes"] == ["HISTORYDEVICE"]
        assert item["binding_relation"] == "设备授权"
        assert item["machine_bind_mode"] == "one_card_one_device"
        assert item["redeemed_at"] is not None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_devices_can_search_device_card_across_all_apps():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    activated_at = get_now_naive()

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_alpha", "Alpha App"))
        session.add(make_app("app_beta", "Beta App"))
        session.add(
            Kami(
                app_id="app_beta",
                kami_code="TARGETDEVICE",
                kami_type=KamiType.lifetime,
                status=KamiStatus.active,
                bind_uuid="beta-device-1",
                activate_time=activated_at,
                redeemed_at=activated_at,
                authorization_owner=AuthorizationOwnerMode.device,
                machine_bind_mode=MachineBindMode.no_limit,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_beta",
                kami_code="TARGETDEVICE",
                device_uuid="beta-device-1",
                fingerprint="beta-fingerprint-1",
                bind_ip="10.0.1.5",
            )
        )
        session.add(
            Device(
                app_id="app_beta",
                uuid="beta-device-1",
                fingerprint="beta-fingerprint-1",
                last_ip="10.0.1.5",
            )
        )
        session.add(
            Device(
                app_id="app_alpha",
                uuid="alpha-device-1",
                fingerprint="alpha-fingerprint-1",
                last_ip="10.0.1.8",
            )
        )
        session.commit()

    try:
        all_response = client.get("/api/v1/admin/devices")
        assert all_response.status_code == 200
        all_items = all_response.json()["data"]["items"]
        assert {item["app_id"] for item in all_items} == {"app_alpha", "app_beta"}

        search_response = client.get("/api/v1/admin/devices", params={"keyword": "TARGETDEVICE"})
        assert search_response.status_code == 200
        data = search_response.json()["data"]
        assert data["total"] == 1
        item = data["items"][0]
        assert item["app_id"] == "app_beta"
        assert item["app_name"] == "Beta App"
        assert item["uuid"] == "beta-device-1"
        assert item["kami_code"] == "TARGETDEVICE"
        assert item["kami_codes"] == ["TARGETDEVICE"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_kami_spec_detail_includes_device_link_and_redeem_time_fallback():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    activated_at = get_now_naive()

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        spec = KamiSpec(
            app_id="app_demo",
            spec_key="monthly-device",
            spec_name="Monthly Device",
            kami_type=KamiType.month,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            authorization_owner=AuthorizationOwnerMode.device,
            user_bind_mode=UserBindMode.none,
        )
        session.add(spec)
        session.commit()
        session.refresh(spec)
        session.add(
            Kami(
                app_id="app_demo",
                spec_id=spec.id,
                kami_code="SPECDEVICE",
                kami_type=KamiType.month,
                status=KamiStatus.active,
                bind_uuid="spec-device-1",
                activate_time=activated_at,
                redeemed_at=None,
                authorization_owner=AuthorizationOwnerMode.device,
                machine_bind_mode=MachineBindMode.one_card_one_device,
                max_bind_devices=1,
            )
        )
        session.commit()
        spec_id = spec.id

    try:
        response = client.get(f"/api/v1/admin/kami-specs/{spec_id}/kamis")
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["kami_code"] == "SPECDEVICE"
        assert item["bind_uuid"] == "spec-device-1"
        assert item["device_bind_count"] == 1
        assert item["bound_device_uuids"] == ["spec-device-1"]
        assert item["redeemed_at"] is not None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_end_user_kamis_preserves_deleted_source_kami_reference():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="frank", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        account = get_or_create_authorization_account(
            session=session,
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user.id,
            username=user.username,
        )
        grant_points(session, account, 88, source_kami_code="DELETEDSOURCE")
        user_id = user.id

    try:
        response = client.get(
            f"/api/v1/admin/end-users/{user_id}/kamis",
            params={"app_id": "app_demo"},
        )
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        item = items[0]
        assert item["kami_code"] == "DELETEDSOURCE"
        assert item["batch_no"] == "来源卡密已删除"
        assert item["source_kami_deleted"] is True
        assert item["binding_relation"] == "用户授权"
        assert item["points_amount"] == 88
        assert item["authorization_lots"][0]["source_kami_code"] == "DELETEDSOURCE"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_authorization_grant_with_source_kami_links_card_to_user():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="erin", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="POINTUSER",
                kami_type=KamiType.points,
                status=KamiStatus.unused,
                points_amount=70,
                authorization_owner=AuthorizationOwnerMode.user,
                user_bind_mode=UserBindMode.required,
                machine_bind_mode=MachineBindMode.no_limit,
                max_bind_devices=0,
            )
        )
        session.commit()
        user_id = user.id

    try:
        response = client.post(
            "/api/v1/admin/authorizations/grant",
            json={
                "app_id": "app_demo",
                "user_id": user_id,
                "benefit_type": "points",
                "amount": 70,
                "source_kami_code": "POINTUSER",
            },
        )
        assert response.status_code == 200

        with Session(engine) as session:
            kami = session.exec(select(Kami).where(Kami.kami_code == "POINTUSER")).one()
            assert kami.status == KamiStatus.active
            assert kami.redeemed_by_user_id == user_id
            assert kami.redeemed_at is not None
            assert kami.activate_time is not None
            assert kami.bind_uuid == f"user:{user_id}"

        kamis_response = client.get("/api/v1/admin/kamis", params={"app_id": "app_demo"})
        assert kamis_response.status_code == 200
        item = kamis_response.json()["data"]["items"][0]
        assert item["kami_code"] == "POINTUSER"
        assert item["redeemed_user"]["username"] == "erin"
        assert item["binding_relation"] == "用户授权"
        assert item["bound_device_uuids"] == []
        assert item["redeemed_at"] is not None

        detail_response = client.get(
            f"/api/v1/admin/end-users/{user_id}/kamis",
            params={"app_id": "app_demo"},
        )
        assert detail_response.status_code == 200
        detail_items = detail_response.json()["data"]["items"]
        assert detail_items[0]["kami_code"] == "POINTUSER"
        assert detail_items[0]["authorization_lots"][0]["amount_total"] == 70
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_devices_include_user_binding_strategy_ip_count_and_inferred_risk():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app("app_demo", "Demo"))
        user = EndUser(app_id="app_demo", username="carol", password_hash="hash")
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="TIMESUSER",
                kami_type=KamiType.times,
                status=KamiStatus.active,
                bind_uuid="device-1",
                times_total=100,
                times_remaining=100,
                redeemed_by_user_id=user.id,
                authorization_owner=AuthorizationOwnerMode.user,
                user_bind_mode=UserBindMode.required,
                machine_bind_mode=MachineBindMode.one_card_multi_device,
                max_bind_devices=3,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_demo",
                kami_code="TIMESUSER",
                device_uuid="device-1",
                fingerprint="fingerprint-1",
                bind_ip="10.0.0.3",
            )
        )
        session.add(Device(app_id="app_demo", uuid="device-1", fingerprint="fingerprint-1", last_ip="10.0.0.3"))
        for ip in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
            session.add(
                EventLog(
                    app_id="app_demo",
                    kami_code="TIMESUSER",
                    event_type="verify",
                    ip_address=ip,
                    device_uuid="device-1",
                    status=1,
                )
            )
        session.commit()

    try:
        response = client.get("/api/v1/admin/devices", params={"app_id": "app_demo"})
        assert response.status_code == 200
        item = response.json()["data"]["items"][0]
        assert item["uuid"] == "device-1"
        assert item["fingerprint"] == "fingerprint-1"
        assert item["username"] == "carol"
        assert item["binding_relation"] == "用户授权"
        assert item["machine_bind_mode"] == "one_card_multi_device"
        assert item["machine_bind_mode_text"] == "一卡多机"
        assert item["ip_count"] == 3
        assert item["risk_level"] == 1
        assert item["risk_level_text"] == "警告"
    finally:
        fastapi_app.dependency_overrides.clear()
