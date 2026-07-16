"""
Admin 管理后台接口路由
包含应用管理、卡密管理、日志查询等接口
需要 JWT 认证
"""

import uuid
import string
import random
import json
import csv
import io
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# 中国时区
CST = ZoneInfo("Asia/Shanghai")

def get_now():
    """获取当前中国时间"""
    return datetime.now(CST)
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select
from database import get_session
from redis_client import get_redis
from models import (
    App,
    Kami,
    EventLog,
    Device,
    AdminUser,
    AdminRole,
    EndUser,
    UserPointAccount,
    UserPointLot,
    PointTransaction,
    PointTransactionType,
    KamiType,
    KamiStatus,
    MachineBindMode,
    KamiBatch,
    KamiDeviceBinding,
    AppAuthorization,
    ApiInterface,
    AppInterfaceConfig,
    AuthorizationAccount,
    AuthorizationLot,
    AuthorizationOwnerMode,
    AuthorizationOwnerType,
    UserBindMode,
)
from datetime_utils import to_api_beijing_iso
from crypto import RSACrypto
from config import settings
from jose import jwt, JWTError
import os
from passlib.context import CryptContext
from point_service import PointServiceError, adjust_points
from authorization_service import (
    get_or_create_authorization_account,
    grant_points,
    grant_time,
    grant_times,
)
from interface_catalog import BUILTIN_API_INTERFACES


logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash passwords with bcrypt."""
    return pwd_context.hash(password)


def _verify_legacy_sha256_password(plain_password: str, hashed_password: str) -> bool:
    import hashlib

    try:
        salt, stored_hash = hashed_password.split("$", 1)
    except ValueError:
        return False
    password_hash = hashlib.sha256((plain_password + salt).encode("utf-8")).hexdigest()
    return password_hash == stored_hash


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    if not hashed_password:
        return False
    if "$" in hashed_password and not hashed_password.startswith("$2"):
        return _verify_legacy_sha256_password(plain_password, hashed_password)
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    if not hashed_password:
        return True
    if "$" in hashed_password and not hashed_password.startswith("$2"):
        return True
    try:
        return pwd_context.needs_update(hashed_password)
    except Exception:
        return True


def _cleanup_used_times_kamis(session: Session, app_id: str):
    """
    自动清理过期次数卡。

    次数卡现在通过 times_remaining 精确扣减，不能因为已经绑定设备就删除。
    """
    # get_now() 返回带时区的时间，需要去掉时区信息后与数据库中的 naive datetime 比较
    now = get_now().replace(tzinfo=None)
    
    # 查找过期的次数卡
    expired_kamis = session.exec(
        select(Kami).where(
            Kami.app_id == app_id,
            Kami.kami_type == KamiType.times,
            Kami.status == KamiStatus.active,
            Kami.expire_time < now
        )
    ).all()
    
    # 删除过期的次数卡
    for kami in expired_kamis:
        session.delete(kami)
    
    # 提交删除操作
    if expired_kamis:
        session.commit()


def _authorization_summary_payload(account: Optional[AuthorizationAccount]) -> dict:
    if not account:
        return {
            "authorization_account_id": None,
            "time_authorization": "-",
            "is_lifetime": False,
            "times_remaining": 0,
            "points_remaining": 0,
        }
    if account.is_lifetime:
        time_authorization = "永久"
    elif account.time_expires_at:
        time_authorization = to_api_beijing_iso(account.time_expires_at, naive="civil")
    else:
        time_authorization = "-"
    return {
        "authorization_account_id": account.id,
        "time_authorization": time_authorization,
        "is_lifetime": account.is_lifetime,
        "times_remaining": account.times_balance,
        "points_remaining": account.points_balance,
    }


def check_app_permission(session: Session, app_id: str, username: str, is_admin: bool) -> bool:
    """
    检查用户是否有权限操作应用
    - admin 用户有所有权限
    - 应用创建者有权限
    """
    if is_admin:
        return True
    
    # 检查是否是创建者
    statement = select(App).where(App.app_id == app_id)
    app = session.exec(statement).first()
    if app and app.created_by == username:
        return True

    return False


def build_audit_diff(
    before: dict,
    after: dict,
    sensitive_fields: Optional[set[str]] = None,
) -> dict:
    sensitive = sensitive_fields or set()
    diff = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value == after_value:
            continue
        if key in sensitive:
            diff[key] = {"before": "***", "after": "***"}
        else:
            diff[key] = {"before": before_value, "after": after_value}
    return diff


def log_admin_action(session: Session, username: str, event_type: str, app_id: Optional[str] = None, 
                     payload: Optional[dict] = None, status: int = 1, message: Optional[str] = None):
    """
    记录管理员操作日志
    
    Args:
        session: 数据库会话
        username: 操作用户名
        event_type: 事件类型
        app_id: 应用ID（可选）
        payload: 额外数据（字典）
        status: 状态（1成功，0失败）
        message: 消息描述
    """
    import json
    
    log = EventLog(
        app_id=app_id,
        event_type=event_type,
        payload=json.dumps(payload) if payload else None,
        status=status,
        message=message or f"用户 {username} 执行了 {event_type} 操作",
        # get_now() 返回带时区的时间，需要去掉时区信息后存入数据库
        created_at=get_now().replace(tzinfo=None)
    )
    session.add(log)
    session.commit()

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])
_runtime_login_aes_key_b64: Optional[str] = None


class PointAdjustRequest(BaseModel):
    user_id: int
    amount: int = PydanticField(..., description="Positive to add points, negative to deduct")
    biz_id: Optional[str] = None
    remark: Optional[str] = None
    metadata: Optional[dict] = None


class EndUserPasswordResetRequest(BaseModel):
    password: str = PydanticField(..., min_length=6, max_length=128)


class AuthorizationGrantRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    user_id: int
    benefit_type: str = PydanticField(..., pattern="^(time|times|points)$")
    amount: Optional[int] = PydanticField(None, gt=0)
    days: Optional[int] = PydanticField(None, gt=0)
    is_lifetime: bool = False
    source_kami_code: Optional[str] = PydanticField(None, max_length=255)
    remark: Optional[str] = None


class DeleteKamisRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    batch_no: Optional[str] = PydanticField(None, max_length=64)
    kami_codes: List[str] = PydanticField(..., min_length=1, max_length=1000)


class KamiBatchCreateRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    batch_no: str = PydanticField(..., min_length=1, max_length=64)
    kami_type: str
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: int = PydanticField(16, ge=4, le=64)
    charset: str = PydanticField("upper_numeric", max_length=32)
    machine_bind_mode: str = PydanticField(
        MachineBindMode.one_card_one_device.value,
        max_length=32,
    )
    max_bind_devices: Optional[int] = PydanticField(None, ge=0, le=1000)
    authorization_owner: str = PydanticField(AuthorizationOwnerMode.device.value, max_length=32)
    user_bind_mode: str = PydanticField(UserBindMode.none.value, max_length=32)
    status: int = PydanticField(1, ge=0, le=1)
    remark: Optional[str] = None


class KamiBatchUpdateRequest(BaseModel):
    batch_no: Optional[str] = PydanticField(None, min_length=1, max_length=64)
    kami_type: Optional[str] = None
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: Optional[int] = PydanticField(None, ge=4, le=64)
    charset: Optional[str] = PydanticField(None, max_length=32)
    machine_bind_mode: Optional[str] = PydanticField(None, max_length=32)
    max_bind_devices: Optional[int] = PydanticField(None, ge=0, le=1000)
    authorization_owner: Optional[str] = PydanticField(None, max_length=32)
    user_bind_mode: Optional[str] = PydanticField(None, max_length=32)
    status: Optional[int] = PydanticField(None, ge=0, le=1)
    remark: Optional[str] = None


class InterfaceCreateRequest(BaseModel):
    name: str = PydanticField(..., min_length=1, max_length=255)
    interface_key: str = PydanticField(..., min_length=1, max_length=128)
    method: str = PydanticField("POST", min_length=1, max_length=16)
    path: str = PydanticField(..., min_length=1, max_length=255)
    category: Optional[str] = PydanticField("core", max_length=64)
    description: Optional[str] = None
    auth_mode: Optional[str] = PydanticField("bearer", max_length=64)
    content_type: Optional[str] = PydanticField("application/json", max_length=128)
    status: int = PydanticField(1, ge=0, le=1)
    request_headers: Optional[Any] = None
    request_params: Optional[Any] = None
    response_params: Optional[Any] = None
    success_example: Optional[Any] = None
    error_example: Optional[Any] = None
    response_example: Optional[Any] = None
    doc_markdown: Optional[str] = None
    remark: Optional[str] = None
    sort_order: int = PydanticField(0, ge=0)


class InterfaceUpdateRequest(BaseModel):
    name: Optional[str] = PydanticField(None, min_length=1, max_length=255)
    interface_key: Optional[str] = PydanticField(None, min_length=1, max_length=128)
    method: Optional[str] = PydanticField(None, min_length=1, max_length=16)
    path: Optional[str] = PydanticField(None, min_length=1, max_length=255)
    category: Optional[str] = PydanticField(None, max_length=64)
    description: Optional[str] = None
    auth_mode: Optional[str] = PydanticField(None, max_length=64)
    content_type: Optional[str] = PydanticField(None, max_length=128)
    status: Optional[int] = PydanticField(None, ge=0, le=1)
    request_headers: Optional[Any] = None
    request_params: Optional[Any] = None
    response_params: Optional[Any] = None
    success_example: Optional[Any] = None
    error_example: Optional[Any] = None
    response_example: Optional[Any] = None
    doc_markdown: Optional[str] = None
    remark: Optional[str] = None
    sort_order: Optional[int] = PydanticField(None, ge=0)


class AppInterfaceConfigRequest(BaseModel):
    enabled: bool = False
    quota_limit: Optional[int] = PydanticField(None, ge=0)
    expires_at: Optional[datetime] = None
    config: Optional[dict] = None
    remark: Optional[str] = None


def _handle_point_error(error: PointServiceError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


def _csv_response(filename: str, fieldnames: List[str], rows: List[dict]) -> Response:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _dump_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _load_json(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def _interface_payload(item: ApiInterface) -> dict:
    success_example = _load_json(item.success_example_json)
    response_example = _load_json(item.response_example_json)
    return {
        "id": item.id,
        "name": item.name,
        "interface_key": item.interface_key,
        "method": item.method,
        "path": item.path,
        "category": item.category,
        "description": item.description,
        "auth_mode": item.auth_mode,
        "content_type": item.content_type,
        "status": item.status,
        "request_headers": _load_json(item.request_headers_json) or [],
        "request_params": _load_json(item.request_params_json),
        "response_params": _load_json(item.response_params_json) or [],
        "success_example": success_example if success_example is not None else response_example,
        "error_example": _load_json(item.error_example_json),
        "response_example": response_example if response_example is not None else success_example,
        "doc_markdown": item.doc_markdown,
        "remark": item.remark,
        "sort_order": item.sort_order,
        "is_builtin": item.is_builtin,
        "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
        "updated_at": to_api_beijing_iso(item.updated_at, naive="civil"),
    }


def _apply_interface_spec(item: ApiInterface, spec: dict, now: datetime) -> None:
    item.name = spec["name"]
    item.interface_key = spec["interface_key"]
    item.method = spec.get("method", "POST").upper()
    item.path = spec["path"]
    item.category = spec.get("category") or "core"
    item.description = spec.get("description")
    item.auth_mode = spec.get("auth_mode") or "bearer"
    item.content_type = spec.get("content_type") or "application/json"
    item.status = spec.get("status", 1)
    item.request_headers_json = _dump_json(spec.get("request_headers", []))
    item.request_params_json = _dump_json(spec.get("request_params", []))
    item.response_params_json = _dump_json(spec.get("response_params", []))
    item.success_example_json = _dump_json(spec.get("success_example"))
    item.error_example_json = _dump_json(spec.get("error_example"))
    item.response_example_json = _dump_json(spec.get("success_example"))
    item.doc_markdown = spec.get("doc_markdown")
    item.remark = spec.get("remark")
    item.sort_order = spec.get("sort_order", 0)
    item.is_builtin = True
    item.updated_at = now


def _ensure_builtin_interfaces(session: Session) -> None:
    keys = [item["interface_key"] for item in BUILTIN_API_INTERFACES]
    existing_items = session.exec(
        select(ApiInterface).where(ApiInterface.interface_key.in_(keys))
    ).all()
    existing_by_key = {item.interface_key: item for item in existing_items}
    now = get_now().replace(tzinfo=None)
    changed = False

    for spec in BUILTIN_API_INTERFACES:
        item = existing_by_key.get(spec["interface_key"])
        if item is None:
            item = ApiInterface(
                name=spec["name"],
                interface_key=spec["interface_key"],
                method=spec.get("method", "POST").upper(),
                path=spec["path"],
                category=spec.get("category") or "core",
                created_at=now,
                updated_at=now,
            )
            _apply_interface_spec(item, spec, now)
            session.add(item)
            changed = True
        elif item.is_builtin:
            _apply_interface_spec(item, spec, now)
            session.add(item)
            changed = True

    if changed:
        session.commit()


def _app_interface_payload(
    interface: ApiInterface,
    config: Optional[AppInterfaceConfig],
    app_id: str,
) -> dict:
    payload = _interface_payload(interface)
    default_enabled = interface.is_builtin
    default_config = (
        {"release_on_logout": True, "heartbeat_timeout_seconds": 180}
        if interface.interface_key == "sdk.device_limit"
        else None
    )
    payload.update({
        "app_id": app_id,
        "interface_id": interface.id,
        "config_id": config.id if config else None,
        "configured": config is not None,
        "enabled": config.enabled if config else default_enabled,
        "config": _load_json(config.config_json) if config else default_config,
        "remark": config.remark if config else None,
        "config_created_at": to_api_beijing_iso(config.created_at, naive="civil") if config else None,
        "config_updated_at": to_api_beijing_iso(config.updated_at, naive="civil") if config else None,
    })
    return payload


def _get_login_aes_key_b64() -> str:
    global _runtime_login_aes_key_b64
    if settings.LOGIN_AES_KEY:
        return settings.LOGIN_AES_KEY
    if not _runtime_login_aes_key_b64:
        import base64

        _runtime_login_aes_key_b64 = base64.b64encode(os.urandom(16)).decode("utf-8")
    return _runtime_login_aes_key_b64


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _int_value(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _apply_app_interface_config_to_app(app: App, interface_key: str, config: Optional[dict]) -> None:
    if not config:
        return

    field_groups = {
        "sdk.app_config": {
            "notice_enabled",
            "notice_title",
            "notice",
            "notice_level",
            "notice_popup",
            "version",
            "version_info",
            "force_update",
            "update_url",
            "update_url_type",
            "download_url",
            "download_note",
            "download_button_text",
        },
        "sdk.verify": {
            "signature_required",
            "nonce_required",
            "timestamp_tolerance_seconds",
            "ip_lock_enabled",
        },
        "sdk.unbind": {
            "allow_unbind",
            "max_unbind_count",
            "unbind_cooldown_hours",
            "unbind_deduct_hours",
            "unbind_deduct_times",
            "ip_lock_enabled",
        },
    }
    bool_fields = {
        "notice_enabled",
        "notice_popup",
        "force_update",
        "signature_required",
        "nonce_required",
        "ip_lock_enabled",
        "allow_unbind",
    }
    int_defaults = {
        "timestamp_tolerance_seconds": app.timestamp_tolerance_seconds,
        "max_unbind_count": app.max_unbind_count,
        "unbind_cooldown_hours": app.unbind_cooldown_hours,
        "unbind_deduct_hours": app.unbind_deduct_hours,
        "unbind_deduct_times": app.unbind_deduct_times,
    }

    for field in field_groups.get(interface_key, set()):
        if field not in config:
            continue
        value = config[field]
        if field in bool_fields:
            value = _bool_value(value)
        elif field in int_defaults:
            value = _int_value(value, int_defaults[field])
        setattr(app, field, value)


# ==================== JWT 工具函数 ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = get_now() + expires_delta
    else:
        expire = get_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """验证 JWT Token"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        expires_at = payload.get("exp")
        if expires_at is not None and int(expires_at) <= int(get_now().timestamp()):
            raise HTTPException(status_code=401, detail="Invalid token")
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


def _role_value(current_user: dict) -> str:
    role = current_user.get("role")
    if role:
        return role.value if hasattr(role, "value") else str(role)
    return AdminRole.super_admin.value if current_user.get("is_admin", False) else AdminRole.operator.value


def _require_role(current_user: dict, allowed_roles: set[str]):
    role = _role_value(current_user)
    if role == AdminRole.super_admin.value or role in allowed_roles:
        return
    raise HTTPException(status_code=403, detail="权限不足")


async def get_current_user(
    authorization: Optional[str] = Header(None, description="Bearer JWT Token"),
):
    """获取当前用户（依赖注入）"""
    resolved_token = None
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials:
            resolved_token = credentials.strip()
    if not resolved_token:
        raise HTTPException(status_code=401, detail="Missing token")
    return verify_token(resolved_token)


# ==================== 应用管理接口 ====================

@router.post("/apps", summary="创建应用")
async def create_app(
    name: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """创建新应用，自动生成 app_id、app_secret 和 RSA 密钥对"""
    # 生成唯一标识
    app_id = f"app_{uuid.uuid4().hex[:12]}"
    app_secret = uuid.uuid4().hex

    # 生成 RSA 密钥对
    key_pair = RSACrypto.generate_key_pair()

    app = App(
        app_id=app_id,
        name=name,
        app_secret=app_secret,
        rsa_public_key=key_pair["public_key"],
        rsa_private_key=key_pair["private_key"],
        status=1,
        created_by=current_user.get("sub"),  # 记录创建人
        created_at=get_now().replace(tzinfo=None)  # 记录创建时间（naive datetime）
    )

    session.add(app)
    session.commit()
    session.refresh(app)

    # 记录日志
    username = current_user.get("sub")
    log_admin_action(
        session=session,
        username=username,
        event_type="app_create",
        app_id=app.app_id,
        payload={"app_name": name},
        message=f"用户 {username} 创建了应用 {name}"
    )

    return {
        "success": True,
        "message": "应用创建成功",
        "data": {
            "app_id": app.app_id,
            "name": app.name,
            "app_secret": app.app_secret,
            "rsa_public_key": app.rsa_public_key,
            "created_by": app.created_by,
            "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
            "status": app.status,
        }
    }


@router.get("/apps", summary="获取应用列表")
async def list_apps(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取应用列表：admin 可见全部，普通管理员只可见自己创建的应用。"""
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    statement = select(App)
    if not is_admin:
        statement = statement.where(App.created_by == username)
    apps = session.exec(statement).all()

    return {
        "success": True,
        "data": [
            {
                "id": app.id,
                "app_id": app.app_id,
                "name": app.name,
                "app_secret": app.app_secret,
                "created_by": app.created_by,
                "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
                "status": app.status,
            }
            for app in apps
        ]
    }


@router.put("/apps/{app_id}", summary="更新应用状态")
async def update_app_status(
    app_id: str,
    status: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """启用或禁用应用（非 admin 只能操作自己的应用）"""
    statement = select(App).where(App.app_id == app_id)
    app = session.exec(statement).first()

    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # 权限检查：非 admin 只能操作自己有权限的应用
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权操作此应用")

    app.status = status
    session.add(app)
    session.commit()

    return {"success": True, "message": "应用状态已更新"}


@router.post("/interfaces", summary="新增接口")
async def create_interface(
    payload: InterfaceCreateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """新增可配置/可开通的接口定义。"""
    _require_admin(current_user)
    existing = session.exec(
        select(ApiInterface).where(ApiInterface.interface_key == payload.interface_key)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="接口标识已存在")

    item = ApiInterface(
        name=payload.name,
        interface_key=payload.interface_key,
        method=payload.method.upper(),
        path=payload.path,
        category=payload.category or "core",
        description=payload.description,
        auth_mode=payload.auth_mode or "bearer",
        content_type=payload.content_type or "application/json",
        status=payload.status,
        request_headers_json=_dump_json(payload.request_headers),
        request_params_json=_dump_json(payload.request_params),
        response_params_json=_dump_json(payload.response_params),
        success_example_json=_dump_json(payload.success_example or payload.response_example),
        error_example_json=_dump_json(payload.error_example),
        response_example_json=_dump_json(payload.response_example),
        doc_markdown=payload.doc_markdown,
        remark=payload.remark,
        sort_order=payload.sort_order,
        is_builtin=False,
        created_at=get_now().replace(tzinfo=None),
        updated_at=get_now().replace(tzinfo=None),
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="interface_create",
        payload={"interface_key": item.interface_key, "path": item.path},
        message=f"用户 {current_user.get('sub')} 新增接口 {item.name}",
    )

    return {"success": True, "message": "接口已新增", "data": _interface_payload(item)}


@router.get("/interfaces", summary="接口列表")
async def list_interfaces(
    category: Optional[str] = Query(None, description="接口分类"),
    status: Optional[int] = Query(None, ge=0, le=1, description="接口状态"),
    keyword: Optional[str] = Query(None, description="接口名称、标识、说明或地址关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取接口定义列表。"""
    _require_admin(current_user)
    _ensure_builtin_interfaces(session)
    statement = select(ApiInterface)
    count_statement = select(ApiInterface)
    conditions = []
    if category:
        conditions.append(ApiInterface.category == category)
    if status is not None:
        conditions.append(ApiInterface.status == status)
    if keyword:
        keyword_like = f"%{keyword}%"
        conditions.append(or_(
            ApiInterface.name.like(keyword_like),
            ApiInterface.interface_key.like(keyword_like),
            ApiInterface.path.like(keyword_like),
            ApiInterface.description.like(keyword_like),
        ))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = len(session.exec(count_statement).all())
    interfaces = session.exec(
        statement.order_by(ApiInterface.sort_order, ApiInterface.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_interface_payload(item) for item in interfaces],
        },
    }


@router.put("/interfaces/{interface_id}", summary="编辑接口")
async def update_interface(
    interface_id: int,
    payload: InterfaceUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """编辑接口定义和文档。"""
    _require_admin(current_user)
    item = session.get(ApiInterface, interface_id)
    if not item:
        raise HTTPException(status_code=404, detail="接口不存在")

    data = payload.model_dump(exclude_unset=True)
    if "interface_key" in data and data["interface_key"] != item.interface_key:
        existing = session.exec(
            select(ApiInterface).where(ApiInterface.interface_key == data["interface_key"])
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="接口标识已存在")

    for field in [
        "name",
        "interface_key",
        "path",
        "category",
        "description",
        "auth_mode",
        "content_type",
        "status",
        "doc_markdown",
        "remark",
        "sort_order",
    ]:
        if field in data:
            setattr(item, field, data[field])
    if "method" in data and data["method"]:
        item.method = data["method"].upper()
    if "request_headers" in data:
        item.request_headers_json = _dump_json(data["request_headers"])
    if "request_params" in data:
        item.request_params_json = _dump_json(data["request_params"])
    if "response_params" in data:
        item.response_params_json = _dump_json(data["response_params"])
    if "success_example" in data:
        item.success_example_json = _dump_json(data["success_example"])
        if "response_example" not in data:
            item.response_example_json = _dump_json(data["success_example"])
    if "error_example" in data:
        item.error_example_json = _dump_json(data["error_example"])
    if "response_example" in data:
        item.response_example_json = _dump_json(data["response_example"])
        if "success_example" not in data:
            item.success_example_json = _dump_json(data["response_example"])
    item.updated_at = get_now().replace(tzinfo=None)

    session.add(item)
    session.commit()
    session.refresh(item)

    return {"success": True, "message": "接口已更新", "data": _interface_payload(item)}


@router.get("/apps/{app_id}/interfaces", summary="应用接口列表")
async def list_app_interfaces(
    app_id: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """查看应用可开通接口及当前配置。"""
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权查看此应用接口")

    _ensure_builtin_interfaces(session)
    interfaces = session.exec(select(ApiInterface).order_by(ApiInterface.sort_order, ApiInterface.id.desc())).all()
    configs = session.exec(
        select(AppInterfaceConfig).where(AppInterfaceConfig.app_id == app_id)
    ).all()
    config_by_interface_id = {config.interface_id: config for config in configs}

    return {
        "success": True,
        "data": [
            _app_interface_payload(
                interface=item,
                config=config_by_interface_id.get(item.id),
                app_id=app_id,
            )
            for item in interfaces
        ],
    }


@router.put("/apps/{app_id}/interfaces/{interface_id}", summary="配置应用接口")
async def update_app_interface(
    app_id: str,
    interface_id: int,
    payload: AppInterfaceConfigRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """开通、关闭或配置某个应用的接口。"""
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    interface = session.get(ApiInterface, interface_id)
    if not interface:
        raise HTTPException(status_code=404, detail="接口不存在")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权配置此应用接口")

    config = session.exec(
        select(AppInterfaceConfig).where(
            AppInterfaceConfig.app_id == app_id,
            AppInterfaceConfig.interface_id == interface_id,
        )
    ).first()
    now = get_now().replace(tzinfo=None)
    if not config:
        config = AppInterfaceConfig(
            app_id=app_id,
            interface_id=interface_id,
            created_at=now,
        )

    config.enabled = payload.enabled
    config.quota_limit = payload.quota_limit
    config.expires_at = payload.expires_at.replace(tzinfo=None) if payload.expires_at and payload.expires_at.tzinfo else payload.expires_at
    config.config_json = _dump_json(payload.config)
    config.remark = payload.remark
    config.updated_at = now
    _apply_app_interface_config_to_app(app, interface.interface_key, payload.config)

    session.add(config)
    session.add(app)
    session.commit()
    session.refresh(config)

    log_admin_action(
        session=session,
        username=username,
        event_type="app_interface_config",
        app_id=app_id,
        payload={
            "interface_id": interface_id,
            "interface_key": interface.interface_key,
            "enabled": config.enabled,
        },
        message=f"用户 {username} 配置了应用 {app.name} 的接口 {interface.name}",
    )

    return {
        "success": True,
        "message": "应用接口配置已更新",
        "data": _app_interface_payload(interface, config, app_id),
    }


@router.delete("/apps/{app_id}", summary="删除应用")
async def delete_app(
    app_id: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """删除应用（会级联删除关联的卡密、设备和日志，非 admin 只能删除自己的应用）"""
    statement = select(App).where(App.app_id == app_id)
    app = session.exec(statement).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    # 权限检查：只有创建者或 admin 可以删除应用
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not is_admin and app.created_by != username:
        raise HTTPException(status_code=403, detail="无权删除此应用，只有创建者可以删除")

    # 统计关联数据
    kami_count = len(session.exec(select(Kami).where(Kami.app_id == app_id)).all())
    device_count = len(session.exec(select(Device).where(Device.app_id == app_id)).all())
    binding_count = len(session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.app_id == app_id)).all())
    legacy_access_count = len(session.exec(select(AppAuthorization).where(AppAuthorization.app_id == app_id)).all())
    
    # 清理旧版应用访问记录，兼容历史数据
    legacy_access_rows = session.exec(select(AppAuthorization).where(AppAuthorization.app_id == app_id)).all()
    for row in legacy_access_rows:
        session.delete(row)

    bindings = session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.app_id == app_id)).all()
    for binding in bindings:
        session.delete(binding)
    
    # 先删除关联的卡密（避免外键约束问题）
    kamis = session.exec(select(Kami).where(Kami.app_id == app_id)).all()
    for kami in kamis:
        session.delete(kami)
    
    # 先删除关联的设备
    devices = session.exec(select(Device).where(Device.app_id == app_id)).all()
    for device in devices:
        session.delete(device)
    
    # 最后删除应用
    session.delete(app)
    session.commit()
    
    # 记录日志
    username = current_user.get("sub")
    log_admin_action(
        session=session,
        username=username,
        event_type="app_delete",
        app_id=app_id,
        payload={
            "kami_count": kami_count,
            "device_count": device_count,
            "binding_count": binding_count,
            "legacy_access_count": legacy_access_count,
        },
        message=f"用户 {username} 删除了应用 {app.name}"
    )

    return {
        "success": True,
        "message": f"应用已删除，同时删除了 {kami_count} 个卡密和 {device_count} 个设备记录"
    }


# ==================== 卡密管理接口 ====================

KAMI_CHARSETS = {
    "upper_numeric": string.ascii_uppercase + string.digits,
    "numeric": string.digits,
    "upper": string.ascii_uppercase,
    "lower_mixed": string.ascii_letters + string.digits,
}

TIME_CARD_UNITS = {
    KamiType.hour: (1, "hour"),
    KamiType.day: (1, "day"),
    KamiType.week: (1, "week"),
    KamiType.month: (1, "month"),
    KamiType.quarter: (1, "quarter"),
    KamiType.year: (1, "year"),
    KamiType.lifetime: (None, "lifetime"),
}


def generate_kami_code(length: int = 16, prefix: str = "", charset: str = "upper_numeric") -> str:
    """生成随机卡密代码。length 表示随机后缀长度，prefix 会原样拼接到前面。"""
    characters = KAMI_CHARSETS.get(charset)
    if not characters:
        raise ValueError("Invalid charset")
    return f"{prefix}{''.join(random.choices(characters, k=length))}"


def getTypeText(kami_type: str) -> str:
    """获取卡密类型文本"""
    type_map = {
        'day': '天卡',
        'hour': '小时卡',
        'week': '周卡',
        'month': '月卡',
        'quarter': '季卡',
        'year': '年卡',
        'lifetime': '永久卡',
        'points': '积分卡',
        'times': '次数卡'
    }
    return type_map.get(kami_type, kami_type)


def get_machine_bind_mode_value(mode) -> str:
    if not mode:
        return MachineBindMode.one_card_one_device.value
    return mode.value if hasattr(mode, "value") else str(mode)


def get_authorization_owner_value(mode) -> str:
    if not mode:
        return AuthorizationOwnerMode.device.value
    return mode.value if hasattr(mode, "value") else str(mode)


def get_user_bind_mode_value(mode) -> str:
    if not mode:
        return UserBindMode.none.value
    return mode.value if hasattr(mode, "value") else str(mode)


def _kami_batch_payload(batch: KamiBatch) -> dict:
    return {
        "id": batch.id,
        "batch_no": batch.batch_no,
        "app_id": batch.app_id,
        "kami_type": batch.kami_type.value,
        "points_amount": batch.points_amount,
        "points_valid_days": batch.points_valid_days,
        "time_value": batch.time_value,
        "time_unit": batch.time_unit,
        "times_total": batch.times_total,
        "code_prefix": batch.code_prefix,
        "code_length": batch.code_length,
        "charset": batch.charset,
        "machine_bind_mode": get_machine_bind_mode_value(batch.machine_bind_mode),
        "max_bind_devices": batch.max_bind_devices,
        "authorization_owner": get_authorization_owner_value(batch.authorization_owner),
        "user_bind_mode": get_user_bind_mode_value(batch.user_bind_mode),
        "status": batch.status,
        "remark": batch.remark,
        "created_at": to_api_beijing_iso(batch.created_at, naive="civil")
        if batch.created_at
        else None,
        "updated_at": to_api_beijing_iso(batch.updated_at, naive="civil")
        if batch.updated_at
        else None,
    }


def _normalize_max_bind_devices(machine_bind_mode: MachineBindMode, max_bind_devices: Optional[int]) -> int:
    if machine_bind_mode == MachineBindMode.no_limit:
        return 0
    if machine_bind_mode == MachineBindMode.one_card_one_device:
        return 1
    if max_bind_devices is None or max_bind_devices < 2:
        return 3
    return max_bind_devices


def _validate_batch_payload(
    payload: KamiBatchCreateRequest,
) -> tuple[KamiType, MachineBindMode, AuthorizationOwnerMode, UserBindMode, Optional[int], Optional[str], int]:
    try:
        kami_type_enum = KamiType(payload.kami_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid kami_type")
    try:
        machine_bind_mode_enum = MachineBindMode(payload.machine_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid machine_bind_mode")
    try:
        authorization_owner_enum = AuthorizationOwnerMode(payload.authorization_owner)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid authorization_owner")
    try:
        user_bind_mode_enum = UserBindMode(payload.user_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_bind_mode")
    if authorization_owner_enum == AuthorizationOwnerMode.user and user_bind_mode_enum == UserBindMode.none:
        raise HTTPException(status_code=400, detail="用户授权批次必须选择自动识别绑定或必须绑定用户")
    if payload.charset not in KAMI_CHARSETS:
        raise HTTPException(status_code=400, detail="Invalid charset")
    if kami_type_enum == KamiType.points and not payload.points_amount:
        raise HTTPException(status_code=400, detail="积分卡批次必须设置有效积分面额")
    if kami_type_enum == KamiType.times and not payload.times_total:
        raise HTTPException(status_code=400, detail="次数卡批次必须设置有效次数")

    max_bind_devices = _normalize_max_bind_devices(machine_bind_mode_enum, payload.max_bind_devices)

    time_value = payload.time_value
    time_unit = payload.time_unit
    if kami_type_enum in TIME_CARD_UNITS:
        default_value, default_unit = TIME_CARD_UNITS[kami_type_enum]
        time_value = time_value or default_value
        time_unit = time_unit or default_unit

    return (
        kami_type_enum,
        machine_bind_mode_enum,
        authorization_owner_enum,
        user_bind_mode_enum,
        time_value,
        time_unit,
        max_bind_devices,
    )


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


@router.post("/kamis/batches", summary="创建卡密批次")
async def create_kami_batch(
    payload: KamiBatchCreateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, payload.app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权在此应用下创建批次")

    existing = session.exec(
        select(KamiBatch).where(
            KamiBatch.app_id == payload.app_id,
            KamiBatch.batch_no == payload.batch_no,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="批次号已存在")

    (
        kami_type_enum,
        machine_bind_mode_enum,
        authorization_owner_enum,
        user_bind_mode_enum,
        time_value,
        time_unit,
        max_bind_devices,
    ) = _validate_batch_payload(payload)
    now = get_now().replace(tzinfo=None)
    batch = KamiBatch(
        app_id=payload.app_id,
        batch_no=payload.batch_no,
        kami_type=kami_type_enum,
        points_amount=payload.points_amount if kami_type_enum == KamiType.points else None,
        points_valid_days=payload.points_valid_days if kami_type_enum == KamiType.points else None,
        time_value=time_value,
        time_unit=time_unit,
        times_total=payload.times_total if kami_type_enum == KamiType.times else None,
        code_prefix=payload.code_prefix or None,
        code_length=payload.code_length,
        charset=payload.charset,
        machine_bind_mode=machine_bind_mode_enum,
        max_bind_devices=max_bind_devices,
        authorization_owner=authorization_owner_enum,
        user_bind_mode=user_bind_mode_enum,
        status=payload.status,
        remark=payload.remark,
        created_at=now,
        updated_at=now,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    log_admin_action(
        session=session,
        username=username,
        event_type="kami_batch_create",
        app_id=payload.app_id,
        payload=_kami_batch_payload(batch),
        message=f"用户 {username} 创建了卡密批次 {batch.batch_no}",
    )

    return {"success": True, "message": "批次已创建", "data": _kami_batch_payload(batch)}


@router.put("/kamis/batches/{batch_id}", summary="Update kami batch")
async def update_kami_batch(
    batch_id: int,
    payload: KamiBatchUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    batch = session.get(KamiBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, batch.app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="No permission to update this batch")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return {"success": True, "message": "Batch unchanged", "data": _kami_batch_payload(batch)}

    current_kamis = session.exec(
        select(Kami).where(Kami.app_id == batch.app_id, Kami.batch_no == batch.batch_no)
    ).all()
    requested_type = data.get("kami_type")
    if requested_type and requested_type != _enum_value(batch.kami_type) and current_kamis:
        raise HTTPException(status_code=400, detail="Batch already has kamis; kami_type cannot be changed")

    merged = {
        "app_id": batch.app_id,
        "batch_no": data.get("batch_no", batch.batch_no),
        "kami_type": data.get("kami_type", _enum_value(batch.kami_type)),
        "points_amount": data.get("points_amount", batch.points_amount),
        "points_valid_days": data.get("points_valid_days", batch.points_valid_days),
        "times_total": data.get("times_total", batch.times_total),
        "time_value": data.get("time_value", batch.time_value),
        "time_unit": data.get("time_unit", batch.time_unit),
        "code_prefix": data.get("code_prefix", batch.code_prefix),
        "code_length": data.get("code_length", batch.code_length),
        "charset": data.get("charset", batch.charset),
        "machine_bind_mode": data.get("machine_bind_mode", get_machine_bind_mode_value(batch.machine_bind_mode)),
        "max_bind_devices": data.get("max_bind_devices", batch.max_bind_devices),
        "authorization_owner": data.get("authorization_owner", get_authorization_owner_value(batch.authorization_owner)),
        "user_bind_mode": data.get("user_bind_mode", get_user_bind_mode_value(batch.user_bind_mode)),
        "status": data.get("status", batch.status),
        "remark": data.get("remark", batch.remark),
    }
    validation_payload = KamiBatchCreateRequest(**merged)
    (
        kami_type_enum,
        machine_bind_mode_enum,
        authorization_owner_enum,
        user_bind_mode_enum,
        time_value,
        time_unit,
        max_bind_devices,
    ) = _validate_batch_payload(validation_payload)

    old_batch_no = batch.batch_no
    new_batch_no = merged["batch_no"]
    if new_batch_no != old_batch_no:
        duplicate = session.exec(
            select(KamiBatch).where(
                KamiBatch.app_id == batch.app_id,
                KamiBatch.batch_no == new_batch_no,
                KamiBatch.id != batch.id,
            )
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Batch number already exists")

    batch.batch_no = new_batch_no
    batch.kami_type = kami_type_enum
    batch.points_amount = merged["points_amount"] if kami_type_enum == KamiType.points else None
    batch.points_valid_days = merged["points_valid_days"] if kami_type_enum == KamiType.points else None
    batch.time_value = time_value
    batch.time_unit = time_unit
    batch.times_total = merged["times_total"] if kami_type_enum == KamiType.times else None
    batch.code_prefix = merged["code_prefix"] or None
    batch.code_length = merged["code_length"]
    batch.charset = merged["charset"]
    batch.machine_bind_mode = machine_bind_mode_enum
    batch.max_bind_devices = max_bind_devices
    batch.authorization_owner = authorization_owner_enum
    batch.user_bind_mode = user_bind_mode_enum
    batch.status = merged["status"]
    batch.remark = merged["remark"]
    batch.updated_at = get_now().replace(tzinfo=None)

    if new_batch_no != old_batch_no:
        for kami in current_kamis:
            kami.batch_no = new_batch_no
            session.add(kami)

    session.add(batch)
    session.commit()
    session.refresh(batch)

    log_admin_action(
        session=session,
        username=username,
        event_type="kami_batch_update",
        app_id=batch.app_id,
        payload=_kami_batch_payload(batch),
        message=f"User {username} updated kami batch {batch.batch_no}",
    )

    return {"success": True, "message": "Batch updated", "data": _kami_batch_payload(batch)}


@router.delete("/kamis/batches/{batch_id}", summary="Delete kami batch")
async def delete_kami_batch(
    batch_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    batch = session.get(KamiBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, batch.app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="No permission to delete this batch")

    existing_kami = session.exec(
        select(Kami).where(Kami.app_id == batch.app_id, Kami.batch_no == batch.batch_no)
    ).first()
    if existing_kami:
        raise HTTPException(status_code=400, detail="该批次下仍有卡密，请先删除或转移卡密后再删除批次。")

    app_id = batch.app_id
    batch_no = batch.batch_no
    payload_data = _kami_batch_payload(batch)
    session.delete(batch)
    session.commit()

    log_admin_action(
        session=session,
        username=username,
        event_type="kami_batch_delete",
        app_id=app_id,
        payload=payload_data,
        message=f"用户 {username} 删除了卡密批次 {batch_no}",
    )

    return {"success": True, "message": "批次已删除", "data": {"id": batch_id, "batch_no": batch_no}}


@router.post("/kamis/batch", summary="批量生成卡密")
async def batch_create_kamis(
    app_id: str,
    kami_type: Optional[str] = Query(None, description="兼容旧参数；实际以批次配置为准"),
    count: int = Query(ge=1, le=1000, description="生成数量"),
    times: Optional[int] = Query(None, description="次数卡次数（仅次数卡类型需要）"),
    points_amount: Optional[int] = Query(None, description="积分卡面额（仅积分卡类型需要）"),
    batch_no: Optional[str] = Query(None, description="卡密批次号，不传则自动生成"),
    points_valid_days: Optional[int] = Query(None, ge=1, description="积分兑换后有效天数，不传表示永久有效"),
    machine_bind_mode: str = Query(
        MachineBindMode.one_card_one_device.value,
        description="机器码绑定模式：no_limit/one_card_one_device/one_card_multi_device",
    ),
    code_prefix: Optional[str] = Query(None, max_length=32, description="卡密前缀"),
    code_length: Optional[int] = Query(None, ge=4, le=64, description="随机后缀长度"),
    charset: Optional[str] = Query(None, description="字符集：upper_numeric/numeric/upper/lower_mixed"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """批量生成卡密"""
    # 验证应用是否存在
    statement = select(App).where(App.app_id == app_id)
    app = session.exec(statement).first()

    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # 权限检查：非 admin 只能在自己有权限的应用下生成卡密
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权在此应用下生成卡密")

    # 验证卡密类型
    if not batch_no:
        raise HTTPException(status_code=400, detail="请先创建批次后再生成卡密")

    batch = session.exec(
        select(KamiBatch).where(
            KamiBatch.app_id == app_id,
            KamiBatch.batch_no == batch_no,
        )
    ).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")
    if batch.status != 1:
        raise HTTPException(status_code=400, detail="批次已停用，无法生成卡密")

    kami_type = batch.kami_type.value
    times = batch.times_total
    points_amount = batch.points_amount
    points_valid_days = batch.points_valid_days
    machine_bind_mode = get_machine_bind_mode_value(batch.machine_bind_mode)
    max_bind_devices = batch.max_bind_devices
    authorization_owner = get_authorization_owner_value(batch.authorization_owner)
    user_bind_mode = get_user_bind_mode_value(batch.user_bind_mode)
    code_prefix = (batch.code_prefix or "") if code_prefix is None else code_prefix
    code_length = batch.code_length if code_length is None else code_length
    charset = batch.charset if charset is None else charset

    try:
        kami_type_enum = KamiType(kami_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid kami_type")
    if charset not in KAMI_CHARSETS:
        raise HTTPException(status_code=400, detail="Invalid charset")
    
    # 次数卡类型需要指定次数
    if kami_type_enum == KamiType.times:
        if not times or times <= 0:
            raise HTTPException(status_code=400, detail="次数卡类型必须指定有效次数")
    if kami_type_enum == KamiType.points:
        if not points_amount or points_amount <= 0:
            raise HTTPException(status_code=400, detail="积分卡类型必须指定有效的积分面额")
    try:
        machine_bind_mode_enum = MachineBindMode(machine_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid machine_bind_mode")
    try:
        authorization_owner_enum = AuthorizationOwnerMode(authorization_owner)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid authorization_owner")
    try:
        user_bind_mode_enum = UserBindMode(user_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_bind_mode")

    # 批量生成卡密
    kamis = []
    generated_codes = []
    effective_batch_no = batch_no or f"batch_{uuid.uuid4().hex[:12]}"
    time_value = None
    time_unit = None
    if kami_type_enum in TIME_CARD_UNITS:
        time_value, time_unit = TIME_CARD_UNITS[kami_type_enum]
    if batch.time_value:
        time_value = batch.time_value
    if batch.time_unit:
        time_unit = batch.time_unit

    for _ in range(count):
        kami_code = generate_kami_code(code_length, code_prefix, charset)

        # 确保唯一性
        while True:
            check_stmt = select(Kami).where(Kami.kami_code == kami_code)
            existing = session.exec(check_stmt).first()
            if not existing:
                break
            kami_code = generate_kami_code(code_length, code_prefix, charset)

        kami = Kami(
            app_id=app_id,
            kami_code=kami_code,
            kami_type=kami_type_enum,
            status=KamiStatus.unused,
            points_amount=points_amount if kami_type_enum == KamiType.points else None,
            batch_no=effective_batch_no,
            points_valid_days=points_valid_days if kami_type_enum == KamiType.points else None,
            time_value=time_value,
            time_unit=time_unit,
            times_total=times if kami_type_enum == KamiType.times else None,
            times_remaining=times if kami_type_enum == KamiType.times else None,
            code_prefix=code_prefix or None,
            code_length=code_length,
            charset=charset,
            machine_bind_mode=machine_bind_mode_enum,
            max_bind_devices=max_bind_devices,
            authorization_owner=authorization_owner_enum,
            user_bind_mode=user_bind_mode_enum,
        )

        kamis.append(kami)
        generated_codes.append(kami_code)

    session.add_all(kamis)
    session.commit()
    
    # 记录日志
    username = current_user.get("sub")
    log_admin_action(
        session=session,
        username=username,
        event_type="kami_generate",
        app_id=app_id,
        payload={
            "count": count,
            "kami_type": kami_type,
            "times": times if kami_type_enum == KamiType.times else None,
            "points_amount": points_amount if kami_type_enum == KamiType.points else None,
            "batch_no": effective_batch_no,
            "points_valid_days": points_valid_days if kami_type_enum == KamiType.points else None,
            "machine_bind_mode": machine_bind_mode_enum.value,
            "max_bind_devices": max_bind_devices,
            "authorization_owner": authorization_owner_enum.value,
            "user_bind_mode": user_bind_mode_enum.value,
            "code_prefix": code_prefix,
            "code_length": code_length,
            "charset": charset,
        },
        message=f"用户 {username} 生成了 {count} 个{getTypeText(kami_type)}卡密"
    )

    return {
        "success": True,
        "message": f"成功生成 {count} 个卡密",
        "data": {
            "count": count,
            "kami_type": kami_type,
            "times": times if kami_type_enum == KamiType.times else None,
            "points_amount": points_amount if kami_type_enum == KamiType.points else None,
            "batch_no": effective_batch_no,
            "points_valid_days": points_valid_days if kami_type_enum == KamiType.points else None,
            "machine_bind_mode": machine_bind_mode_enum.value,
            "max_bind_devices": max_bind_devices,
            "authorization_owner": authorization_owner_enum.value,
            "user_bind_mode": user_bind_mode_enum.value,
            "code_prefix": code_prefix,
            "code_length": code_length,
            "charset": charset,
            "codes": generated_codes
        }
    }


@router.get("/kamis", summary="获取卡密列表")
async def list_kamis(
    app_id: str,
    status: Optional[str] = Query(None, description="卡密状态过滤"),
    kami_type: Optional[str] = Query(None, description="卡密类型过滤"),
    batch_no: Optional[str] = Query(None, description="卡密批次号"),
    keyword: Optional[str] = Query(None, description="搜索卡密、批次号或机器码"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取卡密列表（支持分页和过滤）"""
    # 验证应用是否存在
    statement_app = select(App).where(App.app_id == app_id)
    app = session.exec(statement_app).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    
    # 权限检查：非 admin 只能查看自己有权限的应用的卡密
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权查看此应用的卡密")
    
    # 自动清理过期或已使用的次数卡
    _cleanup_used_times_kamis(session, app_id)

    statement = select(Kami).where(Kami.app_id == app_id)

    if status:
        try:
            status_enum = KamiStatus(status)
            statement = statement.where(Kami.status == status_enum)
        except ValueError:
            pass
    if kami_type:
        try:
            statement = statement.where(Kami.kami_type == KamiType(kami_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid kami_type")
    if batch_no:
        statement = statement.where(Kami.batch_no == batch_no)
    if keyword:
        keyword_like = f"%{keyword}%"
        statement = statement.where(
            or_(
                Kami.kami_code.like(keyword_like),
                Kami.batch_no.like(keyword_like),
                Kami.bind_uuid.like(keyword_like),
            )
        )

    # 分页
    offset = (page - 1) * page_size
    statement = statement.order_by(Kami.id.desc()).offset(offset).limit(page_size)

    kamis = session.exec(statement).all()

    user_ids = sorted({kami.redeemed_by_user_id for kami in kamis if kami.redeemed_by_user_id})
    users_by_id = {}
    accounts_by_user_id = {}
    if user_ids:
        users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all()
        users_by_id = {user.id: user for user in users}
        accounts = session.exec(
            select(UserPointAccount).where(UserPointAccount.user_id.in_(user_ids))
        ).all()
        accounts_by_user_id = {account.user_id: account for account in accounts}

    kami_codes = [kami.kami_code for kami in kamis]
    binding_count_by_code = {code: 0 for code in kami_codes}
    if kami_codes:
        bindings = session.exec(
            select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(kami_codes))
        ).all()
        for binding in bindings:
            binding_count_by_code[binding.kami_code] = binding_count_by_code.get(binding.kami_code, 0) + 1
    last_consume_at_by_code = {}
    if kami_codes:
        consume_logs = session.exec(
            select(EventLog)
            .where(
                EventLog.kami_code.in_(kami_codes),
                EventLog.event_type == "consume",
            )
            .order_by(EventLog.created_at.desc())
        ).all()
        for log in consume_logs:
            if log.kami_code and log.kami_code not in last_consume_at_by_code:
                last_consume_at_by_code[log.kami_code] = log.created_at

    # 统计总数
    count_stmt = select(Kami).where(Kami.app_id == app_id)
    if status:
        try:
            status_enum = KamiStatus(status)
            count_stmt = count_stmt.where(Kami.status == status_enum)
        except ValueError:
            pass
    if kami_type:
        try:
            count_stmt = count_stmt.where(Kami.kami_type == KamiType(kami_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid kami_type")
    if batch_no:
        count_stmt = count_stmt.where(Kami.batch_no == batch_no)
    if keyword:
        keyword_like = f"%{keyword}%"
        count_stmt = count_stmt.where(
            or_(
                Kami.kami_code.like(keyword_like),
                Kami.batch_no.like(keyword_like),
                Kami.bind_uuid.like(keyword_like),
            )
        )
    total = len(session.exec(count_stmt).all())

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": kami.id,
                    "kami_code": kami.kami_code,
                    "kami_type": kami.kami_type.value,
                    "status": kami.status.value,
                    "bind_uuid": kami.bind_uuid,
                    "activate_time": to_api_beijing_iso(kami.activate_time, naive="civil"),
                    "expire_time": to_api_beijing_iso(kami.expire_time, naive="civil"),
                    "points_amount": kami.points_amount,
                    "batch_no": kami.batch_no,
                    "points_valid_days": kami.points_valid_days,
                    "time_value": kami.time_value,
                    "time_unit": kami.time_unit,
                    "times_total": kami.times_total,
                    "times_remaining": kami.times_remaining,
                    "code_prefix": kami.code_prefix,
                    "code_length": kami.code_length,
                    "charset": kami.charset,
                    "bind_ip": kami.bind_ip,
                    "unbind_count": kami.unbind_count,
                    "last_unbind_at": to_api_beijing_iso(kami.last_unbind_at, naive="civil")
                    if kami.last_unbind_at
                    else None,
                    "last_verify_at": to_api_beijing_iso(kami.last_verify_at, naive="civil")
                    if kami.last_verify_at
                    else None,
                    "last_consume_at": to_api_beijing_iso(
                        last_consume_at_by_code.get(kami.kami_code),
                        naive="civil",
                    )
                    if last_consume_at_by_code.get(kami.kami_code)
                    else None,
                    "machine_bind_mode": get_machine_bind_mode_value(kami.machine_bind_mode),
                    "max_bind_devices": kami.max_bind_devices,
                    "authorization_owner": get_authorization_owner_value(kami.authorization_owner),
                    "user_bind_mode": get_user_bind_mode_value(kami.user_bind_mode),
                    "device_bind_count": binding_count_by_code.get(kami.kami_code, 0)
                    or (1 if kami.bind_uuid else 0),
                    "created_at": to_api_beijing_iso(kami.created_at, naive="civil")
                    if kami.created_at
                    else None,
                    "redeemed_by_user_id": kami.redeemed_by_user_id,
                    "redeemed_user": (
                        {
                            "id": users_by_id[kami.redeemed_by_user_id].id,
                            "username": users_by_id[kami.redeemed_by_user_id].username,
                            "email": users_by_id[kami.redeemed_by_user_id].email,
                            "phone": users_by_id[kami.redeemed_by_user_id].phone,
                        }
                        if kami.redeemed_by_user_id in users_by_id
                        else None
                    ),
                    "point_balance": (
                        accounts_by_user_id[kami.redeemed_by_user_id].balance
                        if kami.redeemed_by_user_id in accounts_by_user_id
                        else None
                    ),
                    "point_remaining_balance": (
                        accounts_by_user_id[kami.redeemed_by_user_id].balance
                        if kami.redeemed_by_user_id in accounts_by_user_id
                        else None
                    ),
                    "redeemed_at": to_api_beijing_iso(kami.redeemed_at, naive="civil")
                    if kami.redeemed_at
                    else None
                }
                for kami in kamis
            ]
        }
    }


@router.get("/kamis/batches", summary="获取卡密批次汇总")
async def list_kami_batches(
    app_id: str,
    kami_type: Optional[str] = Query(None, description="卡密类型"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """按批次汇总卡密生成、兑换和冻结情况。"""
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权查看此应用的卡密")

    statement = select(Kami).where(Kami.app_id == app_id)
    if kami_type:
        try:
            statement = statement.where(Kami.kami_type == KamiType(kami_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid kami_type")

    batch_kamis = session.exec(statement).all()
    kami_codes = [kami.kami_code for kami in batch_kamis]
    binding_count_by_code = {code: 0 for code in kami_codes}
    if kami_codes:
        bindings = session.exec(
            select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(kami_codes))
        ).all()
        for binding in bindings:
            binding_count_by_code[binding.kami_code] = binding_count_by_code.get(binding.kami_code, 0) + 1

    batch_statement = select(KamiBatch).where(KamiBatch.app_id == app_id)
    if kami_type:
        batch_statement = batch_statement.where(KamiBatch.kami_type == KamiType(kami_type))
    batch_configs = session.exec(batch_statement).all()

    batches = {}
    for batch in batch_configs:
        item = _kami_batch_payload(batch)
        item.update({
            "total_count": 0,
            "unused_count": 0,
            "active_count": 0,
            "frozen_count": 0,
            "redeemed_count": 0,
            "times_remaining_total": 0,
            "device_bind_count": 0,
        })
        batches[batch.batch_no] = item

    for kami in batch_kamis:
        batch_key = kami.batch_no or "legacy"
        item = batches.setdefault(
            batch_key,
            {
                "batch_no": batch_key,
                "app_id": app_id,
                "kami_type": kami.kami_type.value,
                "points_amount": kami.points_amount,
                "points_valid_days": kami.points_valid_days,
                "time_value": kami.time_value,
                "time_unit": kami.time_unit,
                "times_total": kami.times_total,
                "code_prefix": kami.code_prefix,
                "code_length": kami.code_length,
                "charset": kami.charset,
                "machine_bind_mode": get_machine_bind_mode_value(kami.machine_bind_mode),
                "max_bind_devices": kami.max_bind_devices,
                "authorization_owner": get_authorization_owner_value(kami.authorization_owner),
                "user_bind_mode": get_user_bind_mode_value(kami.user_bind_mode),
                "device_bind_count": 0,
                "created_at": to_api_beijing_iso(kami.created_at, naive="civil")
                if kami.created_at
                else None,
                "total_count": 0,
                "unused_count": 0,
                "active_count": 0,
                "frozen_count": 0,
                "redeemed_count": 0,
                "times_remaining_total": 0,
            },
        )
        item["total_count"] += 1
        item["times_remaining_total"] += kami.times_remaining or 0
        item["device_bind_count"] += binding_count_by_code.get(kami.kami_code, 0) or (
            1 if kami.bind_uuid else 0
        )
        if not item["created_at"] and kami.created_at:
            item["created_at"] = to_api_beijing_iso(kami.created_at, naive="civil")
        if kami.status == KamiStatus.unused:
            item["unused_count"] += 1
        elif kami.status == KamiStatus.active:
            item["active_count"] += 1
        elif kami.status == KamiStatus.frozen:
            item["frozen_count"] += 1
        if kami.redeemed_by_user_id is not None:
            item["redeemed_count"] += 1

    return {
        "success": True,
        "data": sorted(
            batches.values(),
            key=lambda item: (item["batch_no"] == "legacy", item["batch_no"]),
        )
    }


@router.get("/kamis/export", summary="导出卡密 CSV")
async def export_kamis(
    app_id: str,
    status: Optional[str] = Query(None, description="卡密状态"),
    kami_type: Optional[str] = Query(None, description="卡密类型"),
    batch_no: Optional[str] = Query(None, description="卡密批次号"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """导出卡密列表，用于业务分发或对账。"""
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权导出此应用的卡密")

    statement = select(Kami).where(Kami.app_id == app_id)
    if status:
        try:
            statement = statement.where(Kami.status == KamiStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if kami_type:
        try:
            statement = statement.where(Kami.kami_type == KamiType(kami_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid kami_type")
    if batch_no:
        statement = statement.where(Kami.batch_no == batch_no)

    rows = []
    for kami in session.exec(statement.order_by(Kami.id.desc())).all():
        rows.append({
            "id": kami.id,
            "app_id": kami.app_id,
            "kami_code": kami.kami_code,
            "kami_type": kami.kami_type.value,
            "status": kami.status.value,
            "batch_no": kami.batch_no,
            "points_amount": kami.points_amount,
            "points_valid_days": kami.points_valid_days,
            "time_value": kami.time_value,
            "time_unit": kami.time_unit,
            "times_total": kami.times_total,
            "times_remaining": kami.times_remaining,
            "machine_bind_mode": get_machine_bind_mode_value(kami.machine_bind_mode),
            "max_bind_devices": kami.max_bind_devices,
            "authorization_owner": get_authorization_owner_value(kami.authorization_owner),
            "user_bind_mode": get_user_bind_mode_value(kami.user_bind_mode),
            "code_prefix": kami.code_prefix,
            "code_length": kami.code_length,
            "charset": kami.charset,
            "bind_ip": kami.bind_ip,
            "unbind_count": kami.unbind_count,
            "created_at": to_api_beijing_iso(kami.created_at, naive="civil") if kami.created_at else None,
            "redeemed_by_user_id": kami.redeemed_by_user_id,
            "redeemed_at": to_api_beijing_iso(kami.redeemed_at, naive="civil") if kami.redeemed_at else None,
            "activate_time": to_api_beijing_iso(kami.activate_time, naive="civil") if kami.activate_time else None,
            "expire_time": to_api_beijing_iso(kami.expire_time, naive="civil") if kami.expire_time else None,
            "last_unbind_at": to_api_beijing_iso(kami.last_unbind_at, naive="civil") if kami.last_unbind_at else None,
            "last_verify_at": to_api_beijing_iso(kami.last_verify_at, naive="civil") if kami.last_verify_at else None,
        })

    return _csv_response(
        filename=f"kamis_{app_id}.csv",
        fieldnames=[
            "id",
            "app_id",
            "kami_code",
            "kami_type",
            "status",
            "batch_no",
            "points_amount",
            "points_valid_days",
            "time_value",
            "time_unit",
            "times_total",
            "times_remaining",
            "machine_bind_mode",
            "max_bind_devices",
            "authorization_owner",
            "user_bind_mode",
            "code_prefix",
            "code_length",
            "charset",
            "bind_ip",
            "unbind_count",
            "created_at",
            "redeemed_by_user_id",
            "redeemed_at",
            "activate_time",
            "expire_time",
            "last_unbind_at",
            "last_verify_at",
        ],
        rows=rows,
    )


@router.post("/kamis/delete", summary="批量删除卡密")
async def delete_kamis(
    payload: DeleteKamisRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """删除选中的未使用卡密，已激活或已兑换卡密会跳过以保留审计链路。"""
    app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, payload.app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权删除此应用的卡密")

    kami_codes = list(dict.fromkeys(code for code in payload.kami_codes if code))
    if not kami_codes:
        raise HTTPException(status_code=400, detail="kami_codes is required")

    statement = select(Kami).where(
        Kami.app_id == payload.app_id,
        Kami.kami_code.in_(kami_codes),
    )
    if payload.batch_no:
        statement = statement.where(Kami.batch_no == payload.batch_no)

    found_kamis = session.exec(statement).all()
    found_by_code = {kami.kami_code: kami for kami in found_kamis}
    deleted_codes = []
    skipped = []

    for code in kami_codes:
        kami = found_by_code.get(code)
        if not kami:
            skipped.append({"kami_code": code, "reason": "not_found_or_batch_mismatch"})
            continue
        if (
            kami.status == KamiStatus.active
            or kami.redeemed_by_user_id is not None
            or kami.bind_uuid
        ):
            skipped.append({"kami_code": code, "reason": "already_used"})
            continue

        deleted_codes.append(code)
        session.delete(kami)

    session.commit()

    log_admin_action(
        session=session,
        username=username,
        event_type="kami_delete",
        app_id=payload.app_id,
        payload={
            "batch_no": payload.batch_no,
            "requested_codes": kami_codes,
            "deleted_codes": deleted_codes,
            "skipped": skipped,
            "deleted_count": len(deleted_codes),
            "skipped_count": len(skipped),
        },
        message=f"用户 {username} 删除了 {len(deleted_codes)} 个卡密，跳过 {len(skipped)} 个",
    )

    return {
        "success": True,
        "message": "卡密删除完成",
        "data": {
            "deleted_count": len(deleted_codes),
            "deleted_codes": deleted_codes,
            "skipped_count": len(skipped),
            "skipped": skipped,
        }
    }


@router.put("/kamis/{kami_code}/freeze", summary="冻结卡密")
async def freeze_kami(
    kami_code: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """冻结指定卡密"""
    statement = select(Kami).where(Kami.kami_code == kami_code)
    kami = session.exec(statement).first()

    if not kami:
        raise HTTPException(status_code=404, detail="Kami not found")

    kami.status = KamiStatus.frozen
    session.add(kami)
    session.commit()

    return {"success": True, "message": "卡密已冻结"}


# ==================== 日志查询接口 ====================

@router.get("/logs", summary="查询行为日志")
async def list_event_logs(
    app_id: str,
    kami_code: Optional[str] = Query(None, description="卡密代码过滤"),
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """查询行为日志（支持多条件过滤和分页）- 分级权限控制"""
    # 验证应用是否存在
    statement_app = select(App).where(App.app_id == app_id)
    app = session.exec(statement_app).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    # 权限检查：非 admin 只能查看自己有权限的应用的日志
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not check_app_permission(session, app_id, username, is_admin):
        raise HTTPException(status_code=403, detail="无权查看此应用的日志")
    
    statement = select(EventLog).where(EventLog.app_id == app_id)

    if kami_code:
        statement = statement.where(EventLog.kami_code == kami_code)

    if event_type:
        statement = statement.where(EventLog.event_type == event_type)

    if start_date:
        statement = statement.where(EventLog.created_at >= datetime.fromisoformat(start_date))

    if end_date:
        statement = statement.where(EventLog.created_at <= datetime.fromisoformat(end_date))

    # 按时间倒序
    statement = statement.order_by(EventLog.created_at.desc())

    # 分页
    offset = (page - 1) * page_size
    statement = statement.offset(offset).limit(page_size)

    logs = session.exec(statement).all()

    return {
        "success": True,
        "data": {
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": log.id,
                    "kami_code": log.kami_code,
                    "event_type": log.event_type,
                    "payload": log.payload,
                    "created_at": to_api_beijing_iso(log.created_at, naive="civil")
                }
                for log in logs
            ]
        }
    }


# ==================== 设备管理接口 ====================

@router.get("/devices", summary="获取设备列表")
async def list_devices(
    app_id: str,
    risk_level: Optional[int] = Query(None, description="风险等级过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取设备列表（支持风险等级过滤）- 全局共享"""
    # 验证应用是否存在
    statement_app = select(App).where(App.app_id == app_id)
    app = session.exec(statement_app).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    # 移除权限检查，所有人可以查看所有设备
    statement = select(Device).where(Device.app_id == app_id)

    if risk_level is not None:
        statement = statement.where(Device.risk_level == risk_level)

    # 分页
    offset = (page - 1) * page_size
    statement = statement.offset(offset).limit(page_size)

    devices = session.exec(statement).all()

    return {
        "success": True,
        "data": {
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": device.id,
                    "uuid": device.uuid,
                    "fingerprint": device.fingerprint,
                    "last_ip": device.last_ip,
                    "risk_level": device.risk_level
                }
                for device in devices
            ]
        }
    }


@router.put("/devices/{device_id}/risk", summary="更新设备风险等级")
async def update_device_risk(
    device_id: int,
    risk_level: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """更新设备风险等级（0正常，1警告，2黑名单）- 全局共享"""
    statement = select(Device).where(Device.id == device_id)
    device = session.exec(statement).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    # 移除权限检查，所有人可以更新设备风险
    device.risk_level = risk_level
    session.add(device)
    session.commit()

    return {"success": True, "message": "设备风险等级已更新"}


# ==================== 登录接口（简化版）====================

@router.get("/login/public-key", summary="获取登录 AES 密钥")
async def get_login_aes_key():
    """
    获取用于登录加密的 AES 密钥
    前端在登录前调用此接口获取密钥
    """
    try:
        # 使用配置中的固定 AES 密钥（Base64 编码）
        from crypto import CryptoHelper
        
        # 生成或获取固定的 AES 密钥
        aes_key_b64 = _get_login_aes_key_b64()
        
        if not settings.LOGIN_AES_KEY:
            logger.warning("LOGIN_AES_KEY 未配置，当前进程将使用临时登录密钥")
        
        return {
            "success": True,
            "aes_key": aes_key_b64
        }
    except Exception as e:
        logger.exception("获取登录 AES 密钥失败")
        raise


@router.post("/login", summary="管理员登录")
async def admin_login(
    request: Request,
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
):
    """
    管理员登录接口（带风控 + AES+RSA 混合加密）
    
    风控策略：
    1. IP 限流：每分钟最多 5 次登录请求
    2. 账号锁定：连续失败 3 次锁定 10 分钟
    3. 登录日志：记录所有登录尝试
    
    加密方式：
    - 前端使用 AES 加密用户名和密码
    - 使用 RSA 公钥加密 AES 密钥
    - 后端使用 RSA 私钥解密 AES 密钥，再用 AES 解密数据
    """
    client_ip = request.client.host
    
    # 1. IP 限流检查
    ip_rate_key = f"login_rate:{client_ip}"
    login_attempts = redis_client.get(ip_rate_key)
    
    if login_attempts and int(login_attempts) >= 5:
        # 获取剩余时间
        ttl = redis_client.ttl(ip_rate_key)
        raise HTTPException(
            status_code=429,
            detail=f"IP 请求过于频繁，请 {ttl} 秒后重试"
        )
    
    # 增加 IP 计数
    pipe = redis_client.pipeline()
    pipe.incr(ip_rate_key)
    pipe.expire(ip_rate_key, 60)  # 1 分钟过期
    pipe.execute()
    
    # 2. 解析请求体
    username = None
    password = None
    
    try:
        body = await request.json()
        
        encrypted_data = body.get('encrypted_data')
        iv = body.get('iv')
        
        if not encrypted_data or not iv:
            raise HTTPException(status_code=400, detail="登录请求必须使用加密参数")

        from crypto import CryptoHelper

        aes_key_b64 = _get_login_aes_key_b64()
        decrypted_data = CryptoHelper.aes_decrypt(
            encrypted_data=encrypted_data,
            key_b64=aes_key_b64,
            iv=iv
        )

        username = decrypted_data.get('username')
        password = decrypted_data.get('password')

        if not username or not password:
            raise HTTPException(status_code=400, detail="解密后的数据不完整")
            
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("解析管理员登录请求失败")
        raise HTTPException(status_code=400, detail=f"请求解析失败: {str(e)}")
    
    # 3. 查询用户
    statement = select(AdminUser).where(AdminUser.username == username)
    user = session.exec(statement).first()
    
    # 记录登录日志
    log_data = {
        "username": username,
        "ip": client_ip,
        "timestamp": to_api_beijing_iso(get_now(), naive="civil"),
        "user_agent": request.headers.get("user-agent", "")
    }
    
    if not user:
        log_data["success"] = False
        log_data["message"] = "用户名不存在"
        _record_login_log(redis_client, log_data)
        try:
            admin_event_log = EventLog(
                app_id="admin",
                kami_code=None,
                event_type="admin_login",
                ip_address=client_ip,
                device_uuid=None,
                user_agent=request.headers.get("user-agent", ""),
                status=0,
                message=f"管理员登录失败：用户名 {username} 不存在",
                payload=None
            )
            session.add(admin_event_log)
            session.commit()
        except Exception:
            logger.exception("记录管理员登录失败日志失败")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    else:
        # 4. 检查账号是否被锁定
        if user.locked_until:
            # get_now() 返回带时区的时间，需要去掉时区信息后比较
            now_naive = get_now().replace(tzinfo=None)
            if now_naive < user.locked_until:
                remaining = (user.locked_until - now_naive).seconds
                log_data["success"] = False
                log_data["message"] = f"账号已锁定，剩余 {remaining} 秒"
                _record_login_log(redis_client, log_data)
                # 记录到数据库
                try:
                    admin_event_log = EventLog(
                        app_id="admin",
                        kami_code=None,
                        event_type="admin_login",
                        ip_address=client_ip,
                        device_uuid=None,
                        user_agent=request.headers.get("user-agent", ""),
                        status=0,
                        message=f"管理员 {username} 登录失败：账号已锁定",
                        payload=None
                    )
                    session.add(admin_event_log)
                    session.commit()
                except Exception:
                    logger.exception("记录管理员锁定登录日志失败")
                raise HTTPException(
                    status_code=423,
                    detail=f"账号已被锁定，请 {(remaining // 60) + 1} 分钟后重试"
                )
            user.locked_until = None
            user.failed_attempts = 0
        
        # 5. 验证密码
        if not verify_password(password, user.password_hash):
            # 密码错误，增加失败次数
            user.failed_attempts += 1
            
            # 如果失败次数达到 3 次，锁定 10 分钟
            if user.failed_attempts >= 3:
                # get_now() 返回带时区的时间，需要去掉时区信息后存入数据库
                user.locked_until = get_now().replace(tzinfo=None) + timedelta(minutes=10)
                log_data["success"] = False
                log_data["message"] = f"密码错误，账号已锁定 10 分钟"
                _record_login_log(redis_client, log_data)
                session.add(user)
                session.commit()
                raise HTTPException(
                    status_code=423,
                    detail="密码错误次数过多，账号已锁定 10 分钟"
                )
            else:
                remaining_attempts = 3 - user.failed_attempts
                log_data["success"] = False
                log_data["message"] = f"密码错误，还剩 {remaining_attempts} 次机会"
                _record_login_log(redis_client, log_data)
                session.add(user)
                session.commit()
                raise HTTPException(
                    status_code=401,
                    detail=f"用户名或密码错误，还剩 {remaining_attempts} 次机会"
                )

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        
        # 检查状态
        if user.status != 1:
            log_data["success"] = False
            log_data["message"] = "账号已被禁用"
            _record_login_log(redis_client, log_data)
            raise HTTPException(status_code=403, detail="账号已被禁用")
        
        # 登录成功，重置失败次数
        user.failed_attempts = 0
        user.locked_until = None
        # get_now() 返回带时区的时间，需要去掉时区信息后存入数据库
        user.last_login = get_now().replace(tzinfo=None)
        log_data["success"] = True
        log_data["message"] = "登录成功"
        session.add(user)
        session.commit()
    
    # 记录成功日志
    _record_login_log(redis_client, log_data)
    
    # 同时记录到数据库
    try:
        admin_event_log = EventLog(
            app_id="admin",  # 管理员使用特殊 app_id
            kami_code=None,
            event_type="admin_login",
            ip_address=client_ip,
            device_uuid=None,
            user_agent=request.headers.get("user-agent", ""),
            status=1,
            message=f"管理员 {username} 登录成功",
            payload=json.dumps({"user_id": user.id}, ensure_ascii=False)
        )
        session.add(admin_event_log)
        session.commit()
    except Exception:
        logger.exception("记录管理员登录成功日志失败")
    
    # 生成 Token
    user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
    token = create_access_token(
        data={
            "sub": username,
            "user_id": user.id,
            "is_admin": user.is_admin,
            "role": user_role,
        }
    )
    return {
        "success": True,
        "token": token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_info": {
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "role": user_role,
            "last_login": to_api_beijing_iso(user.last_login, naive="civil")
            if user.last_login
            else None
        }
    }


def _record_login_log(redis_client, log_data: dict):
    """记录登录日志到 Redis（保留最近 100 条）"""
    import json
    log_key = "login_logs"
    redis_client.lpush(log_key, json.dumps(log_data, ensure_ascii=False))
    redis_client.ltrim(log_key, 0, 99)  # 只保留最近 100 条


@router.get("/login-logs", summary="获取登录日志")
async def get_login_logs(
    limit: int = Query(50, ge=1, le=100, description="返回条数"),
    current_user: dict = Depends(get_current_user),
    redis_client = Depends(get_redis)
):
    """获取最近的登录日志（Redis）"""
    import json
    log_key = "login_logs"
    logs = redis_client.lrange(log_key, 0, limit - 1)
    
    return {
        "success": True,
        "data": [json.loads(log) for log in logs]
    }


@router.get("/event-logs", summary="获取事件日志")
async def get_event_logs(
    event_type: Optional[str] = Query(None, description="事件类型过滤"),
    app_id: Optional[str] = Query(None, description="应用ID过滤"),
    status: Optional[int] = Query(None, description="状态过滤：1成功，0失败"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取事件日志列表（数据库）- 分级权限控制"""
    from sqlmodel import func
    
    # 构建查询条件
    conditions = []
    
    # 如果指定了 app_id，进行权限检查
    if app_id:
        # 验证应用是否存在
        statement_app = select(App).where(App.app_id == app_id)
        app = session.exec(statement_app).first()
        
        if not app:
            raise HTTPException(status_code=404, detail="应用不存在")
        
        # 权限检查：非 admin 只能查看自己有权限的应用的日志
        username = current_user.get("sub")
        is_admin = current_user.get("is_admin", False)
        if not check_app_permission(session, app_id, username, is_admin):
            raise HTTPException(status_code=403, detail="无权查看此应用的日志")
        
        # 添加应用 ID 过滤条件
        conditions.append(EventLog.app_id == app_id)
    else:
        # 如果没有指定 app_id，需要根据用户权限过滤
        username = current_user.get("sub")
        is_admin = current_user.get("is_admin", False)
        
        if not is_admin:
            # 非 admin 用户：仅获取自己创建的应用 ID
            allowed_app_ids = session.exec(
                select(App.app_id).where(App.created_by == username)
            ).all()

            if not allowed_app_ids:
                # 没有任何权限，返回空列表
                return {
                    "success": True,
                    "data": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }
            
            # 添加应用 ID 过滤条件
            conditions.append(EventLog.app_id.in_(allowed_app_ids))
    
    # 其他过滤条件
    if event_type:
        conditions.append(EventLog.event_type == event_type)
    if status is not None:
        conditions.append(EventLog.status == status)
    
    # 查询总数
    count_statement = select(func.count(EventLog.id))
    if conditions:
        count_statement = count_statement.where(*conditions)
    total = session.exec(count_statement).one()
    
    # 查询数据
    statement = select(EventLog)
    if conditions:
        statement = statement.where(*conditions)
    statement = statement.order_by(EventLog.created_at.desc())
    statement = statement.offset((page - 1) * page_size).limit(page_size)
    
    logs = session.exec(statement).all()
    
    # 获取所有涉及的应用ID，批量查询应用名称
    app_ids = list(set(log.app_id for log in logs if log.app_id))
    apps_map = {}
    if app_ids:
        apps_statement = select(App).where(App.app_id.in_(app_ids))
        apps = session.exec(apps_statement).all()
        apps_map = {app.app_id: app.name for app in apps}
    
    return {
        "success": True,
        "data": [
            {
                "id": log.id,
                "app_id": log.app_id,
                "app_name": apps_map.get(log.app_id, "未知应用"),
                "kami_code": log.kami_code,
                "event_type": log.event_type,
                "ip_address": log.ip_address,
                "device_uuid": log.device_uuid,
                "user_agent": log.user_agent,
                "status": log.status,
                "message": log.message,
                "payload": log.payload,
                "created_at": to_api_beijing_iso(log.created_at, naive="civil")
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }


# ==================== 普通用户与积分管理 ====================

def _require_admin(current_user: dict):
    if _role_value(current_user) not in {AdminRole.super_admin.value, AdminRole.admin.value}:
        raise HTTPException(status_code=403, detail="需要管理员权限")


def _end_user_filter_conditions(
    keyword: Optional[str] = None,
    status: Optional[int] = None,
    app_id: Optional[str] = None,
):
    conditions = []
    if keyword:
        conditions.append(
            or_(
                EndUser.username.contains(keyword),
                EndUser.email.contains(keyword),
            )
        )
    if status is not None:
        conditions.append(EndUser.status == status)
    if app_id:
        legacy_user_ids = select(PointTransaction.user_id).where(
            PointTransaction.app_id == app_id
        )
        authorization_user_ids = select(AuthorizationAccount.user_id).where(
            AuthorizationAccount.app_id == app_id,
            AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
        )
        conditions.append(
            or_(
                EndUser.app_id == app_id,
                EndUser.id.in_(legacy_user_ids),
                EndUser.id.in_(authorization_user_ids),
            )
        )
    return conditions


@router.get("/end-users/stats", summary="获取普通用户统计")
async def get_end_user_stats(
    app_id: Optional[str] = Query(None, description="应用 ID"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取普通用户数量和积分账户统计"""
    from sqlmodel import func

    _require_admin(current_user)
    base_conditions = _end_user_filter_conditions(app_id=app_id)
    total = session.exec(select(func.count(EndUser.id)).where(*base_conditions)).one()
    active = session.exec(
        select(func.count(EndUser.id)).where(*base_conditions, EndUser.status == 1)
    ).one()
    disabled = session.exec(
        select(func.count(EndUser.id)).where(*base_conditions, EndUser.status == 0)
    ).one()

    user_ids = [
        user.id
        for user in session.exec(select(EndUser).where(*base_conditions)).all()
        if user.id is not None
    ]
    if app_id and not user_ids:
        accounts = []
    elif app_id:
        accounts = session.exec(
            select(UserPointAccount).where(UserPointAccount.user_id.in_(user_ids))
        ).all()
    else:
        accounts = session.exec(select(UserPointAccount)).all()
    with_balance = len([account for account in accounts if account.balance > 0])
    total_balance = sum(account.balance for account in accounts)
    authorization_conditions = [
        AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
    ]
    if app_id:
        authorization_conditions.append(AuthorizationAccount.app_id == app_id)
        if user_ids:
            authorization_conditions.append(AuthorizationAccount.user_id.in_(user_ids))
    authorization_accounts = session.exec(
        select(AuthorizationAccount).where(*authorization_conditions)
    ).all() if (not app_id or user_ids) else []
    with_authorization = len([
        account
        for account in authorization_accounts
        if account.is_lifetime
        or account.time_expires_at
        or account.times_balance > 0
        or account.points_balance > 0
    ])
    total_authorized_times = sum(account.times_balance for account in authorization_accounts)
    total_authorized_points = sum(account.points_balance for account in authorization_accounts)
    permanent_time_authorizations = len([account for account in authorization_accounts if account.is_lifetime])

    today_start = get_now().replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    today_new = session.exec(
        select(func.count(EndUser.id)).where(*base_conditions, EndUser.created_at >= today_start)
    ).one()

    return {
        "success": True,
        "data": {
            "total": total,
            "active": active,
            "disabled": disabled,
            "today_new": today_new,
            "with_balance": with_balance,
            "total_balance": total_balance,
            "with_authorization": with_authorization,
            "total_authorized_times": total_authorized_times,
            "total_authorized_points": total_authorized_points,
            "permanent_time_authorizations": permanent_time_authorizations,
        }
    }


@router.get("/end-users", summary="获取普通用户列表")
async def list_end_users(
    keyword: Optional[str] = Query(None, description="用户名/邮箱关键字"),
    app_id: Optional[str] = Query(None, description="应用 ID"),
    status: Optional[int] = Query(None, description="状态：1启用，0禁用"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取普通用户列表"""
    _require_admin(current_user)
    statement = select(EndUser)
    count_statement = select(EndUser)

    conditions = _end_user_filter_conditions(
        keyword=keyword,
        status=status,
        app_id=app_id,
    )
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    users = session.exec(
        statement.order_by(EndUser.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = len(session.exec(count_statement).all())
    user_ids = [user.id for user in users]
    account_map = {}
    authorization_map = {}
    if user_ids:
        accounts = session.exec(
            select(UserPointAccount).where(UserPointAccount.user_id.in_(user_ids))
        ).all()
        account_map = {account.user_id: account for account in accounts}
        auth_statement = select(AuthorizationAccount).where(
            AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
            AuthorizationAccount.user_id.in_(user_ids),
        )
        if app_id:
            auth_statement = auth_statement.where(AuthorizationAccount.app_id == app_id)
        authorization_accounts = session.exec(auth_statement).all()
        authorization_map = {account.user_id: account for account in authorization_accounts}

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": user.id,
                    "app_id": user.app_id or app_id,
                    "username": user.username,
                    "email": user.email,
                    "phone": user.phone,
                    "status": user.status,
                    **_authorization_summary_payload(authorization_map.get(user.id)),
                    "balance": account_map[user.id].balance if user.id in account_map else 0,
                    "total_recharged": account_map[user.id].total_recharged if user.id in account_map else 0,
                    "total_consumed": account_map[user.id].total_consumed if user.id in account_map else 0,
                    "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
                    "last_login": to_api_beijing_iso(user.last_login, naive="civil")
                    if user.last_login
                    else None,
                }
                for user in users
            ]
        }
    }


@router.get("/end-users/{user_id}/kamis", summary="获取普通用户卡密使用明细")
async def list_end_user_kamis(
    user_id: int,
    app_id: Optional[str] = Query(None, description="应用 ID"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """查看注册用户通过卡密兑换或授权来源关联到的卡密。"""
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    account_statement = select(AuthorizationAccount).where(
        AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
        AuthorizationAccount.user_id == user_id,
    )
    if app_id:
        account_statement = account_statement.where(AuthorizationAccount.app_id == app_id)
    authorization_accounts = session.exec(account_statement).all()
    account_ids = [account.id for account in authorization_accounts if account.id is not None]

    authorization_lots = []
    if account_ids:
        authorization_lots = session.exec(
            select(AuthorizationLot).where(AuthorizationLot.account_id.in_(account_ids))
        ).all()
    lots_by_code = {}
    for lot in authorization_lots:
        if lot.source_kami_code:
            lots_by_code.setdefault(lot.source_kami_code, []).append(lot)

    kami_conditions = [Kami.redeemed_by_user_id == user_id]
    if lots_by_code:
        kami_conditions.append(Kami.kami_code.in_(list(lots_by_code.keys())))
    statement = select(Kami).where(or_(*kami_conditions))
    if app_id:
        statement = statement.where(Kami.app_id == app_id)
    kamis = session.exec(statement.order_by(Kami.created_at.desc())).all()

    kami_codes = [kami.kami_code for kami in kamis]
    binding_count_by_code = {code: 0 for code in kami_codes}
    last_consume_at_by_code = {}
    if kami_codes:
        bindings = session.exec(
            select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(kami_codes))
        ).all()
        for binding in bindings:
            binding_count_by_code[binding.kami_code] = binding_count_by_code.get(binding.kami_code, 0) + 1
        consume_logs = session.exec(
            select(EventLog)
            .where(EventLog.kami_code.in_(kami_codes), EventLog.event_type == "consume")
            .order_by(EventLog.created_at.desc())
        ).all()
        for log in consume_logs:
            if log.kami_code and log.kami_code not in last_consume_at_by_code:
                last_consume_at_by_code[log.kami_code] = log.created_at

    def lot_payload(lot: AuthorizationLot) -> dict:
        return {
            "id": lot.id,
            "benefit_type": lot.benefit_type.value if hasattr(lot.benefit_type, "value") else lot.benefit_type,
            "amount_total": lot.amount_total,
            "amount_remaining": lot.amount_remaining,
            "starts_at": to_api_beijing_iso(lot.starts_at, naive="civil") if lot.starts_at else None,
            "expires_at": to_api_beijing_iso(lot.expires_at, naive="civil") if lot.expires_at else None,
            "created_at": to_api_beijing_iso(lot.created_at, naive="civil") if lot.created_at else None,
        }

    return {
        "success": True,
        "data": {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "app_id": user.app_id,
            },
            "items": [
                {
                    "id": kami.id,
                    "app_id": kami.app_id,
                    "kami_code": kami.kami_code,
                    "kami_type": kami.kami_type.value,
                    "status": kami.status.value,
                    "batch_no": kami.batch_no,
                    "points_amount": kami.points_amount,
                    "points_valid_days": kami.points_valid_days,
                    "time_value": kami.time_value,
                    "time_unit": kami.time_unit,
                    "times_total": kami.times_total,
                    "times_remaining": kami.times_remaining,
                    "bind_uuid": kami.bind_uuid,
                    "bind_ip": kami.bind_ip,
                    "machine_bind_mode": get_machine_bind_mode_value(kami.machine_bind_mode),
                    "max_bind_devices": kami.max_bind_devices,
                    "authorization_owner": get_authorization_owner_value(kami.authorization_owner),
                    "user_bind_mode": get_user_bind_mode_value(kami.user_bind_mode),
                    "device_bind_count": binding_count_by_code.get(kami.kami_code, 0)
                    or (1 if kami.bind_uuid else 0),
                    "created_at": to_api_beijing_iso(kami.created_at, naive="civil") if kami.created_at else None,
                    "activate_time": to_api_beijing_iso(kami.activate_time, naive="civil") if kami.activate_time else None,
                    "expire_time": to_api_beijing_iso(kami.expire_time, naive="civil") if kami.expire_time else None,
                    "redeemed_at": to_api_beijing_iso(kami.redeemed_at, naive="civil") if kami.redeemed_at else None,
                    "last_verify_at": to_api_beijing_iso(kami.last_verify_at, naive="civil") if kami.last_verify_at else None,
                    "last_consume_at": to_api_beijing_iso(
                        last_consume_at_by_code.get(kami.kami_code),
                        naive="civil",
                    )
                    if last_consume_at_by_code.get(kami.kami_code)
                    else None,
                    "remark": kami.remark,
                    "authorization_lots": [
                        lot_payload(lot)
                        for lot in lots_by_code.get(kami.kami_code, [])
                    ],
                }
                for kami in kamis
            ],
        },
    }


@router.get("/end-users/export", summary="导出普通用户 CSV")
async def export_end_users(
    keyword: Optional[str] = Query(None, description="用户名/邮箱关键字"),
    app_id: Optional[str] = Query(None, description="应用 ID"),
    status: Optional[int] = Query(None, description="状态：1启用，0禁用"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """导出普通用户与授权摘要。"""
    _require_admin(current_user)
    statement = select(EndUser)
    conditions = _end_user_filter_conditions(
        keyword=keyword,
        status=status,
        app_id=app_id,
    )
    if conditions:
        statement = statement.where(*conditions)

    users = session.exec(statement.order_by(EndUser.id.desc())).all()
    user_ids = [user.id for user in users]
    authorization_map = {}
    if user_ids:
        auth_statement = select(AuthorizationAccount).where(
            AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
            AuthorizationAccount.user_id.in_(user_ids),
        )
        if app_id:
            auth_statement = auth_statement.where(AuthorizationAccount.app_id == app_id)
        authorization_accounts = session.exec(auth_statement).all()
        authorization_map = {account.user_id: account for account in authorization_accounts}

    rows = []
    for user in users:
        authorization = _authorization_summary_payload(authorization_map.get(user.id))
        rows.append({
            "id": user.id,
            "app_id": user.app_id or app_id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "status": user.status,
            "time_authorization": authorization["time_authorization"],
            "times_remaining": authorization["times_remaining"],
            "points_remaining": authorization["points_remaining"],
            "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
            "last_login": to_api_beijing_iso(user.last_login, naive="civil") if user.last_login else None,
        })

    return _csv_response(
        filename="end_users.csv",
        fieldnames=[
            "id",
            "app_id",
            "username",
            "email",
            "phone",
            "status",
            "time_authorization",
            "times_remaining",
            "points_remaining",
            "created_at",
            "last_login",
        ],
        rows=rows,
    )


@router.put("/end-users/{user_id}/password", summary="重置普通用户密码")
async def reset_end_user_password(
    user_id: int,
    payload: EndUserPasswordResetRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """管理员重置普通用户登录密码。"""
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")

    user.password_hash = hash_password(payload.password)
    session.add(user)
    session.commit()
    return {"success": True, "message": "用户密码已重置"}


@router.put("/end-users/{user_id}/status", summary="更新普通用户状态")
async def update_end_user_status(
    user_id: int,
    status: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """启用或禁用普通用户"""
    _require_admin(current_user)
    if status not in (0, 1):
        raise HTTPException(status_code=400, detail="Invalid status")

    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")
    user.status = status
    session.add(user)
    session.commit()
    return {"success": True, "message": "用户状态已更新"}


@router.post("/authorizations/grant", summary="管理员分配用户授权")
async def grant_user_authorization(
    payload: AuthorizationGrantRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """给注册用户分配时间、次数或积分授权。"""
    _require_admin(current_user)
    app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    user = session.get(EndUser, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.app_id and user.app_id != payload.app_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "APP_MISMATCH", "message": "用户所属应用与授权应用不一致"},
        )
    if not user.app_id:
        user.app_id = payload.app_id
        session.add(user)

    account = get_or_create_authorization_account(
        session=session,
        app_id=payload.app_id,
        owner_type=AuthorizationOwnerType.user.value,
        user_id=user.id,
        username=user.username,
    )
    operator = current_user.get("sub")

    if payload.benefit_type == "time":
        if not payload.is_lifetime and not payload.days:
            raise HTTPException(status_code=400, detail="时间授权必须填写天数或选择永久")
        result = grant_time(
            session=session,
            account=account,
            days=payload.days,
            source_kami_code=payload.source_kami_code,
            is_lifetime=payload.is_lifetime,
            operator=operator,
        )
    elif payload.benefit_type == "times":
        if not payload.amount:
            raise HTTPException(status_code=400, detail="次数授权必须填写次数")
        result = grant_times(
            session=session,
            account=account,
            amount=payload.amount,
            source_kami_code=payload.source_kami_code,
            operator=operator,
        )
    else:
        if not payload.amount:
            raise HTTPException(status_code=400, detail="积分授权必须填写积分")
        result = grant_points(
            session=session,
            account=account,
            amount=payload.amount,
            source_kami_code=payload.source_kami_code,
            operator=operator,
        )

    session.refresh(account)
    log_admin_action(
        session=session,
        username=operator,
        event_type="authorization_grant",
        app_id=payload.app_id,
        payload={
            "user_id": payload.user_id,
            "benefit_type": payload.benefit_type,
            "amount": payload.amount,
            "days": payload.days,
            "is_lifetime": payload.is_lifetime,
            "result": result,
        },
        message=f"用户 {operator} 给 {user.username} 分配了 {payload.benefit_type} 授权",
    )
    return {
        "success": True,
        "message": "授权已分配",
        "data": {
            "user": {
                "id": user.id,
                "username": user.username,
                "app_id": user.app_id,
            },
            "authorization": _authorization_summary_payload(account),
            "transaction": result,
        },
    }


@router.get("/points/accounts", summary="获取积分账户列表")
async def list_point_accounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取积分账户列表"""
    _require_admin(current_user)
    all_accounts = session.exec(select(UserPointAccount)).all()
    accounts = session.exec(
        select(UserPointAccount)
        .order_by(UserPointAccount.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = [account.user_id for account in accounts]
    users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: user for user in users}

    return {
        "success": True,
        "data": {
            "total": len(all_accounts),
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": account.id,
                    "user_id": account.user_id,
                    "username": user_map[account.user_id].username if account.user_id in user_map else None,
                    "balance": account.balance,
                    "total_recharged": account.total_recharged,
                    "total_consumed": account.total_consumed,
                    "created_at": to_api_beijing_iso(account.created_at, naive="civil"),
                    "updated_at": to_api_beijing_iso(account.updated_at, naive="civil"),
                }
                for account in accounts
            ]
        }
    }


@router.get("/points/lots", summary="获取积分批次明细")
async def list_point_lots(
    user_id: Optional[int] = Query(None),
    only_available: bool = Query(False, description="仅查看仍有剩余积分的批次"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """查看用户积分批次、剩余积分和到期时间。"""
    _require_admin(current_user)
    statement = select(UserPointLot)
    count_statement = select(UserPointLot)
    conditions = []
    if user_id is not None:
        conditions.append(UserPointLot.user_id == user_id)
    if only_available:
        conditions.append(UserPointLot.points_remaining > 0)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = len(session.exec(count_statement).all())
    lots = session.exec(
        statement.order_by(UserPointLot.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = list(set(item.user_id for item in lots))
    users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: user for user in users}

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "user_id": item.user_id,
                    "username": user_map[item.user_id].username if item.user_id in user_map else None,
                    "source_transaction_id": item.source_transaction_id,
                    "app_id": item.app_id,
                    "kami_code": item.kami_code,
                    "points_total": item.points_total,
                    "points_remaining": item.points_remaining,
                    "expires_at": to_api_beijing_iso(item.expires_at, naive="civil") if item.expires_at else None,
                    "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
                    "updated_at": to_api_beijing_iso(item.updated_at, naive="civil"),
                }
                for item in lots
            ]
        }
    }


@router.get("/points/transactions/export", summary="导出积分流水 CSV")
async def export_point_transactions(
    user_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """导出积分流水，用于财务、订单和客服对账。"""
    _require_admin(current_user)
    statement = select(PointTransaction)
    conditions = []
    if user_id is not None:
        conditions.append(PointTransaction.user_id == user_id)
    if transaction_type:
        try:
            conditions.append(PointTransaction.transaction_type == PointTransactionType(transaction_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid transaction_type")
    if conditions:
        statement = statement.where(*conditions)

    transactions = session.exec(statement.order_by(PointTransaction.id.desc())).all()
    user_ids = list(set(item.user_id for item in transactions))
    users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: user for user in users}

    rows = []
    for item in transactions:
        rows.append({
            "id": item.id,
            "transaction_id": item.transaction_id,
            "user_id": item.user_id,
            "username": user_map[item.user_id].username if item.user_id in user_map else None,
            "app_id": item.app_id,
            "kami_code": item.kami_code,
            "transaction_type": item.transaction_type.value,
            "amount": item.amount,
            "balance_before": item.balance_before,
            "balance_after": item.balance_after,
            "biz_id": item.biz_id,
            "remark": item.remark,
            "metadata": item.metadata_json,
            "operator": item.operator,
            "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
        })

    return _csv_response(
        filename="point_transactions.csv",
        fieldnames=[
            "id",
            "transaction_id",
            "user_id",
            "username",
            "app_id",
            "kami_code",
            "transaction_type",
            "amount",
            "balance_before",
            "balance_after",
            "biz_id",
            "remark",
            "metadata",
            "operator",
            "created_at",
        ],
        rows=rows,
    )


@router.get("/points/transactions", summary="获取积分流水")
async def list_point_transactions(
    user_id: Optional[int] = Query(None),
    transaction_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取积分流水列表"""
    _require_admin(current_user)
    statement = select(PointTransaction)
    count_statement = select(PointTransaction)
    conditions = []
    if user_id is not None:
        conditions.append(PointTransaction.user_id == user_id)
    if transaction_type:
        try:
            conditions.append(PointTransaction.transaction_type == PointTransactionType(transaction_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid transaction_type")
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = len(session.exec(count_statement).all())
    transactions = session.exec(
        statement.order_by(PointTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    user_ids = list(set(item.user_id for item in transactions))
    users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all() if user_ids else []
    user_map = {user.id: user for user in users}

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "transaction_id": item.transaction_id,
                    "user_id": item.user_id,
                    "username": user_map[item.user_id].username if item.user_id in user_map else None,
                    "app_id": item.app_id,
                    "kami_code": item.kami_code,
                    "transaction_type": item.transaction_type.value,
                    "amount": item.amount,
                    "balance_before": item.balance_before,
                    "balance_after": item.balance_after,
                    "biz_id": item.biz_id,
                    "remark": item.remark,
                    "metadata": item.metadata_json,
                    "operator": item.operator,
                    "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
                }
                for item in transactions
            ]
        }
    }


@router.post("/points/adjust", summary="管理员调整积分")
async def admin_adjust_points(
    payload: PointAdjustRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """管理员手动加减积分"""
    _require_admin(current_user)
    user = session.get(EndUser, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")

    try:
        result = adjust_points(
            session=session,
            user_id=payload.user_id,
            amount=payload.amount,
            biz_id=payload.biz_id,
            remark=payload.remark,
            metadata=payload.metadata,
            admin_username=current_user.get("sub"),
        )
    except PointServiceError as error:
        _handle_point_error(error)

    return {"success": True, "message": "积分已调整", "data": result}


# ==================== 管理员账号管理 ====================

@router.get("/users", summary="获取管理员列表")
async def list_admin_users(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """获取所有管理员账号列表（所有人都可以查看，但非 admin 不能操作他人）"""
    statement = select(AdminUser)
    users = session.exec(statement).all()
    
    return {
        "success": True,
        "data": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "is_admin": user.is_admin,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "status": user.status,
                "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
                "last_login": to_api_beijing_iso(user.last_login, naive="civil")
                if user.last_login
                else None
            }
            for user in users
        ]
    }


@router.post("/users", summary="创建管理员账号")
async def create_admin_user(
    username: str,
    password: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    is_admin: bool = False,
    role: str = AdminRole.operator.value,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """创建新的管理员账号（只有 admin 可以创建）"""
    # 权限检查：只有 admin 可以创建用户
    _require_admin(current_user)
    try:
        admin_role = AdminRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效角色")
    
    # 检查用户名是否已存在
    statement = select(AdminUser).where(AdminUser.username == username)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 密码哈希
    password_hash = hash_password(password)
    
    # 创建用户
    user = AdminUser(
        username=username,
        password_hash=password_hash,
        email=email,
        phone=phone,
        is_admin=is_admin,
        role=AdminRole.super_admin if is_admin else admin_role,
        status=1
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {
        "success": True,
        "message": "管理员账号创建成功",
        "data": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "is_admin": user.is_admin,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": user.status
        }
    }


@router.put("/users/{user_id}", summary="更新管理员账号")
async def update_admin_user(
    user_id: int,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    status: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """更新管理员账号信息（只有 admin 可以更新他人，普通用户只能更新自己）"""
    statement = select(AdminUser).where(AdminUser.id == user_id)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 权限检查：非 admin 只能修改自己的信息
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not is_admin and user.username != username:
        raise HTTPException(status_code=403, detail="无权修改其他用户的信息")
    
    # 防止禁用自己
    if status is not None and user.username == username and status == 0:
        raise HTTPException(status_code=400, detail="不能禁用当前登录的账号")
    
    # 非 admin 不能修改 is_admin、status 等关键字段
    if not is_admin:
        # 普通用户只能修改 email 和 phone
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
    else:
        # admin 可以修改所有字段
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if status is not None:
            user.status = status
    
    session.add(user)
    session.commit()
    
    # 记录日志
    log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="user_update",
        payload={"target_user": user.username, "fields": [k for k, v in {"email": email, "phone": phone, "status": status}.items() if v is not None]},
        message=f"用户 {current_user.get('sub')} 更新了用户 {user.username} 的信息"
    )
    
    return {"success": True, "message": "更新成功"}


@router.put("/users/{user_id}/password", summary="重置密码")
async def reset_password(
    user_id: int,
    new_password: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """重置管理员密码（只有 admin 可以重置他人密码，普通用户只能重置自己）"""
    statement = select(AdminUser).where(AdminUser.id == user_id)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 权限检查：非 admin 只能修改自己的密码
    username = current_user.get("sub")
    is_admin = current_user.get("is_admin", False)
    if not is_admin and user.username != username:
        raise HTTPException(status_code=403, detail="无权修改其他用户的密码")
    
    # 密码哈希
    user.password_hash = hash_password(new_password)
    session.add(user)
    session.commit()
    
    # 记录日志
    log_admin_action(
        session=session,
        username=username,
        event_type="password_reset",
        payload={"target_user": user.username},
        message=f"用户 {username} 重置了用户 {user.username} 的密码"
    )
    
    return {"success": True, "message": "密码重置成功"}


@router.delete("/users/{user_id}", summary="删除管理员账号")
async def delete_admin_user(
    user_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """删除管理员账号（只有 admin 可以删除）"""
    # 权限检查：只有 admin 可以删除用户
    if not current_user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="无权删除用户，需要管理员权限")
    
    statement = select(AdminUser).where(AdminUser.id == user_id)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 防止删除自己
    if user.username == current_user.get("sub"):
        raise HTTPException(status_code=400, detail="不能删除当前登录的账号")
    
    session.delete(user)
    session.commit()
    
    # 记录日志
    log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="user_delete",
        payload={"deleted_user": user.username},
        message=f"用户 {current_user.get('sub')} 删除了用户 {user.username}"
    )
    
    return {"success": True, "message": "删除成功"}
