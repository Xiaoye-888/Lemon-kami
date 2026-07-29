import json
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_user
from commercial_service import (
    calculate_recharge_preview,
    cancel_recharge_order,
    create_recharge_order,
    create_recharge_order_from_upload,
    get_recharge_order_or_404,
    merchant_quota_summary,
    recharge_config_payload,
    recharge_order_payload,
    user_quota_transactions_payload,
)
from config import settings
from database import get_session
from datetime_utils import to_api_beijing_iso
from interface_docs_service import (
    dump_json as _dump_json,
    ensure_builtin_interfaces as _ensure_builtin_interfaces,
    interface_payload as _interface_payload,
    load_json as _load_json,
)
from app_release_service import (
    next_notice_revision,
    normalize_notice_level,
    normalize_notice_times,
    normalize_update_platform,
    normalize_update_status,
    normalize_url_type,
    notice_payload,
    version_payload,
)
from kami_query_service import (
    batch_stats_payload,
    kami_csv,
    kami_search_payload,
    merchant_kami_statement,
)
from issue_pricing_service import resolve_issue_pricing
from kami_spec_service import build_spec_key, build_spec_name, infer_spec_group
from models import (
    AuthorizationOwnerMode,
    AuthorizationAccount,
    AuthorizationLot,
    AuthorizationTransaction,
    AdminUser,
    AppAuthorization,
    App,
    AppInterfaceConfig,
    AppNotice,
    AppVersion,
    ApiInterface,
    Device,
    EndUser,
    EventLog,
    Kami,
    KamiStatus,
    KamiBatch,
    KamiDeviceBinding,
    KamiSpecGroup,
    KamiType,
    KamiSpec,
    MachineBindMode,
    PointTransaction,
    RechargeOrder,
    RechargeOrderStatus,
    UserBindMode,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaTransactionType,
    UserQuotaType,
    UserPointLot,
    get_now_naive,
)
from user_quota_service import (
    create_user_app,
    get_or_create_user_quota_account,
    get_user_visible_apps,
    issue_user_kamis,
    list_user_issued_kamis,
    preview_user_kami_issue,
    refund_user_quota,
    user_can_manage_app,
)


router = APIRouter(prefix="/api/v1/merchant", tags=["Merchant Console"])


class RechargePreviewRequest(BaseModel):
    amount: int | float | str
    mode: str = PydanticField("custom", pattern="^(fixed|custom)$")
    option_id: Optional[int] = None


class RechargeOrderCreateRequest(RechargePreviewRequest):
    channel: str = PydanticField(..., pattern="^(wechat|alipay|bank|other)$")
    remark: Optional[str] = None
    proof_image_data_url: Optional[str] = None


class MerchantOrderActionRequest(BaseModel):
    remark: Optional[str] = None


class MerchantProfileUpdateRequest(BaseModel):
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None


class MerchantAppCreateRequest(BaseModel):
    name: str = PydanticField(..., min_length=1, max_length=255)


class MerchantAppUpdateRequest(BaseModel):
    name: str = PydanticField(..., min_length=1, max_length=255)


class MerchantAppInterfaceConfigRequest(BaseModel):
    enabled: bool = True
    quota_limit: Optional[int] = PydanticField(None, ge=0)
    expires_at: Optional[datetime] = None
    config: Optional[dict[str, Any]] = None
    remark: Optional[str] = None


class MerchantAppNoticeRequest(BaseModel):
    title: str = PydanticField(..., min_length=1, max_length=128)
    content: str = PydanticField(..., min_length=1)
    level: str = "normal"
    enabled: bool = True
    popup: bool = False
    show_once: bool = True
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class MerchantAppVersionRequest(BaseModel):
    platform: str = "all"
    version: str = PydanticField(..., min_length=1, max_length=64)
    version_code: int = PydanticField(..., ge=1)
    title: str = PydanticField("发现新版本", min_length=1, max_length=128)
    notes: Optional[str] = None
    force_update: bool = False
    download_url: Optional[str] = None
    url_type: str = "direct"
    button_text: str = PydanticField("立即下载", min_length=1, max_length=64)
    status: str = "draft"


class MerchantSpecCreateRequest(BaseModel):
    kami_type: str = PydanticField(..., max_length=32)
    spec_group: str = PydanticField(KamiSpecGroup.custom.value, max_length=32)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)
    machine_bind_mode: str = PydanticField(MachineBindMode.one_card_one_device.value, max_length=32)
    max_bind_devices: Optional[int] = PydanticField(None, ge=0, le=1000)
    authorization_owner: str = PydanticField(AuthorizationOwnerMode.device.value, max_length=32)
    user_bind_mode: str = PydanticField(UserBindMode.none.value, max_length=32)
    status: int = PydanticField(1, ge=0, le=1)
    sort_order: int = PydanticField(0, ge=0)
    remark: Optional[str] = None


class MerchantSpecUpdateRequest(BaseModel):
    spec_group: Optional[str] = PydanticField(None, max_length=32)
    status: Optional[int] = PydanticField(None, ge=0, le=1)
    sort_order: Optional[int] = PydanticField(None, ge=0)
    remark: Optional[str] = None


class MerchantKamiIssueRequest(BaseModel):
    spec_id: Optional[int] = None
    kami_type: Optional[str] = PydanticField(None, max_length=32)
    count: int = PydanticField(..., gt=0, le=1000)
    batch_no: Optional[str] = PydanticField(None, max_length=64)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: int = PydanticField(16, ge=4, le=64)
    charset: str = PydanticField("upper_numeric", max_length=32)
    code_valid_days: Optional[int] = PydanticField(None, ge=1, le=36500)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)


class MerchantKamiDeleteRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    kami_codes: list[str] = PydanticField(..., min_length=1, max_length=1000)


class MerchantBatchUpdateRequest(BaseModel):
    batch_no: Optional[str] = PydanticField(None, min_length=1, max_length=64)
    kami_type: Optional[str] = PydanticField(None, max_length=32)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: Optional[int] = PydanticField(None, ge=4, le=64)
    charset: Optional[str] = PydanticField(None, max_length=32)
    code_valid_days: Optional[int] = PydanticField(None, ge=1, le=36500)
    machine_bind_mode: Optional[str] = PydanticField(None, max_length=32)
    max_bind_devices: Optional[int] = PydanticField(None, ge=0, le=1000)
    authorization_owner: Optional[str] = PydanticField(None, max_length=32)
    user_bind_mode: Optional[str] = PydanticField(None, max_length=32)
    status: Optional[int] = PydanticField(None, ge=0, le=1)
    remark: Optional[str] = None


class MerchantBatchAppendRequest(BaseModel):
    count: int = PydanticField(..., gt=0, le=1000)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: Optional[int] = PydanticField(None, ge=4, le=64)
    charset: Optional[str] = PydanticField(None, max_length=32)
    code_valid_days: Optional[int] = PydanticField(None, ge=1, le=36500)


TIME_CARD_UNITS = {
    KamiType.hour: (1, "hour"),
    KamiType.day: (1, "day"),
    KamiType.week: (1, "week"),
    KamiType.month: (1, "month"),
    KamiType.quarter: (1, "quarter"),
    KamiType.year: (1, "year"),
    KamiType.lifetime: (None, "lifetime"),
}


MERCHANT_INTERFACE_CONFIG_SCHEMAS: dict[str, list[dict[str, Any]]] = {
    "user.register": [
        {"key": "allow_register", "label": "允许注册", "type": "switch", "default": True},
        {"key": "password_min_length", "label": "密码最小长度", "type": "number", "min": 6, "max": 64, "default": 6},
    ],
    "user.login": [
        {"key": "allow_login", "label": "允许登录", "type": "switch", "default": True},
        {"key": "token_expire_minutes", "label": "Token 有效分钟", "type": "number", "min": 5, "max": 43200, "default": 1440},
    ],
    "points.balance": [
        {"key": "include_ledger_balance", "label": "返回账本余额", "type": "switch", "default": True},
    ],
    "points.redeem": [
        {"key": "allow_redeem", "label": "允许卡密充值", "type": "switch", "default": True},
        {"key": "bind_user_on_redeem", "label": "充值后绑定用户", "type": "switch", "default": True},
    ],
    "points.consume": [
        {"key": "min_amount", "label": "单次最小扣减", "type": "number", "min": 1, "max": 100000000, "default": 1},
        {"key": "max_amount", "label": "单次最大扣减", "type": "number", "min": 1, "max": 100000000, "default": 1000},
        {"key": "require_biz_id", "label": "必须传 biz_id", "type": "switch", "default": True},
    ],
    "points.transactions": [
        {"key": "max_page_size", "label": "最大分页条数", "type": "number", "min": 10, "max": 500, "default": 100},
    ],
    "sdk.public_key": [
        {"key": "allow_public_key", "label": "允许获取公钥", "type": "switch", "default": True},
    ],
    "sdk.verify": [
        {"key": "enable_user_authorization", "label": "启用用户授权能力", "type": "switch", "default": False},
        {"key": "signature_required", "label": "签名校验", "type": "switch", "default": True},
        {"key": "nonce_required", "label": "Nonce 防重放", "type": "switch", "default": True},
        {"key": "timestamp_tolerance_seconds", "label": "时间戳容差秒", "type": "number", "min": 30, "max": 86400, "default": 300},
        {"key": "ip_lock_enabled", "label": "IP 绑定验证", "type": "switch", "default": False},
    ],
    "sdk.unbind": [
        {"key": "allow_unbind", "label": "允许解绑", "type": "switch", "default": False},
        {"key": "max_unbind_count", "label": "最大解绑次数", "type": "number", "min": 0, "max": 100, "default": 0},
        {"key": "unbind_cooldown_hours", "label": "解绑冷却小时", "type": "number", "min": 0, "max": 8760, "default": 24},
        {"key": "unbind_deduct_hours", "label": "时间卡扣减小时", "type": "number", "min": 0, "max": 8760, "default": 0},
        {"key": "unbind_deduct_times", "label": "次数卡扣减次数", "type": "number", "min": 0, "max": 1000000, "default": 0},
        {"key": "ip_lock_enabled", "label": "解绑校验 IP", "type": "switch", "default": False},
    ],
    "sdk.device_limit": [
        {"key": "release_on_logout", "label": "退出自动释放", "type": "switch", "default": True},
        {"key": "heartbeat_timeout_seconds", "label": "心跳超时秒数", "type": "number", "min": 30, "max": 86400, "default": 180},
    ],
    "sdk.notice": [
        {"key": "allow_notice_read", "label": "允许公告读取", "type": "switch", "default": True},
        {"key": "max_notice_length", "label": "公告最大长度", "type": "number", "min": 100, "max": 20000, "default": 5000},
        {"key": "popup_enabled", "label": "允许弹窗公告", "type": "switch", "default": True},
    ],
    "sdk.update_check": [
        {"key": "allow_update_check", "label": "允许版本检查", "type": "switch", "default": True},
        {"key": "min_supported_version_code", "label": "最低支持版本编码", "type": "number", "min": 1, "max": 999999999, "default": 1},
        {"key": "force_update_enabled", "label": "允许强制更新", "type": "switch", "default": True},
    ],
    "sdk.report": [
        {"key": "allow_report", "label": "允许事件上报", "type": "switch", "default": True},
        {"key": "max_payload_kb", "label": "最大载荷 KB", "type": "number", "min": 1, "max": 1024, "default": 64},
    ],
}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _app_is_owned_by_user(app: App, user: EndUser) -> bool:
    return app.owner_user_id == user.id or (bool(app.created_by) and app.created_by == user.username)


def _app_authorized_to_user(session: Session, app_id: str, user: EndUser) -> bool:
    return session.exec(
        select(UserAppAuthorization).where(
            UserAppAuthorization.app_id == app_id,
            UserAppAuthorization.user_id == user.id,
        )
    ).first() is not None


def _get_visible_app_or_404(session: Session, user: EndUser, app_id: str) -> App:
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not user_can_manage_app(session, user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    return app


def _require_self_owned_app(session: Session, user: EndUser, app_id: str) -> App:
    app = _get_visible_app_or_404(session, user, app_id)
    if not _app_is_owned_by_user(app, user):
        raise HTTPException(status_code=403, detail="Only self-owned apps can manage specs")
    return app


def _get_visible_spec_or_404(session: Session, user: EndUser, spec_id: int) -> tuple[KamiSpec, App, bool]:
    spec = session.get(KamiSpec, spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")
    app = _get_visible_app_or_404(session, user, spec.app_id)
    is_owned = _app_is_owned_by_user(app, user)
    if not is_owned and spec.status != 1:
        raise HTTPException(status_code=404, detail="Spec not found")
    return spec, app, is_owned


def _merchant_app_payload(app: App, user: EndUser) -> dict:
    is_owned = _app_is_owned_by_user(app, user)
    capabilities = {
        "can_view": True,
        "can_manage": is_owned,
        "can_rename": is_owned,
        "can_delete": is_owned,
        "can_manage_interfaces": is_owned,
        "can_manage_specs": is_owned,
        "can_create_spec": is_owned,
        "can_edit_spec": is_owned,
        "can_delete_spec": is_owned,
        "can_edit_batch": is_owned,
        "can_append_batch": is_owned,
        "can_delete_batch": is_owned,
        "can_generate_batches": True,
        "can_view_batches": True,
        "can_view_kamis": True,
    }
    payload = {
        "id": app.id,
        "app_id": app.app_id,
        "name": app.name,
        "created_by": app.created_by,
        "owner_user_id": app.owner_user_id,
        "status": app.status,
        "is_owned": is_owned,
        "source": "self_owned" if is_owned else "admin_authorized",
        "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
        "capabilities": capabilities,
    }
    payload.update(capabilities)
    if is_owned:
        payload.update(
            {
                "app_secret": app.app_secret,
                "rsa_public_key": app.rsa_public_key,
            }
        )
    return payload


def _merchant_app_interface_payload(interface: ApiInterface, config: Optional[AppInterfaceConfig], app_id: str) -> dict:
    payload = _interface_payload(interface)
    default_enabled = interface.is_builtin
    config_schema = [dict(item) for item in MERCHANT_INTERFACE_CONFIG_SCHEMAS.get(interface.interface_key, [])]
    default_config = {
        item["key"]: item["default"]
        for item in config_schema
        if "key" in item and "default" in item
    } or None
    payload.update(
        {
            "app_id": app_id,
            "interface_id": interface.id,
            "config_id": config.id if config else None,
            "configured": config is not None,
            "enabled": config.enabled if config else default_enabled,
            "config": _load_json(config.config_json) if config else default_config,
            "config_schema": config_schema,
            "remark": config.remark if config else None,
            "config_created_at": to_api_beijing_iso(config.created_at, naive="civil") if config else None,
            "config_updated_at": to_api_beijing_iso(config.updated_at, naive="civil") if config else None,
        }
    )
    return payload


def _validate_merchant_version_payload(payload: MerchantAppVersionRequest) -> None:
    status = normalize_update_status(payload.status)
    if payload.force_update and status == "published" and not payload.download_url:
        raise HTTPException(status_code=400, detail="强制更新发布前必须填写下载地址")
    if status == "published" and payload.download_url is not None and not payload.download_url.strip():
        raise HTTPException(status_code=400, detail="下载地址不能为空")


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


def _delete_merchant_app_related_rows(session: Session, app_id: str) -> dict:
    kamis = session.exec(select(Kami).where(Kami.app_id == app_id)).all()
    kami_codes = [kami.kami_code for kami in kamis if kami.kami_code]
    devices = session.exec(select(Device).where(Device.app_id == app_id)).all()
    notices = session.exec(select(AppNotice).where(AppNotice.app_id == app_id)).all()
    versions = session.exec(select(AppVersion).where(AppVersion.app_id == app_id)).all()
    bindings = session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.app_id == app_id)).all()
    legacy_access_rows = session.exec(select(AppAuthorization).where(AppAuthorization.app_id == app_id)).all()
    user_authorizations = session.exec(
        select(UserAppAuthorization).where(UserAppAuthorization.app_id == app_id)
    ).all()
    interface_configs = session.exec(
        select(AppInterfaceConfig).where(AppInterfaceConfig.app_id == app_id)
    ).all()
    batches = session.exec(select(KamiBatch).where(KamiBatch.app_id == app_id)).all()
    specs = session.exec(select(KamiSpec).where(KamiSpec.app_id == app_id)).all()
    authorization_accounts = session.exec(
        select(AuthorizationAccount).where(AuthorizationAccount.app_id == app_id)
    ).all()
    account_ids = [account.id for account in authorization_accounts if account.id is not None]
    authorization_lots = []
    authorization_transactions = []
    if account_ids:
        authorization_lots = session.exec(
            select(AuthorizationLot).where(AuthorizationLot.account_id.in_(account_ids))
        ).all()
        authorization_transactions = session.exec(
            select(AuthorizationTransaction).where(AuthorizationTransaction.account_id.in_(account_ids))
        ).all()
    point_lots = session.exec(select(UserPointLot).where(UserPointLot.app_id == app_id)).all()
    point_transactions = session.exec(select(PointTransaction).where(PointTransaction.app_id == app_id)).all()
    log_conditions = [EventLog.app_id == app_id]
    if kami_codes:
        log_conditions.append(EventLog.kami_code.in_(kami_codes))
    event_logs = session.exec(select(EventLog).where(or_(*log_conditions))).all()

    counts = {
        "kami_count": len(kamis),
        "device_count": len(devices),
        "binding_count": len(bindings),
        "legacy_access_count": len(legacy_access_rows),
        "user_authorization_count": len(user_authorizations),
        "event_log_count": len(event_logs),
        "notice_count": len(notices),
        "version_count": len(versions),
        "interface_config_count": len(interface_configs),
        "batch_count": len(batches),
        "spec_count": len(specs),
        "authorization_account_count": len(authorization_accounts),
        "authorization_lot_count": len(authorization_lots),
        "authorization_transaction_count": len(authorization_transactions),
        "point_lot_count": len(point_lots),
        "point_transaction_count": len(point_transactions),
    }

    for row in event_logs:
        session.delete(row)
    for row in notices:
        session.delete(row)
    for row in versions:
        session.delete(row)
    for row in legacy_access_rows:
        session.delete(row)
    for row in user_authorizations:
        session.delete(row)
    for row in interface_configs:
        session.delete(row)
    for row in bindings:
        session.delete(row)
    for row in authorization_transactions:
        session.delete(row)
    for row in authorization_lots:
        session.delete(row)
    for row in point_lots:
        session.delete(row)
    for row in point_transactions:
        session.delete(row)

    session.flush()

    for row in authorization_accounts:
        session.delete(row)
    for row in kamis:
        session.delete(row)

    session.flush()

    for row in batches:
        session.delete(row)
    for row in specs:
        session.delete(row)
    for row in devices:
        session.delete(row)

    session.flush()
    return counts


def _spec_payload(spec: KamiSpec) -> dict:
    return {
        "id": spec.id,
        "app_id": spec.app_id,
        "spec_key": spec.spec_key,
        "spec_name": spec.spec_name,
        "spec_group": spec.spec_group.value if hasattr(spec.spec_group, "value") else spec.spec_group,
        "kami_type": spec.kami_type.value if hasattr(spec.kami_type, "value") else spec.kami_type,
        "points_amount": spec.points_amount,
        "points_valid_days": spec.points_valid_days,
        "time_value": spec.time_value,
        "time_unit": spec.time_unit,
        "times_total": spec.times_total,
        "machine_bind_mode": spec.machine_bind_mode.value if hasattr(spec.machine_bind_mode, "value") else spec.machine_bind_mode,
        "max_bind_devices": spec.max_bind_devices,
        "authorization_owner": spec.authorization_owner.value if hasattr(spec.authorization_owner, "value") else spec.authorization_owner,
        "user_bind_mode": spec.user_bind_mode.value if hasattr(spec.user_bind_mode, "value") else spec.user_bind_mode,
        "status": spec.status,
        "sort_order": spec.sort_order,
    }


def _normalize_max_bind_devices(machine_bind_mode: MachineBindMode, max_bind_devices: Optional[int]) -> int:
    if machine_bind_mode == MachineBindMode.no_limit:
        return 0
    if machine_bind_mode == MachineBindMode.one_card_one_device:
        return 1
    if max_bind_devices is None or max_bind_devices < 2:
        return 3
    return max_bind_devices


def _validate_merchant_spec_payload(
    payload: MerchantSpecCreateRequest,
) -> tuple[KamiType, MachineBindMode, AuthorizationOwnerMode, UserBindMode, Optional[int], Optional[str], int, KamiSpecGroup]:
    try:
        kami_type = KamiType(payload.kami_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid kami_type")
    try:
        machine_bind_mode = MachineBindMode(payload.machine_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid machine_bind_mode")
    try:
        authorization_owner = AuthorizationOwnerMode(payload.authorization_owner)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid authorization_owner")
    try:
        user_bind_mode = UserBindMode(payload.user_bind_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_bind_mode")
    try:
        spec_group = KamiSpecGroup(payload.spec_group)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid spec_group")

    if authorization_owner == AuthorizationOwnerMode.user and user_bind_mode == UserBindMode.none:
        raise HTTPException(status_code=400, detail="user authorization specs require a user binding mode")
    if kami_type == KamiType.points and not payload.points_amount:
        raise HTTPException(status_code=400, detail="points specs require points_amount")
    if kami_type == KamiType.times and not payload.times_total:
        raise HTTPException(status_code=400, detail="times specs require times_total")

    time_value = payload.time_value
    time_unit = payload.time_unit
    if kami_type in TIME_CARD_UNITS:
        default_value, default_unit = TIME_CARD_UNITS[kami_type]
        time_value = time_value or default_value
        time_unit = time_unit or default_unit
    if "spec_group" not in payload.model_fields_set:
        spec_group = KamiSpecGroup(
            infer_spec_group(
                kami_type,
                payload.points_amount,
                payload.points_valid_days,
                payload.times_total,
                time_value,
                time_unit,
            )
        )

    return (
        kami_type,
        machine_bind_mode,
        authorization_owner,
        user_bind_mode,
        time_value,
        time_unit,
        _normalize_max_bind_devices(machine_bind_mode, payload.max_bind_devices),
        spec_group,
    )


def _merchant_spec_stats(session: Session, spec_id: int, user_id: int) -> dict:
    batch_count = session.exec(
        select(KamiBatch)
        .join(Kami, (Kami.app_id == KamiBatch.app_id) & (Kami.batch_no == KamiBatch.batch_no))
        .where(KamiBatch.spec_id == spec_id, Kami.created_by_user_id == user_id)
    ).all()
    kamis = session.exec(
        select(Kami).where(Kami.spec_id == spec_id, Kami.created_by_user_id == user_id)
    ).all()
    codes = [kami.kami_code for kami in kamis if kami.kami_code]
    bindings = []
    if codes:
        bindings = session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(codes))).all()
    return {
        "batch_count": len({batch.id for batch in batch_count}),
        "total_count": len(kamis),
        "unused_count": len([kami for kami in kamis if _enum_value(kami.status) == "unused"]),
        "active_count": len([kami for kami in kamis if _enum_value(kami.status) == "active"]),
        "frozen_count": len([kami for kami in kamis if _enum_value(kami.status) == "frozen"]),
        "device_bound_count": len({binding.kami_code for binding in bindings if binding.kami_code}),
    }


def _merchant_spec_payload(spec: KamiSpec, *, user: EndUser, is_editable: bool, stats: Optional[dict] = None) -> dict:
    payload = _spec_payload(spec)
    batch_count = 0
    payload.update(
        {
            "is_editable": is_editable,
            "source": "self_owned" if is_editable else "admin_authorized",
            "remark": spec.remark,
            "created_at": to_api_beijing_iso(spec.created_at, naive="civil") if spec.created_at else None,
            "updated_at": to_api_beijing_iso(spec.updated_at, naive="civil") if spec.updated_at else None,
            "batch_count": 0,
            "total_count": 0,
            "unused_count": 0,
            "active_count": 0,
            "frozen_count": 0,
            "device_bound_count": 0,
        }
    )
    if stats:
        payload.update(stats)
    batch_count = int(payload.get("batch_count", 0) or 0)
    capabilities = {
        "can_view": True,
        "can_manage": is_editable,
        "can_generate_batch": True,
        "can_view_batches": True,
        "can_view_kamis": True,
        "can_edit": is_editable,
        "can_delete": is_editable and batch_count == 0,
    }
    payload["capabilities"] = capabilities
    payload.update(capabilities)
    return payload


def _merchant_batch_payload(
    session: Session,
    batch: KamiBatch,
    current_user: EndUser,
    *,
    spec: Optional[KamiSpec] = None,
    app: Optional[App] = None,
    stats: Optional[dict] = None,
) -> dict:
    app = app or session.exec(select(App).where(App.app_id == batch.app_id)).first()
    spec = spec or (session.get(KamiSpec, batch.spec_id) if batch.spec_id else None)
    stats = stats or batch_stats_payload(session, batch, created_by_user_id=current_user.id)
    has_user_cards = _merchant_batch_has_user_cards(session, batch, current_user.id, stats=stats)
    is_owned_app = bool(app and _app_is_owned_by_user(app, current_user))
    count = stats.get("total_count", 0)
    payload = {
        "id": batch.id,
        "app_id": batch.app_id,
        "spec_id": batch.spec_id,
        "spec_name": spec.spec_name if spec else None,
        "spec_group": _enum_value(spec.spec_group) if spec else None,
        "batch_no": batch.batch_no,
        "kami_type": _enum_value(batch.kami_type),
        "points_amount": batch.points_amount,
        "points_valid_days": batch.points_valid_days,
        "time_value": batch.time_value,
        "time_unit": batch.time_unit,
        "times_total": batch.times_total,
        "code_prefix": batch.code_prefix,
        "code_length": batch.code_length,
        "charset": batch.charset,
        "code_valid_days": batch.code_valid_days,
        "machine_bind_mode": _enum_value(batch.machine_bind_mode),
        "max_bind_devices": batch.max_bind_devices,
        "authorization_owner": _enum_value(batch.authorization_owner),
        "user_bind_mode": _enum_value(batch.user_bind_mode),
        "status": batch.status,
        "remark": batch.remark,
        "count": count,
        "stats": stats,
        **_batch_cost_snapshot(session, batch, current_user, count),
        "can_manage": has_user_cards,
        "source": "self_owned" if is_owned_app else "admin_authorized",
        "batch_source": "merchant_issued" if has_user_cards else "admin_managed",
        "created_at": to_api_beijing_iso(batch.created_at, naive="civil") if batch.created_at else None,
        "updated_at": to_api_beijing_iso(batch.updated_at, naive="civil") if batch.updated_at else None,
    }
    capabilities = {
        "can_view": True,
        "can_manage": has_user_cards,
        "can_edit": has_user_cards,
        "can_append": has_user_cards,
        "can_delete": has_user_cards and count == 0,
    }
    payload["capabilities"] = capabilities
    payload.update(capabilities)
    return payload


def _merchant_batch_has_user_cards(
    session: Session,
    batch: KamiBatch,
    user_id: int,
    *,
    stats: Optional[dict] = None,
) -> bool:
    if stats is not None and int(stats.get("total_count", 0) or 0) > 0:
        return True
    return session.exec(
        select(Kami.id)
        .where(
            Kami.app_id == batch.app_id,
            Kami.batch_no == batch.batch_no,
            Kami.created_by_user_id == user_id,
        )
        .limit(1)
    ).first() is not None


def _get_visible_merchant_batch_or_404(
    session: Session,
    current_user: EndUser,
    batch_id: int,
) -> tuple[KamiBatch, App, bool]:
    batch = session.get(KamiBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    app = _get_visible_app_or_404(session, current_user, batch.app_id)
    if not _merchant_batch_has_user_cards(session, batch, current_user.id):
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch, app, True


def _batch_cost_snapshot(session: Session, batch: KamiBatch, user: EndUser, fallback_count: int) -> dict:
    prefix = f"kami_issue:{batch.app_id}:{batch.batch_no}:"
    transaction = session.exec(
        select(UserQuotaTransaction)
        .where(
            UserQuotaTransaction.user_id == user.id,
            UserQuotaTransaction.quota_type == UserQuotaType.kami_issue,
            UserQuotaTransaction.transaction_type == UserQuotaTransactionType.consume,
            UserQuotaTransaction.biz_id.like(f"{prefix}%"),
        )
        .order_by(UserQuotaTransaction.id.desc())
    ).first()
    if not transaction:
        return {
            "unit_issue_cost": 1,
            "total_issue_cost": fallback_count,
            "pricing_source": "default",
            "pricing_rule_id": None,
        }
    metadata = {}
    if transaction.metadata_json:
        try:
            metadata = json.loads(transaction.metadata_json)
        except json.JSONDecodeError:
            metadata = {}
    unit_cost = metadata.get("unit_cost")
    total_cost = metadata.get("total_cost")
    return {
        "unit_issue_cost": unit_cost if unit_cost is not None else abs(transaction.amount) // max(fallback_count, 1),
        "total_issue_cost": total_cost if total_cost is not None else abs(transaction.amount),
        "pricing_source": metadata.get("pricing_source") or "default",
        "pricing_rule_id": metadata.get("pricing_rule_id"),
    }


def _merchant_kami_refund_unit_cost(session: Session, kami: Kami, user: EndUser) -> int:
    transaction = None
    if kami.issue_quota_transaction_id:
        transaction = session.exec(
            select(UserQuotaTransaction).where(
                UserQuotaTransaction.transaction_id == kami.issue_quota_transaction_id,
                UserQuotaTransaction.user_id == user.id,
                UserQuotaTransaction.quota_type == UserQuotaType.kami_issue,
                UserQuotaTransaction.transaction_type == UserQuotaTransactionType.consume,
            )
        ).first()

    if transaction:
        metadata = {}
        if transaction.metadata_json:
            try:
                metadata = json.loads(transaction.metadata_json)
            except json.JSONDecodeError:
                metadata = {}
        unit_cost = metadata.get("unit_cost")
        if unit_cost is None:
            try:
                count = int(metadata.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            if count > 0:
                unit_cost = abs(transaction.amount) // count
        if unit_cost is not None:
            try:
                return max(int(unit_cost), 1)
            except (TypeError, ValueError):
                pass

    if kami.batch_no:
        batch = session.exec(
            select(KamiBatch).where(KamiBatch.app_id == kami.app_id, KamiBatch.batch_no == kami.batch_no)
        ).first()
        if batch:
            snapshot = _batch_cost_snapshot(session, batch, user, 1)
            try:
                return max(int(snapshot.get("unit_issue_cost") or 1), 1)
            except (TypeError, ValueError):
                return 1
    return 1


def _resolve_merchant_issue_context(
    session: Session,
    current_user: EndUser,
    app_id: str,
    payload: MerchantKamiIssueRequest,
) -> tuple[App, Optional[KamiSpec]]:
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")

    is_owned = _app_is_owned_by_user(app, current_user)
    is_authorized = _app_authorized_to_user(session, app_id, current_user)
    spec = None
    if is_owned and payload.spec_id:
        spec = session.get(KamiSpec, payload.spec_id)
        if not spec or spec.app_id != app_id or spec.status != 1:
            raise HTTPException(status_code=400, detail="spec_id is not available")
    elif not is_owned and is_authorized:
        if not payload.spec_id:
            raise HTTPException(status_code=400, detail="spec_id is required for authorized apps")
        spec = session.get(KamiSpec, payload.spec_id)
        if not spec or spec.app_id != app_id or spec.status != 1:
            raise HTTPException(status_code=400, detail="spec_id is not available")
    elif payload.spec_id:
        spec = session.get(KamiSpec, payload.spec_id)
        if not spec or spec.app_id != app_id or spec.status != 1:
            raise HTTPException(status_code=400, detail="spec_id is not available")
    return app, spec


def _compact_end_user_payload(user: Optional[EndUser]) -> Optional[dict]:
    if not user:
        return None
    return {"id": user.id, "username": user.username, "app_id": user.app_id}


def _device_matches_binding(device: object, binding: KamiDeviceBinding) -> bool:
    return (
        getattr(device, "app_id", None) == binding.app_id
        and (
            getattr(device, "uuid", None) == binding.device_uuid
            or getattr(device, "fingerprint", None) == binding.fingerprint
        )
    )


def _merchant_device_payload(
    *,
    device: object,
    related_kami_codes: list[str],
    kamis_by_code: dict[str, Kami],
    users_by_id: dict[int, EndUser],
    apps_by_id: dict[str, App],
    current_user: EndUser,
) -> dict:
    related_kami_codes = list(dict.fromkeys([code for code in related_kami_codes if code]))
    related_kamis = [kamis_by_code[code] for code in related_kami_codes if code in kamis_by_code]
    kami = related_kamis[0] if related_kamis else None
    app = apps_by_id.get(getattr(device, "app_id", None))
    redeemed_user = users_by_id.get(kami.redeemed_by_user_id) if kami and kami.redeemed_by_user_id else None
    issuing_user = users_by_id.get(kami.created_by_user_id) if kami and kami.created_by_user_id else None
    owning_user = users_by_id.get(app.owner_user_id) if app and app.owner_user_id else None
    if not owning_user and app and _app_is_owned_by_user(app, current_user):
        owning_user = current_user

    if redeemed_user:
        user_type = "usage_user" if redeemed_user.app_id else "merchant"
    elif issuing_user:
        user_type = "merchant"
    else:
        user_type = "admin"

    risk_level = getattr(device, "risk_level", 0)
    risk_text = {0: "normal", 1: "warning", 2: "blocked"}.get(risk_level, "unknown")
    return {
        "id": getattr(device, "id", None),
        "app_id": getattr(device, "app_id", None),
        "app_name": app.name if app else None,
        "uuid": getattr(device, "uuid", None),
        "fingerprint": getattr(device, "fingerprint", None),
        "last_ip": getattr(device, "last_ip", None),
        "ip_count": 1 if getattr(device, "last_ip", None) else 0,
        "kami_code": related_kami_codes[0] if related_kami_codes else None,
        "kami_codes": related_kami_codes,
        "kami_count": len(related_kami_codes),
        "username": redeemed_user.username if redeemed_user else None,
        "user_id": redeemed_user.id if redeemed_user else None,
        "user_type": user_type,
        "app_source": "merchant_self_owned" if app and _app_is_owned_by_user(app, current_user) else "admin_authorized",
        "card_source": "merchant_issued" if issuing_user and issuing_user.id == current_user.id else "admin_issued" if kami else None,
        "issuing_user": _compact_end_user_payload(issuing_user),
        "owning_user": _compact_end_user_payload(owning_user),
        "risk_level": risk_level,
        "risk_level_text": risk_text,
        "last_verify_at": to_api_beijing_iso(kami.last_verify_at, naive="civil") if kami and kami.last_verify_at else None,
    }


def _merchant_device_payload_matches_keyword(payload: dict, keyword: Optional[str]) -> bool:
    if not keyword:
        return True
    keyword_lower = keyword.lower()
    values = [
        payload.get("app_id"),
        payload.get("app_name"),
        payload.get("uuid"),
        payload.get("fingerprint"),
        payload.get("last_ip"),
        payload.get("kami_code"),
        payload.get("username"),
        payload.get("user_id"),
        payload.get("user_type"),
        payload.get("app_source"),
        payload.get("card_source"),
    ]
    for user_key in ("issuing_user", "owning_user"):
        user_payload = payload.get(user_key) or {}
        values.extend([user_payload.get("id"), user_payload.get("username")])
    values.extend(payload.get("kami_codes") or [])
    return any(keyword_lower in str(value).lower() for value in values if value is not None)


def _merchant_quota_response_payload(data: dict) -> dict:
    threshold = settings.MERCHANT_LOW_ISSUE_QUOTA_THRESHOLD
    issue_card = {
        "balance": data.get("kami_issue_balance", 0),
        "total_granted": data.get("total_kami_issue_granted", 0),
        "warning_threshold": threshold,
        "low_balance_warning": data.get("kami_issue_balance", 0) < threshold,
    }
    return {**data, "issue_card": issue_card}


def _merchant_me_payload(user: EndUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "role": "merchant",
        "status": user.status,
        "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
        "last_login": to_api_beijing_iso(user.last_login, naive="civil")
        if user.last_login
        else None,
    }


def _normalize_optional_profile_text(value: Optional[str], field_name: str, max_length: int) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise HTTPException(status_code=400, detail=f"{field_name}长度不能超过 {max_length} 个字符")
    return normalized


def _sync_merchant_profile_relations(
    session: Session,
    user: EndUser,
    old_username: str,
    new_username: str,
) -> None:
    if user.id is None:
        return

    quota_account = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id == user.id)
    ).first()
    if quota_account:
        quota_account.username = new_username
        session.add(quota_account)

    for auth in session.exec(
        select(UserAppAuthorization).where(UserAppAuthorization.user_id == user.id)
    ).all():
        auth.username = new_username
        session.add(auth)

    for auth_account in session.exec(
        select(AuthorizationAccount).where(AuthorizationAccount.user_id == user.id)
    ).all():
        auth_account.username = new_username
        session.add(auth_account)

    for app in session.exec(
        select(App).where(App.owner_user_id == user.id)
    ).all():
        app.created_by = new_username
        session.add(app)

    if old_username != new_username:
        for app in session.exec(
            select(App).where(App.created_by == old_username)
        ).all():
            app.created_by = new_username
            session.add(app)


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{6,32}$")


async def get_current_merchant(
    current_user: EndUser = Depends(routes_user.get_current_end_user),
) -> EndUser:
    if current_user.app_id is not None:
        raise HTTPException(status_code=403, detail="application users cannot access merchant console")
    return current_user


@router.get("/me", summary="Get current merchant profile")
async def get_merchant_me(
    current_user: EndUser = Depends(get_current_merchant),
):
    return {
        "success": True,
        "data": _merchant_me_payload(current_user),
    }


@router.put("/me", summary="Update current merchant profile")
async def update_merchant_me(
    payload: MerchantProfileUpdateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    new_username = (payload.username or "").strip()
    if len(new_username) < 3 or len(new_username) > 64:
        raise HTTPException(status_code=400, detail="用户名长度需为 3 到 64 位")
    if re.search(r"\s", new_username):
        raise HTTPException(status_code=400, detail="用户名不能包含空格")

    new_email = _normalize_optional_profile_text(payload.email, "邮箱", 255)
    if new_email and not EMAIL_RE.fullmatch(new_email):
        raise HTTPException(status_code=400, detail="请输入有效邮箱")

    new_phone = _normalize_optional_profile_text(payload.phone, "手机号", 32)
    if new_phone and not PHONE_RE.fullmatch(new_phone):
        raise HTTPException(status_code=400, detail="请输入有效手机号")

    if new_username != current_user.username:
        username_exists = session.exec(
            select(EndUser).where(
                EndUser.username == new_username,
                EndUser.id != current_user.id,
            )
        ).first()
        if username_exists:
            raise HTTPException(status_code=400, detail="用户名已被占用")
        admin_exists = session.exec(select(AdminUser).where(AdminUser.username == new_username)).first()
        if admin_exists:
            raise HTTPException(status_code=400, detail="用户名已被系统管理员占用")

    old_username = current_user.username
    current_user.username = new_username
    current_user.email = new_email
    current_user.phone = new_phone
    session.add(current_user)
    _sync_merchant_profile_relations(session, current_user, old_username, new_username)
    session.commit()
    session.refresh(current_user)
    return {
        "success": True,
        "message": "账号资料已更新",
        "data": _merchant_me_payload(current_user),
    }


@router.get("/quotas", summary="Get merchant quota summary")
async def get_merchant_quotas(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    data = merchant_quota_summary(session, current_user)
    session.commit()
    payload = _merchant_quota_response_payload(data)
    return {"success": True, "data": payload, "issue_card": payload["issue_card"]}


@router.get("/dashboard", summary="Get merchant dashboard workbench")
async def get_merchant_dashboard(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    quota_payload = _merchant_quota_response_payload(merchant_quota_summary(session, current_user))
    apps = get_user_visible_apps(session, current_user)
    visible_app_ids = [app.app_id for app in apps]
    owned_app_ids = {app.app_id for app in apps if _app_is_owned_by_user(app, current_user)}

    pending_review_count = session.exec(
        select(RechargeOrder).where(
            RechargeOrder.user_id == current_user.id,
            RechargeOrder.status == RechargeOrderStatus.pending_review,
        )
    ).all()
    recent_orders = session.exec(
        select(RechargeOrder)
        .where(RechargeOrder.user_id == current_user.id)
        .order_by(RechargeOrder.id.desc())
        .limit(5)
    ).all()
    card_total = session.exec(
        select(Kami).where(Kami.created_by_user_id == current_user.id)
    ).all()

    notifications = []
    if visible_app_ids:
        now = get_now_naive()
        notice_rows = session.exec(
            select(AppNotice)
            .where(
                AppNotice.app_id.in_(visible_app_ids),
                AppNotice.enabled == True,  # noqa: E712
                or_(AppNotice.starts_at.is_(None), AppNotice.starts_at <= now),
                or_(AppNotice.ends_at.is_(None), AppNotice.ends_at >= now),
            )
            .order_by(AppNotice.id.desc())
            .limit(5)
        ).all()
        app_name_by_id = {app.app_id: app.name for app in apps}
        notifications = [
            {
                "id": notice.id,
                "app_id": notice.app_id,
                "app_name": app_name_by_id.get(notice.app_id),
                "title": notice.title,
                "content": notice.content,
                "level": notice.level,
                "created_at": to_api_beijing_iso(notice.created_at, naive="civil")
                if notice.created_at
                else None,
            }
            for notice in notice_rows
        ]

    recent_batches = []
    if visible_app_ids:
        for batch in session.exec(
            select(KamiBatch)
            .where(KamiBatch.app_id.in_(visible_app_ids))
            .order_by(KamiBatch.id.desc())
            .limit(12)
        ).all():
            stats = batch_stats_payload(session, batch, created_by_user_id=current_user.id)
            if stats["total_count"] <= 0:
                continue
            recent_batches.append(
                {
                    "id": batch.id,
                    "app_id": batch.app_id,
                    "batch_no": batch.batch_no,
                    "kami_type": _enum_value(batch.kami_type),
                    "count": stats["total_count"],
                    "stats": stats,
                    "created_at": to_api_beijing_iso(batch.created_at, naive="civil")
                    if batch.created_at
                    else None,
                }
            )
            if len(recent_batches) >= 5:
                break

    data = {
        "quota": quota_payload["issue_card"],
        "apps": {
            "total": len(apps),
            "self_owned": len(owned_app_ids),
            "authorized": len(apps) - len(owned_app_ids),
        },
        "orders": {
            "pending_review": len(pending_review_count),
            "recent": [recharge_order_payload(order) for order in recent_orders],
        },
        "cards": {
            "total": len(card_total),
        },
        "notifications": notifications,
        "recent_batches": recent_batches,
        "recent_orders": [recharge_order_payload(order) for order in recent_orders],
    }
    return {"success": True, "data": data}


@router.get("/quota-transactions", summary="List merchant quota transactions")
async def list_merchant_quota_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    return {
        "success": True,
        "data": user_quota_transactions_payload(
            session,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        ),
    }


@router.get("/devices", summary="List merchant visible devices")
async def list_merchant_devices(
    app_id: Optional[str] = Query(None),
    risk_level: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    apps = get_user_visible_apps(session, current_user)
    apps_by_id = {app.app_id: app for app in apps}
    selected_app_id = app_id.strip() if app_id else None
    if selected_app_id and selected_app_id not in apps_by_id:
        raise HTTPException(status_code=403, detail="No permission to view this app")
    if not apps_by_id:
        return {"success": True, "data": {"total": 0, "page": page, "page_size": page_size, "items": []}}

    allowed_app_ids = {selected_app_id} if selected_app_id else set(apps_by_id.keys())
    owned_app_ids = {
        app.app_id
        for app in apps
        if app.app_id in allowed_app_ids and _app_is_owned_by_user(app, current_user)
    }

    kami_visibility_conditions = [Kami.created_by_user_id == current_user.id]
    if owned_app_ids:
        kami_visibility_conditions.append(Kami.app_id.in_(list(owned_app_ids)))
    kami_statement = select(Kami).where(
        Kami.app_id.in_(list(allowed_app_ids)),
        or_(*kami_visibility_conditions),
    )
    kamis = session.exec(kami_statement).all()
    kamis_by_code = {kami.kami_code: kami for kami in kamis}
    visible_kami_codes = set(kamis_by_code.keys())

    binding_conditions = []
    if visible_kami_codes:
        binding_conditions.append(KamiDeviceBinding.kami_code.in_(list(visible_kami_codes)))
    if owned_app_ids:
        binding_conditions.append(KamiDeviceBinding.app_id.in_(list(owned_app_ids)))
    bindings = []
    if binding_conditions:
        bindings = session.exec(
            select(KamiDeviceBinding).where(
                KamiDeviceBinding.app_id.in_(list(allowed_app_ids)),
                or_(*binding_conditions),
            )
        ).all()
        missing_codes = {binding.kami_code for binding in bindings if binding.kami_code not in kamis_by_code}
        if missing_codes:
            extra_kamis = session.exec(
                select(Kami).where(
                    Kami.app_id.in_(list(allowed_app_ids)),
                    Kami.kami_code.in_(list(missing_codes)),
                )
            ).all()
            kamis_by_code.update({kami.kami_code: kami for kami in extra_kamis})

    device_statement = select(Device).where(Device.app_id.in_(list(allowed_app_ids)))
    if risk_level is not None:
        device_statement = device_statement.where(Device.risk_level == risk_level)
    physical_devices = session.exec(device_statement).all()

    related_codes_by_device_id = {}
    primary_binding_by_device_id = {}
    visible_devices = []
    for device in physical_devices:
        matching_bindings = [binding for binding in bindings if _device_matches_binding(device, binding)]
        if device.app_id not in owned_app_ids and not matching_bindings:
            continue
        visible_devices.append(device)
        related_codes_by_device_id[device.id] = [binding.kami_code for binding in matching_bindings]
        if matching_bindings:
            primary_binding_by_device_id[device.id] = matching_bindings[0]

    seen_device_keys = {
        (device.app_id, device.uuid, device.fingerprint)
        for device in visible_devices
    }
    for binding in bindings:
        matched_physical_device = any(_device_matches_binding(device, binding) for device in visible_devices)
        if matched_physical_device:
            continue
        key = (binding.app_id, binding.device_uuid, binding.fingerprint)
        if key in seen_device_keys:
            continue
        virtual_device = SimpleNamespace(
            id=f"binding:{binding.id}",
            app_id=binding.app_id,
            uuid=binding.device_uuid,
            fingerprint=binding.fingerprint,
            last_ip=binding.bind_ip,
            risk_level=0,
        )
        visible_devices.append(virtual_device)
        related_codes_by_device_id[virtual_device.id] = [binding.kami_code]
        primary_binding_by_device_id[virtual_device.id] = binding
        seen_device_keys.add(key)

    user_ids = {current_user.id}
    for app in apps_by_id.values():
        if app.owner_user_id:
            user_ids.add(app.owner_user_id)
    for kami in kamis_by_code.values():
        if kami.redeemed_by_user_id:
            user_ids.add(kami.redeemed_by_user_id)
        if kami.created_by_user_id:
            user_ids.add(kami.created_by_user_id)
    users = session.exec(select(EndUser).where(EndUser.id.in_(list(user_ids)))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}

    keyword_value = keyword.strip() if keyword else None
    payloads = [
        _merchant_device_payload(
            device=device,
            related_kami_codes=related_codes_by_device_id.get(device.id, []),
            kamis_by_code=kamis_by_code,
            users_by_id=users_by_id,
            apps_by_id=apps_by_id,
            current_user=current_user,
        )
        for device in visible_devices
    ]
    payloads = [payload for payload in payloads if _merchant_device_payload_matches_keyword(payload, keyword_value)]
    payloads.sort(key=lambda item: str(item.get("id") or ""), reverse=True)

    total = len(payloads)
    offset = (page - 1) * page_size
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": payloads[offset:offset + page_size],
        },
    }


@router.get("/recharge/config", summary="Get merchant recharge config")
async def get_merchant_recharge_config(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    return {"success": True, "data": recharge_config_payload(session, enabled_only=True)}


@router.post("/recharge/preview", summary="Preview merchant recharge")
async def preview_merchant_recharge(
    payload: RechargePreviewRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        data = calculate_recharge_preview(
            session,
            amount=payload.amount,
            mode=payload.mode,
            option_id=payload.option_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data}


@router.post("/recharge/orders", summary="Create merchant recharge order")
async def create_merchant_recharge_order(
    payload: RechargeOrderCreateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        order = create_recharge_order(
            session,
            user=current_user,
            amount=payload.amount,
            mode=payload.mode,
            option_id=payload.option_id,
            channel=payload.channel,
            remark=payload.remark,
            proof_image_data_url=payload.proof_image_data_url,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(order)
    return {"success": True, "message": "recharge order submitted", "data": recharge_order_payload(order)}


@router.post("/recharge/orders/upload", summary="Create merchant recharge order with proof upload")
async def create_merchant_recharge_order_with_upload(
    amount: str = Form(...),
    mode: str = Form("custom", pattern="^(fixed|custom)$"),
    option_id: Optional[int] = Form(None),
    channel: str = Form(..., pattern="^(wechat|alipay|bank|other)$"),
    remark: Optional[str] = Form(None),
    proof_file: UploadFile = File(...),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        order = await create_recharge_order_from_upload(
            session,
            user=current_user,
            amount=amount,
            mode=mode,
            option_id=option_id,
            channel=channel,
            remark=remark,
            proof_file=proof_file,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(order)
    return {"success": True, "message": "recharge order submitted", "data": recharge_order_payload(order)}


@router.get("/recharge/orders", summary="List merchant recharge orders")
async def list_merchant_recharge_orders(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    statement = select(RechargeOrder).where(RechargeOrder.user_id == current_user.id)
    count_statement = select(RechargeOrder).where(RechargeOrder.user_id == current_user.id)
    if status:
        statement = statement.where(RechargeOrder.status == status)
        count_statement = count_statement.where(RechargeOrder.status == status)
    total = len(session.exec(count_statement).all())
    orders = session.exec(
        statement.order_by(RechargeOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [recharge_order_payload(order) for order in orders],
        },
    }


@router.get("/recharge/orders/{order_no}", summary="Get merchant recharge order detail")
async def get_merchant_recharge_order(
    order_no: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    order = get_recharge_order_or_404(session, order_no)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No permission to view this order")
    return {"success": True, "data": recharge_order_payload(order)}


@router.post("/recharge/orders/{order_no}/cancel", summary="Cancel merchant recharge order")
async def cancel_merchant_recharge_order(
    order_no: str,
    payload: MerchantOrderActionRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    order = get_recharge_order_or_404(session, order_no)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No permission to cancel this order")
    try:
        order = cancel_recharge_order(
            session,
            order=order,
            operator=current_user.username,
            remark=payload.remark,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    return {"success": True, "message": "order canceled", "data": recharge_order_payload(order)}


@router.get("/recharge/orders/{order_no}/proof", summary="Get merchant recharge proof")
async def get_merchant_recharge_proof(
    order_no: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    order = get_recharge_order_or_404(session, order_no)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No permission to view this proof")
    if not order.proof_file_path or not Path(order.proof_file_path).exists():
        raise HTTPException(status_code=404, detail="Proof image not found")
    return FileResponse(order.proof_file_path, media_type=order.proof_content_type or "application/octet-stream")


@router.get("/kamis/export", summary="Export merchant issued kamis CSV")
async def export_merchant_kamis(
    app_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    spec_id: Optional[int] = Query(None),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        if spec_id is not None:
            _get_visible_spec_or_404(session, current_user, spec_id)
        statement = merchant_kami_statement(
            session,
            user_id=current_user.id,
            app_id=app_id,
            keyword=keyword,
            status=status,
            batch_no=batch_no,
            spec_id=spec_id,
        )
        content = kami_csv(session, statement)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="merchant-kamis.csv"'},
    )


@router.get("/kamis", summary="List merchant issued kamis across visible apps")
async def list_merchant_global_kamis(
    app_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    spec_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        if spec_id is not None:
            _get_visible_spec_or_404(session, current_user, spec_id)
        statement = merchant_kami_statement(
            session,
            user_id=current_user.id,
            app_id=app_id,
            keyword=keyword,
            status=status,
            batch_no=batch_no,
            spec_id=spec_id,
        )
        payload = kami_search_payload(session, statement, page=page, page_size=page_size)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": payload, **payload}


@router.get("/kami-specs/{spec_id}/batches", summary="List merchant batches for a spec")
async def list_merchant_spec_batches(
    spec_id: int,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    spec, _app, _is_owned = _get_visible_spec_or_404(session, current_user, spec_id)
    batches = session.exec(
        select(KamiBatch)
        .where(KamiBatch.spec_id == spec.id)
        .order_by(KamiBatch.id.desc())
    ).all()
    items = []
    for batch in batches:
        stats = batch_stats_payload(session, batch, created_by_user_id=current_user.id)
        if not _merchant_batch_has_user_cards(session, batch, current_user.id, stats=stats):
            continue
        items.append(_merchant_batch_payload(session, batch, current_user, spec=spec, stats=stats))
    return {"success": True, "data": {"items": items, "total": len(items)}, "items": items}


@router.get("/kami-specs/{spec_id}/kamis", summary="List merchant kamis for a spec")
async def list_merchant_spec_kamis(
    spec_id: int,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    spec, _app, _is_owned = _get_visible_spec_or_404(session, current_user, spec_id)
    try:
        statement = merchant_kami_statement(
            session,
            user_id=current_user.id,
            app_id=spec.app_id,
            keyword=keyword,
            status=status,
            batch_no=batch_no,
        ).where(Kami.spec_id == spec.id)
        payload = kami_search_payload(session, statement, page=page, page_size=page_size)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": payload, **payload}


@router.get("/batches/{batch_id}/kamis", summary="List merchant kamis for a batch")
async def list_merchant_batch_kamis(
    batch_id: int,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    batch, _app, _can_manage_batch = _get_visible_merchant_batch_or_404(session, current_user, batch_id)
    try:
        statement = merchant_kami_statement(
            session,
            user_id=current_user.id,
            app_id=batch.app_id,
            keyword=keyword,
            status=status,
            batch_no=batch.batch_no,
        )
        payload = kami_search_payload(session, statement, page=page, page_size=page_size)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": payload, **payload}


@router.get("/apps", summary="List merchant apps")
async def list_merchant_apps(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    apps = get_user_visible_apps(session, current_user)
    return {"success": True, "data": [_merchant_app_payload(app, current_user) for app in apps]}


@router.post("/apps", summary="Create merchant self-owned app")
async def create_merchant_app(
    payload: MerchantAppCreateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        app, quota = create_user_app(session, current_user, payload.name.strip())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(app)
    return {
        "success": True,
        "message": "app created",
        "data": {**_merchant_app_payload(app, current_user), "quota": quota},
    }


@router.get("/apps/{app_id}", summary="Get merchant app detail")
async def get_merchant_app_detail(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = _get_visible_app_or_404(session, current_user, app_id)
    return {"success": True, "data": _merchant_app_payload(app, current_user)}


@router.put("/apps/{app_id}", summary="Rename a self-owned merchant app")
async def update_merchant_app(
    app_id: str,
    payload: MerchantAppUpdateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = _require_self_owned_app(session, current_user, app_id)
    app.name = payload.name.strip()
    session.add(app)
    session.commit()
    session.refresh(app)
    return {"success": True, "message": "app updated", "data": _merchant_app_payload(app, current_user)}


@router.delete("/apps/{app_id}", summary="Delete a self-owned merchant app")
async def delete_merchant_app(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = _require_self_owned_app(session, current_user, app_id)
    counts = _delete_merchant_app_related_rows(session, app_id)
    session.delete(app)
    session.commit()
    return {"success": True, "message": "app deleted", "data": counts}


@router.get("/apps/{app_id}/interfaces", summary="List merchant app interfaces")
async def list_merchant_app_interfaces(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _get_visible_app_or_404(session, current_user, app_id)
    _ensure_builtin_interfaces(session)
    interfaces = session.exec(select(ApiInterface).order_by(ApiInterface.sort_order, ApiInterface.id.desc())).all()
    configs = session.exec(select(AppInterfaceConfig).where(AppInterfaceConfig.app_id == app_id)).all()
    config_by_interface_id = {config.interface_id: config for config in configs}
    return {
        "success": True,
        "data": [
            _merchant_app_interface_payload(item, config_by_interface_id.get(item.id), app_id)
            for item in interfaces
        ],
    }


@router.put("/apps/{app_id}/interfaces/{interface_id}", summary="Configure a merchant app interface")
async def update_merchant_app_interface(
    app_id: str,
    interface_id: int,
    payload: MerchantAppInterfaceConfigRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = _require_self_owned_app(session, current_user, app_id)
    _ensure_builtin_interfaces(session)
    interface = session.get(ApiInterface, interface_id)
    if not interface:
        raise HTTPException(status_code=404, detail="Interface not found")

    config = session.exec(
        select(AppInterfaceConfig).where(
            AppInterfaceConfig.app_id == app_id,
            AppInterfaceConfig.interface_id == interface_id,
        )
    ).first()
    now = get_now_naive()
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

    return {
        "success": True,
        "message": "interface updated",
        "data": _merchant_app_interface_payload(interface, config, app_id),
    }


@router.get("/apps/{app_id}/notices", summary="List merchant app notices")
async def list_merchant_app_notices(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _get_visible_app_or_404(session, current_user, app_id)
    notices = session.exec(
        select(AppNotice)
        .where(AppNotice.app_id == app_id)
        .order_by(AppNotice.updated_at.desc(), AppNotice.id.desc())
    ).all()
    return {"success": True, "data": {"total": len(notices), "items": [notice_payload(notice) for notice in notices]}}


@router.post("/apps/{app_id}/notices", summary="Create merchant app notice")
async def create_merchant_app_notice(
    app_id: str,
    payload: MerchantAppNoticeRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    now = get_now_naive()
    notice = AppNotice(
        app_id=app_id,
        title=payload.title.strip(),
        content=payload.content.strip(),
        level=normalize_notice_level(payload.level),
        enabled=payload.enabled,
        popup=payload.popup,
        show_once=payload.show_once,
        revision=next_notice_revision(session, app_id),
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        created_by=current_user.username,
        created_at=now,
        updated_at=now,
    )
    normalize_notice_times(notice)
    if notice.ends_at and notice.starts_at and notice.ends_at < notice.starts_at:
        raise HTTPException(status_code=400, detail="公告失效时间不能早于生效时间")
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return {"success": True, "message": "公告已保存", "data": notice_payload(notice)}


@router.put("/apps/{app_id}/notices/{notice_id}", summary="Update merchant app notice")
async def update_merchant_app_notice(
    app_id: str,
    notice_id: int,
    payload: MerchantAppNoticeRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    notice = session.exec(select(AppNotice).where(AppNotice.id == notice_id, AppNotice.app_id == app_id)).first()
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    notice.title = payload.title.strip()
    notice.content = payload.content.strip()
    notice.level = normalize_notice_level(payload.level)
    notice.enabled = payload.enabled
    notice.popup = payload.popup
    notice.show_once = payload.show_once
    notice.starts_at = payload.starts_at
    notice.ends_at = payload.ends_at
    notice.revision = (notice.revision or 0) + 1
    notice.updated_at = get_now_naive()
    normalize_notice_times(notice)
    if notice.ends_at and notice.starts_at and notice.ends_at < notice.starts_at:
        raise HTTPException(status_code=400, detail="公告失效时间不能早于生效时间")
    session.add(notice)
    session.commit()
    session.refresh(notice)
    return {"success": True, "message": "公告已更新", "data": notice_payload(notice)}


@router.delete("/apps/{app_id}/notices/{notice_id}", summary="Delete merchant app notice")
async def delete_merchant_app_notice(
    app_id: str,
    notice_id: int,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    notice = session.exec(select(AppNotice).where(AppNotice.id == notice_id, AppNotice.app_id == app_id)).first()
    if not notice:
        raise HTTPException(status_code=404, detail="公告不存在")
    session.delete(notice)
    session.commit()
    return {"success": True, "message": "公告已删除"}


@router.get("/apps/{app_id}/updates", summary="List merchant app versions")
async def list_merchant_app_versions(
    app_id: str,
    platform: Optional[str] = Query(None),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _get_visible_app_or_404(session, current_user, app_id)
    statement = select(AppVersion).where(AppVersion.app_id == app_id)
    if platform:
        statement = statement.where(AppVersion.platform == normalize_update_platform(platform))
    versions = session.exec(
        statement.order_by(AppVersion.version_code.desc(), AppVersion.updated_at.desc(), AppVersion.id.desc())
    ).all()
    return {"success": True, "data": {"total": len(versions), "items": [version_payload(version) for version in versions]}}


@router.post("/apps/{app_id}/updates", summary="Create merchant app version")
async def create_merchant_app_version(
    app_id: str,
    payload: MerchantAppVersionRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    _validate_merchant_version_payload(payload)
    platform = normalize_update_platform(payload.platform)
    existing = session.exec(
        select(AppVersion).where(
            AppVersion.app_id == app_id,
            AppVersion.platform == platform,
            AppVersion.version_code == payload.version_code,
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该平台版本编码已存在")
    now = get_now_naive()
    status = normalize_update_status(payload.status)
    version = AppVersion(
        app_id=app_id,
        platform=platform,
        version=payload.version.strip(),
        version_code=payload.version_code,
        title=payload.title.strip(),
        notes=payload.notes,
        force_update=payload.force_update,
        download_url=payload.download_url.strip() if payload.download_url else None,
        url_type=normalize_url_type(payload.url_type),
        button_text=payload.button_text.strip() or "立即下载",
        status=status,
        created_by=current_user.username,
        published_at=now if status == "published" else None,
        created_at=now,
        updated_at=now,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return {"success": True, "message": "版本更新已保存", "data": version_payload(version)}


@router.put("/apps/{app_id}/updates/{version_id}", summary="Update merchant app version")
async def update_merchant_app_version(
    app_id: str,
    version_id: int,
    payload: MerchantAppVersionRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    _validate_merchant_version_payload(payload)
    version = session.exec(select(AppVersion).where(AppVersion.id == version_id, AppVersion.app_id == app_id)).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    platform = normalize_update_platform(payload.platform)
    duplicate = session.exec(
        select(AppVersion).where(
            AppVersion.app_id == app_id,
            AppVersion.platform == platform,
            AppVersion.version_code == payload.version_code,
            AppVersion.id != version_id,
        )
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="该平台版本编码已存在")
    now = get_now_naive()
    new_status = normalize_update_status(payload.status)
    version.platform = platform
    version.version = payload.version.strip()
    version.version_code = payload.version_code
    version.title = payload.title.strip()
    version.notes = payload.notes
    version.force_update = payload.force_update
    version.download_url = payload.download_url.strip() if payload.download_url else None
    version.url_type = normalize_url_type(payload.url_type)
    version.button_text = payload.button_text.strip() or "立即下载"
    if new_status == "published" and version.status != "published":
        version.published_at = now
    version.status = new_status
    version.updated_at = now
    session.add(version)
    session.commit()
    session.refresh(version)
    return {"success": True, "message": "版本更新已保存", "data": version_payload(version)}


@router.delete("/apps/{app_id}/updates/{version_id}", summary="Delete merchant app version")
async def delete_merchant_app_version(
    app_id: str,
    version_id: int,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    version = session.exec(select(AppVersion).where(AppVersion.id == version_id, AppVersion.app_id == app_id)).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    session.delete(version)
    session.commit()
    return {"success": True, "message": "版本已删除"}


@router.get("/apps/{app_id}/specs", summary="List specs for a merchant app")
async def list_merchant_app_specs(
    app_id: str,
    kami_type: Optional[str] = Query(None),
    spec_group: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = _get_visible_app_or_404(session, current_user, app_id)
    is_owned = _app_is_owned_by_user(app, current_user)
    statement = select(KamiSpec).where(KamiSpec.app_id == app_id)
    if not is_owned:
        statement = statement.where(KamiSpec.status == 1)
    if kami_type:
        try:
            statement = statement.where(KamiSpec.kami_type == KamiType(kami_type))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid kami_type")
    if spec_group:
        try:
            statement = statement.where(KamiSpec.spec_group == KamiSpecGroup(spec_group))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid spec_group")
    if keyword:
        statement = statement.where(KamiSpec.spec_name.like(f"%{keyword}%"))
    specs = session.exec(statement.order_by(KamiSpec.sort_order, KamiSpec.id)).all()
    items = [
        _merchant_spec_payload(
            spec,
            user=current_user,
            is_editable=is_owned,
            stats=_merchant_spec_stats(session, spec.id, current_user.id),
        )
        for spec in specs
    ]
    return {"success": True, "data": {"items": items, "total": len(items)}, "items": items}


@router.post("/apps/{app_id}/specs", summary="Create a self-owned merchant app spec")
async def create_merchant_app_spec(
    app_id: str,
    payload: MerchantSpecCreateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    (
        kami_type,
        machine_bind_mode,
        authorization_owner,
        user_bind_mode,
        time_value,
        time_unit,
        max_bind_devices,
        spec_group,
    ) = _validate_merchant_spec_payload(payload)
    spec_key = build_spec_key(
        kami_type=kami_type,
        points_amount=payload.points_amount if kami_type == KamiType.points else None,
        points_valid_days=payload.points_valid_days if kami_type == KamiType.points else None,
        times_total=payload.times_total if kami_type == KamiType.times else None,
        time_value=time_value,
        time_unit=time_unit,
        machine_bind_mode=machine_bind_mode,
        max_bind_devices=max_bind_devices,
        authorization_owner=authorization_owner,
        user_bind_mode=user_bind_mode,
    )
    existing = session.exec(
        select(KamiSpec).where(KamiSpec.app_id == app_id, KamiSpec.spec_key == spec_key)
    ).first()
    if existing:
        return {
            "success": True,
            "message": "spec already exists",
            "data": _merchant_spec_payload(
                existing,
                user=current_user,
                is_editable=True,
                stats=_merchant_spec_stats(session, existing.id, current_user.id),
            ),
        }

    now = get_now_naive()
    spec = KamiSpec(
        app_id=app_id,
        spec_key=spec_key,
        spec_name=build_spec_name(
            kami_type,
            payload.points_amount if kami_type == KamiType.points else None,
            payload.points_valid_days if kami_type == KamiType.points else None,
            payload.times_total if kami_type == KamiType.times else None,
            time_value,
            time_unit,
        ),
        spec_group=spec_group,
        kami_type=kami_type,
        points_amount=payload.points_amount if kami_type == KamiType.points else None,
        points_valid_days=payload.points_valid_days if kami_type == KamiType.points else None,
        times_total=payload.times_total if kami_type == KamiType.times else None,
        time_value=time_value if kami_type in TIME_CARD_UNITS else None,
        time_unit=time_unit if kami_type in TIME_CARD_UNITS else None,
        machine_bind_mode=machine_bind_mode,
        max_bind_devices=max_bind_devices,
        authorization_owner=authorization_owner,
        user_bind_mode=user_bind_mode,
        status=payload.status,
        sort_order=payload.sort_order,
        remark=payload.remark,
        created_at=now,
        updated_at=now,
    )
    session.add(spec)
    session.commit()
    session.refresh(spec)
    return {
        "success": True,
        "message": "spec created",
        "data": _merchant_spec_payload(
            spec,
            user=current_user,
            is_editable=True,
            stats=_merchant_spec_stats(session, spec.id, current_user.id),
        ),
    }


@router.put("/apps/{app_id}/specs/{spec_id}", summary="Update a self-owned merchant app spec")
async def update_merchant_app_spec(
    app_id: str,
    spec_id: int,
    payload: MerchantSpecUpdateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    spec = session.get(KamiSpec, spec_id)
    if not spec or spec.app_id != app_id:
        raise HTTPException(status_code=404, detail="Spec not found")
    data = payload.model_dump(exclude_unset=True)
    if "spec_group" in data and data["spec_group"] is not None:
        try:
            spec.spec_group = KamiSpecGroup(data["spec_group"])
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid spec_group")
    if "status" in data and data["status"] is not None:
        spec.status = data["status"]
    if "sort_order" in data and data["sort_order"] is not None:
        spec.sort_order = data["sort_order"]
    if "remark" in data:
        spec.remark = data["remark"]
    spec.updated_at = get_now_naive()
    session.add(spec)
    session.commit()
    session.refresh(spec)
    return {
        "success": True,
        "message": "spec updated",
        "data": _merchant_spec_payload(
            spec,
            user=current_user,
            is_editable=True,
            stats=_merchant_spec_stats(session, spec.id, current_user.id),
        ),
    }


@router.delete("/apps/{app_id}/specs/{spec_id}", summary="Delete an empty self-owned merchant app spec")
async def delete_merchant_app_spec(
    app_id: str,
    spec_id: int,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    _require_self_owned_app(session, current_user, app_id)
    spec = session.get(KamiSpec, spec_id)
    if not spec or spec.app_id != app_id:
        raise HTTPException(status_code=404, detail="Spec not found")
    existing_batch = session.exec(select(KamiBatch).where(KamiBatch.spec_id == spec_id)).first()
    existing_kami = session.exec(select(Kami).where(Kami.spec_id == spec_id)).first()
    if existing_batch or existing_kami:
        raise HTTPException(status_code=400, detail="spec still has batches or kamis")
    session.delete(spec)
    session.commit()
    return {"success": True, "message": "spec deleted"}


@router.post("/apps/{app_id}/kamis/batch", summary="Issue merchant kamis")
async def issue_merchant_kamis(
    app_id: str,
    payload: MerchantKamiIssueRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app, spec = _resolve_merchant_issue_context(session, current_user, app_id, payload)

    kami_type = payload.kami_type
    points_amount = payload.points_amount
    points_valid_days = payload.points_valid_days
    times_total = payload.times_total
    time_value = payload.time_value
    time_unit = payload.time_unit
    machine_bind_mode = "one_card_one_device"
    max_bind_devices = 1
    authorization_owner = "device"
    user_bind_mode = "none"

    if spec:
        kami_type = spec.kami_type.value if hasattr(spec.kami_type, "value") else spec.kami_type
        points_amount = spec.points_amount
        points_valid_days = spec.points_valid_days
        times_total = spec.times_total
        time_value = spec.time_value
        time_unit = spec.time_unit
        machine_bind_mode = spec.machine_bind_mode
        max_bind_devices = spec.max_bind_devices
        authorization_owner = spec.authorization_owner
        user_bind_mode = spec.user_bind_mode

    if not kami_type:
        raise HTTPException(status_code=400, detail="kami_type is required")

    try:
        pricing = resolve_issue_pricing(session, user=current_user, app=app, spec=spec)
        result = issue_user_kamis(
            session,
            current_user,
            app,
            spec_id=spec.id if spec else None,
            kami_type=kami_type,
            count=payload.count,
            batch_no=payload.batch_no,
            code_prefix=payload.code_prefix,
            code_length=payload.code_length,
            charset=payload.charset,
            code_valid_days=payload.code_valid_days,
            points_amount=points_amount,
            points_valid_days=points_valid_days,
            times_total=times_total,
            time_value=time_value,
            time_unit=time_unit,
            machine_bind_mode=machine_bind_mode,
            max_bind_devices=max_bind_devices,
            authorization_owner=authorization_owner,
            user_bind_mode=user_bind_mode,
            unit_cost=pricing["unit_cost"],
            pricing_source=pricing["pricing_source"],
            pricing_rule_id=pricing["pricing_rule_id"],
        )
        result.update(
            {
                "pricing_source": pricing["pricing_source"],
                "pricing_rule_id": pricing["pricing_rule_id"],
                "pricing_rule_key": pricing["pricing_rule_key"],
            }
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    return {"success": True, "message": "issue success", "data": result}


@router.post("/apps/{app_id}/kamis/preview", summary="Preview merchant kami issue cost")
async def preview_merchant_kamis(
    app_id: str,
    payload: MerchantKamiIssueRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app, spec = _resolve_merchant_issue_context(session, current_user, app_id, payload)
    kami_type = payload.kami_type
    if spec:
        kami_type = spec.kami_type.value if hasattr(spec.kami_type, "value") else spec.kami_type
    if not kami_type:
        raise HTTPException(status_code=400, detail="kami_type is required")
    try:
        pricing = resolve_issue_pricing(session, user=current_user, app=app, spec=spec)
        data = preview_user_kami_issue(
            session,
            current_user,
            app,
            count=payload.count,
            unit_cost=pricing["unit_cost"],
        )
        data.update(
            {
                "pricing_source": pricing["pricing_source"],
                "pricing_rule_id": pricing["pricing_rule_id"],
                "pricing_rule_key": pricing["pricing_rule_key"],
            }
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data}


@router.get("/apps/{app_id}/kamis", summary="List merchant issued kamis")
async def list_merchant_kamis(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    kamis = list_user_issued_kamis(session, current_user, app_id)
    return {
        "success": True,
        "data": [
            {
                "id": kami.id,
                "app_id": kami.app_id,
                "spec_id": kami.spec_id,
                "kami_code": kami.kami_code,
                "kami_type": kami.kami_type.value if hasattr(kami.kami_type, "value") else kami.kami_type,
                "status": kami.status.value if hasattr(kami.status, "value") else kami.status,
                "batch_no": kami.batch_no,
                "points_amount": kami.points_amount,
                "points_valid_days": kami.points_valid_days,
                "times_total": kami.times_total,
                "times_remaining": kami.times_remaining,
                "time_value": kami.time_value,
                "time_unit": kami.time_unit,
                "created_by_user_id": kami.created_by_user_id,
                "created_at": to_api_beijing_iso(kami.created_at, naive="civil") if kami.created_at else None,
            }
            for kami in kamis
        ],
    }


@router.post("/kamis/delete", summary="Delete merchant issued kamis and refund issue quota")
async def delete_merchant_kamis(
    payload: MerchantKamiDeleteRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not user_can_manage_app(session, current_user, payload.app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")

    kami_codes = list(dict.fromkeys(code.strip() for code in payload.kami_codes if code and code.strip()))
    if not kami_codes:
        raise HTTPException(status_code=400, detail="kami_codes is required")

    found_kamis = session.exec(
        select(Kami).where(
            Kami.app_id == payload.app_id,
            Kami.kami_code.in_(kami_codes),
            Kami.created_by_user_id == current_user.id,
        )
    ).all()
    found_by_code = {kami.kami_code: kami for kami in found_kamis}
    skipped = []
    deleted_codes = []
    deleted_details = []
    refunded_amount = 0
    account = get_or_create_user_quota_account(session, current_user.id, current_user.username)

    for code in kami_codes:
        kami = found_by_code.get(code)
        if not kami:
            skipped.append({"kami_code": code, "reason": "not_found_or_not_owned"})
            continue
        if kami.status != KamiStatus.unused:
            skipped.append({"kami_code": code, "reason": "only_unused_kamis_can_be_refunded"})
            continue

        refund_amount = _merchant_kami_refund_unit_cost(session, kami, current_user)
        refund_result = refund_user_quota(
            session=session,
            account=account,
            quota_type=UserQuotaType.kami_issue,
            amount=refund_amount,
            operator=current_user.username,
            biz_id=f"kami_delete:{kami.kami_code}",
            remark=f"删除卡密返还额度 {kami.kami_code}",
            metadata={
                "app_id": kami.app_id,
                "batch_no": kami.batch_no,
                "spec_id": kami.spec_id,
                "issue_quota_transaction_id": kami.issue_quota_transaction_id,
            },
        )
        refunded_amount += refund_amount if not refund_result.get("idempotent") else 0

        bindings = session.exec(
            select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == kami.kami_code)
        ).all()
        for binding in bindings:
            session.delete(binding)

        related_logs = session.exec(select(EventLog).where(EventLog.kami_code == kami.kami_code)).all()
        for log in related_logs:
            log.kami_code = None
            session.add(log)

        deleted_details.append(
            {
                "kami_code": code,
                "batch_no": kami.batch_no,
                "spec_id": kami.spec_id,
                "refund_amount": refund_amount,
                "device_binding_count": len(bindings),
                "detached_event_log_count": len(related_logs),
            }
        )
        deleted_codes.append(code)
        session.delete(kami)

    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "success": True,
        "message": "kami deleted",
        "data": {
            "deleted_count": len(deleted_codes),
            "deleted_codes": deleted_codes,
            "deleted_details": deleted_details,
            "skipped_count": len(skipped),
            "skipped": skipped,
            "refunded_amount": refunded_amount,
            "quota_balance_after": account.kami_issue_balance,
        },
    }


@router.get("/apps/{app_id}/batches", summary="List merchant issued batches")
async def list_merchant_batches(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    batches = session.exec(
        select(KamiBatch).where(KamiBatch.app_id == app_id).order_by(KamiBatch.id.desc())
    ).all()
    result = []
    for batch in batches:
        stats = batch_stats_payload(session, batch, created_by_user_id=current_user.id)
        if not _merchant_batch_has_user_cards(session, batch, current_user.id, stats=stats):
            continue
        result.append(_merchant_batch_payload(session, batch, current_user, stats=stats))
    return {"success": True, "data": result, "items": result}


@router.put("/batches/{batch_id}", summary="Update merchant batch")
async def update_merchant_batch(
    batch_id: int,
    payload: MerchantBatchUpdateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    batch, app, can_manage_batch = _get_visible_merchant_batch_or_404(session, current_user, batch_id)
    if not can_manage_batch:
        raise HTTPException(status_code=403, detail="Only issuer-created batches can be managed")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return {"success": True, "message": "batch unchanged", "data": _merchant_batch_payload(session, batch, current_user, app=app)}

    current_kamis = session.exec(
        select(Kami).where(Kami.app_id == batch.app_id, Kami.batch_no == batch.batch_no)
    ).all()
    requested_type = data.get("kami_type")
    if requested_type and requested_type != _enum_value(batch.kami_type) and current_kamis:
        raise HTTPException(status_code=400, detail="Batch already has kamis; kami_type cannot be changed")

    new_batch_no = data.get("batch_no", batch.batch_no)
    if new_batch_no != batch.batch_no:
        duplicate = session.exec(
            select(KamiBatch).where(
                KamiBatch.app_id == batch.app_id,
                KamiBatch.batch_no == new_batch_no,
                KamiBatch.id != batch.id,
            )
        ).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Batch number already exists")

    try:
        if "kami_type" in data and data["kami_type"] is not None:
            batch.kami_type = KamiType(data["kami_type"])
        if "points_amount" in data:
            batch.points_amount = data["points_amount"] if _enum_value(batch.kami_type) == KamiType.points.value else None
        if "points_valid_days" in data:
            batch.points_valid_days = data["points_valid_days"] if _enum_value(batch.kami_type) == KamiType.points.value else None
        if "times_total" in data:
            batch.times_total = data["times_total"] if _enum_value(batch.kami_type) == KamiType.times.value else None
        if "time_value" in data:
            batch.time_value = data["time_value"] if _enum_value(batch.kami_type) in TIME_CARD_UNITS else None
        if "time_unit" in data:
            batch.time_unit = data["time_unit"] if _enum_value(batch.kami_type) in TIME_CARD_UNITS else None
        if "code_prefix" in data:
            batch.code_prefix = data["code_prefix"] or None
        if "code_length" in data and data["code_length"] is not None:
            batch.code_length = data["code_length"]
        if "charset" in data and data["charset"] is not None:
            batch.charset = data["charset"]
        if "code_valid_days" in data:
            batch.code_valid_days = data["code_valid_days"]
        if "machine_bind_mode" in data and data["machine_bind_mode"] is not None:
            batch.machine_bind_mode = MachineBindMode(data["machine_bind_mode"])
        if "max_bind_devices" in data and data["max_bind_devices"] is not None:
            batch.max_bind_devices = data["max_bind_devices"]
        if "authorization_owner" in data and data["authorization_owner"] is not None:
            batch.authorization_owner = AuthorizationOwnerMode(data["authorization_owner"])
        if "user_bind_mode" in data and data["user_bind_mode"] is not None:
            batch.user_bind_mode = UserBindMode(data["user_bind_mode"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if "status" in data and data["status"] is not None:
        batch.status = data["status"]
    if "remark" in data:
        batch.remark = data["remark"]
    if new_batch_no != batch.batch_no:
        for kami in current_kamis:
            kami.batch_no = new_batch_no
            session.add(kami)
        batch.batch_no = new_batch_no
    batch.updated_at = get_now_naive()

    session.add(batch)
    session.commit()
    session.refresh(batch)
    return {"success": True, "message": "batch updated", "data": _merchant_batch_payload(session, batch, current_user, app=app)}


@router.delete("/batches/{batch_id}", summary="Delete merchant batch")
async def delete_merchant_batch(
    batch_id: int,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    batch, _app, can_manage_batch = _get_visible_merchant_batch_or_404(session, current_user, batch_id)
    if not can_manage_batch:
        raise HTTPException(status_code=403, detail="Only issuer-created batches can be managed")
    existing_kami = session.exec(
        select(Kami).where(Kami.app_id == batch.app_id, Kami.batch_no == batch.batch_no)
    ).first()
    if existing_kami:
        raise HTTPException(status_code=400, detail="Batch still has kamis")
    payload = _merchant_batch_payload(session, batch, current_user)
    session.delete(batch)
    session.commit()
    return {"success": True, "message": "batch deleted", "data": payload}


@router.post("/batches/{batch_id}/append", summary="Append merchant kamis to a batch")
async def append_merchant_batch_kamis(
    batch_id: int,
    payload: MerchantBatchAppendRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    batch, app, can_manage_batch = _get_visible_merchant_batch_or_404(session, current_user, batch_id)
    if not can_manage_batch:
        raise HTTPException(status_code=403, detail="Only issuer-created batches can be managed")
    if batch.status != 1:
        raise HTTPException(status_code=400, detail="Batch is disabled")
    spec = session.get(KamiSpec, batch.spec_id) if batch.spec_id else None
    try:
        pricing = resolve_issue_pricing(session, user=current_user, app=app, spec=spec)
        result = issue_user_kamis(
            session,
            current_user,
            app,
            spec_id=batch.spec_id,
            kami_type=batch.kami_type,
            count=payload.count,
            batch_no=batch.batch_no,
            code_prefix=payload.code_prefix if payload.code_prefix is not None else batch.code_prefix,
            code_length=payload.code_length if payload.code_length is not None else batch.code_length,
            charset=payload.charset if payload.charset is not None else batch.charset,
            code_valid_days=payload.code_valid_days if payload.code_valid_days is not None else batch.code_valid_days,
            points_amount=batch.points_amount,
            points_valid_days=batch.points_valid_days,
            times_total=batch.times_total,
            time_value=batch.time_value,
            time_unit=batch.time_unit,
            machine_bind_mode=batch.machine_bind_mode,
            max_bind_devices=batch.max_bind_devices,
            authorization_owner=batch.authorization_owner,
            user_bind_mode=batch.user_bind_mode,
            unit_cost=pricing["unit_cost"],
            pricing_source=pricing["pricing_source"],
            pricing_rule_id=pricing["pricing_rule_id"],
            allow_existing_batch=True,
            biz_id_suffix=f"append:{batch.id}:{uuid.uuid4().hex[:8]}",
        )
        result.update(
            {
                "pricing_source": pricing["pricing_source"],
                "pricing_rule_id": pricing["pricing_rule_id"],
                "pricing_rule_key": pricing["pricing_rule_key"],
            }
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(batch)
    return {"success": True, "message": "batch appended", "data": result}
