from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

import routes_admin
import routes_user
from auth_utils import verify_password
from config import settings
from database import get_session
from datetime_utils import to_api_beijing_iso
from models import AdminUser, EndUser, get_now


router = APIRouter(prefix="/api/v1/auth", tags=["Shared Auth"])


class SharedLoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    encrypted_data: Optional[str] = None
    iv: Optional[str] = None
    encrypted: bool = False


def _decode_login_payload(payload: SharedLoginRequest) -> tuple[str, str]:
    username = payload.username
    password = payload.password
    if payload.encrypted_data and payload.iv:
        from crypto import CryptoHelper

        decrypted = CryptoHelper.aes_decrypt(
            encrypted_data=payload.encrypted_data,
            key_b64=routes_admin._get_login_aes_key_b64(),
            iv=payload.iv,
        )
        username = decrypted.get("username")
        password = decrypted.get("password")
    if not username or not password:
        raise HTTPException(status_code=400, detail="缺少用户名或密码")
    return username, password


@router.get("/login/public-key", summary="Get shared login AES key")
async def get_shared_login_key():
    return await routes_admin.get_login_aes_key()


@router.post("/login", summary="Shared admin/merchant login")
async def shared_login(
    payload: SharedLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    username, password = _decode_login_payload(payload)
    admin = session.exec(select(AdminUser).where(AdminUser.username == username)).first()
    if admin:
        if admin.status != 1:
            raise HTTPException(status_code=403, detail="账号已被禁用")
        if not verify_password(password, admin.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        admin.last_login = get_now().replace(tzinfo=None)
        admin.failed_attempts = 0
        admin.locked_until = None
        session.add(admin)
        session.commit()
        token = routes_admin.create_access_token(
            data={
                "sub": admin.username,
                "user_id": admin.id,
                "is_admin": admin.is_admin,
                "role": "admin",
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "success": True,
            "token": token,
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "role": "admin",
            "redirect": "/admin/dashboard",
            "user_info": {
                "id": admin.id,
                "username": admin.username,
                "email": admin.email,
                "is_admin": admin.is_admin,
                "role": "admin",
                "last_login": to_api_beijing_iso(admin.last_login, naive="civil")
                if admin.last_login
                else None,
            },
        }

    merchant = session.exec(select(EndUser).where(EndUser.username == username)).first()
    if not merchant or not verify_password(password, merchant.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if merchant.status != 1:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    merchant.last_login = get_now().replace(tzinfo=None)
    session.add(merchant)
    session.commit()
    session.refresh(merchant)
    token = routes_user.create_user_access_token(merchant)
    return {
        "success": True,
        "token": token,
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "role": "merchant",
        "redirect": "/merchant/dashboard",
        "user_info": {
            "id": merchant.id,
            "username": merchant.username,
            "email": merchant.email,
            "phone": merchant.phone,
            "role": "merchant",
            "status": merchant.status,
            "last_login": to_api_beijing_iso(merchant.last_login, naive="civil")
            if merchant.last_login
            else None,
        },
    }
