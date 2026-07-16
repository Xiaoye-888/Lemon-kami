"""
SDK 核心接口路由
包含卡密验证和行为上报接口
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Request
from sqlmodel import Session, select
from database import engine, get_session
from models import (
    App,
    Kami,
    Device,
    EndUser,
    EventLog,
    KamiStatus,
    KamiType,
    MachineBindMode,
    KamiDeviceBinding,
    UserBindMode,
    get_now,
    is_kami_code_expired,
)
from datetime_utils import to_api_beijing_iso
from dependencies import get_decrypted_data
from interface_service import get_app_interface_config, require_app_interface_enabled
from redis_client import get_redis
from crypto import CryptoHelper
import json
import base64
import os
import logging
import uuid as uuid_lib

router = APIRouter(prefix="/api/v1/sdk", tags=["SDK"])
logger = logging.getLogger(__name__)


def _config_bool(config: dict, key: str, default: bool = False) -> bool:
    value = config.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _config_int(config: dict, key: str, default: int = 0) -> int:
    value = config.get(key)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def encrypt_response(data: dict, app_secret: str) -> dict:
    """
    加密响应数据
    
    Args:
        data: 响应数据字典
        app_secret: 应用密钥（用于生成签名）
        
    Returns:
        加密后的响应字典
    """
    import hashlib
    import hmac
    import time
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    
    # 将数据转为 JSON
    json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    # 生成随机 AES 密钥和 IV
    aes_key = os.urandom(16)
    aes_iv = os.urandom(16)
    
    # AES 加密
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(json_data) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(aes_iv))
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # 生成时间戳和随机数
    timestamp = int(time.time())
    nonce = hashlib.md5(f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:16]
    
    # 生成 HMAC-SHA256 签名
    sign_str = f"{timestamp}{nonce}{base64.b64encode(encrypted_data).decode()}"
    signature = hmac.new(
        app_secret.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "encrypted": True,
        "timestamp": timestamp,
        "nonce": nonce,
        "sign": signature,
        "encrypted_key": base64.b64encode(aes_key).decode(),
        "encrypted_data": base64.b64encode(encrypted_data).decode(),
        "iv": base64.b64encode(aes_iv).decode()
    }


@router.get("/public-key")
async def get_public_key(
    app_id: str,
    session: Session = Depends(get_session)
):
    """
    获取应用 RSA 公钥
    
    Args:
        app_id: 应用ID
        
    Returns:
        RSA 公钥字符串
    """
    from sqlmodel import select
    from models import App
    
    # 查询应用
    statement = select(App).where(App.app_id == app_id)
    app = session.exec(statement).first()
    
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    
    if app.status != 1:
        raise HTTPException(status_code=403, detail="应用已禁用")
    
    require_app_interface_enabled(session, app_id, "sdk.public_key")

    return {
        "success": True,
        "public_key": app.rsa_public_key
    }


def _client_ip_from_request(request: Request) -> str:
    return request.client.host if request.client else ""


def _kami_time_delta(kami_type: KamiType) -> Optional[timedelta]:
    if kami_type == KamiType.hour:
        return timedelta(hours=1)
    if kami_type == KamiType.day:
        return timedelta(days=1)
    if kami_type == KamiType.week:
        return timedelta(days=7)
    if kami_type == KamiType.month:
        return timedelta(days=30)
    if kami_type == KamiType.quarter:
        return timedelta(days=90)
    if kami_type == KamiType.year:
        return timedelta(days=365)
    return None


def calculate_expire_time(kami_type: KamiType) -> Optional[datetime]:
    """根据卡密类型计算到期时间"""
    # get_now() 返回带时区的时间，需要去掉时区信息后存入数据库
    now = get_now().replace(tzinfo=None)

    delta = _kami_time_delta(kami_type)
    if delta:
        return now + delta
    elif kami_type == KamiType.lifetime:
        return None  # 永久有效
    elif kami_type == KamiType.points:
        return now + timedelta(days=365)  # 积分型默认1年

    return None


def _build_verify_response(kami: Kami, message: str = "验证成功") -> dict:
    data = {
        "success": True,
        "message": message,
        "kami_type": kami.kami_type.value,
        "expire_time": to_api_beijing_iso(kami.expire_time, naive="civil"),
        "authorization_owner": kami.authorization_owner.value
        if hasattr(kami.authorization_owner, "value")
        else kami.authorization_owner,
        "user_bind_mode": kami.user_bind_mode.value
        if hasattr(kami.user_bind_mode, "value")
        else kami.user_bind_mode,
        "bound_user_id": kami.redeemed_by_user_id,
    }
    if kami.kami_type == KamiType.times:
        data.update({
            "times_total": kami.times_total,
            "times_remaining": kami.times_remaining or 0,
        })
    return data


def _consume_times_if_needed(kami: Kami, amount: int = 1) -> Optional[dict]:
    if kami.kami_type != KamiType.times:
        return None
    if amount <= 0:
        return {"success": False, "message": "核销次数必须大于 0"}
    remaining = kami.times_remaining
    if remaining is None:
        remaining = kami.times_total or 0
        kami.times_remaining = remaining
    if remaining < amount:
        return {"success": False, "message": "次数卡剩余次数不足"}
    kami.times_remaining = remaining - amount
    return None


def _times_available_error(kami: Kami) -> Optional[dict]:
    if kami.kami_type != KamiType.times:
        return None
    remaining = kami.times_remaining
    if remaining is None:
        remaining = kami.times_total or 0
    if remaining <= 0:
        return {"success": False, "message": "次数卡剩余次数不足"}
    return None


def _find_consume_event_payload(
    session: Session,
    app_id: str,
    kami_code: str,
    biz_id: str,
) -> Optional[dict]:
    events = session.exec(
        select(EventLog)
        .where(
            EventLog.app_id == app_id,
            EventLog.kami_code == kami_code,
            EventLog.event_type == "consume",
            EventLog.status == 1,
        )
        .order_by(EventLog.id.desc())
    ).all()
    for event in events:
        if not event.payload:
            continue
        try:
            payload = json.loads(event.payload)
        except json.JSONDecodeError:
            continue
        if payload.get("biz_id") == biz_id:
            return payload
    return None


def _machine_bind_mode(kami: Kami) -> MachineBindMode:
    try:
        return MachineBindMode(kami.machine_bind_mode)
    except (TypeError, ValueError):
        return MachineBindMode.one_card_one_device


def _max_bind_devices(kami: Kami) -> int:
    mode = _machine_bind_mode(kami)
    if mode == MachineBindMode.no_limit:
        return 0
    if mode == MachineBindMode.one_card_one_device:
        return 1
    configured = getattr(kami, "max_bind_devices", None)
    return configured if configured and configured >= 2 else 3


def _app_interface_enabled(
    session: Session,
    app_id: Optional[str],
    interface_key: str,
    default_enabled: bool = False,
) -> tuple[bool, dict]:
    interface, config, config_data = get_app_interface_config(session, app_id, interface_key)
    if not interface:
        return default_enabled, {}
    if interface.status != 1:
        return False, config_data
    if not config:
        return default_enabled, config_data
    now_naive = get_now().replace(tzinfo=None)
    if config.expires_at is not None and config.expires_at < now_naive:
        return False, config_data
    return bool(config.enabled), config_data


def _device_uuid(uuid: str, fingerprint: str) -> str:
    return uuid if uuid else fingerprint


def _kami_binding_count(session: Session, kami_code: str) -> int:
    return len(
        session.exec(
            select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == kami_code)
        ).all()
    )


def _find_current_multi_device_binding(
    session: Session,
    kami_code: str,
    uuid: str,
    fingerprint: str,
) -> Optional[KamiDeviceBinding]:
    binding = session.exec(
        select(KamiDeviceBinding).where(
            KamiDeviceBinding.kami_code == kami_code,
            KamiDeviceBinding.fingerprint == fingerprint,
        )
    ).first()
    if binding or not uuid:
        return binding
    return session.exec(
        select(KamiDeviceBinding).where(
            KamiDeviceBinding.kami_code == kami_code,
            KamiDeviceBinding.device_uuid == uuid,
        )
    ).first()


def _release_current_device_slot(
    session: Session,
    kami: Kami,
    uuid: str,
    fingerprint: str,
    redis_client,
) -> tuple[bool, int]:
    mode = _machine_bind_mode(kami)
    if mode == MachineBindMode.one_card_multi_device:
        binding = _find_current_multi_device_binding(session, kami.kami_code, uuid, fingerprint)
        if not binding:
            return False, _kami_binding_count(session, kami.kami_code)

        session.delete(binding)
        session.flush()
        remaining = session.exec(
            select(KamiDeviceBinding)
            .where(KamiDeviceBinding.kami_code == kami.kami_code)
            .order_by(KamiDeviceBinding.first_bind_at, KamiDeviceBinding.id)
        ).all()
        if remaining:
            kami.bind_uuid = remaining[0].device_uuid
            kami.bind_ip = remaining[0].bind_ip
        else:
            kami.bind_uuid = None
            kami.bind_ip = None
        session.add(kami)
        return True, len(remaining)

    if mode == MachineBindMode.one_card_one_device:
        if not kami.bind_uuid:
            return False, 0

        current_uuid = _device_uuid(uuid, fingerprint)
        bound_device = session.exec(
            select(Device).where(
                Device.app_id == kami.app_id,
                Device.fingerprint == fingerprint,
            )
        ).first()
        device_matches = kami.bind_uuid in {current_uuid, fingerprint} or (
            bound_device is not None and bound_device.uuid == kami.bind_uuid
        )
        if not device_matches:
            return False, 1

        kami.bind_uuid = None
        kami.bind_ip = None
        session.add(kami)
        redis_client.delete(f"device_bind:{kami.kami_code}")
        return True, 0

    return False, 0


def _upsert_device(
    session: Session,
    app_id: str,
    uuid: str,
    fingerprint: str,
    client_ip: str,
) -> Device:
    device_uuid = uuid if uuid else fingerprint
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
    return device


def _upsert_kami_device_binding(
    session: Session,
    app_id: str,
    kami_code: str,
    uuid: str,
    fingerprint: str,
    client_ip: str,
    now_naive: datetime,
) -> KamiDeviceBinding:
    device_uuid = uuid if uuid else fingerprint
    binding = session.exec(
        select(KamiDeviceBinding).where(
            KamiDeviceBinding.kami_code == kami_code,
            KamiDeviceBinding.fingerprint == fingerprint,
        )
    ).first()
    if binding:
        binding.device_uuid = device_uuid
        binding.bind_ip = client_ip or binding.bind_ip
        binding.last_verify_at = now_naive
    else:
        binding = KamiDeviceBinding(
            app_id=app_id,
            kami_code=kami_code,
            device_uuid=device_uuid,
            fingerprint=fingerprint,
            bind_ip=client_ip or None,
            first_bind_at=now_naive,
            last_verify_at=now_naive,
        )
    session.add(binding)
    return binding


def _device_block_response(
    session: Session,
    app_id: str,
    kami_code: str,
    fingerprint: str,
    client_ip: str,
    uuid: str,
    user_agent: str,
) -> Optional[dict]:
    device = session.exec(
        select(Device).where(
            Device.app_id == app_id,
            Device.fingerprint == fingerprint,
        )
    ).first()
    if device and device.risk_level == 2:
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="设备已被拉黑")
        return {"success": False, "message": "该设备已被加入黑名单，禁止使用"}
    if device and device.risk_level == 1:
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=1, message="设备处于警告状态")
    return None


def _user_bind_mode(kami: Kami) -> UserBindMode:
    try:
        mode = UserBindMode(kami.user_bind_mode)
    except ValueError:
        return UserBindMode.none
    if mode == UserBindMode.optional:
        return UserBindMode.auto
    return mode


def _user_identity_from_payload(data: dict) -> tuple[Optional[int], Optional[str]]:
    user_id = data.get("user_id")
    username = data.get("username") or data.get("user")
    try:
        normalized_user_id = int(user_id) if user_id not in (None, "") else None
    except (TypeError, ValueError):
        normalized_user_id = None
    return normalized_user_id, str(username).strip() if username else None


def _user_binding_missing_error(kami: Kami, data: dict) -> Optional[dict]:
    mode = _user_bind_mode(kami)
    if mode == UserBindMode.none:
        return None
    user_id, username = _user_identity_from_payload(data)
    if user_id or username:
        return None
    if mode == UserBindMode.auto and kami.redeemed_by_user_id:
        return {
            "success": False,
            "message": "该卡密已绑定用户，请传入绑定用户信息",
            "error_code": "USER_BINDING_REQUIRED",
        }
    if mode != UserBindMode.required:
        return None
    return {
        "success": False,
        "message": "该批次要求绑定用户，请传入 user_id 或 username",
        "error_code": "USER_BINDING_REQUIRED",
    }


def _bind_kami_user_if_needed(
    session: Session,
    kami: Kami,
    data: dict,
    now_naive: datetime,
) -> Optional[dict]:
    if _user_bind_mode(kami) == UserBindMode.none:
        return None
    missing_error = _user_binding_missing_error(kami, data)
    if missing_error:
        return missing_error

    user_id, username = _user_identity_from_payload(data)
    if not user_id and not username:
        return None

    statement = select(EndUser)
    if user_id:
        statement = statement.where(EndUser.id == user_id)
    else:
        statement = statement.where(EndUser.username == username)
    user = session.exec(statement).first()
    if not user:
        return {
            "success": False,
            "message": "绑定用户不存在",
            "error_code": "USER_NOT_FOUND",
        }
    if user.app_id and user.app_id != kami.app_id:
        return {
            "success": False,
            "message": "绑定用户不属于当前应用",
            "error_code": "USER_APP_MISMATCH",
        }
    if kami.redeemed_by_user_id and kami.redeemed_by_user_id != user.id:
        return {
            "success": False,
            "message": "该卡密已绑定其他用户",
            "error_code": "USER_BINDING_MISMATCH",
        }
    if not kami.redeemed_by_user_id:
        kami.redeemed_by_user_id = user.id
        kami.redeemed_at = now_naive
    return None


@router.post("/verify")
async def verify_kami(
    request: Request,
    data: dict = Depends(get_decrypted_data),
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
):
    """
    卡密验证接口
    
    首次验证：绑定设备并激活卡密
    非首次验证：校验设备指纹是否一致
    """
    kami_code = data.get("kami")
    uuid = data.get("uuid", "")  # 兼容旧版本，可能为空
    fingerprint = data.get("fingerprint")
    app_info = data.get("_app_info", {})
    app_id = app_info.get("app_id")
    
    # 获取请求信息
    client_ip = _client_ip_from_request(request)
    user_agent = request.headers.get("user-agent", "")

    if not all([kami_code, fingerprint]):
        raise HTTPException(status_code=400, detail="Missing required fields: kami and fingerprint")

    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.status != 1:
        raise HTTPException(status_code=403, detail="App is disabled")

    # 查询卡密
    verify_config = require_app_interface_enabled(session, app_id, "sdk.verify")
    device_limit_enabled, _device_limit_config = _app_interface_enabled(
        session,
        app_id,
        "sdk.device_limit",
        default_enabled=True,
    )
    ip_lock_enabled = _config_bool(verify_config, "ip_lock_enabled", app.ip_lock_enabled)

    statement = select(Kami).where(Kami.kami_code == kami_code, Kami.app_id == app_id)
    kami = session.exec(statement).first()

    if not kami:
        # 记录失败日志
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent, 
                         status=0, message="卡密不存在")
        response_data = {"success": False, "message": "卡密不存在"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    if kami.status == KamiStatus.frozen:
        # 记录失败日志
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="卡密已被冻结")
        response_data = {"success": False, "message": "卡密已被冻结"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    # 检查 Redis 缓存的设备绑定信息
    cache_key = f"device_bind:{kami_code}"
    cached_bind = redis_client.hgetall(cache_key)
    now_naive = get_now().replace(tzinfo=None)

    if is_kami_code_expired(kami, now_naive):
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="卡密已过期")
        response_data = {"success": False, "message": "卡密已过期"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    if kami.expire_time and now_naive > kami.expire_time:
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="卡密已过期")
        response_data = {"success": False, "message": "卡密已过期"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    if _config_bool(verify_config, "enable_user_authorization", False):
        user_binding_error = _bind_kami_user_if_needed(session, kami, data, now_naive)
        if user_binding_error:
            _record_event_log(
                session,
                app_id,
                kami_code,
                "verify",
                client_ip,
                uuid,
                user_agent,
                status=0,
                message=user_binding_error["message"],
            )
            return encrypt_response(user_binding_error, app_info.get("app_secret", ""))

    machine_bind_mode = _machine_bind_mode(kami)
    if not device_limit_enabled:
        machine_bind_mode = MachineBindMode.no_limit
    if machine_bind_mode in {MachineBindMode.no_limit, MachineBindMode.one_card_multi_device}:
        block_response = _device_block_response(
            session, app_id, kami_code, fingerprint, client_ip, uuid, user_agent
        )
        if block_response:
            return encrypt_response(block_response, app_info.get("app_secret", ""))

        times_error = _times_available_error(kami)
        if times_error:
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=0, message=times_error["message"])
            return encrypt_response(times_error, app_info.get("app_secret", ""))

        is_first_activation = kami.status == KamiStatus.unused
        if is_first_activation:
            kami.activate_time = now_naive
            kami.expire_time = calculate_expire_time(kami.kami_type)
            kami.status = KamiStatus.active
            kami.bind_ip = client_ip or None

        _upsert_device(session, app_id, uuid, fingerprint, client_ip)
        if machine_bind_mode == MachineBindMode.one_card_multi_device:
            existing_binding = session.exec(
                select(KamiDeviceBinding).where(
                    KamiDeviceBinding.kami_code == kami_code,
                    KamiDeviceBinding.fingerprint == fingerprint,
                )
            ).first()
            if not existing_binding:
                current_bind_count = len(
                    session.exec(
                        select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code == kami_code)
                    ).all()
                )
                max_bind_devices = _max_bind_devices(kami)
                if max_bind_devices and current_bind_count >= max_bind_devices:
                    _record_event_log(
                        session,
                        app_id,
                        kami_code,
                        "verify",
                        client_ip,
                        uuid,
                        user_agent,
                        status=0,
                        message="绑定设备数量已达上限",
                    )
                    response_data = {
                        "success": False,
                        "message": f"绑定设备数量已达上限，最多允许 {max_bind_devices} 台设备",
                        "error_code": "DEVICE_LIMIT_EXCEEDED",
                        "current_device_count": current_bind_count,
                        "max_bind_devices": max_bind_devices,
                    }
                    return encrypt_response(response_data, app_info.get("app_secret", ""))

            _upsert_kami_device_binding(
                session, app_id, kami_code, uuid, fingerprint, client_ip, now_naive
            )
            if not kami.bind_uuid:
                kami.bind_uuid = uuid if uuid else fingerprint

        if ip_lock_enabled and kami.bind_ip and client_ip and kami.bind_ip != client_ip:
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=0, message="IP 不匹配")
            response_data = {"success": False, "message": "IP 不匹配，禁止在其他网络环境使用"}
            return encrypt_response(response_data, app_info.get("app_secret", ""))

        kami.last_verify_at = now_naive
        app.api_call_count += 1
        session.add(kami)
        session.add(app)
        session.commit()

        _record_event_log(
            session,
            app_id,
            kami_code,
            "activate" if is_first_activation else "verify",
            client_ip,
            uuid,
            user_agent,
            status=1,
            message="卡密激活成功" if is_first_activation else "验证成功",
        )

        response_data = _build_verify_response(kami)
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    needs_binding = kami.status == KamiStatus.unused or (
        kami.status == KamiStatus.active and not kami.bind_uuid
    )

    # 首次验证：绑定设备
    if needs_binding:
        times_error = _times_available_error(kami)
        if times_error:
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=0, message=times_error["message"])
            return encrypt_response(times_error, app_info.get("app_secret", ""))

        # 检查设备是否已被拉黑（通过指纹）
        existing_device = session.exec(
            select(Device).where(
                Device.app_id == app_id,
                Device.fingerprint == fingerprint
            )
        ).first()
        
        if existing_device and existing_device.risk_level == 2:
            # 设备在黑名单中，拒绝激活
            _record_event_log(session, app_id, kami_code, "activate", client_ip, uuid, user_agent,
                             status=0, message="设备已被拉黑，禁止激活")
            response_data = {
                "success": False,
                "message": "该设备已被加入黑名单，禁止激活卡密"
            }
            return encrypt_response(response_data, app_info.get("app_secret", ""))
        
        if kami.status == KamiStatus.unused:
            kami.activate_time = now_naive
            kami.expire_time = calculate_expire_time(kami.kami_type)

        # 更新卡密状态
        kami.status = KamiStatus.active
        kami.bind_uuid = uuid if uuid else fingerprint  # 如果没有uuid则使用指纹作为标识
        kami.bind_ip = client_ip or None
        kami.last_verify_at = now_naive
        app.api_call_count += 1
        session.add(kami)
        session.add(app)

        _upsert_device(session, app_id, uuid, fingerprint, client_ip)

        # 缓存设备绑定信息到 Redis
        redis_client.hset(cache_key, mapping={
            "uuid": uuid if uuid else fingerprint,
            "fingerprint": fingerprint
        })
        redis_client.expire(cache_key, 86400 * 365)  # 缓存1年

        session.commit()
        
        # 记录激活日志
        _record_event_log(session, app_id, kami_code, "activate", client_ip, uuid, user_agent,
                         status=1, message=f"卡密激活成功，类型：{kami.kami_type.value}")

        response_data = _build_verify_response(kami)
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    # 非首次验证：检查设备绑定
    if cached_bind:
        cached_uuid = cached_bind.get("uuid")
        cached_fingerprint = cached_bind.get("fingerprint")

        # 主要检查指纹匹配，UUID作为辅助验证
        if fingerprint != cached_fingerprint:
            # 记录失败日志
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=0, message="设备指纹不匹配")
            response_data = {
                "success": False,
                "message": "设备指纹不匹配，禁止在其他设备使用"
            }
            return encrypt_response(response_data, app_info.get("app_secret", ""))
        
        # 如果有UUID，也检查UUID匹配
        if uuid and cached_uuid and uuid != cached_uuid:
            # 记录警告日志，但允许通过（因为指纹已匹配）
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=1, message="设备UUID变更但指纹匹配")
    else:
        # 缓存失效，从数据库查询
        device = session.exec(
            select(Device).where(
                Device.app_id == app_id,
                Device.fingerprint == fingerprint
            )
        ).first()

        if not device or (kami.bind_uuid and uuid and kami.bind_uuid != uuid):
            # 记录失败日志
            _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                             status=0, message="设备未注册")
            response_data = {
                "success": False,
                "message": "设备未注册或绑定不匹配"
            }
            return encrypt_response(response_data, app_info.get("app_secret", ""))

        # 重新缓存
        redis_client.hset(cache_key, mapping={
            "uuid": device.uuid,
            "fingerprint": device.fingerprint
        })
        redis_client.expire(cache_key, 86400 * 365)

    if ip_lock_enabled and kami.bind_ip and client_ip and kami.bind_ip != client_ip:
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="IP 不匹配")
        response_data = {"success": False, "message": "IP 不匹配，禁止在其他网络环境使用"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    
    # 检查设备风险等级
    device_statement = select(Device).where(
        Device.app_id == app_id,
        Device.fingerprint == fingerprint
    )
    device = session.exec(device_statement).first()
    
    if device and device.risk_level == 2:
        # 设备在黑名单中，拒绝验证
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message="设备已被拉黑")
        response_data = {
            "success": False,
            "message": "该设备已被加入黑名单，禁止使用"
        }
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    
    if device and device.risk_level == 1:
        # 设备被警告，记录日志但允许使用
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=1, message="设备处于警告状态")

    times_error = _times_available_error(kami)
    if times_error:
        _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                         status=0, message=times_error["message"])
        return encrypt_response(times_error, app_info.get("app_secret", ""))
    
    kami.last_verify_at = now_naive
    app.api_call_count += 1
    session.add(kami)
    session.add(app)
    session.commit()

    # 记录成功验证日志
    _record_event_log(session, app_id, kami_code, "verify", client_ip, uuid, user_agent,
                     status=1, message="验证成功")

    response_data = _build_verify_response(kami)
    return encrypt_response(response_data, app_info.get("app_secret", ""))


@router.post("/consume")
async def consume_kami(
    request: Request,
    data: dict = Depends(get_decrypted_data),
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
):
    """核销次数卡。验证卡密有效性，但只有此接口会扣减次数。"""
    kami_code = data.get("kami")
    uuid = data.get("uuid", "")
    fingerprint = data.get("fingerprint")
    app_info = data.get("_app_info", {})
    app_id = app_info.get("app_id")
    amount = int(data.get("amount") or 1)
    biz_id = data.get("biz_id") or f"consume_{uuid_lib.uuid4().hex}"

    client_ip = _client_ip_from_request(request)
    user_agent = request.headers.get("user-agent", "")

    if not all([kami_code, fingerprint]):
        raise HTTPException(status_code=400, detail="Missing required fields: kami and fingerprint")

    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.status != 1:
        raise HTTPException(status_code=403, detail="App is disabled")

    consume_enabled, _consume_config = _app_interface_enabled(
        session, app_id, "sdk.consume", default_enabled=True
    )
    if not consume_enabled:
        response_data = {"success": False, "message": "核销接口未开通或已关闭"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    existing_payload = _find_consume_event_payload(session, app_id, kami_code, biz_id)
    if existing_payload:
        response_data = {
            "success": True,
            "message": "核销成功",
            "consume_id": existing_payload.get("consume_id"),
            "biz_id": biz_id,
            "amount": existing_payload.get("amount", amount),
            "idempotent": True,
            "times_total": existing_payload.get("times_total"),
            "times_remaining": existing_payload.get("times_remaining"),
        }
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    kami = session.exec(
        select(Kami).where(Kami.kami_code == kami_code, Kami.app_id == app_id)
    ).first()
    if not kami:
        response_data = {"success": False, "message": "卡密不存在"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if kami.kami_type != KamiType.times:
        response_data = {"success": False, "message": "仅次数卡支持核销"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if kami.status == KamiStatus.frozen:
        response_data = {"success": False, "message": "卡密已被冻结"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    now_naive = get_now().replace(tzinfo=None)
    if is_kami_code_expired(kami, now_naive):
        _record_event_log(
            session,
            app_id,
            kami_code,
            "consume",
            client_ip,
            uuid,
            user_agent,
            status=0,
            message="卡密已过期",
            payload={"biz_id": biz_id, "amount": amount},
        )
        response_data = {"success": False, "message": "卡密已过期"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    if kami.expire_time and now_naive > kami.expire_time:
        response_data = {"success": False, "message": "卡密已过期"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    verify_config = require_app_interface_enabled(session, app_id, "sdk.verify")
    if _config_bool(verify_config, "enable_user_authorization", False):
        user_binding_error = _bind_kami_user_if_needed(session, kami, data, now_naive)
        if user_binding_error:
            _record_event_log(
                session,
                app_id,
                kami_code,
                "consume",
                client_ip,
                uuid,
                user_agent,
                status=0,
                message=user_binding_error["message"],
                payload={"biz_id": biz_id, "amount": amount},
            )
            return encrypt_response(user_binding_error, app_info.get("app_secret", ""))

    device_limit_enabled, _device_limit_config = _app_interface_enabled(
        session, app_id, "sdk.device_limit", default_enabled=True
    )
    machine_bind_mode = _machine_bind_mode(kami) if device_limit_enabled else MachineBindMode.no_limit
    block_response = _device_block_response(
        session, app_id, kami_code, fingerprint, client_ip, uuid, user_agent
    )
    if block_response:
        return encrypt_response(block_response, app_info.get("app_secret", ""))

    if machine_bind_mode == MachineBindMode.one_card_multi_device:
        existing_binding = _find_current_multi_device_binding(session, kami_code, uuid, fingerprint)
        if not existing_binding:
            current_bind_count = _kami_binding_count(session, kami_code)
            max_bind_devices = _max_bind_devices(kami)
            if max_bind_devices and current_bind_count >= max_bind_devices:
                response_data = {
                    "success": False,
                    "message": f"绑定设备数量已达上限，最多允许 {max_bind_devices} 台设备",
                    "error_code": "DEVICE_LIMIT_EXCEEDED",
                    "current_device_count": current_bind_count,
                    "max_bind_devices": max_bind_devices,
                }
                return encrypt_response(response_data, app_info.get("app_secret", ""))
        _upsert_device(session, app_id, uuid, fingerprint, client_ip)
        _upsert_kami_device_binding(session, app_id, kami_code, uuid, fingerprint, client_ip, now_naive)
        if not kami.bind_uuid:
            kami.bind_uuid = uuid if uuid else fingerprint
    elif machine_bind_mode == MachineBindMode.one_card_one_device:
        current_uuid = _device_uuid(uuid, fingerprint)
        if not kami.bind_uuid:
            _upsert_device(session, app_id, uuid, fingerprint, client_ip)
            kami.bind_uuid = current_uuid
            kami.bind_ip = client_ip or None
            redis_client.hset(f"device_bind:{kami_code}", mapping={
                "uuid": current_uuid,
                "fingerprint": fingerprint,
            })
            redis_client.expire(f"device_bind:{kami_code}", 86400 * 365)
        elif kami.bind_uuid not in {current_uuid, fingerprint}:
            device = session.exec(
                select(Device).where(
                    Device.app_id == app_id,
                    Device.fingerprint == fingerprint,
                )
            ).first()
            if not device or device.uuid != kami.bind_uuid:
                response_data = {"success": False, "message": "设备未注册或绑定不匹配"}
                return encrypt_response(response_data, app_info.get("app_secret", ""))

    ip_lock_enabled = _config_bool(verify_config, "ip_lock_enabled", app.ip_lock_enabled)
    if ip_lock_enabled and kami.bind_ip and client_ip and kami.bind_ip != client_ip:
        response_data = {"success": False, "message": "IP 不匹配，禁止在其他网络环境使用"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    if kami.status == KamiStatus.unused:
        kami.activate_time = now_naive
        kami.expire_time = calculate_expire_time(kami.kami_type)
        kami.status = KamiStatus.active

    times_error = _consume_times_if_needed(kami, amount=amount)
    if times_error:
        _record_event_log(
            session, app_id, kami_code, "consume", client_ip, uuid, user_agent,
            status=0, message=times_error["message"], payload={"biz_id": biz_id, "amount": amount}
        )
        return encrypt_response(times_error, app_info.get("app_secret", ""))

    consume_id = f"tc_{uuid_lib.uuid4().hex[:16]}"
    app.api_call_count += 1
    session.add(kami)
    session.add(app)
    session.commit()

    response_data = {
        "success": True,
        "message": "核销成功",
        "consume_id": consume_id,
        "biz_id": biz_id,
        "amount": amount,
        "idempotent": False,
        "kami_type": kami.kami_type.value,
        "authorization_owner": kami.authorization_owner.value
        if hasattr(kami.authorization_owner, "value")
        else kami.authorization_owner,
        "user_bind_mode": kami.user_bind_mode.value
        if hasattr(kami.user_bind_mode, "value")
        else kami.user_bind_mode,
        "bound_user_id": kami.redeemed_by_user_id,
        "times_total": kami.times_total,
        "times_remaining": kami.times_remaining or 0,
    }
    _record_event_log(
        session, app_id, kami_code, "consume", client_ip, uuid, user_agent,
        status=1, message="核销成功", payload=response_data
    )
    return encrypt_response(response_data, app_info.get("app_secret", ""))


@router.get("/apps/{app_id}/config")
async def get_app_config(
    app_id: str,
    request: Request,
    session: Session = Depends(get_session)
):
    """获取应用公告、版本、更新和核心安全策略。"""
    client_ip = _client_ip_from_request(request)
    user_agent = request.headers.get("user-agent", "")
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        _record_event_log(
            session,
            app_id,
            None,
            "app_config",
            client_ip,
            None,
            user_agent,
            status=0,
            message="应用不存在",
        )
        raise HTTPException(status_code=404, detail="App not found")
    if app.status != 1:
        _record_event_log(
            session,
            app_id,
            None,
            "app_config",
            client_ip,
            None,
            user_agent,
            status=0,
            message="应用已禁用",
        )
        raise HTTPException(status_code=403, detail="App is disabled")
    try:
        require_app_interface_enabled(session, app_id, "sdk.app_config")
    except HTTPException as exc:
        _record_event_log(
            session,
            app_id,
            None,
            "app_config",
            client_ip,
            None,
            user_agent,
            status=0,
            message=f"应用配置接口不可用: {exc.detail}",
        )
        raise

    files = []
    if app.download_url:
        files.append({
            "name": app.name,
            "url": app.download_url,
            "type": app.update_url_type or "direct",
            "note": app.download_note,
        })

    response_data = {
        "success": True,
        "data": {
            "app_id": app.app_id,
            "name": app.name,
            "notice_enabled": app.notice_enabled,
            "notice_title": app.notice_title,
            "notice": app.notice,
            "notice_level": app.notice_level,
            "notice_popup": app.notice_popup,
            "version": app.version,
            "version_info": app.version_info,
            "force_update": app.force_update,
            "update_url": app.update_url,
            "update_url_type": app.update_url_type,
            "download_button_text": app.download_button_text or "立即下载",
            "files": files,
            "security": {
                "signature_required": app.signature_required,
                "nonce_required": app.nonce_required,
                "timestamp_tolerance_seconds": app.timestamp_tolerance_seconds,
                "ip_lock_enabled": app.ip_lock_enabled,
                "allow_unbind": app.allow_unbind,
                "max_unbind_count": app.max_unbind_count,
                "unbind_cooldown_hours": app.unbind_cooldown_hours,
                "unbind_deduct_hours": app.unbind_deduct_hours,
                "unbind_deduct_times": app.unbind_deduct_times,
            },
        }
    }
    _record_event_log(
        session,
        app_id,
        None,
        "app_config",
        client_ip,
        None,
        user_agent,
        status=1,
        message="应用配置读取成功",
        payload={
            "notice_enabled": app.notice_enabled,
            "has_update_url": bool(app.update_url),
            "has_download_url": bool(app.download_url),
            "file_count": len(files),
        },
    )
    return response_data


@router.post("/release-device")
async def release_device(
    request: Request,
    data: dict = Depends(get_decrypted_data),
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
):
    """释放当前设备的在线占用名额，用于软件退出或用户退出登录。"""
    kami_code = data.get("kami")
    uuid = data.get("uuid", "")
    fingerprint = data.get("fingerprint")
    app_info = data.get("_app_info", {})
    app_id = app_info.get("app_id")
    client_ip = _client_ip_from_request(request)
    user_agent = request.headers.get("user-agent", "")

    if not all([kami_code, fingerprint]):
        raise HTTPException(status_code=400, detail="Missing required fields: kami and fingerprint")

    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.status != 1:
        raise HTTPException(status_code=403, detail="App is disabled")

    device_limit_enabled, _device_limit_config = _app_interface_enabled(
        session,
        app_id,
        "sdk.device_limit",
        default_enabled=True,
    )
    if not device_limit_enabled:
        response_data = {
            "success": True,
            "message": "设备限制未开通，无需释放",
            "released": False,
            "current_device_count": 0,
            "max_bind_devices": 0,
        }
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    kami = session.exec(
        select(Kami).where(Kami.kami_code == kami_code, Kami.app_id == app_id)
    ).first()
    if not kami:
        response_data = {"success": False, "message": "卡密不存在"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if kami.status == KamiStatus.frozen:
        response_data = {"success": False, "message": "卡密已被冻结"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    released, current_device_count = _release_current_device_slot(
        session,
        kami,
        uuid,
        fingerprint,
        redis_client,
    )
    if released:
        session.commit()
        _record_event_log(
            session,
            app_id,
            kami_code,
            "release_device",
            client_ip,
            uuid,
            user_agent,
            status=1,
            message="设备名额已释放",
        )

    response_data = {
        "success": True,
        "message": "设备名额已释放" if released else "当前设备没有占用名额",
        "released": released,
        "current_device_count": current_device_count,
        "max_bind_devices": _max_bind_devices(kami),
    }
    return encrypt_response(response_data, app_info.get("app_secret", ""))


@router.post("/unbind")
async def unbind_kami(
    request: Request,
    data: dict = Depends(get_decrypted_data),
    session: Session = Depends(get_session),
    redis_client = Depends(get_redis)
):
    """按应用策略解绑卡密设备绑定。"""
    kami_code = data.get("kami")
    uuid = data.get("uuid", "")
    fingerprint = data.get("fingerprint")
    app_info = data.get("_app_info", {})
    app_id = app_info.get("app_id")
    client_ip = _client_ip_from_request(request)
    user_agent = request.headers.get("user-agent", "")

    if not all([kami_code, fingerprint]):
        raise HTTPException(status_code=400, detail="Missing required fields: kami and fingerprint")

    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.status != 1:
        raise HTTPException(status_code=403, detail="App is disabled")
    unbind_config = require_app_interface_enabled(session, app_id, "sdk.unbind")
    allow_unbind = _config_bool(unbind_config, "allow_unbind", app.allow_unbind)
    max_unbind_count = _config_int(unbind_config, "max_unbind_count", app.max_unbind_count)
    unbind_cooldown_hours = _config_int(unbind_config, "unbind_cooldown_hours", app.unbind_cooldown_hours)
    unbind_deduct_hours = _config_int(unbind_config, "unbind_deduct_hours", app.unbind_deduct_hours)
    unbind_deduct_times = _config_int(unbind_config, "unbind_deduct_times", app.unbind_deduct_times)
    ip_lock_enabled = _config_bool(unbind_config, "ip_lock_enabled", app.ip_lock_enabled)

    kami = session.exec(
        select(Kami).where(Kami.kami_code == kami_code, Kami.app_id == app_id)
    ).first()
    if not kami:
        response_data = {"success": False, "message": "卡密不存在"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if kami.status == KamiStatus.frozen:
        response_data = {"success": False, "message": "卡密已被冻结"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if not allow_unbind:
        response_data = {"success": False, "message": "当前应用不允许解绑"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if not kami.bind_uuid:
        response_data = {"success": True, "message": "卡密当前未绑定设备", "unbind_count": kami.unbind_count}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if uuid and kami.bind_uuid != uuid:
        _record_event_log(session, app_id, kami_code, "unbind", client_ip, uuid, user_agent,
                         status=0, message="解绑设备不匹配")
        response_data = {"success": False, "message": "解绑设备不匹配"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if ip_lock_enabled and kami.bind_ip and client_ip and kami.bind_ip != client_ip:
        _record_event_log(session, app_id, kami_code, "unbind", client_ip, uuid, user_agent,
                         status=0, message="解绑 IP 不匹配")
        response_data = {"success": False, "message": "解绑 IP 不匹配"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    device = session.exec(
        select(Device).where(
            Device.app_id == app_id,
            Device.fingerprint == fingerprint,
        )
    ).first()
    if not device:
        response_data = {"success": False, "message": "设备不存在，无法解绑"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    now_naive = get_now().replace(tzinfo=None)
    if kami.expire_time and now_naive > kami.expire_time:
        response_data = {"success": False, "message": "卡密已过期，无法解绑"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if max_unbind_count and kami.unbind_count >= max_unbind_count:
        response_data = {"success": False, "message": "解绑次数已达上限"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))
    if unbind_cooldown_hours and kami.last_unbind_at:
        next_allowed = kami.last_unbind_at + timedelta(hours=unbind_cooldown_hours)
        if now_naive < next_allowed:
            response_data = {
                "success": False,
                "message": "解绑冷却中",
                "next_allowed_at": to_api_beijing_iso(next_allowed, naive="civil"),
            }
            return encrypt_response(response_data, app_info.get("app_secret", ""))

    if kami.kami_type == KamiType.times and unbind_deduct_times:
        remaining = kami.times_remaining or 0
        if remaining <= unbind_deduct_times:
            response_data = {"success": False, "message": "剩余次数不足，无法解绑"}
            return encrypt_response(response_data, app_info.get("app_secret", ""))
        kami.times_remaining = remaining - unbind_deduct_times
    elif kami.expire_time and unbind_deduct_hours:
        new_expire = kami.expire_time - timedelta(hours=unbind_deduct_hours)
        if new_expire <= now_naive:
            response_data = {"success": False, "message": "剩余时长不足，无法解绑"}
            return encrypt_response(response_data, app_info.get("app_secret", ""))
        kami.expire_time = new_expire

    kami.bind_uuid = None
    kami.bind_ip = None
    kami.unbind_count += 1
    kami.last_unbind_at = now_naive
    session.add(kami)
    session.commit()
    redis_client.delete(f"device_bind:{kami_code}")

    _record_event_log(session, app_id, kami_code, "unbind", client_ip, uuid, user_agent,
                     status=1, message="解绑成功")

    response_data = {
        "success": True,
        "message": "解绑成功",
        "unbind_count": kami.unbind_count,
        "expire_time": to_api_beijing_iso(kami.expire_time, naive="civil"),
        "times_remaining": kami.times_remaining,
    }
    return encrypt_response(response_data, app_info.get("app_secret", ""))


@router.post("/report")
async def report_event(
    background_tasks: BackgroundTasks,
    data: dict = Depends(get_decrypted_data),
    session: Session = Depends(get_session)
):
    """
    行为数据上报接口
    使用 BackgroundTasks 异步写入数据库，保证高并发低延迟（后台落库在独立 session 中完成）。
    """
    kami_code = data.get("kami")
    event_type = data.get("event_type")
    extra_data = data.get("extra_data", {})
    app_info = data.get("_app_info", {})
    app_id = app_info.get("app_id")

    if not all([kami_code, event_type]):
        raise HTTPException(status_code=400, detail="Missing required fields")

    # 验证卡密是否存在
    require_app_interface_enabled(session, app_id, "sdk.report")
    statement = select(Kami).where(Kami.kami_code == kami_code, Kami.app_id == app_id)
    kami = session.exec(statement).first()

    if not kami:
        response_data = {"success": False, "message": "卡密不存在"}
        return encrypt_response(response_data, app_info.get("app_secret", ""))

    # 异步写入数据库（新会话在 save_event_log 内打开）
    background_tasks.add_task(
        save_event_log,
        app_id=app_id,
        kami_code=kami_code,
        event_type=event_type,
        payload=extra_data,
    )

    response_data = {"success": True, "message": "上报成功"}
    return encrypt_response(response_data, app_info.get("app_secret", ""))


def save_event_log(
    app_id: str,
    kami_code: str,
    event_type: str,
    payload: dict,
):
    """
    后台任务：保存事件日志到数据库（自管会话，勿复用请求内的 Depends session）。
    """
    try:
        with Session(engine) as session:
            event_log = EventLog(
                app_id=app_id,
                kami_code=kami_code,
                event_type=event_type,
                payload=json.dumps(payload, ensure_ascii=False)
            )
            session.add(event_log)
            session.commit()
    except Exception:
        logger.exception("保存 SDK 事件日志失败")


def _record_event_log(
    session: Session,
    app_id: str,
    kami_code: Optional[str],
    event_type: str,
    ip_address: Optional[str] = None,
    device_uuid: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: int = 1,
    message: Optional[str] = None,
    payload: Optional[dict] = None
):
    """
    记录事件日志的辅助函数
    
    Args:
        session: 数据库会话
        app_id: 应用ID
        kami_code: 卡密代码（可选）
        event_type: 事件类型
        ip_address: IP地址
        device_uuid: 设备UUID
        user_agent: User-Agent
        status: 状态（1成功，0失败）
        message: 消息描述
        payload: 额外数据
    """
    try:
        event_log = EventLog(
            app_id=app_id,
            kami_code=kami_code,
            event_type=event_type,
            ip_address=ip_address,
            device_uuid=device_uuid,
            user_agent=user_agent,
            status=status,
            message=message,
            payload=json.dumps(payload, ensure_ascii=False) if payload else None
        )
        session.add(event_log)
        session.commit()
    except Exception:
        # 日志记录失败不影响主流程
        logger.exception("记录 SDK 事件日志失败")
