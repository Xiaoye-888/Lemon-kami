import csv
import io
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import case, func
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
    approved_conditions = [
        RechargeOrder.status == RechargeOrderStatus.approved,
        RechargeOrder.reviewed_at.is_not(None),
        *_range_conditions(RechargeOrder.reviewed_at, start, end),
    ]
    (
        approved_order_count,
        approved_amount_cents,
        credited_issue_quota,
        bonus_issue_quota,
    ) = session.exec(
        select(
            func.count(RechargeOrder.id),
            func.coalesce(func.sum(RechargeOrder.amount_cents), 0),
            func.coalesce(func.sum(RechargeOrder.credit_quota), 0),
            func.coalesce(func.sum(RechargeOrder.bonus_quota), 0),
        ).where(*approved_conditions)
    ).one()

    status_conditions = _range_conditions(RechargeOrder.created_at, start, end)
    status_statement = select(
        func.coalesce(func.sum(case((RechargeOrder.status == RechargeOrderStatus.pending_review, 1), else_=0)), 0),
        func.coalesce(func.sum(case((RechargeOrder.status == RechargeOrderStatus.rejected, 1), else_=0)), 0),
        func.coalesce(func.sum(case((RechargeOrder.status == RechargeOrderStatus.abnormal, 1), else_=0)), 0),
    )
    if status_conditions:
        status_statement = status_statement.where(*status_conditions)
    pending_review_count, rejected_count, abnormal_count = session.exec(status_statement).one()

    approved_without_reviewed_at_count = int(session.exec(
        select(func.count(RechargeOrder.id)).where(
            RechargeOrder.status == RechargeOrderStatus.approved,
            RechargeOrder.reviewed_at.is_(None),
        )
    ).one() or 0)

    transaction_statement = select(func.count(UserQuotaTransaction.id))
    transaction_conditions = _range_conditions(UserQuotaTransaction.created_at, start, end)
    if transaction_conditions:
        transaction_statement = transaction_statement.where(*transaction_conditions)
    quota_transaction_count = int(session.exec(transaction_statement).one() or 0)

    day_expression = func.date(RechargeOrder.reviewed_at)
    daily_rows = session.exec(
        select(
            day_expression.label("day"),
            func.count(RechargeOrder.id),
            func.coalesce(func.sum(RechargeOrder.amount_cents), 0),
            func.coalesce(func.sum(RechargeOrder.credit_quota), 0),
            func.coalesce(func.sum(RechargeOrder.bonus_quota), 0),
        )
        .where(*approved_conditions)
        .group_by(day_expression)
        .order_by(day_expression)
    ).all()
    daily = [
        {
            "date": day.isoformat() if hasattr(day, "isoformat") else str(day),
            "approved_order_count": int(order_count or 0),
            "approved_amount": _amount_yuan(int(amount_cents or 0)),
            "credited_issue_quota": int(credited_quota or 0),
            "bonus_issue_quota": int(bonus_quota or 0),
        }
        for day, order_count, amount_cents, credited_quota, bonus_quota in daily_rows
    ]

    return {
        "income_basis": "reviewed_at",
        "approved_order_count": int(approved_order_count or 0),
        "approved_amount": _amount_yuan(int(approved_amount_cents or 0)),
        "credited_issue_quota": int(credited_issue_quota or 0),
        "bonus_issue_quota": int(bonus_issue_quota or 0),
        "pending_review_count": int(pending_review_count or 0),
        "rejected_count": int(rejected_count or 0),
        "abnormal_count": int(abnormal_count or 0),
        "approved_without_reviewed_at_count": approved_without_reviewed_at_count,
        "quota_transaction_count": quota_transaction_count,
        "refund_amount": 0,
        "reversal_amount": 0,
        "daily": daily,
    }


def merchant_recharge_ranking_payload(
    session: Session,
    start_date: Optional[str],
    end_date: Optional[str],
    limit: int = 20,
) -> dict:
    start, end = parse_date_range(start_date, end_date)
    approved_order_count = func.count(RechargeOrder.id).label("approved_order_count")
    approved_amount_cents = func.coalesce(func.sum(RechargeOrder.amount_cents), 0).label(
        "approved_amount_cents"
    )
    rows = session.exec(
        select(
            RechargeOrder.user_id,
            RechargeOrder.username,
            approved_order_count,
            approved_amount_cents,
            func.coalesce(func.sum(RechargeOrder.credit_quota), 0),
            func.coalesce(func.sum(RechargeOrder.bonus_quota), 0),
        )
        .where(
            RechargeOrder.status == RechargeOrderStatus.approved,
            RechargeOrder.reviewed_at.is_not(None),
            *_range_conditions(RechargeOrder.reviewed_at, start, end),
        )
        .group_by(RechargeOrder.user_id, RechargeOrder.username)
        .order_by(approved_amount_cents.desc(), approved_order_count.desc())
        .limit(limit)
    ).all()
    items = [
        {
            "user_id": user_id,
            "username": username or "",
            "approved_order_count": int(order_count or 0),
            "approved_amount": _amount_yuan(int(amount_cents or 0)),
            "credited_issue_quota": int(credited_quota or 0),
            "bonus_issue_quota": int(bonus_quota or 0),
        }
        for user_id, username, order_count, amount_cents, credited_quota, bonus_quota in rows
    ]
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


def _range_conditions(column, start: Optional[datetime], end: Optional[datetime]) -> list:
    conditions = []
    if start is not None:
        conditions.append(column >= start)
    if end is not None:
        conditions.append(column < end)
    return conditions


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
