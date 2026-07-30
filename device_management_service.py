"""Shared payload helpers for admin and merchant device management."""

from __future__ import annotations

from copy import deepcopy
from typing import Callable, Optional


DETAIL_FIELDS = (
    "id",
    "app_id",
    "app_name",
    "uuid",
    "fingerprint",
    "device_name",
    "device_model",
    "device_id",
    "last_ip",
    "ip_count",
    "risk_level",
    "risk_level_text",
    "first_bind_at",
    "last_verify_at",
)


def _detail_sort_key(item: dict) -> tuple[str, str]:
    first_seen = item.get("first_bind_at") or item.get("redeemed_at") or item.get("activate_time")
    return (str(first_seen or "9999-12-31T23:59:59"), str(item.get("id") or ""))


def _device_detail_payload(payload: dict) -> dict:
    detail = {field: payload.get(field) for field in DETAIL_FIELDS}
    detail["can_manage_risk"] = isinstance(payload.get("id"), int)
    return detail


def _with_device_count(policy_text: Optional[str], device_count: int) -> Optional[str]:
    if not policy_text:
        return policy_text
    return f"{policy_text}({device_count}台)"


def group_device_payloads_by_kami(payloads: list[dict]) -> list[dict]:
    """Collapse device rows into one row per kami while keeping per-machine details."""
    groups: dict[str, dict] = {}
    ordered_keys: list[str] = []

    for payload in payloads:
        kami_code = payload.get("kami_code")
        if kami_code:
            key = f"kami:{payload.get('app_id')}:{kami_code}"
            row_type = "kami"
        else:
            key = f"device:{payload.get('app_id')}:{payload.get('id')}"
            row_type = "device"

        if key not in groups:
            group = deepcopy(payload)
            group["group_key"] = key
            group["row_type"] = row_type
            group["device_items"] = []
            groups[key] = group
            ordered_keys.append(key)
        groups[key]["device_items"].append(_device_detail_payload(payload))

    grouped_payloads: list[dict] = []
    for key in ordered_keys:
        group = groups[key]
        all_device_items = sorted(group["device_items"], key=_detail_sort_key)
        first_device = all_device_items[0] if all_device_items else {}
        detail_device_items = all_device_items[1:]
        device_count = len(all_device_items)

        for field in DETAIL_FIELDS:
            if field in first_device:
                group[field] = first_device.get(field)
        group["device_items"] = detail_device_items
        group["device_count"] = device_count
        group["detail_device_count"] = len(detail_device_items)
        group["ip_count"] = int(first_device.get("ip_count") or 0) if first_device else 0
        group["machine_bind_mode_text"] = _with_device_count(group.get("machine_bind_mode_text"), device_count)
        grouped_payloads.append(group)

    return grouped_payloads


def device_group_matches_keyword(
    payload: dict,
    keyword: Optional[str],
    payload_matcher: Callable[[dict, Optional[str]], bool],
) -> bool:
    if not keyword:
        return True
    if payload_matcher(payload, keyword):
        return True
    return any(payload_matcher(device, keyword) for device in payload.get("device_items") or [])
