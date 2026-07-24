import json
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from fastapi import HTTPException, Request
from sqlmodel import Session

from datetime_utils import to_api_beijing_iso
from models import AdminAuditLog, AdminUser


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


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def audit_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def _admin_identity(admin: dict | AdminUser) -> tuple[Optional[int], str]:
    if isinstance(admin, AdminUser):
        return admin.id, admin.username
    admin_id = admin.get("user_id") or admin.get("id")
    return admin_id, admin.get("sub") or admin.get("username") or "unknown"


def _request_identity(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    if request is None:
        return None, None
    forwarded_for = request.headers.get("x-forwarded-for")
    request_ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else None
    if not request_ip and request.client:
        request_ip = request.client.host
    return request_ip, request.headers.get("user-agent")


def record_admin_audit(
    session: Session,
    *,
    admin: dict | AdminUser,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    status: str = "success",
    confirm_scope: Optional[str] = None,
    request: Optional[Request] = None,
    summary: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
    error_message: Optional[str] = None,
) -> AdminAuditLog:
    admin_id, admin_username = _admin_identity(admin)
    request_ip, user_agent = _request_identity(request)
    log = AdminAuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        admin_id=admin_id,
        admin_username=admin_username,
        target_user_id=target_user_id,
        target_username=target_username,
        status=status,
        confirm_scope=confirm_scope or action,
        request_ip=request_ip,
        user_agent=user_agent,
        summary=summary,
        before_json=audit_json(before),
        after_json=audit_json(after),
        metadata_json=audit_json(metadata),
        error_message=error_message,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def require_sensitive_confirmation(
    session: Session,
    *,
    admin: dict | AdminUser,
    action: str,
    confirm_text: Optional[str],
    resource_type: str,
    resource_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    request: Optional[Request] = None,
    summary: Optional[str] = None,
    metadata: Any = None,
) -> None:
    expected = CONFIRM_TEXT_BY_SCOPE[action]
    if confirm_text == expected:
        return
    record_admin_audit(
        session,
        admin=admin,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=target_user_id,
        target_username=target_username,
        status="failed",
        confirm_scope=action,
        request=request,
        summary=summary,
        metadata={"expected": expected, **(metadata or {})},
        error_message="sensitive confirmation mismatch",
    )
    raise HTTPException(
        status_code=400,
        detail={
            "message": "Sensitive action confirmation text mismatch",
            "expected": expected,
        },
    )


def _parse_json(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def audit_log_payload(log: AdminAuditLog) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "admin_id": log.admin_id,
        "admin_username": log.admin_username,
        "target_user_id": log.target_user_id,
        "target_username": log.target_username,
        "status": log.status,
        "confirm_scope": log.confirm_scope,
        "request_ip": log.request_ip,
        "user_agent": log.user_agent,
        "summary": log.summary,
        "before": _parse_json(log.before_json),
        "after": _parse_json(log.after_json),
        "metadata": _parse_json(log.metadata_json),
        "error_message": log.error_message,
        "created_at": to_api_beijing_iso(log.created_at, naive="civil"),
    }
