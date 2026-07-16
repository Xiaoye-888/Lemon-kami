import json
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models import ApiInterface, AppInterfaceConfig, get_now_naive


def load_interface_config(config_json: Optional[str]) -> dict[str, Any]:
    if not config_json:
        return {}
    try:
        value = json.loads(config_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def get_app_interface_config(
    session: Session,
    app_id: Optional[str],
    interface_key: str,
) -> tuple[Optional[ApiInterface], Optional[AppInterfaceConfig], dict[str, Any]]:
    if not app_id:
        return None, None, {}

    interface = session.exec(
        select(ApiInterface).where(ApiInterface.interface_key == interface_key)
    ).first()
    if not interface:
        return None, None, {}

    config = session.exec(
        select(AppInterfaceConfig).where(
            AppInterfaceConfig.app_id == app_id,
            AppInterfaceConfig.interface_id == interface.id,
        )
    ).first()
    return interface, config, load_interface_config(config.config_json if config else None)


def require_app_interface_enabled(
    session: Session,
    app_id: Optional[str],
    interface_key: str,
) -> dict[str, Any]:
    if not app_id:
        return {}

    interface, config, config_data = get_app_interface_config(session, app_id, interface_key)
    now = get_now_naive()
    if not interface or interface.status != 1:
        raise HTTPException(
            status_code=403,
            detail={"code": "INTERFACE_DISABLED", "message": "接口未开通或已关闭"},
        )
    if not config:
        if interface.is_builtin:
            return config_data
        raise HTTPException(
            status_code=403,
            detail={"code": "INTERFACE_DISABLED", "message": "接口未开通或已关闭"},
        )
    if (
        not config.enabled
        or (config.expires_at is not None and config.expires_at < now)
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "INTERFACE_DISABLED", "message": "接口未开通或已关闭"},
        )

    return config_data
