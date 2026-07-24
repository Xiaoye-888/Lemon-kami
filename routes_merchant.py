from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

import routes_user
from commercial_service import (
    calculate_recharge_preview,
    create_recharge_order,
    get_recharge_order_or_404,
    merchant_quota_summary,
    recharge_config_payload,
    recharge_order_payload,
    user_quota_transactions_payload,
)
from database import get_session
from datetime_utils import to_api_beijing_iso
from models import (
    App,
    EndUser,
    Kami,
    KamiBatch,
    KamiSpec,
    RechargeOrder,
    UserAppAuthorization,
)
from user_quota_service import (
    create_user_app,
    get_user_visible_apps,
    issue_user_kamis,
    list_user_issued_kamis,
    user_can_manage_app,
)


router = APIRouter(prefix="/api/v1/merchant", tags=["Merchant Console"])


class RechargePreviewRequest(BaseModel):
    amount: int | float | str
    mode: str = PydanticField("custom", pattern="^(fixed|custom)$")
    option_id: Optional[int] = None


class RechargeOrderCreateRequest(RechargePreviewRequest):
    channel: str = PydanticField(..., pattern="^(wechat|alipay|bank|other)$")
    remark: Optional[str] = None
    proof_image_data_url: Optional[str] = None


class MerchantAppCreateRequest(BaseModel):
    name: str = PydanticField(..., min_length=1, max_length=255)


class MerchantKamiIssueRequest(BaseModel):
    spec_id: Optional[int] = None
    kami_type: Optional[str] = PydanticField(None, max_length=32)
    count: int = PydanticField(..., gt=0, le=1000)
    batch_no: Optional[str] = PydanticField(None, max_length=64)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: int = PydanticField(16, ge=4, le=64)
    charset: str = PydanticField("upper_numeric", max_length=32)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)


def _app_is_owned_by_user(app: App, user: EndUser) -> bool:
    return app.owner_user_id == user.id or (bool(app.created_by) and app.created_by == user.username)


def _app_authorized_to_user(session: Session, app_id: str, user: EndUser) -> bool:
    return session.exec(
        select(UserAppAuthorization).where(
            UserAppAuthorization.app_id == app_id,
            UserAppAuthorization.user_id == user.id,
        )
    ).first() is not None


def _merchant_app_payload(app: App, user: EndUser) -> dict:
    is_owned = _app_is_owned_by_user(app, user)
    payload = {
        "id": app.id,
        "app_id": app.app_id,
        "name": app.name,
        "created_by": app.created_by,
        "owner_user_id": app.owner_user_id,
        "status": app.status,
        "is_owned": is_owned,
        "source": "self_owned" if is_owned else "admin_authorized",
        "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
    }
    if is_owned:
        payload.update(
            {
                "app_secret": app.app_secret,
                "rsa_public_key": app.rsa_public_key,
            }
        )
    return payload


def _spec_payload(spec: KamiSpec) -> dict:
    return {
        "id": spec.id,
        "app_id": spec.app_id,
        "spec_key": spec.spec_key,
        "spec_name": spec.spec_name,
        "spec_group": spec.spec_group.value if hasattr(spec.spec_group, "value") else spec.spec_group,
        "kami_type": spec.kami_type.value if hasattr(spec.kami_type, "value") else spec.kami_type,
        "points_amount": spec.points_amount,
        "points_valid_days": spec.points_valid_days,
        "time_value": spec.time_value,
        "time_unit": spec.time_unit,
        "times_total": spec.times_total,
        "machine_bind_mode": spec.machine_bind_mode.value if hasattr(spec.machine_bind_mode, "value") else spec.machine_bind_mode,
        "max_bind_devices": spec.max_bind_devices,
        "authorization_owner": spec.authorization_owner.value if hasattr(spec.authorization_owner, "value") else spec.authorization_owner,
        "user_bind_mode": spec.user_bind_mode.value if hasattr(spec.user_bind_mode, "value") else spec.user_bind_mode,
        "status": spec.status,
        "sort_order": spec.sort_order,
    }


async def get_current_merchant(
    current_user: EndUser = Depends(routes_user.get_current_end_user),
) -> EndUser:
    if current_user.app_id is not None:
        raise HTTPException(status_code=403, detail="application users cannot access merchant console")
    return current_user


@router.get("/me", summary="Get current merchant profile")
async def get_merchant_me(
    current_user: EndUser = Depends(get_current_merchant),
):
    return {
        "success": True,
        "data": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "phone": current_user.phone,
            "role": "merchant",
            "status": current_user.status,
            "created_at": to_api_beijing_iso(current_user.created_at, naive="civil"),
            "last_login": to_api_beijing_iso(current_user.last_login, naive="civil")
            if current_user.last_login
            else None,
        },
    }


@router.get("/quotas", summary="Get merchant quota summary")
async def get_merchant_quotas(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    data = merchant_quota_summary(session, current_user)
    session.commit()
    return {"success": True, "data": data}


@router.get("/quota-transactions", summary="List merchant quota transactions")
async def list_merchant_quota_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    return {
        "success": True,
        "data": user_quota_transactions_payload(
            session,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        ),
    }


@router.get("/recharge/config", summary="Get merchant recharge config")
async def get_merchant_recharge_config(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    return {"success": True, "data": recharge_config_payload(session, enabled_only=True)}


@router.post("/recharge/preview", summary="Preview merchant recharge")
async def preview_merchant_recharge(
    payload: RechargePreviewRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        data = calculate_recharge_preview(
            session,
            amount=payload.amount,
            mode=payload.mode,
            option_id=payload.option_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data}


@router.post("/recharge/orders", summary="Create merchant recharge order")
async def create_merchant_recharge_order(
    payload: RechargeOrderCreateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        order = create_recharge_order(
            session,
            user=current_user,
            amount=payload.amount,
            mode=payload.mode,
            option_id=payload.option_id,
            channel=payload.channel,
            remark=payload.remark,
            proof_image_data_url=payload.proof_image_data_url,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(order)
    return {"success": True, "message": "recharge order submitted", "data": recharge_order_payload(order)}


@router.get("/recharge/orders", summary="List merchant recharge orders")
async def list_merchant_recharge_orders(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    statement = select(RechargeOrder).where(RechargeOrder.user_id == current_user.id)
    count_statement = select(RechargeOrder).where(RechargeOrder.user_id == current_user.id)
    if status:
        statement = statement.where(RechargeOrder.status == status)
        count_statement = count_statement.where(RechargeOrder.status == status)
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
            "items": [recharge_order_payload(order) for order in orders],
        },
    }


@router.get("/recharge/orders/{order_no}", summary="Get merchant recharge order detail")
async def get_merchant_recharge_order(
    order_no: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    order = get_recharge_order_or_404(session, order_no)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No permission to view this order")
    return {"success": True, "data": recharge_order_payload(order)}


@router.get("/recharge/orders/{order_no}/proof", summary="Get merchant recharge proof")
async def get_merchant_recharge_proof(
    order_no: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    order = get_recharge_order_or_404(session, order_no)
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No permission to view this proof")
    if not order.proof_file_path or not Path(order.proof_file_path).exists():
        raise HTTPException(status_code=404, detail="Proof image not found")
    return FileResponse(order.proof_file_path, media_type=order.proof_content_type or "application/octet-stream")


@router.get("/apps", summary="List merchant apps")
async def list_merchant_apps(
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    apps = get_user_visible_apps(session, current_user)
    return {"success": True, "data": [_merchant_app_payload(app, current_user) for app in apps]}


@router.post("/apps", summary="Create merchant self-owned app")
async def create_merchant_app(
    payload: MerchantAppCreateRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        app, quota = create_user_app(session, current_user, payload.name.strip())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(app)
    return {
        "success": True,
        "message": "app created",
        "data": {**_merchant_app_payload(app, current_user), "quota": quota},
    }


@router.get("/apps/{app_id}/specs", summary="List specs for a merchant app")
async def list_merchant_app_specs(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    specs = session.exec(
        select(KamiSpec)
        .where(KamiSpec.app_id == app_id, KamiSpec.status == 1)
        .order_by(KamiSpec.sort_order, KamiSpec.id)
    ).all()
    return {"success": True, "data": [_spec_payload(spec) for spec in specs]}


@router.post("/apps/{app_id}/kamis/batch", summary="Issue merchant kamis")
async def issue_merchant_kamis(
    app_id: str,
    payload: MerchantKamiIssueRequest,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")

    is_owned = _app_is_owned_by_user(app, current_user)
    is_authorized = _app_authorized_to_user(session, app_id, current_user)
    spec = None
    if not is_owned and is_authorized:
        if not payload.spec_id:
            raise HTTPException(status_code=400, detail="spec_id is required for authorized apps")
        spec = session.get(KamiSpec, payload.spec_id)
        if not spec or spec.app_id != app_id or spec.status != 1:
            raise HTTPException(status_code=400, detail="spec_id is not available")
    elif payload.spec_id:
        spec = session.get(KamiSpec, payload.spec_id)
        if not spec or spec.app_id != app_id or spec.status != 1:
            raise HTTPException(status_code=400, detail="spec_id is not available")

    kami_type = payload.kami_type
    points_amount = payload.points_amount
    points_valid_days = payload.points_valid_days
    times_total = payload.times_total
    time_value = payload.time_value
    time_unit = payload.time_unit
    machine_bind_mode = "one_card_one_device"
    max_bind_devices = 1
    authorization_owner = "device"
    user_bind_mode = "none"

    if spec:
        kami_type = spec.kami_type.value if hasattr(spec.kami_type, "value") else spec.kami_type
        points_amount = spec.points_amount
        points_valid_days = spec.points_valid_days
        times_total = spec.times_total
        time_value = spec.time_value
        time_unit = spec.time_unit
        machine_bind_mode = spec.machine_bind_mode
        max_bind_devices = spec.max_bind_devices
        authorization_owner = spec.authorization_owner
        user_bind_mode = spec.user_bind_mode

    if not kami_type:
        raise HTTPException(status_code=400, detail="kami_type is required")

    try:
        result = issue_user_kamis(
            session,
            current_user,
            app,
            spec_id=spec.id if spec else None,
            kami_type=kami_type,
            count=payload.count,
            batch_no=payload.batch_no,
            code_prefix=payload.code_prefix,
            code_length=payload.code_length,
            charset=payload.charset,
            points_amount=points_amount,
            points_valid_days=points_valid_days,
            times_total=times_total,
            time_value=time_value,
            time_unit=time_unit,
            machine_bind_mode=machine_bind_mode,
            max_bind_devices=max_bind_devices,
            authorization_owner=authorization_owner,
            user_bind_mode=user_bind_mode,
            unit_cost=1,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    return {"success": True, "message": "issue success", "data": result}


@router.get("/apps/{app_id}/kamis", summary="List merchant issued kamis")
async def list_merchant_kamis(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    kamis = list_user_issued_kamis(session, current_user, app_id)
    return {
        "success": True,
        "data": [
            {
                "id": kami.id,
                "app_id": kami.app_id,
                "spec_id": kami.spec_id,
                "kami_code": kami.kami_code,
                "kami_type": kami.kami_type.value if hasattr(kami.kami_type, "value") else kami.kami_type,
                "status": kami.status.value if hasattr(kami.status, "value") else kami.status,
                "batch_no": kami.batch_no,
                "points_amount": kami.points_amount,
                "points_valid_days": kami.points_valid_days,
                "times_total": kami.times_total,
                "times_remaining": kami.times_remaining,
                "time_value": kami.time_value,
                "time_unit": kami.time_unit,
                "created_by_user_id": kami.created_by_user_id,
                "created_at": to_api_beijing_iso(kami.created_at, naive="civil") if kami.created_at else None,
            }
            for kami in kamis
        ],
    }


@router.get("/apps/{app_id}/batches", summary="List merchant issued batches")
async def list_merchant_batches(
    app_id: str,
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    batches = session.exec(
        select(KamiBatch).where(KamiBatch.app_id == app_id).order_by(KamiBatch.id.desc())
    ).all()
    result = []
    for batch in batches:
        count = len(
            session.exec(
                select(Kami).where(
                    Kami.app_id == app_id,
                    Kami.batch_no == batch.batch_no,
                    Kami.created_by_user_id == current_user.id,
                )
            ).all()
        )
        if count <= 0:
            continue
        result.append(
            {
                "id": batch.id,
                "app_id": batch.app_id,
                "spec_id": batch.spec_id,
                "batch_no": batch.batch_no,
                "kami_type": batch.kami_type.value if hasattr(batch.kami_type, "value") else batch.kami_type,
                "count": count,
                "created_at": to_api_beijing_iso(batch.created_at, naive="civil") if batch.created_at else None,
            }
        )
    return {"success": True, "data": result}
