import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from jose import JWTError, jwt
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from auth_utils import hash_password, verify_password
from config import settings
from database import get_session
from datetime_utils import to_api_beijing_iso
from interface_service import require_app_interface_enabled
from models import (
    App,
    AuthorizationAccount,
    AuthorizationBenefitType,
    AuthorizationLot,
    AuthorizationOwnerType,
    AuthorizationTransaction,
    Device,
    EndUser,
    EventLog,
    Kami,
    get_now,
)
from user_quota_service import (
    create_user_app,
    get_or_create_user_quota_account,
    get_user_visible_apps,
    issue_user_kamis,
    list_user_issued_kamis,
    user_can_manage_app,
    user_quota_summary,
)
from point_service import (
    PointServiceError,
    consume_points,
    get_or_create_account,
    get_points_balance_summary,
    redeem_points_kami,
)


router = APIRouter(prefix="/api/v1/user", tags=["End User Points"])


class RegisterRequest(BaseModel):
    app_id: Optional[str] = PydanticField(None, max_length=64)
    username: str = PydanticField(min_length=3, max_length=64)
    password: str = PydanticField(min_length=6, max_length=128)
    email: Optional[str] = None
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RedeemRequest(BaseModel):
    kami_code: str


class ConsumeRequest(BaseModel):
    app_id: Optional[str] = PydanticField(None, max_length=64)
    amount: int = PydanticField(gt=0)
    biz_id: str = PydanticField(min_length=1, max_length=128)
    remark: Optional[str] = None
    metadata: Optional[dict] = None
    uuid: Optional[str] = None
    device_uuid: Optional[str] = None
    fingerprint: Optional[str] = None


class UserAppCreateRequest(BaseModel):
    name: str = PydanticField(min_length=1, max_length=255)


class UserKamiIssueRequest(BaseModel):
    kami_type: str = PydanticField(min_length=1, max_length=32)
    count: int = PydanticField(gt=0, le=1000)
    batch_no: Optional[str] = PydanticField(None, max_length=64)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: int = PydanticField(16, ge=4, le=64)
    charset: str = PydanticField("upper_numeric", max_length=32)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)


def create_user_access_token(user: EndUser) -> str:
    expire = get_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user.username,
        "uid": user.id,
        "role": "end_user",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_end_user(
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> EndUser:
    raw_token = token
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization.split(" ", 1)[1].strip()
    if not raw_token:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("role") != "end_user":
        raise HTTPException(status_code=403, detail="Invalid user role")

    user_id = payload.get("uid")
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.status != 1:
        raise HTTPException(status_code=403, detail="User is disabled")
    return user


def _user_data(user: EndUser) -> dict:
    return {
        "id": user.id,
        "app_id": user.app_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
        "last_login": to_api_beijing_iso(user.last_login, naive="civil") if user.last_login else None,
    }


def _handle_point_error(error: PointServiceError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


def _int_config(config: dict, key: str, default: Optional[int] = None) -> Optional[int]:
    value = config.get(key)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _client_ip_from_request(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else ""


def _point_consume_device_identity(payload: ConsumeRequest) -> tuple[Optional[str], Optional[str]]:
    metadata = payload.metadata if isinstance(payload.metadata, dict) else {}
    uuid = (
        payload.uuid
        or payload.device_uuid
        or metadata.get("uuid")
        or metadata.get("device_uuid")
    )
    fingerprint = payload.fingerprint or metadata.get("fingerprint")
    uuid = str(uuid).strip() if uuid else None
    fingerprint = str(fingerprint).strip() if fingerprint else None
    return uuid, fingerprint


def _record_point_consume_device(
    session: Session,
    app_id: str,
    user: EndUser,
    payload: ConsumeRequest,
    request: Request,
) -> None:
    uuid, fingerprint = _point_consume_device_identity(payload)
    if not fingerprint:
        return

    device_uuid = uuid or fingerprint
    client_ip = _client_ip_from_request(request)
    device = session.exec(
        select(Device).where(
            Device.app_id == app_id,
            Device.fingerprint == fingerprint,
        )
    ).first()
    if device:
        device.uuid = device_uuid
        device.last_ip = client_ip
    else:
        device = Device(
            app_id=app_id,
            uuid=device_uuid,
            fingerprint=fingerprint,
            last_ip=client_ip,
            risk_level=0,
        )
    session.add(device)
    session.add(
        EventLog(
            app_id=app_id,
            kami_code=None,
            event_type="points_consume",
            ip_address=client_ip,
            device_uuid=device_uuid,
            user_agent=request.headers.get("user-agent", ""),
            status=1,
            message="points consume",
            payload=json.dumps(
                {
                    "user_id": user.id,
                    "username": user.username,
                    "biz_id": payload.biz_id,
                    "amount": payload.amount,
                    "fingerprint": fingerprint,
                },
                ensure_ascii=False,
            ),
        )
    )
    session.commit()


@router.post("/register", summary="End-user register")
async def register_user(payload: RegisterRequest, session: Session = Depends(get_session)):
    if payload.app_id:
        app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        if app.status != 1:
            raise HTTPException(status_code=403, detail="App is disabled")
        config = require_app_interface_enabled(session, payload.app_id, "user.register")
        if config.get("allow_register") is False:
            raise HTTPException(
                status_code=403,
                detail={"code": "REGISTER_DISABLED", "message": "当前应用不允许用户注册"},
            )
        min_length = _int_config(config, "password_min_length")
        if min_length and len(payload.password) < min_length:
            raise HTTPException(
                status_code=400,
                detail={"code": "PASSWORD_TOO_SHORT", "message": f"密码长度不能少于 {min_length} 位"},
            )

    existing = session.exec(
        select(EndUser).where(EndUser.username == payload.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = EndUser(
        app_id=payload.app_id,
        username=payload.username,
        password_hash=hash_password(payload.password),
        email=payload.email,
        phone=payload.phone,
        status=1,
        last_login=get_now().replace(tzinfo=None),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    get_or_create_account(session, user.id)
    session.commit()

    token = create_user_access_token(user)
    return {
        "success": True,
        "message": "register success",
        "data": {"token": token, "user": _user_data(user)},
    }


@router.post("/login", summary="End-user login")
async def login_user(payload: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(
        select(EndUser).where(EndUser.username == payload.username)
    ).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if user.status != 1:
        raise HTTPException(status_code=403, detail="User is disabled")
    require_app_interface_enabled(session, user.app_id, "user.login")

    user.last_login = get_now().replace(tzinfo=None)
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_user_access_token(user)
    return {
        "success": True,
        "message": "login success",
        "data": {"token": token, "user": _user_data(user)},
    }


@router.get("/me", summary="Get current end user")
async def get_me(
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    require_app_interface_enabled(session, current_user.app_id, "user.me")
    return {"success": True, "data": _user_data(current_user)}


@router.get("/quotas", summary="Get current user quotas")
async def get_user_quotas(
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    account = get_or_create_user_quota_account(session, current_user.id, current_user.username)
    session.commit()
    return {"success": True, "data": user_quota_summary(account)}


@router.get("/apps", summary="List current user apps")
async def list_user_apps(
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    apps = get_user_visible_apps(session, current_user)
    session.commit()
    return {
        "success": True,
        "data": [
            {
                "id": app.id,
                "app_id": app.app_id,
                "name": app.name,
                "app_secret": app.app_secret,
                "created_by": app.created_by,
                "owner_user_id": app.owner_user_id,
                "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
                "status": app.status,
                "is_owned": app.owner_user_id == current_user.id,
            }
            for app in apps
        ],
    }


@router.post("/apps", summary="Create user app")
async def create_user_app_route(
    payload: UserAppCreateRequest,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    try:
        app, quota_result = create_user_app(session, current_user, payload.name.strip())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(app)
    return {
        "success": True,
        "message": "create app success",
        "data": {
            "id": app.id,
            "app_id": app.app_id,
            "name": app.name,
            "app_secret": app.app_secret,
            "rsa_public_key": app.rsa_public_key,
            "owner_user_id": app.owner_user_id,
            "created_by": app.created_by,
            "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
            "status": app.status,
            "quota": quota_result,
        },
    }


@router.post("/apps/{app_id}/kamis/batch", summary="Issue user kamis")
async def issue_user_kamis_route(
    app_id: str,
    payload: UserKamiIssueRequest,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")

    try:
        result = issue_user_kamis(
            session,
            current_user,
            app,
            kami_type=payload.kami_type,
            count=payload.count,
            batch_no=payload.batch_no,
            code_prefix=payload.code_prefix,
            code_length=payload.code_length,
            charset=payload.charset,
            points_amount=payload.points_amount,
            points_valid_days=payload.points_valid_days,
            times_total=payload.times_total,
            time_value=payload.time_value,
            time_unit=payload.time_unit,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    return {"success": True, "message": "issue success", "data": result}


@router.get("/apps/{app_id}/kamis", summary="List user issued kamis")
async def list_user_kamis_route(
    app_id: str,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    if not user_can_manage_app(session, current_user, app_id):
        raise HTTPException(status_code=403, detail="No permission to manage this app")
    kamis = list_user_issued_kamis(session, current_user, app_id)
    session.commit()
    return {
        "success": True,
        "data": [
            {
                "id": kami.id,
                "app_id": kami.app_id,
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


@router.get("/points/balance", summary="Get current points balance")
async def get_points_balance(
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    require_app_interface_enabled(session, current_user.app_id, "points.balance")
    summary = get_points_balance_summary(session, current_user.id, current_user.app_id)
    session.commit()
    return {
        "success": True,
        "data": {
            "user_id": current_user.id,
            "balance": summary["balance"],
            "available_balance": summary["available_balance"],
            "ledger_balance": summary["ledger_balance"],
            "expired_unsettled": summary["expired_unsettled"],
            "total_recharged": summary["total_recharged"],
            "total_consumed": summary["total_consumed"],
        },
    }


@router.post("/points/redeem", summary="Redeem a points kami")
async def redeem_points(
    payload: RedeemRequest,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    kami = session.exec(select(Kami).where(Kami.kami_code == payload.kami_code)).first()
    target_app_id = kami.app_id if kami else current_user.app_id
    require_app_interface_enabled(session, target_app_id, "points.redeem")
    try:
        result = redeem_points_kami(session, current_user, payload.kami_code)
    except PointServiceError as error:
        _handle_point_error(error)
    return {"success": True, "message": "redeem success", "data": result}


@router.post("/points/consume", summary="Consume points")
async def consume_user_points(
    payload: ConsumeRequest,
    request: Request,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    app_id = payload.app_id or current_user.app_id
    config = require_app_interface_enabled(session, app_id, "points.consume")
    min_amount = _int_config(config, "min_amount", 1) or 1
    max_amount = _int_config(config, "max_amount")
    if payload.amount < min_amount:
        raise HTTPException(
            status_code=400,
            detail={"code": "POINTS_AMOUNT_BELOW_LIMIT", "message": f"单次消费不能低于 {min_amount} 积分"},
        )
    if max_amount is not None and payload.amount > max_amount:
        raise HTTPException(
            status_code=400,
            detail={"code": "POINTS_AMOUNT_EXCEEDS_LIMIT", "message": f"单次消费不能超过 {max_amount} 积分"},
        )
    if config.get("require_biz_id", True) and not payload.biz_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "BIZ_ID_REQUIRED", "message": "消费接口必须传入 biz_id"},
        )
    try:
        result = consume_points(
            session=session,
            user_id=current_user.id,
            app_id=app_id,
            amount=payload.amount,
            biz_id=payload.biz_id,
            remark=payload.remark,
            metadata=payload.metadata,
        )
    except PointServiceError as error:
        _handle_point_error(error)
    _record_point_consume_device(session, app_id, current_user, payload, request)
    return {"success": True, "message": "consume success", "data": result}


@router.get("/points/lots", summary="List current user's points lots")
async def list_user_point_lots(
    only_available: bool = Query(False),
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    account = session.exec(
        select(AuthorizationAccount).where(
            AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
            AuthorizationAccount.user_id == current_user.id,
            AuthorizationAccount.app_id == current_user.app_id,
        )
    ).first()
    lots = []
    if account:
        statement = select(AuthorizationLot).where(
            AuthorizationLot.account_id == account.id,
            AuthorizationLot.benefit_type == AuthorizationBenefitType.points,
        )
        if only_available:
            statement = statement.where(AuthorizationLot.amount_remaining > 0)
        lots = session.exec(statement.order_by(AuthorizationLot.id.desc())).all()

    return {
        "success": True,
        "data": [
            {
                "source_transaction_id": None,
                "app_id": current_user.app_id,
                "kami_code": item.source_kami_code,
                "points_total": item.amount_total,
                "points_remaining": item.amount_remaining,
                "expires_at": to_api_beijing_iso(item.expires_at, naive="civil") if item.expires_at else None,
                "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
            }
            for item in lots
        ],
    }


@router.get("/points/transactions", summary="List current user's points transactions")
async def list_user_point_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    require_app_interface_enabled(session, current_user.app_id, "points.transactions")
    account = session.exec(
        select(AuthorizationAccount).where(
            AuthorizationAccount.owner_type == AuthorizationOwnerType.user,
            AuthorizationAccount.user_id == current_user.id,
            AuthorizationAccount.app_id == current_user.app_id,
        )
    ).first()
    all_items = []
    items = []
    if account:
        base = select(AuthorizationTransaction).where(
            AuthorizationTransaction.account_id == account.id,
            AuthorizationTransaction.benefit_type == AuthorizationBenefitType.points,
        )
        all_items = session.exec(base).all()
        items = session.exec(
            base.order_by(AuthorizationTransaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()

    return {
        "success": True,
        "data": {
            "total": len(all_items),
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "transaction_id": item.transaction_id,
                    "transaction_type": item.transaction_type.value
                    if hasattr(item.transaction_type, "value")
                    else item.transaction_type,
                    "amount": item.amount,
                    "balance_before": item.balance_after - item.amount,
                    "balance_after": item.balance_after,
                    "biz_id": item.biz_id,
                    "kami_code": item.source_kami_code,
                    "remark": None,
                    "metadata": item.metadata_json,
                    "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
                }
                for item in items
            ],
        },
    }
