import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from models import (
    AuthorizationAccount,
    AuthorizationBenefitType,
    AuthorizationLot,
    AuthorizationOwnerType,
    AuthorizationTransaction,
    AuthorizationTransactionType,
    get_now_naive,
)


def _now(value: Optional[datetime] = None) -> datetime:
    return value or get_now_naive()


def _transaction_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def get_or_create_authorization_account(
    session: Session,
    app_id: str,
    owner_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    device_uuid: Optional[str] = None,
    fingerprint: Optional[str] = None,
) -> AuthorizationAccount:
    owner = AuthorizationOwnerType(owner_type)
    statement = select(AuthorizationAccount).where(
        AuthorizationAccount.app_id == app_id,
        AuthorizationAccount.owner_type == owner,
    )
    if owner == AuthorizationOwnerType.user:
        if user_id is not None:
            statement = statement.where(AuthorizationAccount.user_id == user_id)
        else:
            statement = statement.where(AuthorizationAccount.username == username)
    else:
        statement = statement.where(AuthorizationAccount.device_uuid == device_uuid)

    account = session.exec(statement).first()
    if account:
        if username and not account.username:
            account.username = username
        if fingerprint and not account.fingerprint:
            account.fingerprint = fingerprint
        account.updated_at = _now()
        session.add(account)
        session.commit()
        session.refresh(account)
        return account

    account = AuthorizationAccount(
        app_id=app_id,
        owner_type=owner,
        user_id=user_id,
        username=username,
        device_uuid=device_uuid,
        fingerprint=fingerprint,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _record_transaction(
    session: Session,
    account: AuthorizationAccount,
    transaction_type: AuthorizationTransactionType,
    benefit_type: AuthorizationBenefitType,
    amount: int,
    balance_after: int,
    source_kami_code: Optional[str] = None,
    biz_id: Optional[str] = None,
    operator: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> AuthorizationTransaction:
    tx = AuthorizationTransaction(
        transaction_id=_transaction_id("auth"),
        account_id=account.id,
        source_kami_code=source_kami_code,
        transaction_type=transaction_type,
        benefit_type=benefit_type,
        amount=amount,
        balance_after=balance_after,
        biz_id=biz_id,
        operator=operator,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
    )
    session.add(tx)
    return tx


def grant_times(
    session: Session,
    account: AuthorizationAccount,
    amount: int,
    source_kami_code: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    operator: Optional[str] = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    account.times_balance += amount
    account.updated_at = _now()
    lot = AuthorizationLot(
        account_id=account.id,
        source_kami_code=source_kami_code,
        benefit_type=AuthorizationBenefitType.times,
        amount_total=amount,
        amount_remaining=amount,
        expires_at=expires_at,
    )
    session.add(lot)
    tx = _record_transaction(
        session,
        account,
        AuthorizationTransactionType.grant,
        AuthorizationBenefitType.times,
        amount,
        account.times_balance,
        source_kami_code=source_kami_code,
        operator=operator,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return {"transaction_id": tx.transaction_id, "times_balance": account.times_balance}


def consume_times(
    session: Session,
    account: AuthorizationAccount,
    amount: int,
    biz_id: str,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    existing = session.exec(
        select(AuthorizationTransaction).where(
            AuthorizationTransaction.account_id == account.id,
            AuthorizationTransaction.transaction_type == AuthorizationTransactionType.consume,
            AuthorizationTransaction.biz_id == biz_id,
        )
    ).first()
    if existing:
        return {
            "transaction_id": existing.transaction_id,
            "times_balance": existing.balance_after,
            "idempotent": True,
        }
    if account.times_balance < amount:
        raise ValueError("insufficient times balance")

    remaining_to_consume = amount
    lots = session.exec(
        select(AuthorizationLot)
        .where(
            AuthorizationLot.account_id == account.id,
            AuthorizationLot.benefit_type == AuthorizationBenefitType.times,
            AuthorizationLot.amount_remaining > 0,
        )
        .order_by(AuthorizationLot.expires_at.is_(None), AuthorizationLot.expires_at, AuthorizationLot.id)
    ).all()
    for lot in lots:
        if remaining_to_consume <= 0:
            break
        take = min(lot.amount_remaining, remaining_to_consume)
        lot.amount_remaining -= take
        lot.updated_at = _now()
        remaining_to_consume -= take
        session.add(lot)
    if remaining_to_consume > 0:
        raise ValueError("insufficient times lots")

    account.times_balance -= amount
    account.updated_at = _now()
    tx = _record_transaction(
        session,
        account,
        AuthorizationTransactionType.consume,
        AuthorizationBenefitType.times,
        -amount,
        account.times_balance,
        biz_id=biz_id,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "transaction_id": tx.transaction_id,
        "times_balance": account.times_balance,
        "idempotent": False,
    }


def grant_time(
    session: Session,
    account: AuthorizationAccount,
    days: Optional[int],
    source_kami_code: Optional[str] = None,
    now: Optional[datetime] = None,
    is_lifetime: bool = False,
    operator: Optional[str] = None,
) -> dict:
    current_now = _now(now)
    if is_lifetime:
        account.is_lifetime = True
        account.time_expires_at = None
        amount = 0
        starts_at = current_now
        expires_at = None
    else:
        if days is None or days <= 0:
            raise ValueError("days must be greater than 0 unless lifetime")
        starts_at = account.time_expires_at if account.time_expires_at and account.time_expires_at > current_now else current_now
        expires_at = starts_at + timedelta(days=days)
        account.time_expires_at = expires_at
        amount = days
    account.updated_at = current_now
    lot = AuthorizationLot(
        account_id=account.id,
        source_kami_code=source_kami_code,
        benefit_type=AuthorizationBenefitType.time,
        amount_total=amount,
        amount_remaining=amount,
        starts_at=starts_at,
        expires_at=expires_at,
    )
    session.add(lot)
    tx = _record_transaction(
        session,
        account,
        AuthorizationTransactionType.grant,
        AuthorizationBenefitType.time,
        amount,
        0,
        source_kami_code=source_kami_code,
        operator=operator,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return {"transaction_id": tx.transaction_id, "time_expires_at": account.time_expires_at}


def grant_points(
    session: Session,
    account: AuthorizationAccount,
    amount: int,
    source_kami_code: Optional[str] = None,
    expires_at: Optional[datetime] = None,
    operator: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    account.points_balance += amount
    account.updated_at = _now()
    lot = AuthorizationLot(
        account_id=account.id,
        source_kami_code=source_kami_code,
        benefit_type=AuthorizationBenefitType.points,
        amount_total=amount,
        amount_remaining=amount,
        expires_at=expires_at,
    )
    session.add(lot)
    tx = _record_transaction(
        session,
        account,
        AuthorizationTransactionType.grant,
        AuthorizationBenefitType.points,
        amount,
        account.points_balance,
        source_kami_code=source_kami_code,
        operator=operator,
        metadata=metadata,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return {"transaction_id": tx.transaction_id, "points_balance": account.points_balance}


def consume_points(
    session: Session,
    account: AuthorizationAccount,
    amount: int,
    biz_id: str,
    metadata: Optional[dict] = None,
) -> dict:
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    if not biz_id:
        raise ValueError("biz_id is required")
    existing = session.exec(
        select(AuthorizationTransaction).where(
            AuthorizationTransaction.account_id == account.id,
            AuthorizationTransaction.transaction_type == AuthorizationTransactionType.consume,
            AuthorizationTransaction.benefit_type == AuthorizationBenefitType.points,
            AuthorizationTransaction.biz_id == biz_id,
        )
    ).first()
    if existing:
        if existing.amount != -amount:
            raise ValueError("biz_id was used with a different amount")
        return {
            "transaction_id": existing.transaction_id,
            "points_balance": existing.balance_after,
            "idempotent": True,
        }
    if account.points_balance < amount:
        raise ValueError("insufficient points balance")

    now = _now()
    remaining_to_consume = amount
    lots = session.exec(
        select(AuthorizationLot)
        .where(
            AuthorizationLot.account_id == account.id,
            AuthorizationLot.benefit_type == AuthorizationBenefitType.points,
            AuthorizationLot.amount_remaining > 0,
        )
        .order_by(AuthorizationLot.expires_at.is_(None), AuthorizationLot.expires_at, AuthorizationLot.id)
    ).all()
    for lot in lots:
        if lot.expires_at is not None and lot.expires_at <= now:
            continue
        if remaining_to_consume <= 0:
            break
        take = min(lot.amount_remaining, remaining_to_consume)
        lot.amount_remaining -= take
        lot.updated_at = now
        remaining_to_consume -= take
        session.add(lot)
    if remaining_to_consume > 0:
        raise ValueError("insufficient points lots")

    account.points_balance -= amount
    account.updated_at = now
    tx = _record_transaction(
        session,
        account,
        AuthorizationTransactionType.consume,
        AuthorizationBenefitType.points,
        -amount,
        account.points_balance,
        biz_id=biz_id,
        metadata=metadata,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return {
        "transaction_id": tx.transaction_id,
        "points_balance": account.points_balance,
        "idempotent": False,
    }
