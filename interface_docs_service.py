import json
from typing import Any, Optional

from sqlmodel import Session, select

from datetime_utils import to_api_beijing_iso
from interface_catalog import BUILTIN_API_INTERFACES
from models import ApiInterface, get_now


def dump_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def load_json(value: Optional[str]) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}


def interface_payload(item: ApiInterface) -> dict:
    success_example = load_json(item.success_example_json)
    response_example = load_json(item.response_example_json)
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
        "request_headers": load_json(item.request_headers_json) or [],
        "request_params": load_json(item.request_params_json),
        "response_params": load_json(item.response_params_json) or [],
        "success_example": success_example if success_example is not None else response_example,
        "error_example": load_json(item.error_example_json),
        "response_example": response_example if response_example is not None else success_example,
        "doc_markdown": item.doc_markdown,
        "remark": item.remark,
        "sort_order": item.sort_order,
        "is_builtin": item.is_builtin,
        "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
        "updated_at": to_api_beijing_iso(item.updated_at, naive="civil"),
    }


def apply_interface_spec(item: ApiInterface, spec: dict, now) -> None:
    item.name = spec["name"]
    item.interface_key = spec["interface_key"]
    item.method = spec.get("method", "POST").upper()
    item.path = spec["path"]
    item.category = spec.get("category") or "core"
    item.description = spec.get("description")
    item.auth_mode = spec.get("auth_mode") or "bearer"
    item.content_type = spec.get("content_type") or "application/json"
    item.status = spec.get("status", 1)
    item.request_headers_json = dump_json(spec.get("request_headers", []))
    item.request_params_json = dump_json(spec.get("request_params", []))
    item.response_params_json = dump_json(spec.get("response_params", []))
    item.success_example_json = dump_json(spec.get("success_example"))
    item.error_example_json = dump_json(spec.get("error_example"))
    item.response_example_json = dump_json(spec.get("success_example"))
    item.doc_markdown = spec.get("doc_markdown")
    item.remark = spec.get("remark")
    item.sort_order = spec.get("sort_order", 0)
    item.is_builtin = True
    item.updated_at = now


def ensure_builtin_interfaces(session: Session) -> None:
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
            apply_interface_spec(item, spec, now)
            session.add(item)
            changed = True
        elif item.is_builtin:
            apply_interface_spec(item, spec, now)
            session.add(item)
            changed = True

    stale_builtin_items = session.exec(
        select(ApiInterface).where(
            ApiInterface.is_builtin == True,
            ~ApiInterface.interface_key.in_(keys),
            ApiInterface.status != 0,
        )
    ).all()
    for item in stale_builtin_items:
        item.status = 0
        item.updated_at = now
        session.add(item)
        changed = True

    if changed:
        session.commit()
