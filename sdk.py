"""
Lemon Kami Python SDK
提供卡密验证、设备指纹收集、行为上报等功能
"""

import time
import uuid
import hashlib
import platform
import requests
from typing import Optional, Dict, Any
from crypto import CryptoHelper, HMACSigner


class LemonClient:
    """Lemon Kami 客户端"""

    def __init__(
        self,
        host: str,
        app_id: str,
        app_secret: str,
        public_key: str
    ):
        """
        初始化客户端
        
        Args:
            host: API 服务器地址（如 http://localhost:8000）
            app_id: 应用 ID
            app_secret: 应用密钥
            public_key: RSA 公钥（PEM 格式）
        """
        self.host = host.rstrip('/')
        self.app_id = app_id
        self.app_secret = app_secret
        self.public_key = public_key
        self.session = requests.Session()
        # 设置默认超时
        self.timeout = 10

    def _generate_nonce(self) -> str:
        """生成随机 nonce"""
        return uuid.uuid4().hex[:16]

    def _build_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建加密请求体
        
        Args:
            data: 业务数据
            
        Returns:
            加密后的请求体
        """
        timestamp = int(time.time())
        nonce = self._generate_nonce()

        # 使用混合加密
        encrypted = CryptoHelper.encrypt_payload(data, self.public_key)

        # 生成签名
        sign_data = f"{timestamp}{nonce}{encrypted['encrypted_data']}{self.app_secret}"
        sign = HMACSigner.generate_sign(sign_data, self.app_secret)

        return {
            "app_id": self.app_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": sign,
            "encrypted_key": encrypted["encrypted_key"],
            "encrypted_data": encrypted["encrypted_data"],
            "iv": encrypted["iv"]
        }

    def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送 POST 请求
        
        Args:
            endpoint: API 端点
            data: 业务数据
            
        Returns:
            响应 JSON
        """
        request_body = self._build_request(data)
        url = f"{self.host}{endpoint}"

        try:
            response = self.session.post(
                url,
                json=request_body,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")

    @staticmethod
    def get_device_fingerprint() -> str:
        """
        收集设备指纹信息并生成 Hash
        
        Returns:
            设备指纹字符串
        """
        # 收集系统信息
        system_info = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "node": platform.node(),
        }

        # 尝试获取 MAC 地址
        mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                                for elements in range(0, 2 * 6, 2)][::-1])

        # 组合所有信息
        fingerprint_data = f"{system_info}{mac_address}"

        # 生成 SHA256 Hash
        fingerprint = hashlib.sha256(fingerprint_data.encode('utf-8')).hexdigest()

        return fingerprint

    def verify_kami(
        self,
        kami: str,
        uuid: Optional[str] = None,
        fingerprint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        验证卡密
        
        Args:
            kami: 卡密代码
            uuid: 设备 UUID（可选，不传则自动生成）
            fingerprint: 设备指纹（可选，不传则自动收集）
            
        Returns:
            验证结果，包含 success、message、expire_time 等字段
        """
        if not uuid:
            uuid = hashlib.md5(f"{platform.node()}_{platform.machine()}".encode()).hexdigest()

        if not fingerprint:
            fingerprint = self.get_device_fingerprint()

        data = {
            "kami": kami,
            "uuid": uuid,
            "fingerprint": fingerprint
        }

        result = self._post("/api/v1/sdk/verify", data)
        return result

    def report_event(
        self,
        kami: str,
        event_type: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上报行为事件
        
        Args:
            kami: 卡密代码
            event_type: 事件类型（如 login, level_up）
            extra_data: 额外的业务数据
            
        Returns:
            上报结果
        """
        data = {
            "kami": kami,
            "event_type": event_type,
            "extra_data": extra_data or {}
        }

        result = self._post("/api/v1/sdk/report", data)
        return result


# 导出便捷函数
def create_client(
    host: str,
    app_id: str,
    app_secret: str,
    public_key: str
) -> LemonClient:
    """
    创建 LemonClient 实例的便捷函数
    
    Usage:
        client = create_client(
            host="http://localhost:8000",
            app_id="your_app_id",
            app_secret="your_app_secret",
            public_key="-----BEGIN PUBLIC KEY-----\n..."
        )
    """
    return LemonClient(host, app_id, app_secret, public_key)
