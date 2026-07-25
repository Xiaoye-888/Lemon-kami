from typing import Optional

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_admin
from audit_service import (
    CONFIRM_TEXT_BY_SCOPE,
    audit_log_payload,
    record_admin_audit,
    require_sensitive_confirmation,
)
from commercial_service import (
    approve_recharge_order,
    calculate_recharge_preview,
    clear_payment_channel_qrcode,
    cleanup_recharge_proofs,
    create_bonus_rule,
    create_recharge_option,
    delete_or_archive_bonus_rule,
    delete_or_archive_recharge_option,
    delete_payment_qrcode_by_url_if_safe,
    expire_recharge_order,
    get_recharge_order_or_404,
    payment_channel_payload,
    payment_qrcode_file_path,
    payment_qrcode_media_type,
    recharge_bonus_rule_payload,
    recharge_config_payload,
    recharge_option_payload,
    recharge_order_payload,
    save_payment_qrcode_upload,
    update_recharge_order_status,
    upsert_payment_channel,
    user_quota_transactions_payload,
)
from database import get_session
from datetime_utils import to_api_beijing_iso
from models import (
    AdminAuditLog,
    EndUser,
    RechargeBonusRule,
    RechargeOrder,
    RechargeOrderStatus,
    RechargePaymentChannel,
    UserQuotaAccount,
)


router = APIRouter(prefix="/api/v1/admin/commercial", tags=["Admin Commercial"])
public_router = APIRouter(prefix="/api/v1/commercial", tags=["Commercial Public"])
get_current_user = routes_admin.get_current_user


class PaymentChannelRequest(BaseModel):
    channel: str = PydanticField(..., pattern="^(wechat|alipay|bank|other)$")
    display_name: str = PydanticField(..., min_length=1, max_length=64)
    qr_code_url: Optional[str] = None
    account_name: Optional[str] = PydanticField(None, max_length=128)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class RechargeOptionRequest(BaseModel):
    amount: int | float | str
    credit_quota: int = PydanticField(..., gt=0)
    label: Optional[str] = PydanticField(None, max_length=64)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class BonusRuleRequest(BaseModel):
    threshold_amount: int | float | str
    bonus_quota: int = PydanticField(..., gt=0)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class OrderReviewRequest(BaseModel):
    remark: Optional[str] = None
    reject_reason: Optional[str] = None
    confirm_text: Optional[str] = None


class RechargeProofCleanupRequest(BaseModel):
    older_than_days: int = PydanticField(..., ge=1, le=3650)
    dry_run: bool = True
    confirm_text: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    routes_admin._require_admin(current_user)


def _record_sensitive_business_failure(
    session: Session,
    *,
    admin: dict,
    action: str,
    resource_type: str,
    request: Request,
    error: Exception,
    resource_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    before: Optional[dict] = None,
    metadata: Optional[dict] = None,
    status_code: int = 400,
) -> None:
    if isinstance(error, HTTPException):
        detail = error.detail
        status_code = error.status_code
    else:
        detail = str(error)
    error_message = detail if isinstance(detail, str) else str(detail)
    session.rollback()
    record_admin_audit(
        session,
        admin=admin,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=target_user_id,
        target_username=target_username,
        status="failed",
        request=request,
        before=before,
        metadata=metadata,
        error_message=error_message,
        summary=f"敏感操作失败：{action}",
    )
    if isinstance(error, HTTPException):
        raise error
    raise HTTPException(status_code=status_code, detail=error_message)


def _merchant_user_payload(user: EndUser, account: Optional[UserQuotaAccount]) -> dict:
    return {
        "id": user.id,
        "app_id": user.app_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "kami_issue_balance": account.kami_issue_balance if account else 0,
        "total_kami_issue_granted": account.total_kami_issue_granted if account else 0,
        "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
        "last_login": to_api_beijing_iso(user.last_login, naive="civil") if user.last_login else None,
    }


@public_router.get("/payment-qrcodes/{filename}", summary="Get payment QR code")
async def get_payment_qrcode(filename: str):
    try:
        path = payment_qrcode_file_path(filename)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payment QR code not found")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Payment QR code not found")
    return FileResponse(path, media_type=payment_qrcode_media_type(filename))


@router.get("/merchants", summary="List merchant/card issuer users")
async def list_merchants(
    keyword: Optional[str] = Query(None),
    status: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(EndUser).where(EndUser.app_id.is_(None))
    count_statement = select(EndUser).where(EndUser.app_id.is_(None))
    conditions = []
    if keyword:
        conditions.append(or_(EndUser.username.contains(keyword), EndUser.email.contains(keyword)))
    if status is not None:
        conditions.append(EndUser.status == status)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    merchants = session.exec(
        statement.order_by(EndUser.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = len(session.exec(count_statement).all())
    user_ids = [user.id for user in merchants if user.id is not None]
    accounts = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id.in_(user_ids))
    ).all() if user_ids else []
    account_map = {account.user_id: account for account in accounts}
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                _merchant_user_payload(user, account_map.get(user.id))
                for user in merchants
            ],
        },
    }


@router.get("/overview", summary="Commercial operations overview")
async def commercial_overview(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    orders = session.exec(select(RechargeOrder)).all()
    pending = [order for order in orders if order.status == RechargeOrderStatus.pending_review]
    approved = [order for order in orders if order.status == RechargeOrderStatus.approved]
    return {
        "success": True,
        "data": {
            "orders_total": len(orders),
            "orders_pending_review": len(pending),
            "orders_approved": len(approved),
            "approved_amount": sum(order.amount_cents for order in approved) // 100,
            "credited_issue_quota": sum(order.credit_quota for order in approved),
        },
    }


@router.get("/recharge-config", summary="Get recharge configuration")
async def get_recharge_config(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {"success": True, "data": recharge_config_payload(session, enabled_only=False)}


@router.get("/payment-channels", summary="List payment channels")
async def list_payment_channels_route(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {"success": True, "data": recharge_config_payload(session, enabled_only=False)["channels"]}


@router.post("/payment-channels", summary="Create or update payment channel")
async def save_payment_channel(
    payload: PaymentChannelRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="payment_channel",
        resource_id=payload.channel,
        request=request,
    )
    payload_data = payload.model_dump(exclude={"confirm_text"})
    try:
        row = upsert_payment_channel(session, **payload_data)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=payload.channel,
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="payment_channel",
        resource_id=payload.channel,
        request=request,
        after=payment_channel_payload(row),
        summary=f"保存收款渠道 {payload.channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_save",
        payload=payment_channel_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新充值收款渠道 {payload.channel}",
    )
    return {"success": True, "message": "payment channel saved", "data": payment_channel_payload(row)}


@router.post("/payment-channels/upload", summary="Create or update payment channel with QR upload")
async def save_payment_channel_with_upload(
    request: Request,
    channel: str = Form(..., pattern="^(wechat|alipay|bank|other)$"),
    display_name: str = Form(..., min_length=1, max_length=64),
    qr_code_url: Optional[str] = Form(None),
    account_name: Optional[str] = Form(None, max_length=128),
    enabled: bool = Form(True),
    sort_order: int = Form(0),
    remark: Optional[str] = Form(None),
    confirm_text: Optional[str] = Form(None),
    qr_code_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
    )
    existing = session.exec(
        select(RechargePaymentChannel).where(RechargePaymentChannel.channel == channel)
    ).first()
    old_qr_code_url = existing.qr_code_url if existing else None
    saved_qr_code_url = None
    try:
        if qr_code_file and qr_code_file.filename:
            saved_qr_code_url = await save_payment_qrcode_upload(qr_code_file, channel)
            qr_code_url = saved_qr_code_url
        elif existing and qr_code_url is None:
            qr_code_url = existing.qr_code_url
        row = upsert_payment_channel(
            session,
            channel=channel,
            display_name=display_name,
            qr_code_url=qr_code_url,
            account_name=account_name,
            enabled=enabled,
            sort_order=sort_order,
            remark=remark,
        )
        session.commit()
        session.refresh(row)
    except ValueError as error:
        if saved_qr_code_url:
            delete_payment_qrcode_by_url_if_safe(saved_qr_code_url)
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
        )
    except Exception as error:
        if saved_qr_code_url:
            delete_payment_qrcode_by_url_if_safe(saved_qr_code_url)
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
            status_code=500,
        )

    if saved_qr_code_url and old_qr_code_url and old_qr_code_url != saved_qr_code_url:
        delete_payment_qrcode_by_url_if_safe(old_qr_code_url)

    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
        after=payment_channel_payload(row),
        summary=f"保存收款渠道 {channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_save",
        payload=payment_channel_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新充值收款渠道 {channel}",
    )
    return {"success": True, "message": "payment channel saved", "data": payment_channel_payload(row)}


@router.delete("/payment-channels/{channel}/qrcode", summary="Delete payment channel QR code")
async def delete_payment_channel_qrcode(
    channel: str,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="delete_payment_qrcode",
        confirm_text=confirm_text,
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
    )
    try:
        row, deleted_file = clear_payment_channel_qrcode(session, channel)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="delete_payment_qrcode",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
            status_code=404,
        )
    session.commit()
    session.refresh(row)
    payload = {**payment_channel_payload(row), "deleted_file": deleted_file}
    record_admin_audit(
        session,
        admin=current_user,
        action="delete_payment_qrcode",
        resource_type="payment_channel_qrcode",
        resource_id=channel,
        request=request,
        after=payload,
        summary=f"删除收款二维码 {channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_qrcode_delete",
        payload=payload,
        message=f"管理员 {current_user.get('sub')} 删除充值收款渠道 {channel} 的二维码",
    )
    return {"success": True, "message": "payment QR code deleted", "data": payload}


@router.post("/recharge-options", summary="Create or update fixed recharge option")
async def save_recharge_option(
    payload: RechargeOptionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="recharge_option",
        request=request,
    )
    try:
        row = create_recharge_option(session, **payload.model_dump(exclude={"confirm_text"}))
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_option",
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_option",
        resource_id=row.id,
        request=request,
        after=recharge_option_payload(row),
        summary="保存固定充值档位",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_option_save",
        payload=recharge_option_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新固定充值额度",
    )
    return {"success": True, "message": "recharge option saved", "data": recharge_option_payload(row)}


@router.delete("/recharge-options/{option_id}", summary="Delete or archive fixed recharge option")
async def delete_recharge_option(
    option_id: int,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="recharge_option",
        resource_id=option_id,
        request=request,
    )
    try:
        row, archived = delete_or_archive_recharge_option(session, option_id)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_option",
            resource_id=str(option_id),
            request=request,
            error=error,
            status_code=404,
        )
    data = {"id": option_id, "deleted": not archived, "archived": archived}
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_option",
        resource_id=option_id,
        request=request,
        after=data,
        summary=f"删除或归档固定充值档位 {option_id}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_option_delete",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 删除或归档固定充值额度 {option_id}",
    )
    return {"success": True, "message": "recharge option archived" if archived else "recharge option deleted", "data": data}


@router.post("/recharge-bonus-rules", summary="Create custom amount bonus rule")
async def save_bonus_rule(
    payload: BonusRuleRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="recharge_bonus_rule",
        request=request,
    )
    try:
        row = create_bonus_rule(session, **payload.model_dump(exclude={"confirm_text"}))
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_bonus_rule",
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_bonus_rule",
        resource_id=row.id,
        request=request,
        after=recharge_bonus_rule_payload(row),
        summary="保存充值赠送规则",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_bonus_rule_save",
        payload=recharge_bonus_rule_payload(row),
        message=f"管理员 {current_user.get('sub')} 新增自定义充值赠送规则",
    )
    return {"success": True, "message": "bonus rule saved", "data": recharge_bonus_rule_payload(row)}


@router.delete("/recharge-bonus-rules/{rule_id}", summary="Delete or archive custom recharge bonus rule")
async def delete_bonus_rule(
    rule_id: int,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="recharge_bonus_rule",
        resource_id=rule_id,
        request=request,
    )
    try:
        row, archived = delete_or_archive_bonus_rule(session, rule_id)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_bonus_rule",
            resource_id=str(rule_id),
            request=request,
            error=error,
            status_code=404,
        )
    data = {"id": rule_id, "deleted": not archived, "archived": archived}
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_bonus_rule",
        resource_id=rule_id,
        request=request,
        after=data,
        summary=f"删除或归档充值赠送规则 {rule_id}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_bonus_rule_delete",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 删除或归档自定义充值赠送规则 {rule_id}",
    )
    return {"success": True, "message": "bonus rule archived" if archived else "bonus rule deleted", "data": data}


@router.post("/recharge-preview", summary="Preview recharge crediting")
async def preview_recharge_as_admin(
    amount: int | float | str,
    mode: str = "custom",
    option_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        data = calculate_recharge_preview(session, amount=amount, mode=mode, option_id=option_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data}


@router.get("/audit-logs", summary="List admin audit logs")
async def list_admin_audit_logs(
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(AdminAuditLog)
    count_statement = select(AdminAuditLog)
    conditions = []
    if action:
        conditions.append(AdminAuditLog.action == action)
    if status:
        conditions.append(AdminAuditLog.status == status)
    if keyword:
        like_conditions = [
            AdminAuditLog.admin_username.contains(keyword),
            AdminAuditLog.target_username.contains(keyword),
            AdminAuditLog.resource_id.contains(keyword),
            AdminAuditLog.summary.contains(keyword),
            AdminAuditLog.error_message.contains(keyword),
        ]
        conditions.append(or_(*like_conditions))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = len(session.exec(count_statement).all())
    logs = session.exec(
        statement.order_by(AdminAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {
            "items": [audit_log_payload(log) for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "confirmation_texts": CONFIRM_TEXT_BY_SCOPE,
        },
    }


@router.get("/recharge-orders", summary="List recharge orders")
async def list_recharge_orders(
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(RechargeOrder)
    count_statement = select(RechargeOrder)
    conditions = []
    if status:
        try:
            conditions.append(RechargeOrder.status == RechargeOrderStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if user_id is not None:
        conditions.append(RechargeOrder.user_id == user_id)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = len(session.exec(count_statement).all())
    orders = session.exec(
        statement.order_by(RechargeOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [recharge_order_payload(order, include_user=True) for order in orders],
        },
    }


@router.get("/recharge-orders/{order_no}", summary="Get recharge order detail")
async def get_recharge_order(
    order_no: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    return {"success": True, "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-proofs/cleanup", summary="Clean old terminal recharge proof files")
async def cleanup_old_recharge_proofs(
    payload: RechargeProofCleanupRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    if not payload.dry_run:
        require_sensitive_confirmation(
            session,
            admin=current_user,
            action="cleanup_proof_files",
            confirm_text=payload.confirm_text,
            resource_type="recharge_proof",
            request=request,
            metadata={"older_than_days": payload.older_than_days},
        )
    try:
        data = cleanup_recharge_proofs(
            session,
            older_than_days=payload.older_than_days,
            dry_run=payload.dry_run,
        )
    except ValueError as error:
        if not payload.dry_run:
            _record_sensitive_business_failure(
                session,
                admin=current_user,
                action="cleanup_proof_files",
                resource_type="recharge_proof",
                request=request,
                error=error,
                metadata={"older_than_days": payload.older_than_days},
            )
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    if not payload.dry_run:
        record_admin_audit(
            session,
            admin=current_user,
            action="cleanup_proof_files",
            resource_type="recharge_proof",
            request=request,
            after=data,
            summary=f"清理超过 {payload.older_than_days} 天的充值凭证文件",
        )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_proof_cleanup",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 清理充值凭证 dry_run={payload.dry_run}",
    )
    return {"success": True, "message": "proof cleanup checked" if payload.dry_run else "proof cleanup completed", "data": data}


@router.get("/recharge-orders/{order_no}/proof", summary="Get recharge proof image")
async def get_recharge_order_proof(
    order_no: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    if not order.proof_file_path or not Path(order.proof_file_path).exists():
        raise HTTPException(status_code=404, detail="Proof image not found")
    return FileResponse(order.proof_file_path, media_type=order.proof_content_type or "application/octet-stream")


@router.post("/recharge-orders/{order_no}/approve", summary="Approve recharge order")
async def approve_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="approve_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order, transaction = approve_recharge_order(
            session,
            order=order,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="approve_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    after = {**recharge_order_payload(order, include_user=True), "transaction": transaction}
    record_admin_audit(
        session,
        admin=current_user,
        action="approve_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=after,
        summary=f"审核通过充值订单 {order_no}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_order_approve",
        payload={"order_no": order_no, "transaction": transaction},
        message=f"管理员 {current_user.get('sub')} 审核通过充值订单 {order_no}",
    )
    return {
        "success": True,
        "message": "order approved",
        "data": {**recharge_order_payload(order, include_user=True), "transaction": transaction},
    }


@router.post("/recharge-orders/{order_no}/reject", summary="Reject recharge order")
async def reject_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="reject_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = update_recharge_order_status(
            session,
            order=order,
            status=RechargeOrderStatus.rejected,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
            reject_reason=payload.reject_reason,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="reject_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="reject_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"驳回充值订单 {order_no}",
    )
    return {"success": True, "message": "order rejected", "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-orders/{order_no}/expire", summary="Expire recharge order")
async def expire_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="expire_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = expire_recharge_order(
            session,
            order=order,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="expire_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="expire_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"关闭充值订单 {order_no}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_order_expire",
        payload={"order_no": order_no, "remark": payload.remark},
        message=f"管理员 {current_user.get('sub')} 标记充值订单 {order_no} 已过期",
    )
    return {"success": True, "message": "order expired", "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-orders/{order_no}/abnormal", summary="Mark recharge order abnormal")
async def mark_order_abnormal(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="mark_recharge_abnormal",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = update_recharge_order_status(
            session,
            order=order,
            status=RechargeOrderStatus.abnormal,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="mark_recharge_abnormal",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="mark_recharge_abnormal",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"标记充值订单异常 {order_no}",
    )
    return {"success": True, "message": "order marked abnormal", "data": recharge_order_payload(order, include_user=True)}


@router.get("/quota-transactions", summary="List issue quota transactions")
async def list_quota_transactions(
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {
        "success": True,
        "data": user_quota_transactions_payload(
            session,
            user_id=user_id,
            page=page,
            page_size=page_size,
        ),
    }
