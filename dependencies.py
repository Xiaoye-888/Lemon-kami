"""
FastAPI 依赖注入模块
包含加密验证、防重放、限流等中间件逻辑
"""

import time
import json
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlmodel import Session, select
from database import get_session
from models import App
from crypto import CryptoHelper, HMACSigner
from redis_client import get_redis
from config import settings


logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """安全验证中间件"""

    @staticmethod
    def _client_token_signing_secret(client_token: Optional[str], app_id: str) -> Optional[str]:
        if not client_token:
            return None
        try:
            payload = jwt.decode(
                client_token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid client token")

        if payload.get("role") != "sdk_client" or payload.get("app_id") != app_id:
            raise HTTPException(status_code=401, detail="Invalid client token")
        try:
            expires_at = int(payload.get("exp"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid client token")
        if expires_at <= int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=401, detail="Invalid client token")
        sdk_secret = payload.get("sdk_secret")
        if not sdk_secret:
            raise HTTPException(status_code=401, detail="Invalid client token")
        return sdk_secret

    @staticmethod
    async def verify_request(
        request: Request,
        session: Session = Depends(get_session),
        redis_client = Depends(get_redis)
    ) -> dict:
        """
        验证请求：解密、签名校验、防重放
        
        Returns:
            解密后的业务数据字典
        """
        # 1. 获取请求体
        try:
            body = await request.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid JSON body")

        # 2. 提取必要字段
        app_id = body.get("app_id")
        timestamp = body.get("timestamp")
        nonce = body.get("nonce")
        sign = body.get("sign")
        client_token = body.get("client_token")
        encrypted_key = body.get("encrypted_key")
        encrypted_data = body.get("encrypted_data")
        iv = body.get("iv")
        
        logger.debug("收到 SDK 加密请求: app_id=%s, timestamp=%s", app_id, timestamp)

        if not all([app_id, timestamp, encrypted_key, encrypted_data, iv]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        # 3. 查询应用信息
        statement = select(App).where(App.app_id == app_id)
        app = session.exec(statement).first()

        if not app:
            raise HTTPException(status_code=404, detail="App not found")

        if app.status != 1:
            raise HTTPException(status_code=403, detail="App is disabled")

        # 4. IP 限流
        client_ip = request.client.host if request.client else ""
        rate_limit_key = f"rate_limit:ip:{client_ip}"
        current_count = redis_client.get(rate_limit_key)

        if current_count and int(current_count) >= settings.RATE_LIMIT_MAX:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        pipe = redis_client.pipeline()
        pipe.incr(rate_limit_key)
        pipe.expire(rate_limit_key, settings.RATE_LIMIT_WINDOW)
        pipe.execute()

        # 5. 校验时间戳（防重放）
        try:
            timestamp_value = int(timestamp)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid timestamp")

        current_time = int(time.time())
        timestamp_tolerance = app.timestamp_tolerance_seconds or settings.TIMESTAMP_TOLERANCE
        if abs(current_time - timestamp_value) > timestamp_tolerance:
            raise HTTPException(status_code=400, detail="Timestamp expired")

        token_signing_secret = SecurityMiddleware._client_token_signing_secret(client_token, app_id)
        signing_secret = token_signing_secret or app.app_secret

        # 6. 校验签名。签名失败不能写入 nonce，避免攻击者污染重放窗口。
        if app.signature_required:
            if not sign:
                raise HTTPException(status_code=400, detail="Missing required fields")
            sign_data = f"{timestamp_value}{nonce or ''}{encrypted_data}"
            expected_sign = HMACSigner.generate_sign(sign_data, signing_secret)
            if not hmac.compare_digest(expected_sign, sign):
                raise HTTPException(status_code=401, detail="Invalid signature")

        # 7. 校验 nonce（防重放）
        if app.nonce_required:
            if not nonce:
                raise HTTPException(status_code=400, detail="Missing required fields")
            nonce_key = f"nonce:{app_id}:{nonce}"
            if redis_client.exists(nonce_key):
                raise HTTPException(status_code=400, detail="Nonce already used")
            redis_client.setex(nonce_key, settings.NONCE_TTL, "1")

        # 8. 解密数据
        try:
            decrypted_data = CryptoHelper.decrypt_payload(
                encrypted_key,
                encrypted_data,
                iv,
                app.rsa_private_key
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Decryption failed: {str(e)}")

        # 9. 将 app 信息附加到解密数据中
        decrypted_data["_app_info"] = {
            "app_id": app.app_id,
            "app_secret": signing_secret,
            "auth_mode": "client_token" if token_signing_secret else "app_secret",
        }

        return decrypted_data


async def get_decrypted_data(
    request: Request,
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
) -> dict:
    """
    FastAPI 依赖函数：获取解密后的请求数据
    
    Usage:
        @app.post("/api/v1/sdk/verify")
        async def verify_kami(data: dict = Depends(get_decrypted_data)):
            ...
    """
    return await SecurityMiddleware.verify_request(request, session, redis_client)
