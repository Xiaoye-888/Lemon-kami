"""
Lemon Kami Python SDK
卡密验证客户端 SDK
"""

import json
import time
import uuid
import hashlib
import hmac
import platform
from typing import Optional, Dict, Any
import requests
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5, AES
from Crypto.Util.Padding import pad, unpad
import base64
import os


class LemonKamiSDK:
    """小柠檬网络验证 SDK"""
    
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        server_url: str = "http://localhost:8000",
        rsa_public_key: Optional[str] = None
    ):
        """
        初始化 SDK
        
        Args:
            app_id: 应用ID
            app_secret: 应用密钥
            server_url: 服务器地址
            rsa_public_key: RSA公钥（可选，会自动从服务器获取）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.server_url = server_url.rstrip('/')
        self.rsa_public_key = rsa_public_key
        # 移除设备UUID缓存，每次重新生成设备指纹
        self.fingerprint = self._generate_device_fingerprint()
        
        # 如果未提供公钥，自动获取
        if not self.rsa_public_key:
            self._fetch_public_key()
    
    def _generate_device_fingerprint(self) -> str:
        """
        生成设备指纹（每次都重新计算，不依赖缓存）
        
        使用多种硬件信息组合生成唯一的设备标识符，确保每次执行结果一致且难以伪造
        """
        # 收集稳定的硬件信息
        info = {
            # CPU 信息（最稳定）
            "machine": platform.machine(),
            "processor": platform.processor(),
            # 系统节点名（计算机名）
            "node": platform.node(),
            # 操作系统平台信息
            "platform": platform.platform(),
            # 网络适配器 MAC 地址（最稳定，但需要权限）
            "mac_addresses": self._get_mac_addresses(),
            # 主板序列号或其他唯一标识（如果可用）
            "system_info": self._get_system_unique_id(),
        }
        
        # 生成指纹哈希 - 使用 SHA256 确保一致性
        fingerprint_str = json.dumps(info, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    def _get_system_unique_id(self) -> str:
        """
        获取系统唯一标识符（跨平台兼容）
        
        Returns:
            系统唯一标识符字符串
        """
        try:
            system = platform.system()
            
            if system == "Windows":
                # Windows: 尝试获取机器GUID或产品ID
                import subprocess
                try:
                    # 尝试获取 MachineGuid
                    result = subprocess.run(
                        ['reg', 'query', 'HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if 'MachineGuid' in line:
                                return line.strip().split()[-1]
                except:
                    pass
                    
                try:
                    # 备选方案：获取产品ID
                    result = subprocess.run(
                        ['wmic', 'csproduct', 'get', 'UUID'],
                        capture_output=True, text=True, timeout=5
                    )
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:
                        uuid_val = lines[1].strip()
                        if uuid_val and uuid_val != 'UUID':
                            return uuid_val
                except:
                    pass
                    
            elif system == "Darwin":  # macOS
                # macOS: 获取硬件UUID
                import subprocess
                try:
                    result = subprocess.run(
                        ['system_profiler', 'SPHardwareDataType'],
                        capture_output=True, text=True, timeout=5
                    )
                    for line in result.stdout.split('\n'):
                        if 'Hardware UUID' in line:
                            return line.split(':')[1].strip()
                except:
                    pass
                    
            else:  # Linux
                # Linux: 尝试获取 machine-id
                try:
                    with open('/etc/machine-id', 'r') as f:
                        return f.read().strip()
                except:
                    pass
                    
                # 备选：获取 dbus machine id
                try:
                    with open('/var/lib/dbus/machine-id', 'r') as f:
                        return f.read().strip()
                except:
                    pass
        except:
            pass
        
        # 如果所有方法都失败，返回一个基于平台信息的标识符
        return f"{platform.system()}_{platform.release()}_{platform.machine()}"
    
    def _get_mac_addresses(self) -> list:
        """
        获取网络适配器的 MAC 地址
        
        Returns:
            MAC 地址列表
        """
        import re
        macs = []
        try:
            # Windows
            if platform.system() == "Windows":
                import subprocess
                result = subprocess.run(['getmac'], capture_output=True, text=True)
                # 提取 MAC 地址
                mac_pattern = r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})'
                macs = re.findall(mac_pattern, result.stdout)
            else:
                # Linux/Mac
                import subprocess
                result = subprocess.run(['ifconfig'], capture_output=True, text=True)
                mac_pattern = r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})'
                macs = re.findall(mac_pattern, result.stdout)
        except:
            pass
        
        # 去重并排序，确保顺序一致
        return sorted(list(set(macs)))
    
    def _fetch_public_key(self):
        """从服务器获取RSA公钥"""
        try:
            response = requests.get(
                f"{self.server_url}/api/v1/sdk/public-key",
                params={"app_id": self.app_id},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.rsa_public_key = data.get("public_key")
                
                # 验证公钥是否成功获取
                if not self.rsa_public_key:
                    raise Exception(f"服务器返回的公钥为空: {data}")
            else:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
                
        except requests.exceptions.ConnectionError:
            raise Exception(f"无法连接到服务器: {self.server_url}，请检查服务器是否运行")
        except requests.exceptions.Timeout:
            raise Exception(f"请求超时: {self.server_url}")
        except Exception as e:
            if "获取公钥失败" in str(e):
                raise
            raise Exception(f"获取公钥失败: {e}")
    
    def _encrypt_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        加密数据
        
        使用 RSA + AES 混合加密：
        1. 生成随机 AES 密钥
        2. 用 AES 加密业务数据
        3. 用 RSA 加密 AES 密钥
        4. 返回符合后端格式的字典
        """
        # 验证公钥是否存在
        if not self.rsa_public_key:
            raise Exception("RSA 公钥未初始化，请检查服务器连接或手动指定公钥")
        
        # 生成随机 AES 密钥和 IV (使用 AES-128, 16字节)
        aes_key = os.urandom(16)  # AES-128
        aes_iv = os.urandom(16)
        
        # AES 加密业务数据
        data_json = json.dumps(data, ensure_ascii=False).encode('utf-8')
        cipher_aes = AES.new(aes_key, AES.MODE_CBC, aes_iv)
        encrypted_data = cipher_aes.encrypt(pad(data_json, AES.block_size))
        
        # RSA 加密 AES 密钥
        # 先将 AES 密钥转为 Base64 字符串，再 RSA 加密（与 JS SDK 保持一致）
        aes_key_base64 = base64.b64encode(aes_key).decode('utf-8')
        rsa_key = RSA.import_key(self.rsa_public_key)
        cipher_rsa = PKCS1_v1_5.new(rsa_key)
        encrypted_aes_key = cipher_rsa.encrypt(aes_key_base64.encode('utf-8'))
        
        # 生成时间戳和随机数
        timestamp = int(time.time())
        nonce = hashlib.md5(f"{time.time()}{os.urandom(8).hex()}".encode()).hexdigest()[:16]
        
        # 生成 HMAC-SHA256 签名（与后端保持一致）
        sign_str = f"{timestamp}{nonce}{base64.b64encode(encrypted_data).decode()}"
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # 返回符合后端格式的字典
        return {
            "app_id": self.app_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "sign": signature,
            "encrypted_key": base64.b64encode(encrypted_aes_key).decode(),
            "encrypted_data": base64.b64encode(encrypted_data).decode(),
            "iv": base64.b64encode(aes_iv).decode()
        }
    
    def verify(self, kami_code: str) -> Dict[str, Any]:
        """
        验证卡密
        
        Args:
            kami_code: 卡密代码
            
        Returns:
            验证结果字典
        """
        # 构建请求数据（不再使用 device_uuid，只使用动态生成的 fingerprint）
        request_data = {
            "kami": kami_code,
            "fingerprint": self.fingerprint,
            "_app_info": {
                "app_id": self.app_id
            }
        }
        
        # 加密数据
        encrypted_payload = self._encrypt_data(request_data)
        
        # 发送请求
        try:
            response = requests.post(
                f"{self.server_url}/api/v1/sdk/verify",
                json=encrypted_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                # 检查是否是加密响应
                if result.get("encrypted"):
                    return self._decrypt_response(result)
                return result
            else:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"网络错误: {str(e)}"
            }
    
    def report_event(
        self,
        kami_code: str,
        event_type: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        上报行为事件
        
        Args:
            kami_code: 卡密代码
            event_type: 事件类型（如：login, level_up, purchase等）
            extra_data: 额外数据
            
        Returns:
            上报结果
        """
        request_data = {
            "kami": kami_code,
            "event_type": event_type,
            "extra_data": extra_data or {},
            "_app_info": {
                "app_id": self.app_id
            }
        }
        
        encrypted_payload = self._encrypt_data(request_data)
        
        try:
            response = requests.post(
                f"{self.server_url}/api/v1/sdk/report",
                json=encrypted_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                # 检查是否是加密响应
                if result.get("encrypted"):
                    return self._decrypt_response(result)
                return result
            else:
                return {
                    "success": False,
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"网络错误: {str(e)}"
            }
    
    def heartbeat(self, kami_code: str) -> Dict[str, Any]:
        """
        发送心跳
        
        Args:
            kami_code: 卡密代码
            
        Returns:
            心跳结果
        """
        return self.report_event(kami_code, "heartbeat")

    def release_device(self, kami_code: str) -> Dict[str, Any]:
        """
        释放当前设备占用名额。

        建议在软件正常退出或用户退出登录时调用，用于一机多码/多设备限制场景。
        """
        request_data = {
            "kami": kami_code,
            "fingerprint": self.fingerprint,
            "_app_info": {
                "app_id": self.app_id
            }
        }

        encrypted_payload = self._encrypt_data(request_data)

        try:
            response = requests.post(
                f"{self.server_url}/api/v1/sdk/release-device",
                json=encrypted_payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("encrypted"):
                    return self._decrypt_response(result)
                return result
            return {
                "success": False,
                "message": f"HTTP {response.status_code}: {response.text}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"网络错误: {str(e)}"
            }
    
    def _decrypt_response(self, encrypted_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        解密响应数据
        
        Args:
            encrypted_response: 加密的响应数据
            
        Returns:
            解密后的数据字典
        """
        import hmac as hmac_module
        
        try:
            # 提取加密字段
            timestamp = encrypted_response.get("timestamp")
            nonce = encrypted_response.get("nonce")
            sign = encrypted_response.get("sign")
            encrypted_key_b64 = encrypted_response.get("encrypted_key")
            encrypted_data_b64 = encrypted_response.get("encrypted_data")
            iv_b64 = encrypted_response.get("iv")
            
            if not all([timestamp, nonce, sign, encrypted_key_b64, encrypted_data_b64, iv_b64]):
                raise Exception("响应数据格式错误")
            
            # 验证签名
            sign_str = f"{timestamp}{nonce}{encrypted_data_b64}"
            expected_sign = hmac_module.new(
                self.app_secret.encode('utf-8'),
                sign_str.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac_module.compare_digest(expected_sign, sign):
                raise Exception("响应签名验证失败")
            
            # AES 密钥已经是明文（Base64编码）
            aes_key = base64.b64decode(encrypted_key_b64)
            aes_iv = base64.b64decode(iv_b64)
            encrypted_data = base64.b64decode(encrypted_data_b64)
            
            # AES 解密
            cipher = AES.new(aes_key, AES.MODE_CBC, aes_iv)
            decrypted_padded = cipher.decrypt(encrypted_data)
            
            # 去除填充
            from Crypto.Util.Padding import unpad
            decrypted_data = unpad(decrypted_padded, AES.block_size)
            
            # 解析 JSON
            return json.loads(decrypted_data.decode('utf-8'))
            
        except Exception as e:
            return {
                "success": False,
                "message": f"响应解密失败: {str(e)}"
            }
