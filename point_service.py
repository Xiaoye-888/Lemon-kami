import json
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from models import (
    AuthorizationBenefitType,
    AuthorizationOwnerType,
    AuthorizationTransaction,
    EndUser,
    Kami,
    KamiStatus,
    KamiType,
    PointTransaction,
    PointTransactionType,
    UserPointAccount,
    UserPointLot,
    get_now_naive,
    is_kami_code_expired,
)
from authorization_service import (
    consume_points as consume_authorization_points,
    get_or_create_authorization_account,
    grant_points,
)


class PointServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _new_transaction_id() -> str:
    return f"pt_{uuid.uuid4().hex}"


def _metadata_to_json(metadata: Optional[dict]) -> Optional[str]:
    if metadata is None:
        return None
    return json.dumps(metadata, ensure_ascii=False)


def _metadata_from_json(metadata_json: Optional[str]) -> dict:
    if not metadata_json:
        return {}
    try:
        return json.loads(metadata_json)
    except json.JSONDecodeError:
        return {}


def _lot_sort_key(lot: UserPointLot):
    return (
        lot.expires_at is None,
        lot.expires_at or datetime.max,
        lot.id or 0,
    )


def _active_lots(session: Session, user_id: int, now: datetime, lock: bool = False) -> list[UserPointLot]:
    statement = select(UserPointLot).where(
        UserPointLot.user_id == user_id,
        UserPointLot.points_remaining > 0,
    )
    if lock:
        statement = statement.with_for_update()
    lots = session.exec(statement).all()
    return sorted(
        [lot for lot in lots if lot.expires_at is None or lot.expires_at > now],
        key=_lot_sort_key,
    )


def _deduct_from_lots(session: Session, user_id: int, amount: int, now: datetime) -> bool:
    lots = _active_lots(session, user_id, now, lock=True)
    if not lots:
        return False

    active_balance = sum(lot.points_remaining for lot in lots)
    if active_balance < amount:
        return False

    remaining = amount
    for lot in lots:
        if remaining <= 0:
            break
        used = min(lot.points_remaining, remaining)
        lot.points_remaining -= used
        lot.updated_at = now
        remaining -= used
        session.add(lot)

    return True


def _create_lot(
    session: Session,
    user_id: int,
    transaction_id: str,
    amount: int,
    now: datetime,
    app_id: Optional[str] = None,
    kami_code: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> UserPointLot:
    lot = UserPointLot(
        user_id=user_id,
        source_transaction_id=transaction_id,
        app_id=app_id,
        kami_code=kami_code,
        points_total=amount,
        points_remaining=amount,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    session.add(lot)
    return lot


def _expires_at_for_kami(kami: Kami, now: datetime) -> Optional[datetime]:
    if not kami.points_valid_days or kami.points_valid_days <= 0:
        return None
    return now + timedelta(days=kami.points_valid_days)


def get_or_create_account(session: Session, user_id: int, lock: bool = False) -> UserPointAccount:
    statement = select(UserPointAccount).where(UserPointAccount.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    account = session.exec(statement).first()
    if account:
        return account

    account = UserPointAccount(
        user_id=user_id,
        balance=0,
        total_recharged=0,
        total_consumed=0,
        created_at=get_now_naive(),
        updated_at=get_now_naive(),
    )
    session.add(account)
    session.flush()
    session.refresh(account)
    return account


def get_points_balance_summary(session: Session, user_id: int, app_id: Optional[str] = None) -> dict:
    if app_id:
        auth_account = get_or_create_authorization_account(
            session=session,
            app_id=app_id,
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user_id,
        )
        transactions = session.exec(
            select(AuthorizationTransaction).where(
                AuthorizationTransaction.account_id == auth_account.id,
                AuthorizationTransaction.benefit_type == AuthorizationBenefitType.points,
            )
        ).all()
        total_recharged = sum(tx.amount for tx in transactions if tx.amount > 0)
        total_consumed = -sum(tx.amount for tx in transactions if tx.amount < 0)
        return {
            "balance": auth_account.points_balance,
            "available_balance": auth_account.points_balance,
            "ledger_balance": auth_account.points_balance,
            "expired_unsettled": 0,
            "total_recharged": total_recharged,
            "total_consumed": total_consumed,
        }

    account = get_or_create_account(session, user_id)
    now = get_now_naive()
    lots = session.exec(
        select(UserPointLot).where(
            UserPointLot.user_id == user_id,
            UserPointLot.points_remaining > 0,
        )
    ).all()
    if not lots:
        return {
            "balance": account.balance,
            "available_balance": account.balance,
            "ledger_balance": account.balance,
            "expired_unsettled": 0,
            "total_recharged": account.total_recharged,
            "total_consumed": account.total_consumed,
        }

    available_balance = sum(
        lot.points_remaining
        for lot in lots
        if lot.expires_at is None or lot.expires_at > now
    )
    expired_unsettled = sum(
        lot.points_remaining
        for lot in lots
        if lot.expires_at is not None and lot.expires_at <= now
    )
    return {
        "balance": available_balance,
        "available_balance": available_balance,
        "ledger_balance": account.balance,
        "expired_unsettled": expired_unsettled,
        "total_recharged": account.total_recharged,
        "total_consumed": account.total_consumed,
    }


def redeem_points_kami(session: Session, user: EndUser, kami_code: str) -> dict:
    if not user.id:
        raise PointServiceError("invalid_user", "User must be persisted")

    kami = session.exec(select(Kami).where(Kami.kami_code == kami_code)).first()
    if not kami:
        raise PointServiceError("kami_not_found", "Kami not found", 404)
    if kami.kami_type != KamiType.points:
        raise PointServiceError("not_points_kami", "Kami is not a points kami")
    if kami.status == KamiStatus.frozen:
        raise PointServiceError("kami_frozen", "Kami is frozen")
    now = get_now_naive()
    if is_kami_code_expired(kami, now):
        raise PointServiceError("kami_expired", "卡密已过期")
    if kami.redeemed_by_user_id is not None or kami.status != KamiStatus.unused:
        raise PointServiceError("already_redeemed", "Kami has already been redeemed")
    if not kami.points_amount or kami.points_amount <= 0:
        raise PointServiceError("invalid_points_amount", "Kami has no valid points amount")

    account = get_or_create_authorization_account(
        session=session,
        app_id=kami.app_id,
        owner_type=AuthorizationOwnerType.user.value,
        user_id=user.id,
        username=user.username,
    )

    kami.status = KamiStatus.active
    kami.bind_uuid = f"user:{user.id}"
    kami.activate_time = now
    kami.redeemed_by_user_id = user.id
    kami.redeemed_at = now
    if not user.app_id:
        user.app_id = kami.app_id

    result = grant_points(
        session=session,
        account=account,
        amount=kami.points_amount,
        source_kami_code=kami.kami_code,
    )

    session.add(user)
    session.add(kami)
    session.commit()
    session.refresh(account)

    return {
        "transaction_id": result["transaction_id"],
        "amount": kami.points_amount,
        "balance": account.points_balance,
    }


def consume_points(
    session: Session,
    user_id: int,
    amount: int,
    biz_id: str,
    app_id: Optional[str] = None,
    remark: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    if amount <= 0:
        raise PointServiceError("invalid_amount", "Amount must be greater than zero")
    if not biz_id:
        raise PointServiceError("missing_biz_id", "biz_id is required")

    if app_id:
        user = session.get(EndUser, user_id)
        account = get_or_create_authorization_account(
            session=session,
            app_id=app_id,
            owner_type=AuthorizationOwnerType.user.value,
            user_id=user_id,
            username=user.username if user else None,
        )
        try:
            result = consume_authorization_points(
                session=session,
                account=account,
                amount=amount,
                biz_id=biz_id,
                metadata=metadata,
            )
        except ValueError as error:
            message = str(error)
            if "different amount" in message:
                raise PointServiceError("biz_id_conflict", message)
            if "insufficient" in message:
                raise PointServiceError("insufficient_balance", "Insufficient points balance")
            raise PointServiceError("consume_failed", message)
        return {
            "transaction_id": result["transaction_id"],
            "amount": amount,
            "balance": result["points_balance"],
            "balance_after": result["points_balance"],
            "idempotent": result["idempotent"],
        }

    existing = session.exec(
        select(PointTransaction).where(
            PointTransaction.user_id == user_id,
            PointTransaction.transaction_type == PointTransactionType.consume,
            PointTransaction.biz_id == biz_id,
        )
    ).first()
    if existing:
        if existing.amount != -amount:
            raise PointServiceError("biz_id_conflict", "biz_id was used with a different amount")
        return {
            "transaction_id": existing.transaction_id,
            "amount": amount,
            "balance": existing.balance_after,
            "idempotent": True,
        }

    now = get_now_naive()
    account = get_or_create_account(session, user_id, lock=True)
    lot_deducted = _deduct_from_lots(session, user_id, amount, now)
    has_lots = session.exec(
        select(UserPointLot).where(UserPointLot.user_id == user_id)
    ).first() is not None

    if account.balance < amount or (has_lots and not lot_deducted):
        raise PointServiceError("insufficient_balance", "Insufficient points balance")

    balance_before = account.balance
    balance_after = balance_before - amount

    account.balance = balance_after
    account.total_consumed += amount
    account.updated_at = now

    tx = PointTransaction(
        transaction_id=_new_transaction_id(),
        user_id=user_id,
        app_id=app_id,
        transaction_type=PointTransactionType.consume,
        amount=-amount,
        balance_before=balance_before,
        balance_after=balance_after,
        biz_id=biz_id,
        remark=remark,
        metadata_json=_metadata_to_json(metadata),
        created_at=now,
    )

    session.add(account)
    session.add(tx)
    session.commit()
    session.refresh(account)
    session.refresh(tx)

    return {
        "transaction_id": tx.transaction_id,
        "amount": amount,
        "balance": account.balance,
        "idempotent": False,
    }


def adjust_points(
    session: Session,
    user_id: int,
    amount: int,
    biz_id: Optional[str] = None,
    remark: Optional[str] = None,
    metadata: Optional[dict] = None,
    admin_username: Optional[str] = None,
) -> dict:
    if amount == 0:
        raise PointServiceError("invalid_amount", "Amount must not be zero")

    account = get_or_create_account(session, user_id, lock=True)
    balance_before = account.balance
    balance_after = balance_before + amount
    if balance_after < 0:
        raise PointServiceError("insufficient_balance", "Adjustment would make balance negative")

    now = get_now_naive()
    if amount < 0:
        lot_deducted = _deduct_from_lots(session, user_id, abs(amount), now)
        has_lots = session.exec(
            select(UserPointLot).where(UserPointLot.user_id == user_id)
        ).first() is not None
        if has_lots and not lot_deducted:
            raise PointServiceError("insufficient_balance", "Adjustment would make available balance negative")

    account.balance = balance_after
    if amount > 0:
        account.total_recharged += amount
    else:
        account.total_consumed += abs(amount)
    account.updated_at = now

    transaction_id = _new_transaction_id()
    tx = PointTransaction(
        transaction_id=transaction_id,
        user_id=user_id,
        transaction_type=PointTransactionType.adjust,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        biz_id=biz_id,
        remark=remark,
        metadata_json=_metadata_to_json(metadata),
        operator=admin_username,
        created_at=now,
    )

    session.add(account)
    session.add(tx)
    if amount > 0:
        _create_lot(
            session,
            user_id=user_id,
            transaction_id=transaction_id,
            amount=amount,
            now=now,
        )
    session.commit()
    session.refresh(account)
    session.refresh(tx)

    return {
        "transaction_id": tx.transaction_id,
        "amount": amount,
        "balance": account.balance,
    }


def refund_points(
    session: Session,
    user_id: int,
    refund_biz_id: str,
    consume_biz_id: Optional[str] = None,
    consume_transaction_id: Optional[str] = None,
    amount: Optional[int] = None,
    remark: Optional[str] = None,
    metadata: Optional[dict] = None,
    admin_username: Optional[str] = None,
) -> dict:
    if not refund_biz_id:
        raise PointServiceError("missing_refund_biz_id", "refund_biz_id is required")
    if not consume_biz_id and not consume_transaction_id:
        raise PointServiceError("missing_consume_reference", "consume_biz_id or consume_transaction_id is required")
    if amount is not None and amount <= 0:
        raise PointServiceError("invalid_amount", "Refund amount must be greater than zero")

    existing = session.exec(
        select(PointTransaction).where(
            PointTransaction.user_id == user_id,
            PointTransaction.transaction_type == PointTransactionType.refund,
            PointTransaction.biz_id == refund_biz_id,
        )
    ).first()
    if existing:
        if amount is not None and existing.amount != amount:
            raise PointServiceError("biz_id_conflict", "refund_biz_id was used with a different amount")
        return {
            "transaction_id": existing.transaction_id,
            "amount": existing.amount,
            "balance": existing.balance_after,
            "idempotent": True,
        }

    conditions = [
        PointTransaction.user_id == user_id,
        PointTransaction.transaction_type == PointTransactionType.consume,
    ]
    if consume_transaction_id:
        conditions.append(PointTransaction.transaction_id == consume_transaction_id)
    else:
        conditions.append(PointTransaction.biz_id == consume_biz_id)

    consume_tx = session.exec(select(PointTransaction).where(*conditions)).first()
    if not consume_tx:
        raise PointServiceError("consume_transaction_not_found", "Consume transaction not found", 404)

    refund_amount = amount or abs(consume_tx.amount)
    consumed_amount = abs(consume_tx.amount)

    refund_txs = session.exec(
        select(PointTransaction).where(
            PointTransaction.user_id == user_id,
            PointTransaction.transaction_type == PointTransactionType.refund,
        )
    ).all()
    already_refunded = 0
    for tx in refund_txs:
        tx_metadata = _metadata_from_json(tx.metadata_json)
        if tx_metadata.get("refunded_transaction_id") == consume_tx.transaction_id:
            already_refunded += tx.amount

    if already_refunded + refund_amount > consumed_amount:
        raise PointServiceError("refund_amount_exceeded", "Refund amount exceeds refundable points")

    account = get_or_create_account(session, user_id, lock=True)
    now = get_now_naive()
    balance_before = account.balance
    balance_after = balance_before + refund_amount
    account.balance = balance_after
    account.updated_at = now

    refund_metadata = {
        **(metadata or {}),
        "refunded_transaction_id": consume_tx.transaction_id,
        "consume_biz_id": consume_tx.biz_id,
    }
    transaction_id = _new_transaction_id()
    tx = PointTransaction(
        transaction_id=transaction_id,
        user_id=user_id,
        transaction_type=PointTransactionType.refund,
        amount=refund_amount,
        balance_before=balance_before,
        balance_after=balance_after,
        biz_id=refund_biz_id,
        remark=remark,
        metadata_json=_metadata_to_json(refund_metadata),
        operator=admin_username,
        created_at=now,
    )

    session.add(account)
    session.add(tx)
    _create_lot(
        session,
        user_id=user_id,
        transaction_id=transaction_id,
        amount=refund_amount,
        now=now,
    )
    session.commit()
    session.refresh(account)
    session.refresh(tx)

    return {
        "transaction_id": tx.transaction_id,
        "amount": refund_amount,
        "balance": account.balance,
        "idempotent": False,
    }
