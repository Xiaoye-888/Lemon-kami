from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin_advanced
import routes_commercial
import routes_merchant
from auth_utils import hash_password
from audit_service import CONFIRM_TEXT_BY_SCOPE
from main import app as fastapi_app
from models import (
    AdminAuditLog,
    AdminUser,
    App,
    EndUser,
    Kami,
    KamiBatch,
    KamiDeviceBinding,
    KamiStatus,
    OpsBackupRecord,
    RechargeChannel,
    RechargeMode,
    RechargeOrder,
    RechargeOrderStatus,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaTransactionType,
    UserQuotaType,
)
import database


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


def seed_admin_and_merchant(session: Session, username: str = "merchant-a") -> tuple[AdminUser, EndUser]:
    admin = AdminUser(
        username="admin",
        password_hash=hash_password("admin-pass"),
        is_admin=True,
        status=1,
    )
    merchant = EndUser(
        username=username,
        password_hash=hash_password("merchant-pass"),
        status=1,
    )
    session.add_all([admin, merchant])
    session.commit()
    session.refresh(admin)
    session.refresh(merchant)
    return admin, merchant


def test_phase2_schema_creates_audit_backup_and_proof_columns():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "admin_audit_logs" in inspector.get_table_names()
    assert "ops_backup_records" in inspector.get_table_names()

    backup_record_columns = {
        column["name"]: column for column in inspector.get_columns("ops_backup_records")
    }
    assert backup_record_columns["created_by"]["nullable"] is False
    admin_audit_index_columns = {
        column
        for index in inspector.get_indexes("admin_audit_logs")
        for column in index["column_names"]
    }
    assert {"resource_id", "admin_id", "admin_username"}.issubset(admin_audit_index_columns)

    backup_record_index_columns = {
        column
        for index in inspector.get_indexes("ops_backup_records")
        for column in index["column_names"]
    }
    assert {"backup_no", "backup_type", "created_by", "created_at"}.issubset(
        backup_record_index_columns
    )

    recharge_order_columns = {
        column["name"] for column in inspector.get_columns("recharge_orders")
    }
    assert "proof_file_deleted" in recharge_order_columns
    assert "proof_deleted_at" in recharge_order_columns

    with Session(engine) as session:
        audit_log = AdminAuditLog(
            action="approve",
            resource_type="recharge_order",
            resource_id="ORDER-001",
            admin_id=1,
            admin_username="admin",
            target_user_id=2,
            target_username="merchant-a",
            status="success",
            confirm_scope="single_order",
            request_ip="127.0.0.1",
            user_agent="pytest",
            summary="Approved recharge order",
            before_json='{"status":"pending_review"}',
            after_json='{"status":"approved"}',
            metadata_json='{"source":"phase2-test"}',
        )
        backup_record = OpsBackupRecord(
            backup_no="BACKUP-001",
            backup_type="manual",
            file_path="/app/backups/BACKUP-001.sql",
            file_name="BACKUP-001.sql",
            table_counts_json='{"recharge_orders":1}',
            created_by="admin",
        )
        recharge_order = RechargeOrder(
            order_no="ORDER-001",
            user_id=2,
            username="merchant-a",
            channel=RechargeChannel.wechat,
            amount_cents=1000,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            proof_file_deleted=True,
        )

        session.add(audit_log)
        session.add(backup_record)
        session.add(recharge_order)
        session.commit()

        saved_audit_log = session.exec(select(AdminAuditLog)).one()
        saved_backup_record = session.exec(select(OpsBackupRecord)).one()
        saved_recharge_order = session.exec(select(RechargeOrder)).one()

        assert saved_audit_log.action == "approve"
        assert saved_backup_record.backup_no == "BACKUP-001"
        assert saved_backup_record.status == "created"
        assert saved_backup_record.file_size == 0
        assert saved_recharge_order.proof_file_deleted is True


def test_phase2_schema_backfills_existing_sqlite_recharge_order_proof_columns(monkeypatch):
    engine = make_engine()
    with engine.connect() as conn:
        conn.execute(
            text(
                "CREATE TABLE recharge_orders ("
                "id INTEGER PRIMARY KEY, "
                "order_no VARCHAR(64)"
                ")"
            )
        )
        conn.commit()

    monkeypatch.setattr(database, "engine", engine)

    database._ensure_phase2_recharge_order_schema()

    recharge_order_columns = {
        column["name"] for column in inspect(engine).get_columns("recharge_orders")
    }
    assert "proof_file_deleted" in recharge_order_columns
    assert "proof_deleted_at" in recharge_order_columns


def test_finance_summary_uses_admin_reviewed_at_for_approved_income():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            session.add_all(
                [
                    RechargeOrder(
                        order_no="R202607250101",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=1000,
                        base_quota=10,
                        bonus_quota=0,
                        credit_quota=10,
                        status=RechargeOrderStatus.approved,
                        reviewed_at=datetime(2026, 7, 25, 10, 0, 0),
                    ),
                    RechargeOrder(
                        order_no="R202607240101",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=2000,
                        base_quota=20,
                        bonus_quota=5,
                        credit_quota=25,
                        status=RechargeOrderStatus.approved,
                        reviewed_at=datetime(2026, 7, 24, 10, 0, 0),
                    ),
                    RechargeOrder(
                        order_no="R202607250102",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=3000,
                        base_quota=30,
                        bonus_quota=0,
                        credit_quota=30,
                        status=RechargeOrderStatus.pending_review,
                        created_at=datetime(2026, 7, 25, 12, 0, 0),
                    ),
                    RechargeOrder(
                        order_no="R202607250103",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=4000,
                        base_quota=40,
                        bonus_quota=0,
                        credit_quota=40,
                        status=RechargeOrderStatus.approved,
                    ),
                ]
            )
            session.commit()

        response = client.get(
            "/api/v1/admin/commercial/finance/summary",
            params={"start_date": "2026-07-25", "end_date": "2026-07-25"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["income_basis"] == "reviewed_at"
        assert data["approved_order_count"] == 1
        assert data["approved_amount"] == 10
        assert data["credited_issue_quota"] == 10
        assert data["bonus_issue_quota"] == 0
        assert data["pending_review_count"] == 1
        assert data["approved_without_reviewed_at_count"] == 1
        assert data["refund_amount"] == 0
        assert data["reversal_amount"] == 0
        assert data["daily"] == [
            {
                "date": "2026-07-25",
                "approved_order_count": 1,
                "approved_amount": 10,
                "credited_issue_quota": 10,
                "bonus_issue_quota": 0,
            }
        ]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_finance_exports_respect_filters_and_include_bom():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            account = UserQuotaAccount(
                user_id=merchant.id,
                username=merchant.username,
                kami_issue_balance=10,
                total_kami_issue_granted=10,
            )
            session.add(account)
            session.commit()
            session.refresh(account)
            session.add_all(
                [
                    RechargeOrder(
                        order_no="R202607250201",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=1000,
                        base_quota=10,
                        bonus_quota=0,
                        credit_quota=10,
                        status=RechargeOrderStatus.approved,
                        reviewed_at=datetime(2026, 7, 25, 10, 0, 0),
                    ),
                    RechargeOrder(
                        order_no="R202607250202",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=2000,
                        base_quota=20,
                        bonus_quota=0,
                        credit_quota=20,
                        status=RechargeOrderStatus.rejected,
                        reviewed_at=datetime(2026, 7, 25, 11, 0, 0),
                    ),
                    UserQuotaTransaction(
                        transaction_id="Q202607250201",
                        account_id=account.id,
                        user_id=merchant.id,
                        username=merchant.username,
                        quota_type=UserQuotaType.kami_issue,
                        transaction_type=UserQuotaTransactionType.grant,
                        amount=10,
                        balance_before=0,
                        balance_after=10,
                        biz_id="R202607250201",
                        operator="admin",
                        created_at=datetime(2026, 7, 25, 10, 1, 0),
                    ),
                ]
            )
            session.commit()

        orders = client.get(
            "/api/v1/admin/commercial/recharge-orders/export",
            params={"status": "approved", "start_date": "2026-07-25", "end_date": "2026-07-25"},
        )
        assert orders.status_code == 200
        assert orders.headers["content-type"].startswith("text/csv")
        assert orders.content.startswith(b"\xef\xbb\xbf")
        order_text = orders.content.decode("utf-8-sig")
        assert "订单号" in order_text
        assert "R202607250201" in order_text
        assert "R202607250202" not in order_text

        transactions = client.get(
            "/api/v1/admin/commercial/quota-transactions/export",
            params={
                "username": merchant.username,
                "transaction_type": "grant",
                "start_date": "2026-07-25",
                "end_date": "2026-07-25",
            },
        )
        assert transactions.status_code == 200
        assert transactions.content.startswith(b"\xef\xbb\xbf")
        transaction_text = transactions.content.decode("utf-8-sig")
        assert "流水号" in transaction_text
        assert "Q202607250201" in transaction_text
        assert "merchant-a" in transaction_text
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_global_kami_search_is_scoped_and_export_matches_filter():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            other = EndUser(username="merchant-b", password_hash=hash_password("merchant-pass"), status=1)
            app = App(
                app_id="phase2_kami_search_app",
                name="Phase2 Kami Search App",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
                owner_user_id=merchant.id,
                status=1,
            )
            session.add_all([other, app])
            session.commit()
            session.refresh(other)
            session.add_all(
                [
                    Kami(
                        app_id=app.app_id,
                        kami_code="MERCHANT-A-001",
                        kami_type="points",
                        status=KamiStatus.unused,
                        created_by_user_id=merchant.id,
                        batch_no="B-A",
                        remark="remark-alpha",
                    ),
                    Kami(
                        app_id=app.app_id,
                        kami_code="MERCHANT-B-001",
                        kami_type="points",
                        status=KamiStatus.unused,
                        created_by_user_id=other.id,
                        batch_no="B-B",
                        remark="remark-alpha",
                    ),
                ]
            )
            session.commit()
            merchant_id = merchant.id
            merchant_username = merchant.username

        fastapi_app.dependency_overrides[routes_merchant.get_current_merchant] = lambda: EndUser(
            id=merchant_id,
            username=merchant_username,
            password_hash="hash",
            status=1,
        )

        listed = client.get("/api/v1/merchant/kamis", params={"keyword": "MERCHANT"})
        assert listed.status_code == 200
        codes = [item["kami_code"] for item in listed.json()["items"]]
        assert codes == ["MERCHANT-A-001"]
        assert listed.json()["items"][0]["remark"] == "remark-alpha"

        listed_by_remark = client.get("/api/v1/merchant/kamis", params={"keyword": "remark-alpha"})
        assert listed_by_remark.status_code == 200
        assert [item["kami_code"] for item in listed_by_remark.json()["items"]] == ["MERCHANT-A-001"]

        exported = client.get("/api/v1/merchant/kamis/export", params={"keyword": "remark-alpha"})
        assert exported.status_code == 200
        assert exported.content.startswith(b"\xef\xbb\xbf")
        text = exported.content.decode("utf-8-sig")
        assert "MERCHANT-A-001" in text
        assert "remark-alpha" in text
        assert "MERCHANT-B-001" not in text
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_batches_include_status_stats_and_low_quota_warning():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            account = UserQuotaAccount(
                user_id=merchant.id,
                username=merchant.username,
                kami_issue_balance=5,
                total_kami_issue_granted=5,
            )
            app = App(
                app_id="phase2_batch_stats_app",
                name="Phase2 Batch Stats App",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
                owner_user_id=merchant.id,
                status=1,
            )
            batch = KamiBatch(
                app_id=app.app_id,
                batch_no="B-STATS",
                kami_type="points",
                points_amount=100,
                code_prefix="B",
            )
            session.add_all([account, app, batch])
            session.commit()
            session.add_all(
                [
                    Kami(
                        app_id=app.app_id,
                        kami_code="B-STATS-1",
                        kami_type="points",
                        status=KamiStatus.unused,
                        created_by_user_id=merchant.id,
                        batch_no="B-STATS",
                    ),
                    Kami(
                        app_id=app.app_id,
                        kami_code="B-STATS-2",
                        kami_type="points",
                        status=KamiStatus.active,
                        created_by_user_id=merchant.id,
                        batch_no="B-STATS",
                    ),
                    KamiDeviceBinding(
                        app_id=app.app_id,
                        kami_code="B-STATS-2",
                        device_uuid="device-a",
                        fingerprint="fingerprint-a",
                    ),
                ]
            )
            session.commit()
            merchant_id = merchant.id
            merchant_username = merchant.username

        fastapi_app.dependency_overrides[routes_merchant.get_current_merchant] = lambda: EndUser(
            id=merchant_id,
            username=merchant_username,
            password_hash="hash",
            status=1,
        )

        batches = client.get("/api/v1/merchant/apps/phase2_batch_stats_app/batches")
        assert batches.status_code == 200
        item = batches.json()["items"][0]
        assert item["stats"]["total_count"] == 2
        assert item["stats"]["unused_count"] == 1
        assert item["stats"]["active_count"] == 1
        assert item["stats"]["device_bound_count"] == 1

        quotas = client.get("/api/v1/merchant/quotas")
        assert quotas.status_code == 200
        assert quotas.json()["issue_card"]["low_balance_warning"] is True
        assert quotas.json()["issue_card"]["warning_threshold"] == 20
    finally:
        fastapi_app.dependency_overrides.clear()


def test_ops_health_backup_and_safe_download(tmp_path, monkeypatch):
    import routes_ops

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("config.settings.BACKUP_ROOT", str(tmp_path / "backups"))
    fastapi_app.dependency_overrides[routes_ops.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_ops.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        health = client.get("/api/v1/admin/ops/health")
        assert health.status_code == 200
        assert health.json()["database"]["ok"] is True

        created = client.post(
            "/api/v1/admin/ops/backups",
            json={"backup_type": "database", "confirm_text": CONFIRM_TEXT_BY_SCOPE["create_ops_backup"]},
        )
        assert created.status_code == 200
        backup_no = created.json()["backup_no"]

        with Session(engine) as session:
            record = session.exec(
                select(OpsBackupRecord).where(OpsBackupRecord.backup_no == backup_no)
            ).one()
            assert record.status == "succeeded"
            assert Path(record.file_path).exists()

        denied = client.post(
            "/api/v1/admin/ops/backups/../../etc/passwd/download",
            json={"confirm_text": "纭涓嬭浇澶囦唤"},
        )
        assert denied.status_code in (400, 404)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_ops_health_recovers_missing_upload_directory(tmp_path, monkeypatch):
    import commercial_service
    import ops_service

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    upload_root = tmp_path / "uploads" / "commercial"
    monkeypatch.setattr(commercial_service, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr(ops_service, "UPLOAD_ROOT", upload_root)
    monkeypatch.setattr("config.settings.BACKUP_ROOT", str(tmp_path / "backups"))

    with Session(engine) as session:
        payload = ops_service.ops_health_payload(session)

    assert payload["uploads"]["ok"] is True
    assert upload_root.is_dir()
    assert (upload_root / "proofs").is_dir()
    assert (upload_root / "payment-qrcodes").is_dir()


def test_ops_upload_cleanup_marks_terminal_proofs_only(tmp_path, monkeypatch):
    import routes_ops

    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    uploads = tmp_path / "uploads"
    proofs = uploads / "proofs"
    proofs.mkdir(parents=True)
    old_file = proofs / "old.jpg"
    pending_file = proofs / "pending.jpg"
    old_file.write_bytes(b"old")
    pending_file.write_bytes(b"pending")
    monkeypatch.setattr("commercial_service.UPLOAD_ROOT", uploads)
    fastapi_app.dependency_overrides[routes_ops.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_ops.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            session.add_all(
                [
                    RechargeOrder(
                        order_no="R202607250301",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=1000,
                        base_quota=10,
                        bonus_quota=0,
                        credit_quota=10,
                        status=RechargeOrderStatus.approved,
                        proof_file_path=str(old_file),
                        proof_file_name="old.jpg",
                        proof_content_type="image/jpeg",
                        reviewed_at=datetime(2026, 6, 1, 10, 0, 0),
                        created_at=datetime(2026, 6, 1, 10, 0, 0),
                    ),
                    RechargeOrder(
                        order_no="R202607250302",
                        user_id=merchant.id,
                        username=merchant.username,
                        mode=RechargeMode.custom,
                        channel=RechargeChannel.wechat,
                        amount_cents=1000,
                        base_quota=10,
                        bonus_quota=0,
                        credit_quota=10,
                        status=RechargeOrderStatus.pending_review,
                        proof_file_path=str(pending_file),
                        proof_file_name="pending.jpg",
                        proof_content_type="image/jpeg",
                        created_at=datetime(2026, 6, 1, 10, 0, 0),
                    ),
                ]
            )
            session.commit()

        preview = client.post(
            "/api/v1/admin/ops/uploads/proofs/cleanup",
            json={"older_than_days": 1, "dry_run": True},
        )
        assert preview.status_code == 200
        assert preview.json()["matched_count"] == 1
        assert old_file.exists()

        cleanup = client.post(
            "/api/v1/admin/ops/uploads/proofs/cleanup",
            json={
                "older_than_days": 1,
                "dry_run": False,
                "confirm_text": CONFIRM_TEXT_BY_SCOPE["cleanup_proof_files"],
            },
        )
        assert cleanup.status_code == 200
        assert cleanup.json()["deleted_count"] == 1
        assert not old_file.exists()
        assert pending_file.exists()

        with Session(engine) as session:
            approved_order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "R202607250301")
            ).one()
            pending_order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "R202607250302")
            ).one()
            assert approved_order.proof_file_deleted is True
            assert approved_order.proof_deleted_at is not None
            assert approved_order.proof_file_path is None
            assert pending_order.proof_file_deleted is False
            assert pending_order.proof_file_path == str(pending_file)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_recharge_approval_requires_confirmation_and_writes_audit():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            merchant = EndUser(
                username="merchant-a",
                password_hash=hash_password("merchant-pass"),
                status=1,
            )
            session.add(merchant)
            session.commit()
            session.refresh(merchant)
            session.add(
                RechargeOrder(
                    order_no="RC_CONFIRM_APPROVE",
                    user_id=merchant.id,
                    username=merchant.username,
                    mode=RechargeMode.custom,
                    channel=RechargeChannel.wechat,
                    amount_cents=1000,
                    base_quota=10,
                    bonus_quota=0,
                    credit_quota=10,
                    status=RechargeOrderStatus.pending_review,
                )
            )
            session.commit()
            merchant_id = merchant.id

        missing_response = client.post(
            "/api/v1/admin/commercial/recharge-orders/RC_CONFIRM_APPROVE/approve",
            json={"remark": "approve without confirmation"},
        )
        assert missing_response.status_code == 400
        assert missing_response.json()["detail"]["expected"] == "确认审核入账"

        wrong_response = client.post(
            "/api/v1/admin/commercial/recharge-orders/RC_CONFIRM_APPROVE/approve",
            json={"remark": "approve with wrong confirmation", "confirm_text": "确认通过"},
        )
        assert wrong_response.status_code == 400
        assert wrong_response.json()["detail"]["expected"] == "确认审核入账"

        with Session(engine) as session:
            failed_logs = session.exec(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == "approve_recharge_order",
                    AdminAuditLog.status == "failed",
                )
            ).all()
            assert len(failed_logs) == 2
            assert all(log.confirm_scope == "approve_recharge_order" for log in failed_logs)

        success_response = client.post(
            "/api/v1/admin/commercial/recharge-orders/RC_CONFIRM_APPROVE/approve",
            json={"remark": "confirmed approval", "confirm_text": "确认审核入账"},
        )
        assert success_response.status_code == 200
        assert success_response.json()["data"]["status"] == "approved"

        with Session(engine) as session:
            saved_order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "RC_CONFIRM_APPROVE")
            ).one()
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            success_log = session.exec(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == "approve_recharge_order",
                    AdminAuditLog.status == "success",
                )
            ).one()

            assert saved_order.status == RechargeOrderStatus.approved
            assert account.kami_issue_balance == 10
            assert success_log.resource_type == "recharge_order"
            assert success_log.resource_id == "RC_CONFIRM_APPROVE"
            assert success_log.target_user_id == merchant_id
            assert success_log.target_username == "merchant-a"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_recharge_approval_business_failure_writes_failed_audit_without_mutation():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            merchant = EndUser(
                username="merchant-approved",
                password_hash=hash_password("merchant-pass"),
                status=1,
            )
            session.add(merchant)
            session.commit()
            session.refresh(merchant)
            session.add(
                RechargeOrder(
                    order_no="RC_ALREADY_APPROVED",
                    user_id=merchant.id,
                    username=merchant.username,
                    mode=RechargeMode.custom,
                    channel=RechargeChannel.wechat,
                    amount_cents=1000,
                    base_quota=10,
                    bonus_quota=0,
                    credit_quota=10,
                    status=RechargeOrderStatus.approved,
                    reviewed_by="admin",
                )
            )
            account = UserQuotaAccount(
                user_id=merchant.id,
                username=merchant.username,
                kami_issue_balance=10,
                total_kami_issue_granted=10,
            )
            session.add(account)
            session.commit()
            merchant_id = merchant.id

        response = client.post(
            "/api/v1/admin/commercial/recharge-orders/RC_ALREADY_APPROVED/approve",
            json={"remark": "repeat approval", "confirm_text": "确认审核入账"},
        )
        assert response.status_code == 400

        with Session(engine) as session:
            saved_order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == "RC_ALREADY_APPROVED")
            ).one()
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            failed_log = session.exec(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == "approve_recharge_order",
                    AdminAuditLog.status == "failed",
                )
            ).one()

            assert saved_order.status == RechargeOrderStatus.approved
            assert account.kami_issue_balance == 10
            assert account.total_kami_issue_granted == 10
            assert failed_log.resource_type == "recharge_order"
            assert failed_log.resource_id == "RC_ALREADY_APPROVED"
            assert failed_log.target_user_id == merchant_id
            assert failed_log.target_username == "merchant-approved"
            assert failed_log.error_message
    finally:
        fastapi_app.dependency_overrides.clear()


def test_quota_grant_and_app_authorization_require_confirmation():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin_advanced.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin_advanced.legacy_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            merchant = EndUser(
                username="merchant-b",
                password_hash=hash_password("merchant-pass"),
                status=1,
            )
            app = App(
                app_id="phase2_app",
                name="Phase2 App",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
                status=1,
                created_by="admin",
            )
            session.add(merchant)
            session.add(app)
            session.commit()
            session.refresh(merchant)
            merchant_id = merchant.id

        grant_missing = client.post(
            f"/api/v1/admin/end-users/{merchant_id}/quotas/grant",
            json={"quota_type": "kami_issue", "amount": 5},
        )
        assert grant_missing.status_code == 400
        assert grant_missing.json()["detail"]["expected"] == "确认调整额度"

        grant_success = client.post(
            f"/api/v1/admin/end-users/{merchant_id}/quotas/grant",
            json={
                "quota_type": "kami_issue",
                "amount": 5,
                "confirm_text": "确认调整额度",
            },
        )
        assert grant_success.status_code == 200
        assert grant_success.json()["data"]["kami_issue_balance"] == 5

        auth_missing = client.post(
            f"/api/v1/admin/end-users/{merchant_id}/app-authorizations",
            json={"app_id": "phase2_app"},
        )
        assert auth_missing.status_code == 400
        assert auth_missing.json()["detail"]["expected"] == "确认授权应用"

        auth_success = client.post(
            f"/api/v1/admin/end-users/{merchant_id}/app-authorizations",
            json={"app_id": "phase2_app", "confirm_text": "确认授权应用"},
        )
        assert auth_success.status_code == 200

        with Session(engine) as session:
            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant_id)
            ).one()
            authorization = session.exec(select(UserAppAuthorization)).one()
            audit_logs = session.exec(select(AdminAuditLog).order_by(AdminAuditLog.id)).all()

            assert account.kami_issue_balance == 5
            assert authorization.user_id == merchant_id
            assert [(log.action, log.status) for log in audit_logs] == [
                ("grant_issue_quota", "failed"),
                ("grant_issue_quota", "success"),
                ("grant_app_authorization", "failed"),
                ("grant_app_authorization", "success"),
            ]
    finally:
        fastapi_app.dependency_overrides.clear()


def test_revoke_app_authorization_requires_confirmation_and_audits_success():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin_advanced.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin_advanced.legacy_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            merchant = EndUser(
                username="merchant-revoke",
                password_hash=hash_password("merchant-pass"),
                status=1,
            )
            other_merchant = EndUser(
                username="merchant-other",
                password_hash=hash_password("merchant-pass"),
                status=1,
            )
            app = App(
                app_id="phase2_revoke_app",
                name="Phase2 Revoke App",
                app_secret="secret",
                rsa_public_key="public",
                rsa_private_key="private",
                status=1,
                created_by="admin",
            )
            session.add_all([merchant, other_merchant, app])
            session.commit()
            session.refresh(merchant)
            session.refresh(other_merchant)
            authorization = UserAppAuthorization(
                app_id=app.app_id,
                user_id=merchant.id,
                username=merchant.username,
                granted_by="admin",
                remark="temporary grant",
            )
            session.add(authorization)
            session.commit()
            session.refresh(authorization)
            merchant_id = merchant.id
            other_merchant_id = other_merchant.id
            authorization_id = authorization.id

        missing = client.request(
            "DELETE",
            f"/api/v1/admin/end-users/{merchant_id}/app-authorizations/{authorization_id}",
            json={},
        )
        assert missing.status_code == 400
        assert missing.json()["detail"]["expected"] == "确认取消授权"

        wrong_user = client.request(
            "DELETE",
            f"/api/v1/admin/end-users/{other_merchant_id}/app-authorizations/{authorization_id}",
            json={"confirm_text": "确认取消授权"},
        )
        assert wrong_user.status_code == 404

        success = client.request(
            "DELETE",
            f"/api/v1/admin/end-users/{merchant_id}/app-authorizations/{authorization_id}",
            json={"confirm_text": "确认取消授权"},
        )
        assert success.status_code == 200
        assert success.json()["data"]["id"] == authorization_id

        with Session(engine) as session:
            assert session.get(UserAppAuthorization, authorization_id) is None
            audit_logs = session.exec(
                select(AdminAuditLog).where(
                    AdminAuditLog.action == "revoke_app_authorization"
                ).order_by(AdminAuditLog.id)
            ).all()
            assert [(log.status, log.resource_type, log.resource_id) for log in audit_logs] == [
                ("failed", "user_app_authorization", str(authorization_id)),
                ("failed", "user_app_authorization", str(authorization_id)),
                ("success", "user_app_authorization", str(authorization_id)),
            ]
            assert audit_logs[-1].target_user_id == merchant_id
            assert audit_logs[-1].target_username == "merchant-revoke"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_direct_app_delete_requires_confirmation_and_audits_success_and_failure():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_admin_advanced.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin_advanced.legacy_admin.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            session.add(
                App(
                    app_id="phase2_delete_app",
                    name="Phase2 Delete App",
                    app_secret="secret",
                    rsa_public_key="public",
                    rsa_private_key="private",
                    status=1,
                    created_by="admin",
                )
            )
            session.commit()

        missing_confirm = client.delete("/api/v1/admin/apps/phase2_delete_app")
        assert missing_confirm.status_code == 400
        assert missing_confirm.json()["detail"]["expected"] == "确认删除应用"

        success = client.request(
            "DELETE",
            "/api/v1/admin/apps/phase2_delete_app",
            json={"confirm_text": "确认删除应用"},
        )
        assert success.status_code == 200

        not_found = client.request(
            "DELETE",
            "/api/v1/admin/apps/phase2_missing_app",
            json={"confirm_text": "确认删除应用"},
        )
        assert not_found.status_code == 404

        with Session(engine) as session:
            assert session.exec(select(App).where(App.app_id == "phase2_delete_app")).first() is None
            audit_logs = session.exec(
                select(AdminAuditLog)
                .where(AdminAuditLog.action == "delete_app")
                .order_by(AdminAuditLog.id)
            ).all()
            assert [(log.status, log.resource_type, log.resource_id) for log in audit_logs] == [
                ("failed", "app", "phase2_delete_app"),
                ("success", "app", "phase2_delete_app"),
                ("failed", "app", "phase2_missing_app"),
            ]
            assert audit_logs[1].summary == "删除应用 phase2_delete_app"
            assert audit_logs[2].error_message == "App not found"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_admin_audit_logs_are_filterable_and_include_confirmation_texts():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)

    try:
        with Session(engine) as session:
            session.add_all(
                [
                    AdminAuditLog(
                        action="approve_recharge_order",
                        resource_type="recharge_order",
                        resource_id="RC_AUDIT_1",
                        admin_id=1,
                        admin_username="admin",
                        target_username="merchant-a",
                        status="success",
                        confirm_scope="approve_recharge_order",
                        summary="Approved RC_AUDIT_1",
                    ),
                    AdminAuditLog(
                        action="grant_issue_quota",
                        resource_type="end_user",
                        resource_id="2",
                        admin_id=1,
                        admin_username="ops-admin",
                        target_username="merchant-b",
                        status="failed",
                        confirm_scope="grant_issue_quota",
                        error_message="confirmation mismatch",
                    ),
                    AdminAuditLog(
                        action="delete_kami",
                        resource_type="kami",
                        resource_id="KAMI-001",
                        admin_id=1,
                        admin_username="admin",
                        status="success",
                        confirm_scope="delete_kami",
                    ),
                ]
            )
            session.commit()

        action_response = client.get(
            "/api/v1/admin/commercial/audit-logs",
            params={"action": "approve_recharge_order"},
        )
        assert action_response.status_code == 200
        action_data = action_response.json()["data"]
        assert action_data["total"] == 1
        assert action_data["items"][0]["resource_id"] == "RC_AUDIT_1"

        status_response = client.get(
            "/api/v1/admin/commercial/audit-logs",
            params={"status": "failed"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["data"]["items"][0]["action"] == "grant_issue_quota"

        keyword_response = client.get(
            "/api/v1/admin/commercial/audit-logs",
            params={"keyword": "merchant-b"},
        )
        assert keyword_response.status_code == 200
        keyword_data = keyword_response.json()["data"]
        assert keyword_data["total"] == 1
        assert keyword_data["items"][0]["target_username"] == "merchant-b"
        assert keyword_data["confirmation_texts"]["approve_recharge_order"] == "确认审核入账"
        assert keyword_data["confirmation_texts"]["delete_payment_qrcode"] == "确认删除二维码"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_phase2_acceptance_recharge_approval_finance_audit_and_export_flow():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_user] = override_admin_user
    client = TestClient(fastapi_app)
    order_no = "R202607250401"

    try:
        with Session(engine) as session:
            _, merchant = seed_admin_and_merchant(session)
            session.add(
                RechargeOrder(
                    order_no=order_no,
                    user_id=merchant.id,
                    username=merchant.username,
                    mode=RechargeMode.custom,
                    channel=RechargeChannel.wechat,
                    amount_cents=3000,
                    base_quota=30,
                    bonus_quota=5,
                    credit_quota=35,
                    status=RechargeOrderStatus.pending_review,
                )
            )
            session.commit()

        approved = client.post(
            f"/api/v1/admin/commercial/recharge-orders/{order_no}/approve",
            json={"confirm_text": CONFIRM_TEXT_BY_SCOPE["approve_recharge_order"]},
        )
        assert approved.status_code == 200, approved.text

        with Session(engine) as session:
            order = session.exec(
                select(RechargeOrder).where(RechargeOrder.order_no == order_no)
            ).one()
            assert order.status == RechargeOrderStatus.approved
            assert order.reviewed_at is not None
            reviewed_day = order.reviewed_at.date().isoformat()

            account = session.exec(
                select(UserQuotaAccount).where(UserQuotaAccount.user_id == order.user_id)
            ).one()
            assert account.kami_issue_balance == 35
            transaction = session.exec(
                select(UserQuotaTransaction).where(
                    UserQuotaTransaction.transaction_id == order.quota_transaction_id
                )
            ).one()
            assert transaction.amount == 35
            assert transaction.biz_id == f"recharge_order:{order_no}"

        finance = client.get(
            "/api/v1/admin/commercial/finance/summary",
            params={"start_date": reviewed_day, "end_date": reviewed_day},
        )
        assert finance.status_code == 200
        finance_data = finance.json()
        assert finance_data["income_basis"] == "reviewed_at"
        assert finance_data["approved_order_count"] == 1
        assert finance_data["approved_amount"] == 30
        assert finance_data["credited_issue_quota"] == 35
        assert finance_data["bonus_issue_quota"] == 5

        audits = client.get(
            "/api/v1/admin/commercial/audit-logs",
            params={"action": "approve_recharge_order"},
        )
        assert audits.status_code == 200
        audit_items = audits.json()["data"]["items"]
        assert audit_items[0]["status"] == "success"
        assert audit_items[0]["resource_id"] == order_no
        assert audit_items[0]["target_username"] == "merchant-a"

        exported = client.get(
            "/api/v1/admin/commercial/recharge-orders/export",
            params={"status": "approved", "start_date": reviewed_day, "end_date": reviewed_day},
        )
        assert exported.status_code == 200
        exported_text = exported.content.decode("utf-8-sig")
        assert "订单号" in exported_text
        assert order_no in exported_text
    finally:
        fastapi_app.dependency_overrides.clear()
