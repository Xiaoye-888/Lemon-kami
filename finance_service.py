import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from datetime_utils import to_api_beijing_iso
from models import (
    RechargeOrder,
    RechargeOrderStatus,
    UserQuotaTransaction,
    UserQuotaTransactionType,
)


def parse_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[Optional[datetime], Optional[datetime]]:
    start = _parse_date_start(start_date) if start_date else None
    end = _parse_date_start(end_date) + timedelta(days=1) if end_date else None
    return start, end


def finance_summary_payload(
    session: Session,
    start_date: Optional[str],
    end_date: Optional[str],
) -> dict:
    start, end = parse_date_range(start_date, end_date)
    orders = session.exec(select(RechargeOrder)).all()
    transactions = session.exec(select(UserQuotaTransaction)).all()

    approved_income_orders = [
        order
        for order in orders
        if order.status == RechargeOrderStatus.approved
        and order.reviewed_at is not None
        and _in_range(order.reviewed_at, start, end)
    ]
    status_orders = [
        order
        for order in orders
        if _in_range(order.created_at, start, end)
    ]
    ranged_transactions = [
        transaction
        for transaction in transactions
        if _in_range(transaction.created_at, start, end)
    ]

    daily_map: dict[str, dict] = {}
    for order in approved_income_orders:
        day = order.reviewed_at.date().isoformat()
        row = daily_map.setdefault(
            day,
            {
                "date": day,
                "approved_order_count": 0,
                "approved_amount": 0,
                "credited_issue_quota": 0,
                "bonus_issue_quota": 0,
            },
        )
        row["approved_order_count"] += 1
        row["approved_amount"] += _amount_yuan(order.amount_cents)
        row["credited_issue_quota"] += order.credit_quota or 0
        row["bonus_issue_quota"] += order.bonus_quota or 0

    return {
        "income_basis": "reviewed_at",
        "approved_order_count": len(approved_income_orders),
        "approved_amount": _sum_amount_yuan(order.amount_cents for order in approved_income_orders),
        "credited_issue_quota": sum(order.credit_quota or 0 for order in approved_income_orders),
        "bonus_issue_quota": sum(order.bonus_quota or 0 for order in approved_income_orders),
        "pending_review_count": sum(
            1 for order in status_orders if order.status == RechargeOrderStatus.pending_review
        ),
        "rejected_count": sum(1 for order in status_orders if order.status == RechargeOrderStatus.rejected),
        "abnormal_count": sum(1 for order in status_orders if order.status == RechargeOrderStatus.abnormal),
        "approved_without_reviewed_at_count": sum(
            1 for order in orders if order.status == RechargeOrderStatus.approved and order.reviewed_at is None
        ),
        "quota_transaction_count": len(ranged_transactions),
        "refund_amount": 0,
        "reversal_amount": 0,
        "daily": [daily_map[day] for day in sorted(daily_map)],
    }


def merchant_recharge_ranking_payload(
    session: Session,
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int = 20,
) -> dict:
    start, end = parse_date_range(start_date, end_date)
    grouped: dict[tuple[Optional[int], str], dict] = defaultdict(
        lambda: {
            "user_id": None,
            "username": "",
            "approved_order_count": 0,
            "approved_amount": 0,
            "credited_issue_quota": 0,
            "bonus_issue_quota": 0,
        }
    )
    orders = session.exec(select(RechargeOrder)).all()
    for order in orders:
        if order.status != RechargeOrderStatus.approved or order.reviewed_at is None:
            continue
        if not _in_range(order.reviewed_at, start, end):
            continue
        key = (order.user_id, order.username or "")
        row = grouped[key]
        row["user_id"] = order.user_id
        row["username"] = order.username or ""
        row["approved_order_count"] += 1
        row["approved_amount"] += _amount_yuan(order.amount_cents)
        row["credited_issue_quota"] += order.credit_quota or 0
        row["bonus_issue_quota"] += order.bonus_quota or 0

    items = sorted(
        grouped.values(),
        key=lambda item: (item["approved_amount"], item["approved_order_count"]),
        reverse=True,
    )[:limit]
    return {"income_basis": "reviewed_at", "items": items}


def recharge_orders_csv(
    session: Session,
    *,
    status: Optional[str] = None,
    username: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bytes:
    start, end = parse_date_range(start_date, end_date)
    status_filter = _parse_recharge_status(status) if status else None
    orders = session.exec(select(RechargeOrder).order_by(RechargeOrder.id.desc())).all()
    rows = [
        order
        for order in orders
        if (status_filter is None or order.status == status_filter)
        and (not username or (order.username or "") == username)
        and _order_in_export_range(order, start, end)
    ]

    return _csv_bytes(
        [
            "订单号",
            "用户",
            "金额",
            "到账发卡额度",
            "赠送额度",
            "状态",
            "审核通过时间",
            "创建时间",
        ],
        [
            [
                order.order_no,
                order.username or "",
                _amount_yuan(order.amount_cents),
                order.credit_quota or 0,
                order.bonus_quota or 0,
                order.status.value if hasattr(order.status, "value") else str(order.status),
                to_api_beijing_iso(order.reviewed_at, naive="civil") if order.reviewed_at else "",
                to_api_beijing_iso(order.created_at, naive="civil") if order.created_at else "",
            ]
            for order in rows
        ],
    )


def quota_transactions_csv(
    session: Session,
    *,
    username: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> bytes:
    start, end = parse_date_range(start_date, end_date)
    type_filter = _parse_transaction_type(transaction_type) if transaction_type else None
    transactions = session.exec(select(UserQuotaTransaction).order_by(UserQuotaTransaction.id.desc())).all()
    rows = [
        transaction
        for transaction in transactions
        if (not username or (transaction.username or "") == username)
        and (type_filter is None or transaction.transaction_type == type_filter)
        and _in_range(transaction.created_at, start, end)
    ]

    return _csv_bytes(
        [
            "流水号",
            "用户",
            "额度类型",
            "流水类型",
            "变动额度",
            "变动前",
            "变动后",
            "业务单号",
            "操作人",
            "创建时间",
        ],
        [
            [
                transaction.transaction_id,
                transaction.username or "",
                transaction.quota_type.value if hasattr(transaction.quota_type, "value") else str(transaction.quota_type),
                transaction.transaction_type.value
                if hasattr(transaction.transaction_type, "value")
                else str(transaction.transaction_type),
                transaction.amount,
                transaction.balance_before if transaction.balance_before is not None else "",
                transaction.balance_after,
                transaction.biz_id or "",
                transaction.operator or "",
                to_api_beijing_iso(transaction.created_at, naive="civil") if transaction.created_at else "",
            ]
            for transaction in rows
        ],
    )


def _parse_date_start(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("Date must use YYYY-MM-DD format") from error


def _parse_recharge_status(value: str) -> RechargeOrderStatus:
    try:
        return RechargeOrderStatus(value)
    except ValueError as error:
        raise ValueError("Invalid recharge order status") from error


def _parse_transaction_type(value: str) -> UserQuotaTransactionType:
    try:
        return UserQuotaTransactionType(value)
    except ValueError as error:
        raise ValueError("Invalid quota transaction type") from error


def _in_range(value: Optional[datetime], start: Optional[datetime], end: Optional[datetime]) -> bool:
    if value is None:
        return start is None and end is None
    if start is not None and value < start:
        return False
    if end is not None and value >= end:
        return False
    return True


def _order_in_export_range(
    order: RechargeOrder,
    start: Optional[datetime],
    end: Optional[datetime],
) -> bool:
    basis = order.reviewed_at if order.reviewed_at is not None else order.created_at
    return _in_range(basis, start, end)


def _amount_yuan(cents: int) -> float | int:
    if cents % 100 == 0:
        return cents // 100
    return round(cents / 100, 2)


def _sum_amount_yuan(cents_values) -> float | int:
    total_cents = sum(cents_values)
    return _amount_yuan(total_cents)


def _csv_bytes(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
