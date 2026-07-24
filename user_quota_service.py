import json
import random
import string
import uuid
from datetime import timedelta
from typing import Optional

from sqlmodel import Session, select

from crypto import RSACrypto
from models import (
    App,
    AuthorizationOwnerMode,
    Kami,
    KamiBatch,
    KamiSpec,
    KamiStatus,
    KamiType,
    MachineBindMode,
    UserAppAuthorization,
    UserBindMode,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaTransactionType,
    UserQuotaType,
    EndUser,
    get_now_naive,
)

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
    characters = KAMI_CHARSETS.get(charset)
    if not characters:
        raise ValueError("Invalid charset")
    return f"{prefix}{''.join(random.choices(characters, k=length))}"


def _now() -> object:
    return get_now_naive()


def _quota_field_names(quota_type: UserQuotaType) -> tuple[str, str]:
    mapping = {
        UserQuotaType.app_create: ("app_create_balance", "total_app_create_granted"),
        UserQuotaType.kami_issue: ("kami_issue_balance", "total_kami_issue_granted"),
        UserQuotaType.recharge: ("recharge_balance", "total_recharge_granted"),
    }
    return mapping[quota_type]


def _normalize_quota_type(quota_type: str | UserQuotaType) -> UserQuotaType:
    return quota_type if isinstance(quota_type, UserQuotaType) else UserQuotaType(quota_type)


def _normalize_kami_type(kami_type: str | KamiType) -> KamiType:
    return kami_type if isinstance(kami_type, KamiType) else KamiType(kami_type)


def get_or_create_user_quota_account(
    session: Session,
    user_id: int,
    username: Optional[str] = None,
) -> UserQuotaAccount:
    account = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id == user_id)
    ).first()
    if account:
        if username and not account.username:
            account.username = username
        account.updated_at = _now()
        session.add(account)
        session.flush()
        return account

    account = UserQuotaAccount(
        user_id=user_id,
        username=username,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(account)
    session.flush()
    return account


def user_quota_summary(account: UserQuotaAccount) -> dict:
    return {
        "user_id": account.user_id,
        "username": account.username,
        "app_create_balance": account.app_create_balance,
        "kami_issue_balance": account.kami_issue_balance,
        "recharge_balance": account.recharge_balance,
        "total_app_create_granted": account.total_app_create_granted,
        "total_kami_issue_granted": account.total_kami_issue_granted,
        "total_recharge_granted": account.total_recharge_granted,
        "status": account.status,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def grant_user_quota(
    session: Session,
    account: UserQuotaAccount,
    quota_type: str | UserQuotaType,
    amount: int,
    operator: Optional[str] = None,
    biz_id: Optional[str] = None,
    remark: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    quota_type_enum = _normalize_quota_type(quota_type)
    if amount <= 0:
        raise ValueError("amount must be greater than 0")

    balance_field, total_field = _quota_field_names(quota_type_enum)
    balance_before = getattr(account, balance_field)
    balance_after = balance_before + amount
    setattr(account, balance_field, balance_after)
    setattr(account, total_field, getattr(account, total_field) + amount)
    account.updated_at = _now()

    tx = UserQuotaTransaction(
        transaction_id=f"uq_{uuid.uuid4().hex}",
        account_id=account.id,
        user_id=account.user_id,
        username=account.username,
        quota_type=quota_type_enum,
        transaction_type=UserQuotaTransactionType.grant,
        amount=amount,
        balance_before=balance_before,
        balance_after=balance_after,
        biz_id=biz_id,
        operator=operator,
        remark=remark,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        created_at=_now(),
    )
    session.add(account)
    session.add(tx)
    session.flush()
    return {
        "transaction_id": tx.transaction_id,
        "quota_type": quota_type_enum.value,
        "amount": amount,
        "balance_after": balance_after,
    }


def consume_user_quota(
    session: Session,
    account: UserQuotaAccount,
    quota_type: str | UserQuotaType,
    amount: int,
    operator: Optional[str] = None,
    biz_id: Optional[str] = None,
    remark: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    quota_type_enum = _normalize_quota_type(quota_type)
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    if not biz_id:
        raise ValueError("biz_id is required")

    existing = session.exec(
        select(UserQuotaTransaction).where(
            UserQuotaTransaction.account_id == account.id,
            UserQuotaTransaction.quota_type == quota_type_enum,
            UserQuotaTransaction.transaction_type == UserQuotaTransactionType.consume,
            UserQuotaTransaction.biz_id == biz_id,
        )
    ).first()
    if existing:
        if existing.amount != -amount:
            raise ValueError("biz_id was used with a different amount")
        return {
            "transaction_id": existing.transaction_id,
            "quota_type": quota_type_enum.value,
            "amount": amount,
            "balance_after": existing.balance_after,
            "idempotent": True,
        }

    balance_field, _ = _quota_field_names(quota_type_enum)
    balance_before = getattr(account, balance_field)
    if balance_before < amount:
        raise ValueError("insufficient quota")

    balance_after = balance_before - amount
    setattr(account, balance_field, balance_after)
    account.updated_at = _now()

    tx = UserQuotaTransaction(
        transaction_id=f"uq_{uuid.uuid4().hex}",
        account_id=account.id,
        user_id=account.user_id,
        username=account.username,
        quota_type=quota_type_enum,
        transaction_type=UserQuotaTransactionType.consume,
        amount=-amount,
        balance_before=balance_before,
        balance_after=balance_after,
        biz_id=biz_id,
        operator=operator,
        remark=remark,
        metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
        created_at=_now(),
    )
    session.add(account)
    session.add(tx)
    session.flush()
    return {
        "transaction_id": tx.transaction_id,
        "quota_type": quota_type_enum.value,
        "amount": amount,
        "balance_after": balance_after,
        "idempotent": False,
    }


def grant_app_authorization(
    session: Session,
    app_id: str,
    user: EndUser,
    granted_by: str,
    remark: Optional[str] = None,
) -> UserAppAuthorization:
    existing = session.exec(
        select(UserAppAuthorization).where(
            UserAppAuthorization.app_id == app_id,
            UserAppAuthorization.user_id == user.id,
        )
    ).first()
    if existing:
        if remark is not None:
            existing.remark = remark
        existing.username = user.username
        existing.granted_by = granted_by
        session.add(existing)
        session.flush()
        return existing

    authorization = UserAppAuthorization(
        app_id=app_id,
        user_id=user.id,
        username=user.username,
        granted_by=granted_by,
        remark=remark,
        created_at=_now(),
    )
    session.add(authorization)
    session.flush()
    return authorization


def get_user_visible_apps(session: Session, user: EndUser) -> list[App]:
    authorized_app_ids = session.exec(
        select(UserAppAuthorization.app_id).where(UserAppAuthorization.user_id == user.id)
    ).all()
    statement = select(App).where(
        (App.owner_user_id == user.id)
        | (App.created_by == user.username)
        | (App.app_id.in_(authorized_app_ids) if authorized_app_ids else False)
    )
    apps = session.exec(statement).all()
    seen = set()
    result = []
    for app in sorted(apps, key=lambda item: (item.created_at or _now(), item.id or 0), reverse=True):
        if app.app_id in seen:
            continue
        seen.add(app.app_id)
        result.append(app)
    return result


def user_can_manage_app(session: Session, user: EndUser, app_id: str) -> bool:
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        return False
    if app.owner_user_id == user.id:
        return True
    if app.created_by and app.created_by == user.username:
        return True
    return session.exec(
        select(UserAppAuthorization).where(
            UserAppAuthorization.app_id == app_id,
            UserAppAuthorization.user_id == user.id,
        )
    ).first() is not None


def create_user_app(
    session: Session,
    user: EndUser,
    name: str,
) -> tuple[App, dict]:
    account = get_or_create_user_quota_account(session, user.id, user.username)
    app_id = f"app_{uuid.uuid4().hex[:12]}"
    secret = uuid.uuid4().hex
    key_pair = RSACrypto.generate_key_pair()
    app = App(
        app_id=app_id,
        name=name,
        app_secret=secret,
        rsa_public_key=key_pair["public_key"],
        rsa_private_key=key_pair["private_key"],
        status=1,
        created_by=user.username,
        owner_user_id=user.id,
        created_at=_now(),
    )
    session.add(app)
    session.flush()
    result = {
        "transaction_id": None,
        "quota_type": UserQuotaType.app_create.value,
        "amount": 0,
        "balance_after": account.app_create_balance,
        "idempotent": False,
        "metered": False,
    }
    return app, result


def issue_user_kamis(
    session: Session,
    user: EndUser,
    app: App,
    *,
    kami_type: str | KamiType,
    count: int,
    spec_id: Optional[int] = None,
    unit_cost: int = 1,
    batch_no: Optional[str] = None,
    code_prefix: Optional[str] = None,
    code_length: int = 16,
    charset: str = "upper_numeric",
    points_amount: Optional[int] = None,
    points_valid_days: Optional[int] = None,
    times_total: Optional[int] = None,
    time_value: Optional[int] = None,
    time_unit: Optional[str] = None,
    machine_bind_mode: str | MachineBindMode = MachineBindMode.one_card_one_device,
    max_bind_devices: int = 1,
    authorization_owner: str | AuthorizationOwnerMode = AuthorizationOwnerMode.device,
    user_bind_mode: str | UserBindMode = UserBindMode.none,
) -> dict:
    if count <= 0:
        raise ValueError("count must be greater than 0")
    if unit_cost <= 0:
        raise ValueError("unit_cost must be greater than 0")
    effective_batch_no = batch_no or f"user_{uuid.uuid4().hex[:12]}"
    existing_batch = session.exec(
        select(KamiBatch).where(
            KamiBatch.app_id == app.app_id,
            KamiBatch.batch_no == effective_batch_no,
        )
    ).first()
    if existing_batch:
        raise ValueError("batch_no already exists")

    account = get_or_create_user_quota_account(session, user.id, user.username)
    total_cost = count * unit_cost
    quota_result = consume_user_quota(
        session=session,
        account=account,
        quota_type=UserQuotaType.kami_issue,
        amount=total_cost,
        biz_id=f"kami_issue:{app.app_id}:{effective_batch_no}:{code_prefix or ''}:{count}",
        operator=user.username,
        remark=f"Issue {count} kamis",
        metadata={
            "app_id": app.app_id,
            "kami_type": _normalize_kami_type(kami_type).value,
            "spec_id": spec_id,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
        },
    )
    if quota_result.get("idempotent"):
        raise ValueError("batch_no already processed")

    kami_type_enum = _normalize_kami_type(kami_type)
    if charset not in KAMI_CHARSETS:
        raise ValueError("Invalid charset")
    machine_bind_mode_enum = (
        machine_bind_mode
        if isinstance(machine_bind_mode, MachineBindMode)
        else MachineBindMode(machine_bind_mode)
    )
    authorization_owner_enum = (
        authorization_owner
        if isinstance(authorization_owner, AuthorizationOwnerMode)
        else AuthorizationOwnerMode(authorization_owner)
    )
    user_bind_mode_enum = (
        user_bind_mode
        if isinstance(user_bind_mode, UserBindMode)
        else UserBindMode(user_bind_mode)
    )

    if kami_type_enum in TIME_CARD_UNITS:
        default_value, default_unit = TIME_CARD_UNITS[kami_type_enum]
        if time_value is None:
            time_value = default_value
        if time_unit is None:
            time_unit = default_unit

    now = _now()
    code_expires_at = None
    codes: list[str] = []
    kamis: list[Kami] = []
    session.add(
        KamiBatch(
            spec_id=spec_id,
            app_id=app.app_id,
            batch_no=effective_batch_no,
            kami_type=kami_type_enum,
            points_amount=points_amount if kami_type_enum == KamiType.points else None,
            points_valid_days=points_valid_days if kami_type_enum == KamiType.points else None,
            time_value=time_value if kami_type_enum in TIME_CARD_UNITS else None,
            time_unit=time_unit if kami_type_enum in TIME_CARD_UNITS else None,
            times_total=times_total if kami_type_enum == KamiType.times else None,
            code_prefix=code_prefix,
            code_length=code_length,
            charset=charset,
            machine_bind_mode=machine_bind_mode_enum,
            max_bind_devices=max_bind_devices,
            authorization_owner=authorization_owner_enum,
            user_bind_mode=user_bind_mode_enum,
            status=1,
            remark=f"Merchant issued by {user.username}",
            created_at=now,
            updated_at=now,
        )
    )

    for _ in range(count):
        kami_code = generate_kami_code(code_length, code_prefix or "", charset)
        while session.exec(select(Kami).where(Kami.kami_code == kami_code)).first():
            kami_code = generate_kami_code(code_length, code_prefix or "", charset)
        codes.append(kami_code)
        kami = Kami(
            spec_id=spec_id,
            app_id=app.app_id,
            kami_code=kami_code,
            kami_type=kami_type_enum,
            status=KamiStatus.unused,
            points_amount=points_amount if kami_type_enum == KamiType.points else None,
            batch_no=effective_batch_no,
            points_valid_days=points_valid_days if kami_type_enum == KamiType.points else None,
            time_value=time_value if kami_type_enum in TIME_CARD_UNITS else None,
            time_unit=time_unit if kami_type_enum in TIME_CARD_UNITS else None,
            times_total=times_total if kami_type_enum == KamiType.times else None,
            times_remaining=times_total if kami_type_enum == KamiType.times else None,
            code_prefix=code_prefix,
            code_length=code_length,
            charset=charset,
            code_valid_days=None,
            code_expires_at=code_expires_at,
            machine_bind_mode=machine_bind_mode_enum,
            max_bind_devices=max_bind_devices,
            authorization_owner=authorization_owner_enum,
            user_bind_mode=user_bind_mode_enum,
            created_at=now,
            created_by_user_id=user.id,
        )
        kamis.append(kami)

    session.add_all(kamis)
    session.flush()
    return {
        "batch_no": effective_batch_no,
        "spec_id": spec_id,
        "count": count,
        "codes": codes,
        "unit_cost": unit_cost,
        "total_cost": total_cost,
        "quota": quota_result,
    }


def list_user_issued_kamis(session: Session, user: EndUser, app_id: Optional[str] = None) -> list[Kami]:
    statement = select(Kami).where(Kami.created_by_user_id == user.id)
    if app_id:
        statement = statement.where(Kami.app_id == app_id)
    return session.exec(statement.order_by(Kami.id.desc())).all()
