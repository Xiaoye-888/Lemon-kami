from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from models import (
    AdminAuditLog,
    OpsBackupRecord,
    RechargeChannel,
    RechargeOrder,
    RechargeOrderStatus,
)


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_phase2_schema_creates_audit_backup_and_proof_columns():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "admin_audit_logs" in inspector.get_table_names()
    assert "ops_backup_records" in inspector.get_table_names()

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
            status="completed",
            file_path="/app/backups/BACKUP-001.sql",
            file_name="BACKUP-001.sql",
            file_size=128,
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
        assert saved_recharge_order.proof_file_deleted is True
