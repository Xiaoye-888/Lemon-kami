from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select

import routes_admin_advanced
import routes_commercial
from auth_utils import hash_password
from main import app as fastapi_app
from models import (
    AdminAuditLog,
    AdminUser,
    App,
    EndUser,
    OpsBackupRecord,
    RechargeChannel,
    RechargeMode,
    RechargeOrder,
    RechargeOrderStatus,
    UserAppAuthorization,
    UserQuotaAccount,
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
