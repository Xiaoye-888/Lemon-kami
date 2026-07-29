import base64
import json
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from datetime_utils import to_api_beijing_iso
from models import (
    EndUser,
    RechargeBonusRule,
    RechargeChannel,
    RechargeMode,
    RechargeOption,
    RechargeOrder,
    RechargeOrderStatus,
    RechargePaymentChannel,
    UserQuotaAccount,
    UserQuotaTransaction,
    UserQuotaTransactionType,
    get_now_naive,
)
from user_quota_service import (
    grant_user_quota,
    get_or_create_user_quota_account,
    user_quota_summary,
)


UPLOAD_ROOT = Path("uploads") / "commercial"
PUBLIC_PAYMENT_QRCODE_PREFIX = "/api/v1/commercial/payment-qrcodes"
SUPPORTED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_QRCODE_BYTES = 2 * 1024 * 1024
MAX_PROOF_BYTES = 5 * 1024 * 1024


def amount_to_cents(value) -> int:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("amount must be a valid number")
    if amount <= 0:
        raise ValueError("amount must be greater than 0")
    cents = int(amount * 100)
    if cents % 100 != 0:
        raise ValueError("amount must be a whole yuan value")
    return cents


def cents_to_amount(cents: int) -> int | float:
    if cents % 100 == 0:
        return cents // 100
    return float(Decimal(cents) / Decimal(100))


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


QUOTA_TYPE_LABELS = {
    "app_create": "应用创建额度",
    "kami_issue": "发卡额度",
    "recharge": "充值额度",
}

QUOTA_TRANSACTION_TYPE_LABELS = {
    "grant": "入账",
    "consume": "扣减",
    "adjust": "调整",
    "expire": "过期",
    "refund": "退回",
}


def _short_quota_transaction_no(transaction_id: Optional[str]) -> str:
    if not transaction_id:
        return "-"
    normalized = transaction_id.replace("_", "").replace("-", "").upper()
    return f"UQ-{normalized[-8:]}" if len(normalized) >= 8 else normalized


def _quota_transaction_display(item: UserQuotaTransaction) -> dict:
    quota_type = _enum_value(item.quota_type)
    transaction_type = _enum_value(item.transaction_type)
    direction = QUOTA_TRANSACTION_TYPE_LABELS.get(transaction_type, transaction_type or "-")
    if item.amount > 0 and transaction_type in {"adjust", "refund"}:
        direction = f"{direction}入账"
    elif item.amount < 0 and transaction_type in {"adjust", "expire"}:
        direction = f"{direction}扣减"

    biz_id = item.biz_id or ""
    scene = "额度调整"
    subject = item.remark or "手动处理"
    if biz_id.startswith("recharge_order:"):
        order_no = biz_id.split(":", 1)[1]
        scene = "充值入账"
        subject = f"充值订单 {order_no}"
    elif biz_id.startswith("kami_issue:"):
        parts = biz_id.split(":")
        batch_no = parts[2] if len(parts) > 2 else ""
        scene = "生成卡密"
        subject = f"卡密批次 {batch_no}" if batch_no else "卡密批次"
    elif transaction_type == "grant":
        scene = "管理员发放"
    elif transaction_type == "consume":
        scene = "额度扣减"
    elif transaction_type == "expire":
        scene = "额度过期"
    elif transaction_type == "refund":
        scene = "额度退回"

    return {
        "short_transaction_no": _short_quota_transaction_no(item.transaction_id),
        "display_scene": scene,
        "display_direction": direction,
        "display_quota_type": QUOTA_TYPE_LABELS.get(quota_type, quota_type or "-"),
        "display_subject": subject,
    }


def normalize_recharge_mode(value: str | RechargeMode | None) -> RechargeMode:
    if isinstance(value, RechargeMode):
        return value
    if not value:
        return RechargeMode.custom
    return RechargeMode(value)


def normalize_recharge_channel(value: str | RechargeChannel) -> RechargeChannel:
    return value if isinstance(value, RechargeChannel) else RechargeChannel(value)


def make_order_no(now: Optional[datetime] = None) -> str:
    current = now or get_now_naive()
    return f"RC{current.strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def payment_channel_payload(channel: RechargePaymentChannel) -> dict:
    return {
        "id": channel.id,
        "channel": _enum_value(channel.channel),
        "display_name": channel.display_name,
        "qr_code_url": channel.qr_code_url,
        "account_name": channel.account_name,
        "enabled": channel.enabled,
        "sort_order": channel.sort_order,
        "remark": channel.remark,
        "created_at": to_api_beijing_iso(channel.created_at, naive="civil") if channel.created_at else None,
        "updated_at": to_api_beijing_iso(channel.updated_at, naive="civil") if channel.updated_at else None,
    }


def recharge_option_payload(option: RechargeOption) -> dict:
    return {
        "id": option.id,
        "amount": cents_to_amount(option.amount_cents),
        "amount_cents": option.amount_cents,
        "credit_quota": option.credit_quota,
        "label": option.label or f"{cents_to_amount(option.amount_cents)} 元：到账 {option.credit_quota} 额度",
        "enabled": option.enabled,
        "sort_order": option.sort_order,
        "remark": option.remark,
        "created_at": to_api_beijing_iso(option.created_at, naive="civil") if option.created_at else None,
        "updated_at": to_api_beijing_iso(option.updated_at, naive="civil") if option.updated_at else None,
    }


def recharge_bonus_rule_payload(rule: RechargeBonusRule) -> dict:
    return {
        "id": rule.id,
        "threshold_amount": cents_to_amount(rule.threshold_amount_cents),
        "threshold_amount_cents": rule.threshold_amount_cents,
        "bonus_quota": rule.bonus_quota,
        "enabled": rule.enabled,
        "sort_order": rule.sort_order,
        "remark": rule.remark,
        "created_at": to_api_beijing_iso(rule.created_at, naive="civil") if rule.created_at else None,
        "updated_at": to_api_beijing_iso(rule.updated_at, naive="civil") if rule.updated_at else None,
    }


def list_payment_channels(session: Session, enabled_only: bool = False) -> list[RechargePaymentChannel]:
    statement = select(RechargePaymentChannel)
    if enabled_only:
        statement = statement.where(RechargePaymentChannel.enabled == True)  # noqa: E712
    return session.exec(
        statement.order_by(RechargePaymentChannel.sort_order, RechargePaymentChannel.id)
    ).all()


def list_recharge_options(session: Session, enabled_only: bool = False) -> list[RechargeOption]:
    statement = select(RechargeOption)
    if enabled_only:
        statement = statement.where(RechargeOption.enabled == True)  # noqa: E712
    return session.exec(
        statement.order_by(RechargeOption.sort_order, RechargeOption.amount_cents, RechargeOption.id)
    ).all()


def list_bonus_rules(session: Session, enabled_only: bool = False) -> list[RechargeBonusRule]:
    statement = select(RechargeBonusRule)
    if enabled_only:
        statement = statement.where(RechargeBonusRule.enabled == True)  # noqa: E712
    return session.exec(
        statement.order_by(
            RechargeBonusRule.threshold_amount_cents.desc(),
            RechargeBonusRule.sort_order,
            RechargeBonusRule.id,
        )
    ).all()


def upsert_payment_channel(
    session: Session,
    *,
    channel: str | RechargeChannel,
    display_name: str,
    qr_code_url: Optional[str] = None,
    account_name: Optional[str] = None,
    enabled: bool = True,
    sort_order: int = 0,
    remark: Optional[str] = None,
) -> RechargePaymentChannel:
    channel_enum = normalize_recharge_channel(channel)
    row = session.exec(
        select(RechargePaymentChannel).where(RechargePaymentChannel.channel == channel_enum)
    ).first()
    now = get_now_naive()
    if row:
        row.display_name = display_name
        row.qr_code_url = qr_code_url
        row.account_name = account_name
        row.enabled = enabled
        row.sort_order = sort_order
        row.remark = remark
        row.updated_at = now
    else:
        row = RechargePaymentChannel(
            channel=channel_enum,
            display_name=display_name,
            qr_code_url=qr_code_url,
            account_name=account_name,
            enabled=enabled,
            sort_order=sort_order,
            remark=remark,
            created_at=now,
            updated_at=now,
        )
    session.add(row)
    session.flush()
    return row


def create_recharge_option(
    session: Session,
    *,
    amount,
    credit_quota: int,
    label: Optional[str] = None,
    enabled: bool = True,
    sort_order: int = 0,
    remark: Optional[str] = None,
) -> RechargeOption:
    if credit_quota <= 0:
        raise ValueError("credit_quota must be greater than 0")
    amount_cents = amount_to_cents(amount)
    existing = session.exec(
        select(RechargeOption).where(RechargeOption.amount_cents == amount_cents)
    ).first()
    if existing:
        existing.credit_quota = credit_quota
        existing.label = label
        existing.enabled = enabled
        existing.sort_order = sort_order
        existing.remark = remark
        existing.updated_at = get_now_naive()
        session.add(existing)
        session.flush()
        return existing
    option = RechargeOption(
        amount_cents=amount_cents,
        credit_quota=credit_quota,
        label=label,
        enabled=enabled,
        sort_order=sort_order,
        remark=remark,
        created_at=get_now_naive(),
        updated_at=get_now_naive(),
    )
    session.add(option)
    session.flush()
    return option


def create_bonus_rule(
    session: Session,
    *,
    threshold_amount,
    bonus_quota: int,
    enabled: bool = True,
    sort_order: int = 0,
    remark: Optional[str] = None,
) -> RechargeBonusRule:
    if bonus_quota <= 0:
        raise ValueError("bonus_quota must be greater than 0")
    rule = RechargeBonusRule(
        threshold_amount_cents=amount_to_cents(threshold_amount),
        bonus_quota=bonus_quota,
        enabled=enabled,
        sort_order=sort_order,
        remark=remark,
        created_at=get_now_naive(),
        updated_at=get_now_naive(),
    )
    session.add(rule)
    session.flush()
    return rule


def delete_or_archive_recharge_option(session: Session, option_id: int) -> tuple[RechargeOption, bool]:
    option = session.get(RechargeOption, option_id)
    if not option:
        raise ValueError("recharge option not found")
    used_order = session.exec(
        select(RechargeOrder).where(RechargeOrder.option_id == option_id)
    ).first()
    if used_order:
        option.enabled = False
        option.updated_at = get_now_naive()
        session.add(option)
        session.flush()
        return option, True
    session.delete(option)
    session.flush()
    return option, False


def delete_or_archive_bonus_rule(session: Session, rule_id: int) -> tuple[RechargeBonusRule, bool]:
    rule = session.get(RechargeBonusRule, rule_id)
    if not rule:
        raise ValueError("recharge bonus rule not found")
    used_order = session.exec(
        select(RechargeOrder).where(RechargeOrder.bonus_rule_id == rule_id)
    ).first()
    if used_order:
        rule.enabled = False
        rule.updated_at = get_now_naive()
        session.add(rule)
        session.flush()
        return rule, True
    session.delete(rule)
    session.flush()
    return rule, False


def recharge_config_payload(session: Session, enabled_only: bool = False) -> dict:
    return {
        "channels": [
            payment_channel_payload(item)
            for item in list_payment_channels(session, enabled_only=enabled_only)
        ],
        "options": [
            recharge_option_payload(item)
            for item in list_recharge_options(session, enabled_only=enabled_only)
        ],
        "bonus_rules": [
            recharge_bonus_rule_payload(item)
            for item in list_bonus_rules(session, enabled_only=enabled_only)
        ],
        "custom_base_ratio": {
            "amount": 1,
            "credit_quota": 1,
            "label": "自定义充值：1 元 = 1 发卡额度",
        },
    }


def calculate_recharge_preview(
    session: Session,
    *,
    amount,
    mode: str | RechargeMode = RechargeMode.custom,
    option_id: Optional[int] = None,
) -> dict:
    mode_enum = normalize_recharge_mode(mode)
    amount_cents = amount_to_cents(amount)
    selected_option = None
    bonus_rule = None

    if mode_enum == RechargeMode.fixed or option_id is not None:
        if option_id is not None:
            selected_option = session.get(RechargeOption, option_id)
        else:
            selected_option = session.exec(
                select(RechargeOption).where(RechargeOption.amount_cents == amount_cents)
            ).first()
        if not selected_option or not selected_option.enabled:
            raise ValueError("fixed recharge option is not available")
        base_quota = selected_option.credit_quota
        bonus_quota = 0
        credit_quota = selected_option.credit_quota
        pricing_source = "fixed_option"
        amount_cents = selected_option.amount_cents
    else:
        base_quota = amount_cents // 100
        rules = list_bonus_rules(session, enabled_only=True)
        for rule in rules:
            if amount_cents >= rule.threshold_amount_cents:
                bonus_rule = rule
                break
        bonus_quota = bonus_rule.bonus_quota if bonus_rule else 0
        credit_quota = base_quota + bonus_quota
        pricing_source = "custom_bonus" if bonus_rule else "custom_base"

    if credit_quota <= 0:
        raise ValueError("credit quota must be greater than 0")

    return {
        "amount": cents_to_amount(amount_cents),
        "amount_cents": amount_cents,
        "mode": mode_enum.value,
        "option_id": selected_option.id if selected_option else None,
        "base_quota": base_quota,
        "bonus_quota": bonus_quota,
        "credit_quota": credit_quota,
        "bonus_rule_id": bonus_rule.id if bonus_rule else None,
        "pricing_source": pricing_source,
    }


def _payment_snapshot(channel: RechargePaymentChannel) -> dict:
    return {
        "channel": _enum_value(channel.channel),
        "display_name": channel.display_name,
        "qr_code_url": channel.qr_code_url,
        "account_name": channel.account_name,
    }


def _proof_root() -> Path:
    return UPLOAD_ROOT / "proofs"


def _payment_qrcode_root() -> Path:
    return UPLOAD_ROOT / "payment-qrcodes"


def ensure_upload_directories() -> None:
    _proof_root().mkdir(parents=True, exist_ok=True)
    _payment_qrcode_root().mkdir(parents=True, exist_ok=True)


def _safe_file_prefix(value: str) -> str:
    prefix = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return prefix[:80] or "upload"


def _image_extension(content_type: Optional[str], label: str) -> tuple[str, str]:
    normalized = (content_type or "").split(";", 1)[0].strip().lower()
    extension = SUPPORTED_IMAGE_TYPES.get(normalized)
    if not extension:
        raise ValueError(f"unsupported {label} image type")
    return normalized, extension


def _path_is_inside(path: Path, root: Path) -> bool:
    resolved_path = path.resolve(strict=False)
    resolved_root = root.resolve(strict=False)
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


def _delete_file_if_safe(file_path: Optional[str | Path], root: Optional[Path] = None) -> bool:
    if not file_path:
        return False
    path = Path(file_path)
    safety_root = root or UPLOAD_ROOT
    if not _path_is_inside(path, safety_root):
        return False
    if not path.exists() or not path.is_file():
        return False
    path.unlink()
    return True


def payment_qrcode_public_url(filename: str) -> str:
    return f"{PUBLIC_PAYMENT_QRCODE_PREFIX}/{filename}"


def payment_qrcode_path_from_public_url(url: Optional[str]) -> Optional[Path]:
    if not url or not url.startswith(f"{PUBLIC_PAYMENT_QRCODE_PREFIX}/"):
        return None
    filename = url.rsplit("/", 1)[-1]
    if not filename or filename != Path(filename).name:
        return None
    return _payment_qrcode_root() / filename


def delete_payment_qrcode_by_url_if_safe(url: Optional[str]) -> bool:
    path = payment_qrcode_path_from_public_url(url)
    if not path:
        return False
    return _delete_file_if_safe(path, _payment_qrcode_root())


def payment_qrcode_file_path(filename: str) -> Path:
    if not filename or filename != Path(filename).name:
        raise ValueError("invalid payment QR code filename")
    path = _payment_qrcode_root() / filename
    if not _path_is_inside(path, _payment_qrcode_root()):
        raise ValueError("invalid payment QR code filename")
    return path


def payment_qrcode_media_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


async def _save_upload_image(
    upload: UploadFile,
    *,
    target_dir: Path,
    file_prefix: str,
    max_bytes: int,
    label: str,
) -> tuple[str, str, str]:
    content_type, extension = _image_extension(upload.content_type, label)
    dir_preexisted = target_dir.exists()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_file_prefix(file_prefix)}_{uuid.uuid4().hex[:12]}{extension}"
    final_path = target_dir / filename
    temp_path = target_dir / f".{filename}.tmp"
    size = 0
    try:
        with temp_path.open("wb") as target:
            while True:
                chunk = await upload.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(f"{label} image is too large")
                target.write(chunk)
        if size <= 0:
            raise ValueError(f"{label} image is empty")
        temp_path.replace(final_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        if not dir_preexisted:
            try:
                target_dir.rmdir()
            except OSError:
                pass
        raise
    finally:
        await upload.close()
    return final_path.as_posix(), filename, content_type


async def save_payment_qrcode_upload(upload: UploadFile, channel: str | RechargeChannel) -> str:
    channel_enum = normalize_recharge_channel(channel)
    _, filename, _ = await _save_upload_image(
        upload,
        target_dir=_payment_qrcode_root(),
        file_prefix=f"{channel_enum.value}_qrcode",
        max_bytes=MAX_QRCODE_BYTES,
        label="payment QR code",
    )
    return payment_qrcode_public_url(filename)


def clear_payment_channel_qrcode(
    session: Session,
    channel: str | RechargeChannel,
) -> tuple[RechargePaymentChannel, bool]:
    channel_enum = normalize_recharge_channel(channel)
    row = session.exec(
        select(RechargePaymentChannel).where(RechargePaymentChannel.channel == channel_enum)
    ).first()
    if not row:
        raise ValueError("payment channel not found")
    deleted_file = delete_payment_qrcode_by_url_if_safe(row.qr_code_url)
    row.qr_code_url = None
    row.updated_at = get_now_naive()
    session.add(row)
    session.flush()
    return row, deleted_file


def _save_data_url_image(data_url: Optional[str], order_no: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not data_url:
        return None, None, None
    if ";base64," not in data_url or not data_url.startswith("data:"):
        raise ValueError("proof_image_data_url must be a base64 data URL")
    header, encoded = data_url.split(";base64,", 1)
    content_type = header.replace("data:", "", 1).strip().lower()
    extension = SUPPORTED_IMAGE_TYPES.get(content_type)
    if not extension:
        raise ValueError("unsupported proof image type")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as error:
        raise ValueError("invalid proof image data") from error
    if len(data) > MAX_PROOF_BYTES:
        raise ValueError("proof image is too large")
    target_dir = _proof_root()
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{order_no}_{uuid.uuid4().hex[:8]}{extension}"
    path = target_dir / filename
    path.write_bytes(data)
    return path.as_posix(), filename, content_type


def _create_recharge_order_record(
    session: Session,
    *,
    user: EndUser,
    channel_enum: RechargeChannel,
    payment_channel: RechargePaymentChannel,
    preview: dict,
    order_no: str,
    remark: Optional[str] = None,
    proof_path: Optional[str] = None,
    proof_name: Optional[str] = None,
    proof_content_type: Optional[str] = None,
) -> RechargeOrder:
    order = RechargeOrder(
        order_no=order_no,
        user_id=user.id,
        username=user.username,
        mode=RechargeMode(preview["mode"]),
        channel=channel_enum,
        amount_cents=preview["amount_cents"],
        base_quota=preview["base_quota"],
        bonus_quota=preview["bonus_quota"],
        credit_quota=preview["credit_quota"],
        option_id=preview["option_id"],
        bonus_rule_id=preview["bonus_rule_id"],
        status=RechargeOrderStatus.pending_review,
        payment_snapshot_json=json.dumps(_payment_snapshot(payment_channel), ensure_ascii=False),
        preview_snapshot_json=json.dumps(preview, ensure_ascii=False),
        proof_file_path=proof_path,
        proof_file_name=proof_name,
        proof_content_type=proof_content_type,
        user_remark=remark,
        created_at=get_now_naive(),
        updated_at=get_now_naive(),
    )
    session.add(order)
    session.flush()
    return order


def _recharge_order_inputs(
    session: Session,
    *,
    amount,
    channel: str | RechargeChannel,
    mode: str | RechargeMode = RechargeMode.custom,
    option_id: Optional[int] = None,
) -> tuple[RechargeChannel, RechargePaymentChannel, dict]:
    channel_enum = normalize_recharge_channel(channel)
    payment_channel = session.exec(
        select(RechargePaymentChannel).where(RechargePaymentChannel.channel == channel_enum)
    ).first()
    if not payment_channel or not payment_channel.enabled:
        raise ValueError("payment channel is not available")
    preview = calculate_recharge_preview(session, amount=amount, mode=mode, option_id=option_id)
    return channel_enum, payment_channel, preview


def create_recharge_order(
    session: Session,
    *,
    user: EndUser,
    amount,
    channel: str | RechargeChannel,
    mode: str | RechargeMode = RechargeMode.custom,
    option_id: Optional[int] = None,
    remark: Optional[str] = None,
    proof_image_data_url: Optional[str] = None,
) -> RechargeOrder:
    channel_enum, payment_channel, preview = _recharge_order_inputs(
        session,
        amount=amount,
        mode=mode,
        option_id=option_id,
        channel=channel,
    )
    order_no = make_order_no()
    proof_path, proof_name, proof_content_type = _save_data_url_image(proof_image_data_url, order_no)
    return _create_recharge_order_record(
        session,
        user=user,
        channel_enum=channel_enum,
        payment_channel=payment_channel,
        preview=preview,
        order_no=order_no,
        remark=remark,
        proof_path=proof_path,
        proof_name=proof_name,
        proof_content_type=proof_content_type,
    )


async def create_recharge_order_from_upload(
    session: Session,
    *,
    user: EndUser,
    amount,
    channel: str | RechargeChannel,
    mode: str | RechargeMode = RechargeMode.custom,
    option_id: Optional[int] = None,
    remark: Optional[str] = None,
    proof_file: UploadFile,
) -> RechargeOrder:
    channel_enum, payment_channel, preview = _recharge_order_inputs(
        session,
        amount=amount,
        mode=mode,
        option_id=option_id,
        channel=channel,
    )
    order_no = make_order_no()
    proof_path, proof_name, proof_content_type = await _save_upload_image(
        proof_file,
        target_dir=_proof_root(),
        file_prefix=order_no,
        max_bytes=MAX_PROOF_BYTES,
        label="proof",
    )
    return _create_recharge_order_record(
        session,
        user=user,
        channel_enum=channel_enum,
        payment_channel=payment_channel,
        preview=preview,
        order_no=order_no,
        remark=remark,
        proof_path=proof_path,
        proof_name=proof_name,
        proof_content_type=proof_content_type,
    )


def recharge_order_payload(order: RechargeOrder, include_user: bool = False) -> dict:
    payload = {
        "id": order.id,
        "order_no": order.order_no,
        "user_id": order.user_id,
        "username": order.username,
        "mode": _enum_value(order.mode),
        "channel": _enum_value(order.channel),
        "amount": cents_to_amount(order.amount_cents),
        "amount_cents": order.amount_cents,
        "base_quota": order.base_quota,
        "bonus_quota": order.bonus_quota,
        "credit_quota": order.credit_quota,
        "option_id": order.option_id,
        "bonus_rule_id": order.bonus_rule_id,
        "status": _enum_value(order.status),
        "has_proof": bool(order.proof_file_path),
        "proof_file_name": order.proof_file_name,
        "proof_content_type": order.proof_content_type,
        "user_remark": order.user_remark,
        "admin_remark": order.admin_remark,
        "reject_reason": order.reject_reason,
        "reviewer": order.reviewer,
        "reviewed_at": to_api_beijing_iso(order.reviewed_at, naive="civil") if order.reviewed_at else None,
        "quota_transaction_id": order.quota_transaction_id,
        "created_at": to_api_beijing_iso(order.created_at, naive="civil") if order.created_at else None,
        "updated_at": to_api_beijing_iso(order.updated_at, naive="civil") if order.updated_at else None,
    }
    if include_user:
        payload["user"] = {
            "id": order.user_id,
            "username": order.username,
        }
    return payload


def get_recharge_order_or_404(session: Session, order_no: str) -> RechargeOrder:
    order = session.exec(
        select(RechargeOrder).where(RechargeOrder.order_no == order_no)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Recharge order not found")
    return order


def _delete_proof_file_if_safe(proof_file_path: Optional[str]) -> bool:
    return _delete_file_if_safe(proof_file_path, UPLOAD_ROOT)


TERMINAL_RECHARGE_ORDER_STATUSES = {
    RechargeOrderStatus.approved,
    RechargeOrderStatus.rejected,
    RechargeOrderStatus.canceled,
    RechargeOrderStatus.expired,
    RechargeOrderStatus.abnormal,
}


def delete_recharge_orders_for_users(session: Session, user_ids: list[int]) -> dict:
    if not user_ids:
        return {"deleted_recharge_orders": 0, "deleted_recharge_proofs": 0}
    orders = session.exec(
        select(RechargeOrder).where(RechargeOrder.user_id.in_(user_ids))
    ).all()
    deleted_proofs = 0
    for order in orders:
        if _delete_proof_file_if_safe(order.proof_file_path):
            deleted_proofs += 1
        session.delete(order)
    session.flush()
    return {
        "deleted_recharge_orders": len(orders),
        "deleted_recharge_proofs": deleted_proofs,
    }


def approve_recharge_order(
    session: Session,
    *,
    order: RechargeOrder,
    reviewer: str,
    remark: Optional[str] = None,
) -> tuple[RechargeOrder, dict]:
    if order.status != RechargeOrderStatus.pending_review:
        raise ValueError("only pending_review orders can be approved")
    user = session.get(EndUser, order.user_id)
    if not user:
        raise ValueError("order user does not exist")
    account = get_or_create_user_quota_account(session, user.id, user.username)
    tx = grant_user_quota(
        session=session,
        account=account,
        quota_type="kami_issue",
        amount=order.credit_quota,
        operator=reviewer,
        biz_id=f"recharge_order:{order.order_no}",
        remark=remark or f"Recharge order {order.order_no}",
        metadata={
            "order_no": order.order_no,
            "amount": cents_to_amount(order.amount_cents),
            "base_quota": order.base_quota,
            "bonus_quota": order.bonus_quota,
            "credit_quota": order.credit_quota,
        },
    )
    order.status = RechargeOrderStatus.approved
    order.reviewer = reviewer
    order.reviewed_at = get_now_naive()
    order.admin_remark = remark
    order.quota_transaction_id = tx["transaction_id"]
    order.updated_at = get_now_naive()
    session.add(order)
    session.flush()
    return order, tx


def update_recharge_order_status(
    session: Session,
    *,
    order: RechargeOrder,
    status: RechargeOrderStatus,
    reviewer: str,
    remark: Optional[str] = None,
    reject_reason: Optional[str] = None,
) -> RechargeOrder:
    if order.status != RechargeOrderStatus.pending_review:
        raise ValueError("only pending_review orders can be reviewed")
    if status == RechargeOrderStatus.rejected and not reject_reason:
        raise ValueError("reject_reason is required")
    order.status = status
    order.reviewer = reviewer
    order.reviewed_at = get_now_naive()
    order.admin_remark = remark
    order.reject_reason = reject_reason
    order.updated_at = get_now_naive()
    session.add(order)
    session.flush()
    return order


def cancel_recharge_order(
    session: Session,
    *,
    order: RechargeOrder,
    operator: str,
    remark: Optional[str] = None,
) -> RechargeOrder:
    if order.status != RechargeOrderStatus.pending_review:
        raise ValueError("only pending_review orders can be canceled")
    order.status = RechargeOrderStatus.canceled
    order.admin_remark = remark
    order.updated_at = get_now_naive()
    session.add(order)
    session.flush()
    return order


def expire_recharge_order(
    session: Session,
    *,
    order: RechargeOrder,
    reviewer: str,
    remark: Optional[str] = None,
) -> RechargeOrder:
    if order.status != RechargeOrderStatus.pending_review:
        raise ValueError("only pending_review orders can be expired")
    order.status = RechargeOrderStatus.expired
    order.reviewer = reviewer
    order.reviewed_at = get_now_naive()
    order.admin_remark = remark
    order.updated_at = get_now_naive()
    session.add(order)
    session.flush()
    return order


def cleanup_recharge_proofs(
    session: Session,
    *,
    older_than_days: int,
    dry_run: bool = True,
) -> dict:
    if older_than_days <= 0:
        raise ValueError("older_than_days must be greater than 0")
    cutoff = get_now_naive() - timedelta(days=older_than_days)
    orders = session.exec(
        select(RechargeOrder).where(
            RechargeOrder.status.in_(TERMINAL_RECHARGE_ORDER_STATUSES),
            RechargeOrder.created_at <= cutoff,
            RechargeOrder.proof_file_path.is_not(None),
        )
    ).all()
    deleted_proofs = 0
    for order in orders:
        if dry_run:
            if order.proof_file_path and Path(order.proof_file_path).exists():
                deleted_proofs += 1
            continue
        file_missing = bool(order.proof_file_path) and not Path(order.proof_file_path).exists()
        if _delete_proof_file_if_safe(order.proof_file_path):
            deleted_proofs += 1
        if file_missing or order.proof_file_path:
            order.proof_file_deleted = True
            order.proof_deleted_at = get_now_naive()
        order.proof_file_path = None
        order.proof_file_name = None
        order.proof_content_type = None
        order.updated_at = get_now_naive()
        session.add(order)
    if not dry_run:
        session.flush()
    return {
        "dry_run": dry_run,
        "older_than_days": older_than_days,
        "matched_orders": len(orders),
        "deleted_proofs": deleted_proofs,
    }


def user_quota_transactions_payload(
    session: Session,
    *,
    user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    statement = select(UserQuotaTransaction)
    count_statement = select(UserQuotaTransaction)
    if user_id is not None:
        statement = statement.where(UserQuotaTransaction.user_id == user_id)
        count_statement = count_statement.where(UserQuotaTransaction.user_id == user_id)
    total = len(session.exec(count_statement).all())
    items = session.exec(
        statement.order_by(UserQuotaTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": item.id,
                "transaction_id": item.transaction_id,
                "account_id": item.account_id,
                "user_id": item.user_id,
                "username": item.username,
                "quota_type": _enum_value(item.quota_type),
                "transaction_type": _enum_value(item.transaction_type),
                "amount": item.amount,
                "balance_before": item.balance_before,
                "balance_after": item.balance_after,
                "biz_id": item.biz_id,
                "operator": item.operator,
                "remark": item.remark,
                "metadata": item.metadata_json,
                "created_at": to_api_beijing_iso(item.created_at, naive="civil") if item.created_at else None,
                **_quota_transaction_display(item),
            }
            for item in items
        ],
    }


def merchant_quota_summary(session: Session, user: EndUser) -> dict:
    account = get_or_create_user_quota_account(session, user.id, user.username)
    session.flush()
    return user_quota_summary(account)
