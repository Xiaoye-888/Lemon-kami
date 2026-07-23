from sqlalchemy import event, inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import routes_admin
from models import (
    ApiInterface,
    App,
    AppInterfaceConfig,
    AuthorizationAccount,
    AuthorizationBenefitType,
    AuthorizationLot,
    AuthorizationOwnerMode,
    AuthorizationOwnerType,
    AuthorizationTransaction,
    AuthorizationTransactionType,
    EndUser,
    EventLog,
    Kami,
    KamiBatch,
    KamiDeviceBinding,
    KamiSpec,
    KamiStatus,
    KamiType,
    MachineBindMode,
    UserAppAuthorization,
    UserBindMode,
)
from point_service import PointServiceError, redeem_points_kami


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


def make_app(app_id="app_demo"):
    return App(
        app_id=app_id,
        name="Demo",
        app_secret="secret",
        rsa_public_key="public",
        rsa_private_key="private",
    )


def test_kami_spec_schema_exists():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "kami_specs" in inspector.get_table_names()

    batch_columns = {column["name"] for column in inspector.get_columns("kami_batches")}
    kami_columns = {column["name"] for column in inspector.get_columns("kamis")}
    spec_columns = {column["name"] for column in inspector.get_columns("kami_specs")}

    assert "spec_id" in batch_columns
    assert "spec_id" in kami_columns
    assert "code_valid_days" in batch_columns
    assert "code_valid_days" in kami_columns
    assert "code_expires_at" in kami_columns
    assert {
        "app_id",
        "spec_key",
        "spec_name",
        "spec_group",
        "kami_type",
        "points_amount",
        "points_valid_days",
        "times_total",
        "time_value",
        "time_unit",
        "machine_bind_mode",
        "max_bind_devices",
        "authorization_owner",
        "user_bind_mode",
        "status",
        "sort_order",
    }.issubset(spec_columns)


def test_points_specs_group_same_custom_value_with_same_policy():
    from kami_spec_service import build_spec_key, build_spec_name, infer_spec_group

    key_a = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )
    key_b = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )

    assert key_a == key_b
    assert build_spec_name(KamiType.points, 150, None, None, None, None) == "150积分"
    assert infer_spec_group(KamiType.points, 150, None, None, None, None) == "custom"


def test_points_specs_do_not_merge_different_policy():
    from kami_spec_service import build_spec_key

    one_device_key = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )
    no_limit_key = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.no_limit,
        max_bind_devices=0,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )

    assert one_device_key != no_limit_key


def test_common_values_are_classified_as_common():
    from kami_spec_service import infer_spec_group

    assert infer_spec_group(KamiType.points, 100, None, None, None, None) == "common"
    assert infer_spec_group(KamiType.points, 68, None, None, None, None) == "custom"
    assert infer_spec_group(KamiType.times, None, None, 10, None, None) == "common"
    assert infer_spec_group(KamiType.times, None, None, 143, None, None) == "custom"
    assert infer_spec_group(KamiType.month, None, None, None, 1, "month") == "common"


def test_backfill_groups_existing_batches_by_value_and_policy():
    from kami_spec_service import backfill_specs_for_session

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(make_app())
        session.commit()

        batch_a = KamiBatch(
            app_id="app_demo",
            batch_no="p150-a",
            kami_type=KamiType.points,
            points_amount=150,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        batch_b = KamiBatch(
            app_id="app_demo",
            batch_no="p150-b",
            kami_type=KamiType.points,
            points_amount=150,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        session.add(batch_a)
        session.add(batch_b)
        session.commit()

        backfill_specs_for_session(session)
        session.refresh(batch_a)
        session.refresh(batch_b)

        assert batch_a.spec_id is not None
        assert batch_a.spec_id == batch_b.spec_id


def test_backfill_attaches_cards_to_existing_batch_spec():
    from kami_spec_service import backfill_specs_for_session

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(make_app())
        session.commit()
        batch = KamiBatch(
            app_id="app_demo",
            batch_no="p68",
            kami_type=KamiType.points,
            points_amount=68,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        kami = Kami(
            app_id="app_demo",
            kami_code="ABC123",
            kami_type=KamiType.points,
            status=KamiStatus.unused,
            points_amount=68,
            batch_no="p68",
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        session.add(batch)
        session.add(kami)
        session.commit()

        backfill_specs_for_session(session)
        session.refresh(batch)
        session.refresh(kami)
        specs = session.exec(select(KamiSpec)).all()

        assert len(specs) == 1
        assert specs[0].spec_name == "68积分"
        assert batch.spec_id == specs[0].id
        assert kami.spec_id == specs[0].id


def override_admin_user():
    return {"sub": "admin", "is_admin": True}


def test_admin_spec_list_and_generate_flow():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()

    try:
        create_response = client.post(
            "/api/v1/admin/kami-specs",
            json={
                "app_id": "app_demo",
                "kami_type": "points",
                "points_amount": 150,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "spec_group": "custom",
                "status": 1,
            },
        )
        assert create_response.status_code == 200
        spec_id = create_response.json()["data"]["id"]

        generate_response = client.post(
            f"/api/v1/admin/kami-specs/{spec_id}/generate",
            json={"count": 2, "batch_no": "p150-test", "code_length": 8, "charset": "upper_numeric"},
        )
        assert generate_response.status_code == 200
        assert generate_response.json()["data"]["count"] == 2

        list_response = client.get(
            "/api/v1/admin/kami-specs",
            params={"app_id": "app_demo", "kami_type": "points"},
        )
        assert list_response.status_code == 200
        items = list_response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["spec_name"] == "150积分"
        assert items[0]["spec_group"] == "custom"
        assert items[0]["batch_count"] == 1
        assert items[0]["total_count"] == 2
        assert items[0]["unused_count"] == 2
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_spec_batches_include_card_counts():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()

    try:
        create_response = client.post(
            "/api/v1/admin/kami-specs",
            json={
                "app_id": "app_demo",
                "kami_type": "points",
                "points_amount": 100,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "spec_group": "common",
                "status": 1,
            },
        )
        assert create_response.status_code == 200
        spec_id = create_response.json()["data"]["id"]

        generate_response = client.post(
            f"/api/v1/admin/kami-specs/{spec_id}/generate",
            json={"count": 3, "batch_no": "p100-a", "code_length": 8, "charset": "upper_numeric"},
        )
        assert generate_response.status_code == 200

        batches_response = client.get(f"/api/v1/admin/kami-specs/{spec_id}/batches")
        assert batches_response.status_code == 200
        rows = batches_response.json()["data"]
        assert len(rows) == 1
        assert rows[0]["batch_no"] == "p100-a"
        assert rows[0]["total_count"] == 3
        assert rows[0]["unused_count"] == 3
        assert rows[0]["active_count"] == 0
        assert rows[0]["frozen_count"] == 0
    finally:
        fastapi_app.dependency_overrides.clear()


def test_spec_generate_applies_code_valid_days_to_batch_and_cards():
    from datetime import timedelta

    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()

    try:
        create_response = client.post(
            "/api/v1/admin/kami-specs",
            json={
                "app_id": "app_demo",
                "kami_type": "times",
                "times_total": 10,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "spec_group": "common",
                "status": 1,
            },
        )
        assert create_response.status_code == 200
        spec_id = create_response.json()["data"]["id"]

        generate_response = client.post(
            f"/api/v1/admin/kami-specs/{spec_id}/generate",
            json={
                "count": 2,
                "batch_no": "times-valid-7",
                "code_length": 8,
                "charset": "upper_numeric",
                "code_valid_days": 7,
            },
        )
        assert generate_response.status_code == 200
        assert generate_response.json()["data"]["code_valid_days"] == 7

        with Session(engine) as session:
            batch = session.exec(select(KamiBatch).where(KamiBatch.batch_no == "times-valid-7")).first()
            kamis = session.exec(select(Kami).where(Kami.batch_no == "times-valid-7")).all()
            assert batch is not None
            assert batch.code_valid_days == 7
            assert len(kamis) == 2
            for kami in kamis:
                assert kami.code_valid_days == 7
                assert kami.code_expires_at is not None
                assert kami.created_at is not None
                assert abs((kami.code_expires_at - (kami.created_at + timedelta(days=7))).total_seconds()) < 2

        batches_response = client.get(f"/api/v1/admin/kami-specs/{spec_id}/batches")
        assert batches_response.status_code == 200
        row = batches_response.json()["data"][0]
        assert row["code_valid_days"] == 7
        assert row["code_validity_text"] == "生成后 7 天"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_redeem_points_rejects_expired_unused_kami():
    from datetime import timedelta

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(make_app())
        user = EndUser(app_id="app_demo", username="alice", password_hash="hash")
        session.add(user)
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="EXPIREDPOINTS",
                kami_type=KamiType.points,
                status=KamiStatus.unused,
                points_amount=100,
                code_valid_days=1,
                code_expires_at=routes_admin.get_now().replace(tzinfo=None) - timedelta(seconds=1),
            )
        )
        session.commit()
        session.refresh(user)

        try:
            redeem_points_kami(session, user, "EXPIREDPOINTS")
        except PointServiceError as error:
            assert error.code == "kami_expired"
            assert error.message == "卡密已过期"
        else:
            raise AssertionError("expired kami redeem should fail")

        kami = session.exec(select(Kami).where(Kami.kami_code == "EXPIREDPOINTS")).first()
        assert kami.status == KamiStatus.unused
        assert kami.redeemed_by_user_id is None


def test_delete_empty_spec_and_reject_non_empty_spec():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()

    try:
        empty_response = client.post(
            "/api/v1/admin/kami-specs",
            json={
                "app_id": "app_demo",
                "kami_type": "times",
                "times_total": 10,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "spec_group": "common",
                "status": 1,
            },
        )
        assert empty_response.status_code == 200
        empty_spec_id = empty_response.json()["data"]["id"]
        delete_empty = client.delete(f"/api/v1/admin/kami-specs/{empty_spec_id}")
        assert delete_empty.status_code == 200

        non_empty_response = client.post(
            "/api/v1/admin/kami-specs",
            json={
                "app_id": "app_demo",
                "kami_type": "points",
                "points_amount": 143,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "spec_group": "custom",
                "status": 1,
            },
        )
        assert non_empty_response.status_code == 200
        non_empty_spec_id = non_empty_response.json()["data"]["id"]
        generate_response = client.post(
            f"/api/v1/admin/kami-specs/{non_empty_spec_id}/generate",
            json={"count": 1, "batch_no": "p143-a", "code_length": 8, "charset": "upper_numeric"},
        )
        assert generate_response.status_code == 200

        delete_non_empty = client.delete(f"/api/v1/admin/kami-specs/{non_empty_spec_id}")
        assert delete_non_empty.status_code == 400
        assert "规格下仍有批次或卡密" in delete_non_empty.json()["detail"]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_delete_kamis_allows_active_card_and_clears_direct_relations():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="ACTIVE001",
                kami_type=KamiType.times,
                status=KamiStatus.active,
                bind_uuid="device-1",
                batch_no="times-a",
                times_total=10,
                times_remaining=7,
                machine_bind_mode=MachineBindMode.one_card_one_device,
                max_bind_devices=1,
                authorization_owner=AuthorizationOwnerMode.auto,
                user_bind_mode=UserBindMode.auto,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_demo",
                kami_code="ACTIVE001",
                device_uuid="device-1",
                fingerprint="fingerprint-1",
            )
        )
        session.add(
            EventLog(
                app_id="app_demo",
                kami_code="ACTIVE001",
                event_type="activate",
                status=1,
                message="activated",
            )
        )
        session.commit()

    try:
        response = client.post(
            "/api/v1/admin/kamis/delete",
            json={"app_id": "app_demo", "kami_codes": ["ACTIVE001"]},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["deleted_count"] == 1
        assert data["skipped_count"] == 0

        with Session(engine) as session:
            assert session.exec(select(Kami).where(Kami.kami_code == "ACTIVE001")).first() is None
            bindings = session.exec(
                select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == "ACTIVE001")
            ).all()
            assert bindings == []
            log = session.exec(select(EventLog).where(EventLog.event_type == "activate")).first()
            assert log is not None
            assert log.kami_code is None
    finally:
        fastapi_app.dependency_overrides.clear()


def test_delete_app_cleans_app_scoped_child_rows_before_parent_rows():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine_with_foreign_keys()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()
        interface = ApiInterface(
            name="Verify",
            interface_key="sdk.verify",
            method="POST",
            path="/api/v1/sdk/verify",
        )
        spec = KamiSpec(
            app_id="app_demo",
            spec_key="points:100",
            spec_name="100 points",
            kami_type=KamiType.points,
            points_amount=100,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        session.add(interface)
        session.add(spec)
        session.commit()
        session.refresh(interface)
        session.refresh(spec)
        batch = KamiBatch(
            app_id="app_demo",
            spec_id=spec.id,
            batch_no="app-delete-batch",
            kami_type=KamiType.points,
            points_amount=100,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        account = AuthorizationAccount(
            app_id="app_demo",
            owner_type=AuthorizationOwnerType.user,
            owner_key="username:app-delete-user",
            username="app-delete-user",
            points_balance=100,
        )
        user = EndUser(app_id="app_demo", username="app-delete-user", password_hash="hash")
        session.add(user)
        session.add(batch)
        session.add(account)
        session.add(AppInterfaceConfig(app_id="app_demo", interface_id=interface.id, enabled=True))
        session.commit()
        session.refresh(user)
        session.refresh(batch)
        session.refresh(account)
        session.add(
            UserAppAuthorization(
                app_id="app_demo",
                user_id=user.id,
                username=user.username,
                granted_by="admin",
            )
        )
        session.add(
            Kami(
                app_id="app_demo",
                kami_code="APPDEL001",
                kami_type=KamiType.points,
                status=KamiStatus.active,
                bind_uuid="app-delete-device",
                spec_id=spec.id,
                batch_no=batch.batch_no,
                points_amount=100,
                machine_bind_mode=MachineBindMode.one_card_one_device,
                max_bind_devices=1,
                authorization_owner=AuthorizationOwnerMode.auto,
                user_bind_mode=UserBindMode.auto,
            )
        )
        session.commit()
        session.add(
            AuthorizationLot(
                account_id=account.id,
                source_kami_code="APPDEL001",
                benefit_type=AuthorizationBenefitType.points,
                amount_total=100,
                amount_remaining=100,
            )
        )
        session.add(
            AuthorizationTransaction(
                transaction_id="app-delete-auth-tx",
                account_id=account.id,
                source_kami_code="APPDEL001",
                transaction_type=AuthorizationTransactionType.grant,
                benefit_type=AuthorizationBenefitType.points,
                amount=100,
                balance_after=100,
            )
        )
        session.add(
            EventLog(
                app_id="app_demo",
                kami_code="APPDEL001",
                event_type="verify",
                status=1,
            )
        )
        session.add(
            KamiDeviceBinding(
                app_id="app_demo",
                kami_code="APPDEL001",
                device_uuid="app-delete-device",
                fingerprint="app-delete-fingerprint",
            )
        )
        session.commit()

    try:
        response = client.delete("/api/v1/admin/apps/app_demo")
        assert response.status_code == 200

        with Session(engine) as session:
            assert session.exec(select(App).where(App.app_id == "app_demo")).first() is None
            assert session.exec(select(AppInterfaceConfig).where(AppInterfaceConfig.app_id == "app_demo")).all() == []
            assert session.exec(select(KamiSpec).where(KamiSpec.app_id == "app_demo")).all() == []
            assert session.exec(select(KamiBatch).where(KamiBatch.app_id == "app_demo")).all() == []
            assert session.exec(select(AuthorizationAccount).where(AuthorizationAccount.app_id == "app_demo")).all() == []
            assert session.exec(
                select(AuthorizationLot).where(AuthorizationLot.source_kami_code == "APPDEL001")
            ).all() == []
            assert session.exec(
                select(AuthorizationTransaction).where(AuthorizationTransaction.source_kami_code == "APPDEL001")
            ).all() == []
            assert session.exec(select(Kami).where(Kami.kami_code == "APPDEL001")).first() is None
            assert session.exec(
                select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == "APPDEL001")
            ).all() == []
            assert session.exec(
                select(UserAppAuthorization).where(UserAppAuthorization.app_id == "app_demo")
            ).all() == []
            stale_logs = session.exec(
                select(EventLog).where(EventLog.kami_code == "APPDEL001")
            ).all()
            assert stale_logs == []
    finally:
        fastapi_app.dependency_overrides.clear()


def test_legacy_batch_create_and_generate_attach_spec():
    from fastapi.testclient import TestClient
    from main import app as fastapi_app

    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(make_app())
        session.commit()

    try:
        batch_response = client.post(
            "/api/v1/admin/kamis/batches",
            json={
                "app_id": "app_demo",
                "batch_no": "p68-batch",
                "kami_type": "points",
                "points_amount": 68,
                "machine_bind_mode": "one_card_one_device",
                "max_bind_devices": 1,
                "authorization_owner": "auto",
                "user_bind_mode": "auto",
                "status": 1,
            },
        )
        assert batch_response.status_code == 200
        assert batch_response.json()["data"]["spec_id"] is not None

        generate_response = client.post(
            "/api/v1/admin/kamis/batch",
            params={"app_id": "app_demo", "batch_no": "p68-batch", "count": 1},
        )
        assert generate_response.status_code == 200

        with Session(engine) as session:
            batch = session.exec(select(KamiBatch).where(KamiBatch.batch_no == "p68-batch")).first()
            kami = session.exec(select(Kami).where(Kami.batch_no == "p68-batch")).first()
            assert batch.spec_id is not None
            assert kami.spec_id == batch.spec_id
    finally:
        fastapi_app.dependency_overrides.clear()
