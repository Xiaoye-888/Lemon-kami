import csv
import io
from collections import Counter
from typing import Optional

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from datetime_utils import to_api_beijing_iso
from models import App, Kami, KamiBatch, KamiDeviceBinding, KamiStatus, get_now_naive, is_kami_code_expired


def merchant_kami_statement(
    session: Session,
    *,
    user_id: int,
    legacy_owned_app_ids: Optional[list[str]] = None,
    app_id: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    batch_no: Optional[str] = None,
    spec_id: Optional[int] = None,
):
    visibility_conditions = [Kami.created_by_user_id == user_id]
    if legacy_owned_app_ids:
        visibility_conditions.append(
            and_(Kami.created_by_user_id.is_(None), Kami.app_id.in_(legacy_owned_app_ids))
        )
    statement = select(Kami).where(or_(*visibility_conditions))
    return _apply_kami_filters(
        statement,
        app_id=app_id,
        keyword=keyword,
        status=status,
        batch_no=batch_no,
        spec_id=spec_id,
    )


def admin_kami_statement(
    session: Session,
    *,
    app_id: Optional[str] = None,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    batch_no: Optional[str] = None,
    created_by_user_id: Optional[int] = None,
    spec_id: Optional[int] = None,
):
    statement = select(Kami)
    if created_by_user_id is not None:
        statement = statement.where(Kami.created_by_user_id == created_by_user_id)
    return _apply_kami_filters(
        statement,
        app_id=app_id,
        keyword=keyword,
        status=status,
        batch_no=batch_no,
        spec_id=spec_id,
    )


def kami_search_payload(session: Session, statement, *, page: int, page_size: int) -> dict:
    kamis = session.exec(statement.order_by(Kami.id.desc())).all()
    total = len(kamis)
    offset = (page - 1) * page_size
    page_items = kamis[offset:offset + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": _kami_rows(session, page_items),
    }


def kami_csv(session: Session, statement) -> bytes:
    kamis = session.exec(statement.order_by(Kami.id.desc())).all()
    rows = _kami_rows(session, kamis)
    return _csv_bytes(
        ["卡密", "应用", "应用ID", "批次号", "备注", "类型", "状态", "绑定设备数", "创建时间", "激活时间"],
        [
            [
                row["kami_code"],
                row.get("app_name") or "",
                row["app_id"],
                row.get("batch_no") or "",
                row.get("remark") or "",
                row.get("kami_type") or "",
                row.get("status") or "",
                row.get("bound_device_count") or 0,
                row.get("created_at") or "",
                row.get("activate_time") or "",
            ]
            for row in rows
        ],
    )


def batch_stats_payload(
    session: Session,
    batch: KamiBatch,
    *,
    created_by_user_id: Optional[int] = None,
    include_unassigned: bool = False,
) -> dict:
    statement = select(Kami).where(Kami.app_id == batch.app_id, Kami.batch_no == batch.batch_no)
    if batch.created_by_user_id is not None:
        statement = statement.where(Kami.created_by_user_id == batch.created_by_user_id)
    elif created_by_user_id is not None:
        visibility_conditions = [Kami.created_by_user_id == created_by_user_id]
        if include_unassigned:
            visibility_conditions.append(Kami.created_by_user_id.is_(None))
        statement = statement.where(or_(*visibility_conditions))
    elif include_unassigned:
        statement = statement.where(Kami.created_by_user_id.is_(None))
    kamis = session.exec(statement).all()
    codes = [kami.kami_code for kami in kamis if kami.kami_code]
    bindings = []
    if codes:
        bindings = session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(codes))).all()
    status_counts = Counter(_status_text(kami) for kami in kamis)
    return {
        "total_count": len(kamis),
        "unused_count": status_counts.get("unused", 0),
        "active_count": status_counts.get("active", 0),
        "frozen_count": status_counts.get("frozen", 0),
        "expired_count": status_counts.get("expired", 0),
        "device_bound_count": len({binding.kami_code for binding in bindings if binding.kami_code}),
    }


def _apply_kami_filters(
    statement,
    *,
    app_id: Optional[str],
    keyword: Optional[str],
    status: Optional[str],
    batch_no: Optional[str],
    spec_id: Optional[int] = None,
):
    if app_id:
        statement = statement.where(Kami.app_id == app_id)
    if batch_no:
        statement = statement.where(Kami.batch_no == batch_no)
    elif spec_id:
        statement = statement.where(Kami.spec_id == spec_id)
    if status == "expired":
        statement = statement.where(
            Kami.status == KamiStatus.unused,
            Kami.code_expires_at.is_not(None),
            Kami.code_expires_at < get_now_naive(),
        )
    elif status:
        try:
            statement = statement.where(Kami.status == KamiStatus(status))
        except ValueError as error:
            raise ValueError("Invalid kami status") from error
    if keyword:
        like_value = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                Kami.kami_code.like(like_value),
                Kami.app_id.like(like_value),
                Kami.batch_no.like(like_value),
                Kami.remark.like(like_value),
            )
        )
    return statement


def _kami_rows(session: Session, kamis: list[Kami]) -> list[dict]:
    app_ids = {kami.app_id for kami in kamis if kami.app_id}
    codes = [kami.kami_code for kami in kamis if kami.kami_code]
    apps = session.exec(select(App).where(App.app_id.in_(list(app_ids)))).all() if app_ids else []
    bindings = session.exec(select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(codes))).all() if codes else []
    app_names = {app.app_id: app.name for app in apps}
    binding_counts = Counter(binding.kami_code for binding in bindings)
    return [
        {
            "id": kami.id,
            "app_id": kami.app_id,
            "app_name": app_names.get(kami.app_id),
            "spec_id": kami.spec_id,
            "kami_code": kami.kami_code,
            "kami_type": kami.kami_type.value if hasattr(kami.kami_type, "value") else kami.kami_type,
            "status": _status_text(kami),
            "batch_no": kami.batch_no,
            "remark": kami.remark,
            "points_amount": kami.points_amount,
            "points_valid_days": kami.points_valid_days,
            "times_total": kami.times_total,
            "times_remaining": kami.times_remaining,
            "time_value": kami.time_value,
            "time_unit": kami.time_unit,
            "created_by_user_id": kami.created_by_user_id,
            "bound_device_count": binding_counts.get(kami.kami_code, 0),
            "activate_time": to_api_beijing_iso(kami.activate_time, naive="civil") if kami.activate_time else None,
            "created_at": to_api_beijing_iso(kami.created_at, naive="civil") if kami.created_at else None,
        }
        for kami in kamis
    ]


def _status_text(kami: Kami) -> str:
    if is_kami_code_expired(kami):
        return "expired"
    return kami.status.value if hasattr(kami.status, "value") else str(kami.status)


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
