from typing import Optional

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_admin
from commercial_service import (
    approve_recharge_order,
    calculate_recharge_preview,
    create_bonus_rule,
    create_recharge_option,
    get_recharge_order_or_404,
    payment_channel_payload,
    recharge_bonus_rule_payload,
    recharge_config_payload,
    recharge_option_payload,
    recharge_order_payload,
    update_recharge_order_status,
    upsert_payment_channel,
    user_quota_transactions_payload,
)
from database import get_session
from datetime_utils import to_api_beijing_iso
from models import (
    EndUser,
    RechargeBonusRule,
    RechargeOrder,
    RechargeOrderStatus,
    RechargePaymentChannel,
    UserQuotaAccount,
)


router = APIRouter(prefix="/api/v1/admin/commercial", tags=["Admin Commercial"])
get_current_user = routes_admin.get_current_user


class PaymentChannelRequest(BaseModel):
    channel: str = PydanticField(..., pattern="^(wechat|alipay|bank|other)$")
    display_name: str = PydanticField(..., min_length=1, max_length=64)
    qr_code_url: Optional[str] = None
    account_name: Optional[str] = PydanticField(None, max_length=128)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None


class RechargeOptionRequest(BaseModel):
    amount: int | float | str
    credit_quota: int = PydanticField(..., gt=0)
    label: Optional[str] = PydanticField(None, max_length=64)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None


class BonusRuleRequest(BaseModel):
    threshold_amount: int | float | str
    bonus_quota: int = PydanticField(..., gt=0)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None


class OrderReviewRequest(BaseModel):
    remark: Optional[str] = None
    reject_reason: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    routes_admin._require_admin(current_user)


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
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    row = upsert_payment_channel(session, **payload.model_dump())
    session.commit()
    session.refresh(row)
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_save",
        payload=payment_channel_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新充值收款渠道 {payload.channel}",
    )
    return {"success": True, "message": "payment channel saved", "data": payment_channel_payload(row)}


@router.post("/recharge-options", summary="Create or update fixed recharge option")
async def save_recharge_option(
    payload: RechargeOptionRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        row = create_recharge_option(session, **payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(row)
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_option_save",
        payload=recharge_option_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新固定充值额度",
    )
    return {"success": True, "message": "recharge option saved", "data": recharge_option_payload(row)}


@router.post("/recharge-bonus-rules", summary="Create custom amount bonus rule")
async def save_bonus_rule(
    payload: BonusRuleRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        row = create_bonus_rule(session, **payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(row)
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_bonus_rule_save",
        payload=recharge_bonus_rule_payload(row),
        message=f"管理员 {current_user.get('sub')} 新增自定义充值赠送规则",
    )
    return {"success": True, "message": "bonus rule saved", "data": recharge_bonus_rule_payload(row)}


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
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    try:
        order, transaction = approve_recharge_order(
            session,
            order=order,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
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
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
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
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    return {"success": True, "message": "order rejected", "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-orders/{order_no}/abnormal", summary="Mark recharge order abnormal")
async def mark_order_abnormal(
    order_no: str,
    payload: OrderReviewRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    try:
        order = update_recharge_order_status(
            session,
            order=order,
            status=RechargeOrderStatus.abnormal,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
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
