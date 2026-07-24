# Commercial Phase 2 Ops Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在一期商业版后台上补齐轻量财务运营、管理员操作审计、商户卡密效率工具、后台运维稳定性入口，并保持个人可控规模。

**Architecture:** 保持一期边界：共用登录页，管理员进入 `/admin/...`，发卡用户进入 `/merchant/...`，普通应用使用用户不得进入商户控制台。新增能力按服务拆分到审计、财务、卡密查询导出、运维服务，路由保持 `/api/v1/admin/...` 和 `/api/v1/merchant/...`。敏感动作统一二次确认并记录审计，财务收入只按管理员审核通过时间 `reviewed_at` 统计已通过充值订单。

**Tech Stack:** FastAPI, SQLModel, PyMySQL/SQLite, pytest, Vue 3, Element Plus, Vite, CSV/JSONL/Gzip/Tarfile from Python stdlib.

---

## Confirmed Scope

- 二期不做代理体系。
- 二期不做微信/支付宝自动支付回调。
- 二期不做充值额度退款，也不做冲正流程。
- 二期不新增管理员角色或 RBAC 分层。
- 二期以个人运营后台为主，重点是对账、审计、搜索导出、批次统计、额度预警、备份、日志、上传文件生命周期。
- 管理员仍然可以审核人工充值订单，审核通过后给发卡额度入账。
- 财务收入统计口径只统计 `RechargeOrder.status == approved` 且 `reviewed_at` 落在筛选时间范围内的数据。
- 管理员确认文案必须固定，前端展示和后端校验使用同一套 `scope -> confirm_text`。

## File Map

- Modify `models.py`: 增加 `AdminAuditLog`、`OpsBackupRecord`，给 `RechargeOrder` 增加凭证清理标记字段。
- Modify `database.py`: 增加 MySQL/SQLite 二期 schema 补齐函数，已有生产库启动时自动补列建表。
- Create `audit_service.py`: 管理员审计记录、二次确认校验、审计列表 payload。
- Create `finance_service.py`: 财务统计、订单对账、充值订单 CSV、额度流水 CSV。
- Create `kami_query_service.py`: 管理员和商户共用的卡密筛选、批次统计、CSV 导出。
- Create `ops_service.py`: 运维健康聚合、备份生成、备份下载、上传文件生命周期预览和执行、日志读取。
- Modify `routes_commercial.py`: 财务接口、审计接入、充值配置和充值审核敏感确认。
- Modify `routes_admin_advanced.py`: 商户额度授权、应用授权、用户删除接入敏感确认和审计。
- Modify `routes_admin.py`: 应用、规格、批次、卡密、设备风险相关敏感操作接入审计；卡密搜索导出增强。
- Modify `routes_merchant.py`: 商户全局卡密搜索、卡密导出、批次统计、额度预警字段。
- Create `routes_ops.py`: 管理员运维中心 API。
- Modify `main.py`: 注册 `routes_ops.py`。
- Modify `config.py`: 增加备份目录、低额度预警阈值、日志读取行数配置。
- Modify `Dockerfile`: 创建 `/app/backups` 并设置可写权限。
- Modify `docker-compose.prod.yml`: 挂载生产备份目录到 `/app/backups`。
- Create `tests/test_commercial_phase2.py`: 二期后端业务测试。
- Modify `tests/test_frontend_static.py`: 二期页面、菜单、API、确认文案静态测试。
- Create `admin/src/api/finance.js`: 财务运营 API。
- Create `admin/src/api/audit.js`: 审计日志 API。
- Create `admin/src/api/ops.js`: 运维中心 API。
- Modify `admin/src/api/commercial.js`: 给敏感动作增加 `confirm_text` 参数，增加导出接口。
- Modify `admin/src/api/merchant.js`: 增加商户卡密搜索、导出、批次统计字段消费。
- Modify `admin/src/api/kami.js`: 管理员卡密搜索导出增强。
- Modify `admin/src/router/index.js`: 增加财务运营、操作审计、运维中心路由。
- Modify `admin/src/layouts/MainLayout.vue`: 增加管理员二期导航入口；保持商户左侧只显示发卡相关功能。
- Create `admin/src/views/AdminFinance.vue`: 财务运营页。
- Create `admin/src/views/AdminAuditLogs.vue`: 操作审计页。
- Create `admin/src/views/AdminOps.vue`: 运维中心页。
- Modify `admin/src/views/AdminRechargeOrders.vue`: 审核、驳回、异常、过期、凭证清理加入二次确认。
- Modify `admin/src/views/AdminRechargeSettings.vue`: 充值渠道、档位、赠送规则、二维码删除加入二次确认。
- Modify `admin/src/views/AdminMerchants.vue`: 额度授权、应用授权、删除用户加入二次确认。
- Modify `admin/src/views/Kamis.vue`: 管理员卡密搜索、筛选、导出交互增强。
- Modify `admin/src/views/KamiBatches.vue`: 管理员批次统计增强。
- Modify `admin/src/views/MerchantCards.vue`: 商户卡密搜索、筛选、导出交互增强。
- Modify `admin/src/views/MerchantBatches.vue`: 商户批次统计和低额度提醒增强。

## Confirmation Texts

These strings are the backend source of truth and must be shown by the frontend before submitting each sensitive action.

```python
CONFIRM_TEXT_BY_SCOPE = {
    "approve_recharge_order": "确认审核入账",
    "reject_recharge_order": "确认驳回订单",
    "mark_recharge_abnormal": "确认标记异常",
    "expire_recharge_order": "确认关闭订单",
    "grant_issue_quota": "确认调整额度",
    "grant_app_authorization": "确认授权应用",
    "revoke_app_authorization": "确认取消授权",
    "delete_merchant": "确认删除用户",
    "delete_app": "确认删除应用",
    "delete_kami": "确认删除卡密",
    "delete_kami_batch": "确认删除批次",
    "delete_payment_qrcode": "确认删除二维码",
    "change_recharge_config": "确认修改充值配置",
    "cleanup_proof_files": "确认清理凭证",
    "create_ops_backup": "确认创建备份",
    "download_ops_backup": "确认下载备份",
}
```

---

### Task 1: Phase 2 Persistence Foundation

**Files:**
- Modify: `models.py`
- Modify: `database.py`
- Modify: `config.py`
- Modify: `Dockerfile`
- Modify: `docker-compose.prod.yml`
- Create: `tests/test_commercial_phase2.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write the failing schema test**

Add this test to `tests/test_commercial_phase2.py`:

```python
from datetime import datetime
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from models import AdminAuditLog, OpsBackupRecord, RechargeOrder, RechargeOrderStatus


def make_phase2_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_phase2_schema_creates_audit_backup_and_proof_columns():
    engine = make_phase2_engine()
    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "admin_audit_logs" in inspector.get_table_names()
    assert "ops_backup_records" in inspector.get_table_names()

    recharge_columns = {column["name"] for column in inspector.get_columns("recharge_orders")}
    assert "proof_file_deleted" in recharge_columns
    assert "proof_deleted_at" in recharge_columns

    with Session(engine) as session:
        audit = AdminAuditLog(
            action="approve_recharge_order",
            resource_type="recharge_order",
            resource_id="R202607250001",
            admin_username="admin",
            status="success",
            confirm_scope="approve_recharge_order",
            summary="审核入账 10 元，到账 10 发卡额度",
        )
        backup = OpsBackupRecord(
            backup_no="B202607250001",
            backup_type="database",
            status="succeeded",
            file_path=str(Path("backups") / "B202607250001.jsonl.gz"),
            file_name="B202607250001.jsonl.gz",
            file_size=128,
            created_by="admin",
        )
        order = RechargeOrder(
            order_no="R202607250001",
            user_id=1,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            proof_file_deleted=True,
            proof_deleted_at=datetime(2026, 7, 25, 9, 0, 0),
        )
        session.add(audit)
        session.add(backup)
        session.add(order)
        session.commit()

        assert session.exec(select(AdminAuditLog)).first().action == "approve_recharge_order"
        assert session.exec(select(OpsBackupRecord)).first().status == "succeeded"
        assert session.exec(select(RechargeOrder)).first().proof_file_deleted is True
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_phase2_schema_creates_audit_backup_and_proof_columns -q
```

Expected: `FAIL` because `AdminAuditLog`, `OpsBackupRecord`, `proof_file_deleted`, or `proof_deleted_at` do not exist.

- [ ] **Step 3: Add SQLModel classes and recharge proof fields**

In `models.py`, add these table models near the commercial models:

```python
class AdminAuditLog(SQLModel, table=True):
    __tablename__ = "admin_audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(index=True, max_length=64)
    resource_type: str = Field(index=True, max_length=64)
    resource_id: Optional[str] = Field(default=None, index=True, max_length=128)
    admin_id: Optional[int] = Field(default=None, index=True)
    admin_username: str = Field(index=True, max_length=255)
    target_user_id: Optional[int] = Field(default=None, index=True)
    target_username: Optional[str] = Field(default=None, index=True, max_length=255)
    status: str = Field(default="success", index=True, max_length=32)
    confirm_scope: Optional[str] = Field(default=None, index=True, max_length=64)
    request_ip: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    before_json: Optional[str] = Field(default=None)
    after_json: Optional[str] = Field(default=None)
    metadata_json: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_now_naive, index=True)


class OpsBackupRecord(SQLModel, table=True):
    __tablename__ = "ops_backup_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    backup_no: str = Field(unique=True, index=True, max_length=64)
    backup_type: str = Field(index=True, max_length=32)
    status: str = Field(default="created", index=True, max_length=32)
    file_path: Optional[str] = Field(default=None)
    file_name: Optional[str] = Field(default=None, max_length=255)
    file_size: int = Field(default=0)
    table_counts_json: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_by: str = Field(index=True, max_length=255)
    created_at: datetime = Field(default_factory=get_now_naive, index=True)
    completed_at: Optional[datetime] = Field(default=None)
```

In `RechargeOrder`, add:

```python
    proof_file_deleted: bool = Field(default=False, index=True)
    proof_deleted_at: Optional[datetime] = Field(default=None)
```

- [ ] **Step 4: Add startup schema补齐**

In `database.py`, add `_ensure_phase2_schema()` and call it after `SQLModel.metadata.create_all(engine)` for MySQL and SQLite.

SQLite branch adds columns only when missing:

```python
if "recharge_orders" in tables:
    columns = {row[1] for row in conn.execute(text("PRAGMA table_info(recharge_orders)")).fetchall()}
    if "proof_file_deleted" not in columns:
        conn.execute(text("ALTER TABLE recharge_orders ADD COLUMN proof_file_deleted BOOLEAN DEFAULT 0"))
    if "proof_deleted_at" not in columns:
        conn.execute(text("ALTER TABLE recharge_orders ADD COLUMN proof_deleted_at DATETIME DEFAULT NULL"))
```

MySQL branch adds columns only when missing:

```python
if "recharge_orders" in existing_tables:
    columns = {row[0] for row in conn.execute(text("SHOW COLUMNS FROM recharge_orders")).fetchall()}
    if "proof_file_deleted" not in columns:
        conn.execute(text("ALTER TABLE recharge_orders ADD COLUMN proof_file_deleted BOOLEAN DEFAULT FALSE"))
        conn.commit()
    if "proof_deleted_at" not in columns:
        conn.execute(text("ALTER TABLE recharge_orders ADD COLUMN proof_deleted_at DATETIME DEFAULT NULL"))
        conn.commit()
```

`SQLModel.metadata.create_all(engine)` creates `admin_audit_logs` and `ops_backup_records`.

- [ ] **Step 5: Add runtime backup directory settings**

In `config.py`, add fields with non-secret defaults:

```python
BACKUP_ROOT: str = "/app/backups"
MERCHANT_LOW_ISSUE_QUOTA_THRESHOLD: int = 20
OPS_RECENT_LOG_LINES: int = 200
```

In `Dockerfile`, create `/app/backups` beside `/app/uploads` and `/app/logs`.

In `docker-compose.prod.yml`, mount a host path or named volume to `/app/backups` so production backups survive container replacement.

- [ ] **Step 6: Run the schema test to verify it passes**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_phase2_schema_creates_audit_backup_and_proof_columns -q
```

Expected: `1 passed`.

- [ ] **Step 7: Update Engramory and commit**

Append a 2026-07-25 note recording the new persistence foundation, backup directory contract, and verification command. Do not record backup file contents or secrets.

Run:

```powershell
git add models.py database.py config.py Dockerfile docker-compose.prod.yml tests/test_commercial_phase2.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: add phase two persistence foundation"
```

Expected: commit succeeds.

---

### Task 2: Admin Audit and Sensitive Confirmation

**Files:**
- Create: `audit_service.py`
- Modify: `routes_commercial.py`
- Modify: `routes_admin_advanced.py`
- Modify: `routes_admin.py`
- Modify: `tests/test_commercial_phase2.py`
- Modify: `admin/src/api/commercial.js`
- Modify: `admin/src/api/kami.js`
- Modify: `admin/src/views/AdminRechargeOrders.vue`
- Modify: `admin/src/views/AdminRechargeSettings.vue`
- Modify: `admin/src/views/AdminMerchants.vue`
- Modify: `admin/src/views/Kamis.vue`
- Modify: `admin/src/views/KamiBatches.vue`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write failing backend tests**

Add these tests to `tests/test_commercial_phase2.py`:

```python
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select

import routes_admin
import routes_commercial
from main import app as fastapi_app
from models import AdminAuditLog, AdminUser, RechargeOrder, RechargeOrderStatus, UserQuotaAccount
from tests.test_commercial_phase1 import make_engine, override_session_factory, override_admin_user, seed_admin_and_merchant


def test_recharge_approval_requires_confirmation_and_writes_audit():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)
        order = RechargeOrder(
            order_no="R202607250002",
            user_id=2,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.pending_review,
        )
        session.add(order)
        session.commit()

    try:
        missing = client.post("/api/v1/admin/commercial/recharge-orders/R202607250002/approve", json={})
        assert missing.status_code == 400
        assert "确认审核入账" in missing.json()["detail"]

        wrong = client.post(
            "/api/v1/admin/commercial/recharge-orders/R202607250002/approve",
            json={"confirm_text": "确认"},
        )
        assert wrong.status_code == 400

        ok = client.post(
            "/api/v1/admin/commercial/recharge-orders/R202607250002/approve",
            json={"confirm_text": "确认审核入账", "admin_remark": "人工核对通过"},
        )
        assert ok.status_code == 200

        with Session(engine) as session:
            order = session.exec(select(RechargeOrder).where(RechargeOrder.order_no == "R202607250002")).one()
            account = session.exec(select(UserQuotaAccount).where(UserQuotaAccount.user_id == 2)).one()
            audits = session.exec(select(AdminAuditLog).order_by(AdminAuditLog.id)).all()
            assert order.status == RechargeOrderStatus.approved
            assert account.issue_balance == 10
            assert [item.status for item in audits] == ["failed", "failed", "success"]
            assert audits[-1].action == "approve_recharge_order"
            assert audits[-1].confirm_scope == "approve_recharge_order"
    finally:
        fastapi_app.dependency_overrides.clear()


def test_quota_grant_and_app_authorization_require_confirmation():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_admin.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_admin.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)

    try:
        grant = client.post(
            "/api/v1/admin/end-users/2/quotas/grant",
            json={"quota_type": "issue_card", "amount": 10, "remark": "manual"},
        )
        assert grant.status_code == 400
        assert "确认调整额度" in grant.json()["detail"]

        with Session(engine) as session:
            audits = session.exec(select(AdminAuditLog)).all()
            assert audits[-1].action == "grant_issue_quota"
            assert audits[-1].status == "failed"
    finally:
        fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the backend tests to verify they fail**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_recharge_approval_requires_confirmation_and_writes_audit tests\test_commercial_phase2.py::test_quota_grant_and_app_authorization_require_confirmation -q
```

Expected: `FAIL` because `audit_service.py`, confirmation checks, or audit rows do not exist.

- [ ] **Step 3: Create the audit service**

Create `audit_service.py` with these public functions:

```python
from datetime import datetime
import json
from typing import Any, Optional

from fastapi import HTTPException, Request
from sqlmodel import Session, select

from models import AdminAuditLog, AdminUser, get_now_naive


CONFIRM_TEXT_BY_SCOPE = {
    "approve_recharge_order": "确认审核入账",
    "reject_recharge_order": "确认驳回订单",
    "mark_recharge_abnormal": "确认标记异常",
    "expire_recharge_order": "确认关闭订单",
    "grant_issue_quota": "确认调整额度",
    "grant_app_authorization": "确认授权应用",
    "revoke_app_authorization": "确认取消授权",
    "delete_merchant": "确认删除用户",
    "delete_app": "确认删除应用",
    "delete_kami": "确认删除卡密",
    "delete_kami_batch": "确认删除批次",
    "delete_payment_qrcode": "确认删除二维码",
    "change_recharge_config": "确认修改充值配置",
    "cleanup_proof_files": "确认清理凭证",
    "create_ops_backup": "确认创建备份",
    "download_ops_backup": "确认下载备份",
}


def audit_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def request_context(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    return ip, request.headers.get("user-agent")


def record_admin_audit(
    session: Session,
    *,
    admin: AdminUser | dict,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    status: str = "success",
    confirm_scope: Optional[str] = None,
    summary: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
    error_message: Optional[str] = None,
    request: Optional[Request] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
) -> AdminAuditLog:
    ip, user_agent = request_context(request)
    admin_username = admin.get("sub") if isinstance(admin, dict) else admin.username
    admin_id = admin.get("user_id") if isinstance(admin, dict) else admin.id
    audit = AdminAuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        admin_id=admin_id,
        admin_username=admin_username or "unknown",
        target_user_id=target_user_id,
        target_username=target_username,
        status=status,
        confirm_scope=confirm_scope,
        request_ip=ip,
        user_agent=user_agent,
        summary=summary,
        before_json=audit_json(before),
        after_json=audit_json(after),
        metadata_json=audit_json(metadata),
        error_message=error_message,
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit


def require_sensitive_confirmation(
    session: Session,
    *,
    admin: AdminUser | dict,
    scope: str,
    confirm_text: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    request: Optional[Request] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
) -> None:
    expected = CONFIRM_TEXT_BY_SCOPE[scope]
    if confirm_text != expected:
        record_admin_audit(
            session,
            admin=admin,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status="failed",
            confirm_scope=scope,
            summary="敏感操作确认文本不匹配",
            error_message=f"需要输入：{expected}",
            request=request,
            target_user_id=target_user_id,
            target_username=target_username,
        )
        raise HTTPException(status_code=400, detail=f"请输入确认文本：{expected}")


def audit_log_payload(item: AdminAuditLog) -> dict:
    return {
        "id": item.id,
        "action": item.action,
        "resource_type": item.resource_type,
        "resource_id": item.resource_id,
        "admin_username": item.admin_username,
        "target_user_id": item.target_user_id,
        "target_username": item.target_username,
        "status": item.status,
        "confirm_scope": item.confirm_scope,
        "summary": item.summary,
        "error_message": item.error_message,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
```

- [ ] **Step 4: Wire confirmation into sensitive admin routes**

For each route below, add `confirm_text: Optional[str]` to the request body, call `require_sensitive_confirmation(...)` before mutating data, and call `record_admin_audit(...)` after a successful mutation:

```text
routes_commercial.py
- POST /recharge-orders/{order_no}/approve -> approve_recharge_order
- POST /recharge-orders/{order_no}/reject -> reject_recharge_order
- POST /recharge-orders/{order_no}/abnormal -> mark_recharge_abnormal
- POST /recharge-orders/{order_no}/expire -> expire_recharge_order
- POST /recharge-proofs/cleanup -> cleanup_proof_files
- DELETE /payment-channels/{channel}/qrcode -> delete_payment_qrcode
- POST /payment-channels -> change_recharge_config
- POST /payment-channels/upload -> change_recharge_config
- POST /recharge-options -> change_recharge_config
- DELETE /recharge-options/{option_id} -> change_recharge_config
- POST /recharge-bonus-rules -> change_recharge_config
- DELETE /recharge-bonus-rules/{rule_id} -> change_recharge_config

routes_admin_advanced.py
- POST /end-users/{user_id}/quotas/grant -> grant_issue_quota
- POST /end-users/{user_id}/app-authorizations -> grant_app_authorization
- DELETE /end-users/{user_id}/app-authorizations/{authorization_id} -> revoke_app_authorization
- POST /end-users/delete -> delete_merchant
- DELETE /apps/{app_id} -> delete_app

routes_admin.py
- DELETE /apps/{app_id} -> delete_app
- DELETE /kami-specs/{spec_id} -> delete_kami
- DELETE /kamis/batches/{batch_id} -> delete_kami_batch
- POST /kamis/delete -> delete_kami
- PUT /devices/{device_id}/risk -> record audit without confirmation
```

The success audit must include `before` and `after` snapshots for status or config changes, and `summary` must be human-readable in Chinese.

- [ ] **Step 5: Add admin audit list route**

In `routes_commercial.py`, add:

```python
@router.get("/audit-logs", summary="List admin audit logs")
async def list_admin_audit_logs(
    action: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    session: Session = Depends(get_session),
    admin: dict = Depends(get_current_admin),
):
    ...
```

Return shape:

```python
{
    "items": [audit_log_payload(item) for item in items],
    "total": total,
    "page": page,
    "page_size": page_size,
    "confirmation_texts": CONFIRM_TEXT_BY_SCOPE,
}
```

- [ ] **Step 6: Add frontend confirmation prompts**

In the affected Vue pages, before calling a sensitive API, open an Element Plus prompt with the exact text from the backend map. Send `{ confirm_text: enteredText }` in the request body or `FormData`.

Frontend rule:

```javascript
const expected = confirmationTexts.approve_recharge_order || '确认审核入账'
const { value } = await ElMessageBox.prompt(
  `请输入“${expected}”继续`,
  '敏感操作确认',
  { confirmButtonText: '确认', cancelButtonText: '取消', inputPattern: new RegExp(`^${expected}$`) }
)
await approveRechargeOrder(row.order_no, { confirm_text: value, admin_remark: reviewRemark.value })
```

- [ ] **Step 7: Add frontend static tests**

In `tests/test_frontend_static.py`, add assertions:

```python
def test_phase2_sensitive_actions_use_fixed_confirmation_texts():
    recharge_orders = read_file("admin/src/views/AdminRechargeOrders.vue")
    recharge_settings = read_file("admin/src/views/AdminRechargeSettings.vue")
    merchants = read_file("admin/src/views/AdminMerchants.vue")
    assert "确认审核入账" in recharge_orders
    assert "confirm_text" in recharge_orders
    assert "确认修改充值配置" in recharge_settings
    assert "确认删除二维码" in recharge_settings
    assert "确认调整额度" in merchants
    assert "确认授权应用" in merchants
```

- [ ] **Step 8: Verify audit and confirmation**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_recharge_approval_requires_confirmation_and_writes_audit tests\test_commercial_phase2.py::test_quota_grant_and_app_authorization_require_confirmation -q
pytest tests\test_frontend_static.py::test_phase2_sensitive_actions_use_fixed_confirmation_texts -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Update Engramory and commit**

Record the confirmation scopes and audit route. Do not record administrator tokens or passwords.

Run:

```powershell
git add audit_service.py routes_commercial.py routes_admin_advanced.py routes_admin.py tests/test_commercial_phase2.py admin/src/api/commercial.js admin/src/api/kami.js admin/src/views/AdminRechargeOrders.vue admin/src/views/AdminRechargeSettings.vue admin/src/views/AdminMerchants.vue admin/src/views/Kamis.vue admin/src/views/KamiBatches.vue tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: add admin audit confirmations"
```

Expected: commit succeeds.

---

### Task 3: Finance Operations and Exports

**Files:**
- Create: `finance_service.py`
- Modify: `routes_commercial.py`
- Modify: `tests/test_commercial_phase2.py`
- Create: `admin/src/api/finance.js`
- Create: `admin/src/views/AdminFinance.vue`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write failing finance tests**

Add these tests to `tests/test_commercial_phase2.py`:

```python
from datetime import datetime
from sqlmodel import Session, SQLModel

import routes_commercial
from main import app as fastapi_app
from models import RechargeOrder, RechargeOrderStatus, UserQuotaTransaction, UserQuotaTransactionType, UserQuotaType
from tests.test_commercial_phase1 import make_engine, override_session_factory, override_admin_user, seed_admin_and_merchant


def test_finance_summary_uses_admin_reviewed_at_for_approved_income():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)
        session.add(RechargeOrder(
            order_no="R202607250101",
            user_id=2,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            reviewed_at=datetime(2026, 7, 25, 10, 0, 0),
        ))
        session.add(RechargeOrder(
            order_no="R202607240101",
            user_id=2,
            username="merchant-a",
            amount=20,
            base_quota=20,
            bonus_quota=5,
            credit_quota=25,
            status=RechargeOrderStatus.approved,
            reviewed_at=datetime(2026, 7, 24, 10, 0, 0),
        ))
        session.add(RechargeOrder(
            order_no="R202607250102",
            user_id=2,
            username="merchant-a",
            amount=30,
            base_quota=30,
            bonus_quota=0,
            credit_quota=30,
            status=RechargeOrderStatus.pending_review,
        ))
        session.commit()

    try:
        response = client.get("/api/v1/admin/commercial/finance/summary", params={
            "start_date": "2026-07-25",
            "end_date": "2026-07-25",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["approved_order_count"] == 1
        assert data["approved_amount"] == 10
        assert data["credited_issue_quota"] == 10
        assert data["pending_review_count"] == 1
        assert data["income_basis"] == "reviewed_at"
        assert data["refund_amount"] == 0
        assert data["reversal_amount"] == 0
    finally:
        fastapi_app.dependency_overrides.clear()


def test_finance_exports_respect_filters_and_include_bom():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)
        session.add(RechargeOrder(
            order_no="R202607250201",
            user_id=2,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            reviewed_at=datetime(2026, 7, 25, 10, 0, 0),
        ))
        session.add(UserQuotaTransaction(
            transaction_no="Q202607250201",
            user_id=2,
            username="merchant-a",
            quota_type=UserQuotaType.issue_card,
            transaction_type=UserQuotaTransactionType.recharge,
            amount=10,
            balance_before=0,
            balance_after=10,
            biz_id="R202607250201",
            operator="admin",
        ))
        session.commit()

    try:
        orders = client.get("/api/v1/admin/commercial/recharge-orders/export", params={"status": "approved"})
        assert orders.status_code == 200
        assert orders.content.startswith(b"\xef\xbb\xbf")
        assert "R202607250201" in orders.content.decode("utf-8-sig")

        tx = client.get("/api/v1/admin/commercial/quota-transactions/export", params={"username": "merchant-a"})
        assert tx.status_code == 200
        assert "Q202607250201" in tx.content.decode("utf-8-sig")
    finally:
        fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the finance tests to verify they fail**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_finance_summary_uses_admin_reviewed_at_for_approved_income tests\test_commercial_phase2.py::test_finance_exports_respect_filters_and_include_bom -q
```

Expected: `FAIL` because finance endpoints and CSV exports are missing.

- [ ] **Step 3: Create finance service**

Create `finance_service.py` with these public functions:

```python
def parse_date_range(start_date: str | None, end_date: str | None) -> tuple[datetime | None, datetime | None]:
    ...

def finance_summary_payload(session: Session, start_date: str | None, end_date: str | None) -> dict:
    ...

def merchant_recharge_ranking_payload(session: Session, start_date: str | None, end_date: str | None, limit: int = 20) -> dict:
    ...

def recharge_orders_csv(session: Session, *, status: str | None, username: str | None, start_date: str | None, end_date: str | None) -> bytes:
    ...

def quota_transactions_csv(session: Session, *, username: str | None, transaction_type: str | None, start_date: str | None, end_date: str | None) -> bytes:
    ...
```

The summary returns:

```python
{
    "income_basis": "reviewed_at",
    "approved_order_count": approved_order_count,
    "approved_amount": approved_amount,
    "credited_issue_quota": credited_issue_quota,
    "bonus_issue_quota": bonus_issue_quota,
    "pending_review_count": pending_review_count,
    "rejected_count": rejected_count,
    "abnormal_count": abnormal_count,
    "approved_without_reviewed_at_count": approved_without_reviewed_at_count,
    "quota_transaction_count": quota_transaction_count,
    "refund_amount": 0,
    "reversal_amount": 0,
    "daily": daily_rows,
}
```

CSV exports must:

```python
import csv
import io

buffer = io.StringIO()
writer = csv.writer(buffer)
writer.writerow(["订单号", "用户", "金额", "到账发卡额度", "状态", "审核时间"])
return ("\ufeff" + buffer.getvalue()).encode("utf-8")
```

- [ ] **Step 4: Add admin finance routes**

In `routes_commercial.py`, add:

```python
@router.get("/finance/summary", summary="Commercial finance summary")
@router.get("/finance/merchant-ranking", summary="Commercial merchant recharge ranking")
@router.get("/recharge-orders/export", summary="Export recharge orders CSV")
@router.get("/quota-transactions/export", summary="Export issue quota transactions CSV")
```

Use `StreamingResponse` or `Response` with:

```python
media_type="text/csv; charset=utf-8"
headers={"Content-Disposition": 'attachment; filename="recharge-orders.csv"'}
```

- [ ] **Step 5: Add finance frontend**

Create `admin/src/api/finance.js`:

```javascript
import request from '../utils/request'

export function getFinanceSummary(params) {
  return request({ url: '/admin/commercial/finance/summary', method: 'get', params })
}

export function getMerchantRechargeRanking(params) {
  return request({ url: '/admin/commercial/finance/merchant-ranking', method: 'get', params })
}

export function exportRechargeOrders(params) {
  return request({ url: '/admin/commercial/recharge-orders/export', method: 'get', params, responseType: 'blob' })
}

export function exportQuotaTransactions(params) {
  return request({ url: '/admin/commercial/quota-transactions/export', method: 'get', params, responseType: 'blob' })
}
```

Create `admin/src/views/AdminFinance.vue` with:

```text
Top filters: date range, username keyword, status shortcut.
Cards: 已审核收入, 已到账发卡额度, 赠送额度, 待审核订单, 异常订单.
Tables: 每日收入统计, 用户充值排行.
Buttons: 导出订单流水, 导出额度流水.
```

No refund or reversal controls appear on the page.

- [ ] **Step 6: Wire route and menu**

In `admin/src/router/index.js`, add admin route:

```javascript
{
  path: '/admin/commercial/finance',
  name: 'AdminFinance',
  component: () => import('@/views/AdminFinance.vue'),
  meta: { title: '财务运营', requiresAuth: true, role: 'admin' }
}
```

In `admin/src/layouts/MainLayout.vue`, add admin menu item `财务运营` under commercial operation entries. Do not add it to merchant navigation.

- [ ] **Step 7: Add frontend static tests**

Add:

```python
def test_phase2_finance_page_has_reviewed_at_income_scope_and_exports():
    router = read_file("admin/src/router/index.js")
    layout = read_file("admin/src/layouts/MainLayout.vue")
    finance_api = read_file("admin/src/api/finance.js")
    finance_view = read_file("admin/src/views/AdminFinance.vue")
    assert "/admin/commercial/finance" in router
    assert "财务运营" in layout
    assert "/admin/commercial/finance/summary" in finance_api
    assert "/admin/commercial/recharge-orders/export" in finance_api
    assert "审核通过时间" in finance_view
    assert "退款" not in finance_view
    assert "冲正" not in finance_view
```

- [ ] **Step 8: Verify finance**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_finance_summary_uses_admin_reviewed_at_for_approved_income tests\test_commercial_phase2.py::test_finance_exports_respect_filters_and_include_bom -q
pytest tests\test_frontend_static.py::test_phase2_finance_page_has_reviewed_at_income_scope_and_exports -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Update Engramory and commit**

Record the finance统计口径: approved recharge orders grouped by `reviewed_at`; no refund or reversal flow.

Run:

```powershell
git add finance_service.py routes_commercial.py tests/test_commercial_phase2.py admin/src/api/finance.js admin/src/views/AdminFinance.vue admin/src/router/index.js admin/src/layouts/MainLayout.vue tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: add commercial finance reporting"
```

Expected: commit succeeds.

---

### Task 4: Merchant Card Search, Export, Batch Stats, and Quota Warning

**Files:**
- Create: `kami_query_service.py`
- Modify: `routes_merchant.py`
- Modify: `routes_admin.py`
- Modify: `tests/test_commercial_phase2.py`
- Modify: `admin/src/api/merchant.js`
- Modify: `admin/src/api/kami.js`
- Modify: `admin/src/views/MerchantCards.vue`
- Modify: `admin/src/views/MerchantBatches.vue`
- Modify: `admin/src/views/Kamis.vue`
- Modify: `admin/src/views/KamiBatches.vue`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write failing card query tests**

Add:

```python
from models import App, Kami, KamiBatch, KamiStatus


def test_merchant_global_kami_search_is_scoped_and_export_matches_filter():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        other = EndUser(username="merchant-b", password_hash="hash", status=1)
        app = App(app_id="app-a", name="App A", app_secret="secret", rsa_public_key="pub", rsa_private_key="priv", owner_user_id=merchant.id)
        session.add(other)
        session.add(app)
        session.commit()
        session.add(Kami(app_id="app-a", kami_code="MERCHANT-A-001", kami_type="day", status=KamiStatus.unused, created_by_user_id=merchant.id, batch_no="B-A"))
        session.add(Kami(app_id="app-a", kami_code="MERCHANT-B-001", kami_type="day", status=KamiStatus.unused, created_by_user_id=other.id, batch_no="B-B"))
        session.commit()

    fastapi_app.dependency_overrides[routes_merchant.get_current_merchant] = lambda: {"sub": "merchant-a", "user_id": 2, "role": "merchant"}
    try:
        listed = client.get("/api/v1/merchant/kamis", params={"keyword": "MERCHANT"})
        assert listed.status_code == 200
        codes = [item["kami_code"] for item in listed.json()["items"]]
        assert codes == ["MERCHANT-A-001"]

        exported = client.get("/api/v1/merchant/kamis/export", params={"keyword": "MERCHANT-A"})
        assert exported.status_code == 200
        text = exported.content.decode("utf-8-sig")
        assert "MERCHANT-A-001" in text
        assert "MERCHANT-B-001" not in text
    finally:
        fastapi_app.dependency_overrides.clear()


def test_merchant_batches_include_status_stats_and_low_quota_warning():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_merchant.get_current_merchant] = lambda: {"sub": "merchant-a", "user_id": 2, "role": "merchant"}
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        _, merchant = seed_admin_and_merchant(session)
        account = UserQuotaAccount(user_id=merchant.id, username=merchant.username, issue_balance=5)
        app = App(app_id="app-b", name="App B", app_secret="secret", rsa_public_key="pub", rsa_private_key="priv", owner_user_id=merchant.id)
        batch = KamiBatch(app_id="app-b", batch_no="B-STATS", quantity=2, kami_type="day", created_by_user_id=merchant.id, total_issue_cost=2)
        session.add(account)
        session.add(app)
        session.add(batch)
        session.add(Kami(app_id="app-b", kami_code="B-STATS-1", kami_type="day", status=KamiStatus.unused, created_by_user_id=merchant.id, batch_no="B-STATS"))
        session.add(Kami(app_id="app-b", kami_code="B-STATS-2", kami_type="day", status=KamiStatus.active, created_by_user_id=merchant.id, batch_no="B-STATS"))
        session.commit()

    try:
        batches = client.get("/api/v1/merchant/apps/app-b/batches")
        assert batches.status_code == 200
        item = batches.json()["items"][0]
        assert item["stats"]["unused_count"] == 1
        assert item["stats"]["active_count"] == 1
        assert item["total_issue_cost"] == 2

        quotas = client.get("/api/v1/merchant/quotas")
        assert quotas.status_code == 200
        assert quotas.json()["issue_card"]["low_balance_warning"] is True
    finally:
        fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run card query tests to verify they fail**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_merchant_global_kami_search_is_scoped_and_export_matches_filter tests\test_commercial_phase2.py::test_merchant_batches_include_status_stats_and_low_quota_warning -q
```

Expected: `FAIL` because global merchant card search/export and enriched batch stats are missing.

- [ ] **Step 3: Create shared card query service**

Create `kami_query_service.py` with:

```python
def merchant_kami_statement(
    session: Session,
    *,
    user_id: int,
    app_id: str | None,
    keyword: str | None,
    status: str | None,
    batch_no: str | None,
):
    ...

def admin_kami_statement(
    session: Session,
    *,
    app_id: str | None,
    keyword: str | None,
    status: str | None,
    batch_no: str | None,
    created_by_user_id: int | None,
):
    ...

def kami_search_payload(session: Session, statement, *, page: int, page_size: int) -> dict:
    ...

def kami_csv(session: Session, statement) -> bytes:
    ...

def batch_stats_payload(session: Session, batch: KamiBatch) -> dict:
    ...
```

`merchant_kami_statement` must require `Kami.created_by_user_id == user_id`. Authorized admin apps and merchant self-owned apps are both visible only when the merchant generated those cards.

`batch_stats_payload` returns:

```python
{
    "total_count": total_count,
    "unused_count": unused_count,
    "active_count": active_count,
    "frozen_count": frozen_count,
    "expired_count": expired_count,
    "device_bound_count": device_bound_count,
}
```

- [ ] **Step 4: Add backend routes**

In `routes_merchant.py`, add:

```python
@router.get("/kamis", summary="List merchant issued kamis across visible apps")
@router.get("/kamis/export", summary="Export merchant issued kamis CSV")
```

Enhance existing:

```text
GET /api/v1/merchant/apps/{app_id}/batches
GET /api/v1/merchant/quotas
```

In `routes_admin.py`, keep existing admin routes and add shared filters to:

```text
GET /api/v1/admin/kamis
GET /api/v1/admin/kamis/batches
GET /api/v1/admin/kamis/export
```

- [ ] **Step 5: Add frontend API methods**

In `admin/src/api/merchant.js`:

```javascript
export function getMerchantKamis(params) {
  return request({ url: '/merchant/kamis', method: 'get', params })
}

export function exportMerchantKamis(params) {
  return request({ url: '/merchant/kamis/export', method: 'get', params, responseType: 'blob' })
}
```

In `admin/src/api/kami.js`, make `exportKamis(params)` pass all active filters.

- [ ] **Step 6: Update card and batch pages**

`MerchantCards.vue`:

```text
Toolbar: app selector, keyword input, status selector, batch number input, search button, reset button, export button.
Table: card code, app name, batch number, type/spec, status, created time, activation time, bound device count.
Export: uses the same filters currently applied to the table.
```

`MerchantBatches.vue`:

```text
Show total cards, unused, active, frozen, expired, bound device count, total issue cost.
Show a low-balance warning above generation form when issue quota balance is less than configured threshold.
```

`Kamis.vue` and `KamiBatches.vue` get the same filter-to-export rule for管理员.

- [ ] **Step 7: Add frontend static tests**

Add:

```python
def test_phase2_merchant_card_search_export_and_batch_stats_are_visible():
    merchant_api = read_file("admin/src/api/merchant.js")
    merchant_cards = read_file("admin/src/views/MerchantCards.vue")
    merchant_batches = read_file("admin/src/views/MerchantBatches.vue")
    assert "/merchant/kamis" in merchant_api
    assert "/merchant/kamis/export" in merchant_api
    assert "批次号" in merchant_cards
    assert "导出" in merchant_cards
    assert "低额度" in merchant_batches
    assert "unused_count" in merchant_batches
    assert "active_count" in merchant_batches
```

- [ ] **Step 8: Verify card operations**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_merchant_global_kami_search_is_scoped_and_export_matches_filter tests\test_commercial_phase2.py::test_merchant_batches_include_status_stats_and_low_quota_warning -q
pytest tests\test_frontend_static.py::test_phase2_merchant_card_search_export_and_batch_stats_are_visible -q
```

Expected: all selected tests pass.

- [ ] **Step 9: Update Engramory and commit**

Record the merchant card visibility rule: merchants can search/export only cards they generated, regardless of self-owned app or admin-authorized app.

Run:

```powershell
git add kami_query_service.py routes_merchant.py routes_admin.py tests/test_commercial_phase2.py admin/src/api/merchant.js admin/src/api/kami.js admin/src/views/MerchantCards.vue admin/src/views/MerchantBatches.vue admin/src/views/Kamis.vue admin/src/views/KamiBatches.vue tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: improve merchant card operations"
```

Expected: commit succeeds.

---

### Task 5: Admin Operations Center

**Files:**
- Create: `ops_service.py`
- Create: `routes_ops.py`
- Modify: `main.py`
- Modify: `commercial_service.py`
- Modify: `tests/test_commercial_phase2.py`
- Create: `admin/src/api/ops.js`
- Create: `admin/src/views/AdminOps.vue`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write failing ops tests**

Add:

```python
from pathlib import Path
from sqlmodel import Session, SQLModel, select

import routes_ops
from main import app as fastapi_app
from models import OpsBackupRecord, RechargeOrder, RechargeOrderStatus


def test_ops_health_backup_and_safe_download(tmp_path, monkeypatch):
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

        created = client.post("/api/v1/admin/ops/backups", json={"backup_type": "database", "confirm_text": "确认创建备份"})
        assert created.status_code == 200
        backup_no = created.json()["backup_no"]

        with Session(engine) as session:
            record = session.exec(select(OpsBackupRecord).where(OpsBackupRecord.backup_no == backup_no)).one()
            assert record.status == "succeeded"
            assert Path(record.file_path).exists()

        denied = client.post("/api/v1/admin/ops/backups/../../etc/passwd/download", json={"confirm_text": "确认下载备份"})
        assert denied.status_code in (400, 404)
    finally:
        fastapi_app.dependency_overrides.clear()


def test_ops_upload_cleanup_marks_terminal_proofs_only(tmp_path, monkeypatch):
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    uploads = tmp_path / "uploads"
    proofs = uploads / "commercial" / "proofs"
    proofs.mkdir(parents=True)
    old_file = proofs / "old.jpg"
    pending_file = proofs / "pending.jpg"
    old_file.write_bytes(b"old")
    pending_file.write_bytes(b"pending")
    monkeypatch.setattr("commercial_service.UPLOAD_ROOT", uploads)
    fastapi_app.dependency_overrides[routes_ops.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_ops.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)
        session.add(RechargeOrder(
            order_no="R202607250301",
            user_id=2,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.approved,
            proof_file_path=str(old_file),
            proof_file_name="old.jpg",
            proof_content_type="image/jpeg",
            reviewed_at=datetime(2026, 6, 1, 10, 0, 0),
        ))
        session.add(RechargeOrder(
            order_no="R202607250302",
            user_id=2,
            username="merchant-a",
            amount=10,
            base_quota=10,
            bonus_quota=0,
            credit_quota=10,
            status=RechargeOrderStatus.pending_review,
            proof_file_path=str(pending_file),
            proof_file_name="pending.jpg",
            proof_content_type="image/jpeg",
        ))
        session.commit()

    try:
        preview = client.post("/api/v1/admin/ops/uploads/proofs/cleanup", json={"older_than_days": 1, "dry_run": True})
        assert preview.status_code == 200
        assert preview.json()["matched_count"] == 1
        assert old_file.exists()

        cleanup = client.post(
            "/api/v1/admin/ops/uploads/proofs/cleanup",
            json={"older_than_days": 1, "dry_run": False, "confirm_text": "确认清理凭证"},
        )
        assert cleanup.status_code == 200
        assert cleanup.json()["deleted_count"] == 1
        assert not old_file.exists()
        assert pending_file.exists()

        with Session(engine) as session:
            order = session.exec(select(RechargeOrder).where(RechargeOrder.order_no == "R202607250301")).one()
            assert order.proof_file_deleted is True
            assert order.proof_deleted_at is not None
    finally:
        fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run ops tests to verify they fail**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_ops_health_backup_and_safe_download tests\test_commercial_phase2.py::test_ops_upload_cleanup_marks_terminal_proofs_only -q
```

Expected: `FAIL` because `routes_ops.py` and `ops_service.py` do not exist.

- [ ] **Step 3: Create ops service**

Create `ops_service.py` with:

```python
def ops_health_payload(session: Session) -> dict:
    ...

def create_database_backup(session: Session, *, created_by: str, backup_root: str) -> OpsBackupRecord:
    ...

def create_uploads_backup(*, created_by: str, backup_root: str, uploads_root: str) -> OpsBackupRecord:
    ...

def safe_backup_path(record: OpsBackupRecord, backup_root: str) -> Path:
    ...

def recent_error_logs(log_root: str = "logs", max_lines: int = 200) -> dict:
    ...
```

Backup rules:

```text
- Do not execute shell commands.
- Database backup writes JSONL.GZ by table using SQLAlchemy inspector and SELECT *.
- File backup writes TAR.GZ from /app/uploads only.
- Backup files are stored only under settings.BACKUP_ROOT.
- Download rejects paths whose resolved path is not inside BACKUP_ROOT.
- Backup records store metadata, not file content.
```

`ops_health_payload` returns:

```python
{
    "database": {"ok": True, "message": "connected"},
    "uploads": {"ok": True, "path": settings.UPLOAD_ROOT},
    "backups": {"ok": True, "path": settings.BACKUP_ROOT},
    "logs": {"ok": True, "path": "logs"},
    "recent_errors": recent_error_count,
}
```

- [ ] **Step 4: Improve proof cleanup metadata**

In `commercial_service.cleanup_recharge_proofs`, when `dry_run is False` and a terminal proof file is deleted or already missing, set:

```python
order.proof_file_deleted = True
order.proof_deleted_at = get_now_naive()
order.proof_file_path = None
order.proof_file_name = None
order.proof_content_type = None
```

Pending orders must never be changed by lifecycle cleanup.

- [ ] **Step 5: Add ops routes**

Create `routes_ops.py`:

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/admin/ops", tags=["Admin Ops"])

@router.get("/health", summary="Admin ops health")
@router.get("/backups", summary="List ops backups")
@router.post("/backups", summary="Create ops backup")
@router.post("/backups/{backup_no}/download", summary="Download ops backup")
@router.post("/uploads/proofs/cleanup", summary="Clean old recharge proof files")
@router.get("/logs/recent-errors", summary="Read recent application errors")
```

Backup create and download must call `require_sensitive_confirmation` with `create_ops_backup` or `download_ops_backup`.

- [ ] **Step 6: Register ops router**

In `main.py`, import and include:

```python
from routes_ops import router as ops_router

app.include_router(ops_router)
```

- [ ] **Step 7: Add ops frontend**

Create `admin/src/api/ops.js`:

```javascript
import request from '../utils/request'

export function getOpsHealth() {
  return request({ url: '/admin/ops/health', method: 'get' })
}

export function getOpsBackups(params) {
  return request({ url: '/admin/ops/backups', method: 'get', params })
}

export function createOpsBackup(data) {
  return request({ url: '/admin/ops/backups', method: 'post', data })
}

export function downloadOpsBackup(backupNo, data) {
  return request({ url: `/admin/ops/backups/${backupNo}/download`, method: 'post', data, responseType: 'blob' })
}

export function cleanupProofUploads(data) {
  return request({ url: '/admin/ops/uploads/proofs/cleanup', method: 'post', data })
}

export function getRecentErrorLogs(params) {
  return request({ url: '/admin/ops/logs/recent-errors', method: 'get', params })
}
```

Create `admin/src/views/AdminOps.vue`:

```text
Sections: health cards, backup list, create database backup, create uploads backup, download backup, proof cleanup dry-run/result, recent errors.
Buttons requiring confirmation: 创建备份, 下载备份, 执行凭证清理.
No arbitrary shell command input appears in the UI.
```

- [ ] **Step 8: Wire route/menu and static tests**

In router:

```javascript
{
  path: '/admin/ops',
  name: 'AdminOps',
  component: () => import('@/views/AdminOps.vue'),
  meta: { title: '运维中心', requiresAuth: true, role: 'admin' }
}
```

Static test:

```python
def test_phase2_ops_center_has_safe_backup_and_cleanup_controls():
    router = read_file("admin/src/router/index.js")
    layout = read_file("admin/src/layouts/MainLayout.vue")
    ops_api = read_file("admin/src/api/ops.js")
    ops_view = read_file("admin/src/views/AdminOps.vue")
    assert "/admin/ops" in router
    assert "运维中心" in layout
    assert "/admin/ops/backups" in ops_api
    assert "确认创建备份" in ops_view
    assert "确认清理凭证" in ops_view
    assert "shell" not in ops_view.lower()
```

- [ ] **Step 9: Verify ops**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_ops_health_backup_and_safe_download tests\test_commercial_phase2.py::test_ops_upload_cleanup_marks_terminal_proofs_only -q
pytest tests\test_frontend_static.py::test_phase2_ops_center_has_safe_backup_and_cleanup_controls -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Update Engramory and commit**

Record the backup location contract and upload cleanup lifecycle rule.

Run:

```powershell
git add ops_service.py routes_ops.py main.py commercial_service.py tests/test_commercial_phase2.py admin/src/api/ops.js admin/src/views/AdminOps.vue admin/src/router/index.js admin/src/layouts/MainLayout.vue tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: add admin ops center"
```

Expected: commit succeeds.

---

### Task 6: Audit Log Page and Navigation Cleanup

**Files:**
- Create: `admin/src/api/audit.js`
- Create: `admin/src/views/AdminAuditLogs.vue`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Write failing static test**

Add:

```python
def test_phase2_audit_page_is_admin_only_and_visible():
    router = read_file("admin/src/router/index.js")
    layout = read_file("admin/src/layouts/MainLayout.vue")
    audit_api = read_file("admin/src/api/audit.js")
    audit_view = read_file("admin/src/views/AdminAuditLogs.vue")
    assert "/admin/commercial/audit-logs" in router
    assert "操作审计" in layout
    assert "/admin/commercial/audit-logs" in audit_api
    assert "管理员" in audit_view
    assert "操作类型" in audit_view
    assert "操作结果" in audit_view
```

- [ ] **Step 2: Run static test to verify it fails**

Run:

```powershell
pytest tests\test_frontend_static.py::test_phase2_audit_page_is_admin_only_and_visible -q
```

Expected: `FAIL` because audit API/page/route/menu are missing.

- [ ] **Step 3: Create audit API**

Create `admin/src/api/audit.js`:

```javascript
import request from '../utils/request'

export function getAdminAuditLogs(params) {
  return request({ url: '/admin/commercial/audit-logs', method: 'get', params })
}
```

- [ ] **Step 4: Create audit page**

Create `admin/src/views/AdminAuditLogs.vue` with:

```text
Top filters: 操作类型, 操作结果, 关键词, 日期范围.
Table columns: 时间, 管理员, 操作类型, 对象类型, 对象编号, 目标用户, 操作结果, 摘要.
Detail drawer: 请求 IP, 浏览器, 错误信息, before/after JSON.
```

The page is read-only. It has no delete or clear button.

- [ ] **Step 5: Wire route and menu**

Router:

```javascript
{
  path: '/admin/commercial/audit-logs',
  name: 'AdminAuditLogs',
  component: () => import('@/views/AdminAuditLogs.vue'),
  meta: { title: '操作审计', requiresAuth: true, role: 'admin' }
}
```

Menu:

```text
管理员导航显示 操作审计。
商户导航不显示 操作审计。
```

- [ ] **Step 6: Verify audit page**

Run:

```powershell
pytest tests\test_frontend_static.py::test_phase2_audit_page_is_admin_only_and_visible -q
```

Expected: `1 passed`.

- [ ] **Step 7: Update Engramory and commit**

Record that the audit page is admin-only and read-only.

Run:

```powershell
git add admin/src/api/audit.js admin/src/views/AdminAuditLogs.vue admin/src/router/index.js admin/src/layouts/MainLayout.vue tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "feat: add admin audit console"
```

Expected: commit succeeds.

---

### Task 7: Full Local Verification and Phase 2 Acceptance

**Files:**
- Modify: `tests/test_commercial_phase2.py`
- Modify: `tests/test_frontend_static.py`
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Add integrated acceptance tests**

Add:

```python
def test_phase2_acceptance_recharge_approval_finance_audit_and_export_flow():
    engine = make_phase2_engine()
    SQLModel.metadata.create_all(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_session] = override_session_factory(engine)
    fastapi_app.dependency_overrides[routes_commercial.get_current_admin] = override_admin_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        seed_admin_and_merchant(session)
        session.add(RechargeOrder(
            order_no="R202607250401",
            user_id=2,
            username="merchant-a",
            amount=30,
            base_quota=30,
            bonus_quota=5,
            credit_quota=35,
            status=RechargeOrderStatus.pending_review,
        ))
        session.commit()

    try:
        approved = client.post(
            "/api/v1/admin/commercial/recharge-orders/R202607250401/approve",
            json={"confirm_text": "确认审核入账"},
        )
        assert approved.status_code == 200

        finance = client.get("/api/v1/admin/commercial/finance/summary", params={"start_date": "2026-07-25", "end_date": "2026-07-25"})
        assert finance.status_code == 200
        assert finance.json()["approved_amount"] == 30
        assert finance.json()["credited_issue_quota"] == 35

        audits = client.get("/api/v1/admin/commercial/audit-logs", params={"action": "approve_recharge_order"})
        assert audits.status_code == 200
        assert audits.json()["items"][0]["status"] == "success"

        exported = client.get("/api/v1/admin/commercial/recharge-orders/export", params={"status": "approved"})
        assert exported.status_code == 200
        assert "R202607250401" in exported.content.decode("utf-8-sig")
    finally:
        fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run integrated acceptance test**

Run:

```powershell
pytest tests\test_commercial_phase2.py::test_phase2_acceptance_recharge_approval_finance_audit_and_export_flow -q
```

Expected: `1 passed`.

- [ ] **Step 3: Run complete backend tests**

Run:

```powershell
pytest -q
```

Expected: all tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```powershell
npm run build
```

Working directory: `admin`

Expected: Vite build completes successfully and exits with code `0`.

- [ ] **Step 5: Run frontend static tests**

Run:

```powershell
pytest tests\test_frontend_static.py -q
```

Expected: all frontend static tests pass.

- [ ] **Step 6: Update Engramory**

Record:

```text
2026-07-25: Phase 2 local verification passed with pytest and admin frontend build. Finance uses reviewed_at. No proxy, automatic payment, refund/reversal, or new roles were introduced.
```

- [ ] **Step 7: Commit verification tests**

Run:

```powershell
git add tests/test_commercial_phase2.py tests/test_frontend_static.py .engramory-memory/2026-07-24-commercial-phase1-backend.md
git commit -m "test: verify phase two workflows"
```

Expected: commit succeeds when test files changed after previous commits. If there are no changes, skip this commit and record that no verification-only commit was needed.

---

### Task 8: Deployment and Production Validation

**Files:**
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] **Step 1: Confirm local branch state**

Run:

```powershell
git status --short
git branch --show-current
git log -1 --oneline
```

Expected:

```text
current branch is main
only intended files are committed
latest commit is the phase 2 final commit
```

If `admin/package-lock.json` is dirty from an unrelated earlier local change, do not stage it unless a current task modified dependencies and `package.json` changed with it.

- [ ] **Step 2: Push main**

Run with the working proxy pattern already used by this project:

```powershell
git -c http.proxy=http://127.0.0.1:9674 -c https.proxy=http://127.0.0.1:9674 push origin main
```

Expected: push succeeds.

- [ ] **Step 3: Wait for GitHub Actions**

Use the existing project deployment workflow and wait until the run for the pushed commit finishes.

Expected: workflow conclusion is `success`.

- [ ] **Step 4: Production smoke checks**

Run read-only checks first:

```powershell
Invoke-WebRequest -Uri http://154.12.26.231/health -UseBasicParsing
Invoke-WebRequest -Uri http://154.12.26.231/admin/dashboard -UseBasicParsing
Invoke-WebRequest -Uri http://154.12.26.231/admin/commercial/finance -UseBasicParsing
Invoke-WebRequest -Uri http://154.12.26.231/admin/commercial/audit-logs -UseBasicParsing
Invoke-WebRequest -Uri http://154.12.26.231/admin/ops -UseBasicParsing
```

Expected: each page route returns `200` and the SPA shell loads.

- [ ] **Step 5: Production authenticated API checks**

Using the existing administrator account supplied by the user in the current project thread, obtain a temporary token in memory only. Do not write the password or token to files or Engramory.

Verify:

```text
GET /api/v1/admin/commercial/finance/summary -> 200
GET /api/v1/admin/commercial/audit-logs -> 200
GET /api/v1/admin/ops/health -> 200
GET /api/v1/admin/ops/backups -> 200
GET /api/v1/admin/commercial/recharge-orders/export -> 200 CSV
GET /api/v1/admin/commercial/quota-transactions/export -> 200 CSV
```

- [ ] **Step 6: Production controlled write validation with cleanup**

Use a test prefix `PHASE2_QA_YYYYMMDDHHMMSS`. Create only temporary merchant/order/card data, then delete it after assertions.

Validate:

```text
1. Register test merchant.
2. Admin grants a small issue quota with confirm_text "确认调整额度".
3. Merchant creates a self-owned app.
4. Merchant generates one small card batch; quota decreases by exact total cost.
5. Merchant card search returns only the generated card.
6. Merchant card export contains the generated card.
7. Merchant submits a small no-scan manual recharge order using configured payment channel and amount.
8. Admin approval without confirm_text returns 400.
9. Admin approval with "确认审核入账" returns 200.
10. User quota increases by exact credited quota.
11. Finance summary includes the approved amount by reviewed_at.
12. Audit log contains success rows for quota grant and recharge approval.
13. Proof cleanup dry-run returns safe counts and does not delete pending proof files.
14. Delete temporary merchant and temporary self-owned app.
15. Confirm no PHASE2_QA_ users, apps, cards, batches, recharge orders, quota transactions, devices, or logs remain except admin audit rows.
```

Audit rows may remain because they are the historical record of administrator actions.

- [ ] **Step 7: Update Engramory after production verification**

Record deployment commit, GitHub Actions run id, production health result, and QA cleanup result. Do not record credentials, tokens, payment QR URLs, card codes, or temporary passwords.

---

## Self-Review Checklist

- 财务运营 is covered by Task 3 and Task 7: order reconciliation, income stats, approved-time basis, order CSV, quota transaction CSV.
- 退款 and 冲正 are explicitly out of scope; finance response returns zero fields for display clarity and no mutation route exists.
- 权限审计 is covered by Task 2 and Task 6: audit model, audit route, read-only audit page, sensitive confirmation for high-impact admin actions.
- No new role is introduced; existing admin and merchant identities are preserved.
- 商户体验 is covered by Task 4: global card search, filtered export, enriched batch stats, low issue quota warning.
- 稳定性 is covered by Task 5 and Task 8: health aggregation, backup, safe backup download, recent errors, proof lifecycle cleanup, production validation.
- Upload lifecycle is covered without storing images in memory or DB blobs.
- Backup strategy avoids arbitrary shell and does not depend on `mysqldump` being installed in the Docker image.
- API identity remains token user id, `app_id`, `order_no`, `batch_no`, and `transaction_no`; no username or app name is used as path identity for business ownership.
- Merchant scope remains strict: merchants can see/export only their own generated cards and their own recharge records.
- Admin scope remains separate from merchant navigation; no merchant page receives finance, audit, or ops menu entries.
