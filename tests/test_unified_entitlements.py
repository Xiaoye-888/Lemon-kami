from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin
from authorization_service import grant_time, grant_times, get_or_create_authorization_account
from main import app as fastapi_app
from models import (
    App,
    AuthorizationAccount,
    AuthorizationOwnerMode,
    AuthorizationOwnerType,
    Device,
    EndUser,
    EventLog,
    Kami,
    KamiDeviceBinding,
    KamiStatus,
    KamiType,
    MachineBindMode,
    PointTransaction,
    UserBindMode,
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
