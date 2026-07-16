from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from config import settings
from database import get_session
from datetime_utils import to_api_beijing_iso
from interface_service import require_app_interface_enabled
from models import App, EndUser, Kami, PointTransaction, UserPointAccount, UserPointLot, get_now
from point_service import (
    PointServiceError,
    consume_points,
    get_or_create_account,
    get_points_balance_summary,
    redeem_points_kami,
)
from routes_admin import hash_password, password_needs_rehash, verify_password


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
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> EndUser:
    raw_token = None
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

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

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


@router.get("/points/balance", summary="Get current points balance")
async def get_points_balance(
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    require_app_interface_enabled(session, current_user.app_id, "points.balance")
    account = get_or_create_account(session, current_user.id)
    summary = get_points_balance_summary(session, current_user.id)
    session.commit()
    return {
        "success": True,
        "data": {
            "user_id": current_user.id,
            "balance": summary["balance"],
            "available_balance": summary["available_balance"],
            "ledger_balance": summary["ledger_balance"],
            "expired_unsettled": summary["expired_unsettled"],
            "total_recharged": account.total_recharged,
            "total_consumed": account.total_consumed,
        },
    }


@router.post("/points/redeem", summary="Redeem a points kami")
async def redeem_points(
    payload: RedeemRequest,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    target_app_id = current_user.app_id
    if not target_app_id:
        kami = session.exec(select(Kami).where(Kami.kami_code == payload.kami_code)).first()
        target_app_id = kami.app_id if kami else None
    require_app_interface_enabled(session, target_app_id, "points.redeem")
    try:
        result = redeem_points_kami(session, current_user, payload.kami_code)
    except PointServiceError as error:
        _handle_point_error(error)
    return {"success": True, "message": "redeem success", "data": result}


@router.post("/points/consume", summary="Consume points")
async def consume_user_points(
    payload: ConsumeRequest,
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    if current_user.app_id:
        if payload.app_id and payload.app_id != current_user.app_id:
            raise HTTPException(
                status_code=403,
                detail={"code": "APP_MISMATCH", "message": "请求应用与当前用户所属应用不一致"},
            )
        app_id = current_user.app_id
    else:
        if not payload.app_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "APP_REQUIRED", "message": "未绑定应用的用户必须传入 app_id"},
            )
        app_id = payload.app_id

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
    return {"success": True, "message": "consume success", "data": result}


@router.get("/points/lots", summary="List current user's points lots")
async def list_user_point_lots(
    only_available: bool = Query(False),
    current_user: EndUser = Depends(get_current_end_user),
    session: Session = Depends(get_session),
):
    statement = select(UserPointLot).where(UserPointLot.user_id == current_user.id)
    if only_available:
        statement = statement.where(UserPointLot.points_remaining > 0)
    lots = session.exec(statement.order_by(UserPointLot.id.desc())).all()

    return {
        "success": True,
        "data": [
            {
                "source_transaction_id": item.source_transaction_id,
                "app_id": item.app_id,
                "kami_code": item.kami_code,
                "points_total": item.points_total,
                "points_remaining": item.points_remaining,
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
    base = select(PointTransaction).where(PointTransaction.user_id == current_user.id)
    all_items = session.exec(base).all()
    items = session.exec(
        base.order_by(PointTransaction.id.desc())
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
                    "transaction_type": item.transaction_type.value,
                    "amount": item.amount,
                    "balance_before": item.balance_before,
                    "balance_after": item.balance_after,
                    "biz_id": item.biz_id,
                    "kami_code": item.kami_code,
                    "remark": item.remark,
                    "metadata": item.metadata_json,
                    "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
                }
                for item in items
            ],
        },
    }
