from pathlib import Path
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_user
from commercial_service import (
    calculate_recharge_preview,
    create_recharge_order,
    create_recharge_order_from_upload,
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
    Device,
    EndUser,
    Kami,
    KamiBatch,
    KamiDeviceBinding,
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


def _compact_end_user_payload(user: Optional[EndUser]) -> Optional[dict]:
    if not user:
        return None
    return {"id": user.id, "username": user.username, "app_id": user.app_id}


def _device_matches_binding(device: object, binding: KamiDeviceBinding) -> bool:
    return (
        getattr(device, "app_id", None) == binding.app_id
        and (
            getattr(device, "uuid", None) == binding.device_uuid
            or getattr(device, "fingerprint", None) == binding.fingerprint
        )
    )


def _merchant_device_payload(
    *,
    device: object,
    related_kami_codes: list[str],
    kamis_by_code: dict[str, Kami],
    users_by_id: dict[int, EndUser],
    apps_by_id: dict[str, App],
    current_user: EndUser,
) -> dict:
    related_kami_codes = list(dict.fromkeys([code for code in related_kami_codes if code]))
    related_kamis = [kamis_by_code[code] for code in related_kami_codes if code in kamis_by_code]
    kami = related_kamis[0] if related_kamis else None
    app = apps_by_id.get(getattr(device, "app_id", None))
    redeemed_user = users_by_id.get(kami.redeemed_by_user_id) if kami and kami.redeemed_by_user_id else None
    issuing_user = users_by_id.get(kami.created_by_user_id) if kami and kami.created_by_user_id else None
    owning_user = users_by_id.get(app.owner_user_id) if app and app.owner_user_id else None
    if not owning_user and app and _app_is_owned_by_user(app, current_user):
        owning_user = current_user

    if redeemed_user:
        user_type = "usage_user" if redeemed_user.app_id else "merchant"
    elif issuing_user:
        user_type = "merchant"
    else:
        user_type = "admin"

    risk_level = getattr(device, "risk_level", 0)
    risk_text = {0: "normal", 1: "warning", 2: "blocked"}.get(risk_level, "unknown")
    return {
        "id": getattr(device, "id", None),
        "app_id": getattr(device, "app_id", None),
        "app_name": app.name if app else None,
        "uuid": getattr(device, "uuid", None),
        "fingerprint": getattr(device, "fingerprint", None),
        "last_ip": getattr(device, "last_ip", None),
        "ip_count": 1 if getattr(device, "last_ip", None) else 0,
        "kami_code": related_kami_codes[0] if related_kami_codes else None,
        "kami_codes": related_kami_codes,
        "kami_count": len(related_kami_codes),
        "username": redeemed_user.username if redeemed_user else None,
        "user_id": redeemed_user.id if redeemed_user else None,
        "user_type": user_type,
        "app_source": "merchant_self_owned" if app and _app_is_owned_by_user(app, current_user) else "admin_authorized",
        "card_source": "merchant_issued" if issuing_user and issuing_user.id == current_user.id else "admin_issued" if kami else None,
        "issuing_user": _compact_end_user_payload(issuing_user),
        "owning_user": _compact_end_user_payload(owning_user),
        "risk_level": risk_level,
        "risk_level_text": risk_text,
        "last_verify_at": to_api_beijing_iso(kami.last_verify_at, naive="civil") if kami and kami.last_verify_at else None,
    }


def _merchant_device_payload_matches_keyword(payload: dict, keyword: Optional[str]) -> bool:
    if not keyword:
        return True
    keyword_lower = keyword.lower()
    values = [
        payload.get("app_id"),
        payload.get("app_name"),
        payload.get("uuid"),
        payload.get("fingerprint"),
        payload.get("last_ip"),
        payload.get("kami_code"),
        payload.get("username"),
        payload.get("user_id"),
        payload.get("user_type"),
        payload.get("app_source"),
        payload.get("card_source"),
    ]
    for user_key in ("issuing_user", "owning_user"):
        user_payload = payload.get(user_key) or {}
        values.extend([user_payload.get("id"), user_payload.get("username")])
    values.extend(payload.get("kami_codes") or [])
    return any(keyword_lower in str(value).lower() for value in values if value is not None)


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


@router.get("/devices", summary="List merchant visible devices")
async def list_merchant_devices(
    app_id: Optional[str] = Query(None),
    risk_level: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    apps = get_user_visible_apps(session, current_user)
    apps_by_id = {app.app_id: app for app in apps}
    if not apps_by_id:
        return {"success": True, "data": {"total": 0, "page": page, "page_size": page_size, "items": []}}

    selected_app_id = app_id.strip() if app_id else None
    if selected_app_id and selected_app_id not in apps_by_id:
        raise HTTPException(status_code=403, detail="No permission to view this app")

    allowed_app_ids = {selected_app_id} if selected_app_id else set(apps_by_id.keys())
    owned_app_ids = {
        app.app_id
        for app in apps
        if app.app_id in allowed_app_ids and _app_is_owned_by_user(app, current_user)
    }

    kami_visibility_conditions = [Kami.created_by_user_id == current_user.id]
    if owned_app_ids:
        kami_visibility_conditions.append(Kami.app_id.in_(list(owned_app_ids)))
    kami_statement = select(Kami).where(
        Kami.app_id.in_(list(allowed_app_ids)),
        or_(*kami_visibility_conditions),
    )
    kamis = session.exec(kami_statement).all()
    kamis_by_code = {kami.kami_code: kami for kami in kamis}
    visible_kami_codes = set(kamis_by_code.keys())

    binding_conditions = []
    if visible_kami_codes:
        binding_conditions.append(KamiDeviceBinding.kami_code.in_(list(visible_kami_codes)))
    if owned_app_ids:
        binding_conditions.append(KamiDeviceBinding.app_id.in_(list(owned_app_ids)))
    bindings = []
    if binding_conditions:
        bindings = session.exec(
            select(KamiDeviceBinding).where(
                KamiDeviceBinding.app_id.in_(list(allowed_app_ids)),
                or_(*binding_conditions),
            )
        ).all()
        missing_codes = {binding.kami_code for binding in bindings if binding.kami_code not in kamis_by_code}
        if missing_codes:
            extra_kamis = session.exec(
                select(Kami).where(
                    Kami.app_id.in_(list(allowed_app_ids)),
                    Kami.kami_code.in_(list(missing_codes)),
                )
            ).all()
            kamis_by_code.update({kami.kami_code: kami for kami in extra_kamis})

    device_statement = select(Device).where(Device.app_id.in_(list(allowed_app_ids)))
    if risk_level is not None:
        device_statement = device_statement.where(Device.risk_level == risk_level)
    physical_devices = session.exec(device_statement).all()

    related_codes_by_device_id = {}
    primary_binding_by_device_id = {}
    visible_devices = []
    for device in physical_devices:
        matching_bindings = [binding for binding in bindings if _device_matches_binding(device, binding)]
        if device.app_id not in owned_app_ids and not matching_bindings:
            continue
        visible_devices.append(device)
        related_codes_by_device_id[device.id] = [binding.kami_code for binding in matching_bindings]
        if matching_bindings:
            primary_binding_by_device_id[device.id] = matching_bindings[0]

    seen_device_keys = {
        (device.app_id, device.uuid, device.fingerprint)
        for device in visible_devices
    }
    for binding in bindings:
        matched_physical_device = any(_device_matches_binding(device, binding) for device in visible_devices)
        if matched_physical_device:
            continue
        key = (binding.app_id, binding.device_uuid, binding.fingerprint)
        if key in seen_device_keys:
            continue
        virtual_device = SimpleNamespace(
            id=f"binding:{binding.id}",
            app_id=binding.app_id,
            uuid=binding.device_uuid,
            fingerprint=binding.fingerprint,
            last_ip=binding.bind_ip,
            risk_level=0,
        )
        visible_devices.append(virtual_device)
        related_codes_by_device_id[virtual_device.id] = [binding.kami_code]
        primary_binding_by_device_id[virtual_device.id] = binding
        seen_device_keys.add(key)

    user_ids = {current_user.id}
    for app in apps_by_id.values():
        if app.owner_user_id:
            user_ids.add(app.owner_user_id)
    for kami in kamis_by_code.values():
        if kami.redeemed_by_user_id:
            user_ids.add(kami.redeemed_by_user_id)
        if kami.created_by_user_id:
            user_ids.add(kami.created_by_user_id)
    users = session.exec(select(EndUser).where(EndUser.id.in_(list(user_ids)))).all() if user_ids else []
    users_by_id = {user.id: user for user in users}

    keyword_value = keyword.strip() if keyword else None
    payloads = [
        _merchant_device_payload(
            device=device,
            related_kami_codes=related_codes_by_device_id.get(device.id, []),
            kamis_by_code=kamis_by_code,
            users_by_id=users_by_id,
            apps_by_id=apps_by_id,
            current_user=current_user,
        )
        for device in visible_devices
    ]
    payloads = [payload for payload in payloads if _merchant_device_payload_matches_keyword(payload, keyword_value)]
    payloads.sort(key=lambda item: str(item.get("id") or ""), reverse=True)

    total = len(payloads)
    offset = (page - 1) * page_size
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": payloads[offset:offset + page_size],
        },
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


@router.post("/recharge/orders/upload", summary="Create merchant recharge order with proof upload")
async def create_merchant_recharge_order_with_upload(
    amount: str = Form(...),
    mode: str = Form("custom", pattern="^(fixed|custom)$"),
    option_id: Optional[int] = Form(None),
    channel: str = Form(..., pattern="^(wechat|alipay|bank|other)$"),
    remark: Optional[str] = Form(None),
    proof_file: UploadFile = File(...),
    current_user: EndUser = Depends(get_current_merchant),
    session: Session = Depends(get_session),
):
    try:
        order = await create_recharge_order_from_upload(
            session,
            user=current_user,
            amount=amount,
            mode=mode,
            option_id=option_id,
            channel=channel,
            remark=remark,
            proof_file=proof_file,
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
