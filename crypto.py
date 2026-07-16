"""
加密工具模块
包含 RSA、AES、HMAC-SHA256 等加密算法实现
"""

import base64
import hashlib
import hmac
import os
import json
import logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# 获取日志记录器
logger = logging.getLogger("lemon_kami.crypto")


class RSACrypto:
    """RSA 加密解密工具类"""

    @staticmethod
    def generate_key_pair():
        """生成 RSA 密钥对"""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        # 序列化私钥
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # 序列化公钥
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return {
            "private_key": private_pem.decode('utf-8'),
            "public_key": public_pem.decode('utf-8')
        }

    @staticmethod
    def encrypt_with_public_key(data: bytes, public_key_pem: str) -> bytes:
        """使用公钥加密数据"""
        public_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )

        encrypted_data = public_key.encrypt(
            data,
            padding.PKCS1v15()
        )
        return encrypted_data

    @staticmethod
    def decrypt_with_private_key(encrypted_data: bytes, private_key_pem: str) -> bytes:
        """使用私钥解密数据（支持 PKCS1v15 和 OAEP）"""
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )

        # 先尝试 OAEP (Web Crypto API 默认使用)
        try:
            decrypted_data = private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            logger.debug(f"RSA 解密成功 (OAEP), 密钥长度: {len(decrypted_data)} 字节")
            return decrypted_data
        except Exception as e:
            logger.debug(f"OAEP 解密失败: {e}")
            # 如果失败，尝试 PKCS1v15 (Python pycryptodome 默认使用)
            try:
                decrypted_data = private_key.decrypt(
                    encrypted_data,
                    padding.PKCS1v15()
                )
                logger.debug(f"RSA 解密成功 (PKCS1v15), 密钥长度: {len(decrypted_data)} 字节")
                return decrypted_data
            except Exception as e2:
                logger.error(f"PKCS1v15 解密也失败: {e2}")
                raise


class AESCrypto:
    """AES 加密解密工具类 (AES-256-CBC)"""

    @staticmethod
    def generate_key() -> bytes:
        """生成 16 位随机 AES 密钥"""
        return os.urandom(16)

    @staticmethod
    def encrypt(data: bytes, key: bytes) -> dict:
        """
        AES 加密
        返回包含 iv 和 ciphertext 的字典
        """
        if len(key) != 16:
            raise ValueError("AES key must be 16 bytes")

        # 生成随机 IV
        iv = os.urandom(16)

        # 填充数据 (PKCS7)
        pad_len = 16 - (len(data) % 16)
        padded_data = data + bytes([pad_len] * pad_len)

        # 加密
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        return {
            "iv": base64.b64encode(iv).decode('utf-8'),
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8')
        }

    @staticmethod
    def decrypt(iv_b64: str, ciphertext_b64: str, key: bytes) -> bytes:
        """AES 解密"""
        if len(key) != 16:
            raise ValueError("AES key must be 16 bytes")

        iv = base64.b64decode(iv_b64)
        ciphertext = base64.b64decode(ciphertext_b64)

        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        # 使用 cryptography 库的 unpad 函数去除 PKCS7 填充
        from cryptography.hazmat.primitives import padding
        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()
        
        logger.debug(f"AES 去填充后数据长度: {len(data)} 字节")

        return data


class HMACSigner:
    """HMAC-SHA256 签名工具类"""

    @staticmethod
    def generate_sign(data: str, secret: str) -> str:
        """生成 HMAC-SHA256 签名"""
        sign = hmac.new(
            secret.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return sign

    @staticmethod
    def verify_sign(data: str, secret: str, sign: str) -> bool:
        """验证签名"""
        expected_sign = HMACSigner.generate_sign(data, secret)
        return hmac.compare_digest(expected_sign, sign)


class CryptoHelper:
    """加密辅助类，整合 RSA + AES 混合加密流程"""

    @staticmethod
    def encrypt_payload(data: dict, public_key_pem: str) -> dict:
        """
        混合加密：AES 加密数据 + RSA 加密 AES 密钥
        
        Args:
            data: 要加密的业务数据（字典）
            public_key_pem: RSA 公钥
            
        Returns:
            包含 encrypted_key 和 encrypted_data 的字典
        """
        # 1. 将数据转为 JSON 字符串
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')

        # 2. 生成随机 AES 密钥
        aes_key = AESCrypto.generate_key()

        # 3. 使用 AES 加密数据
        aes_result = AESCrypto.encrypt(json_data, aes_key)

        # 4. 使用 RSA 公钥加密 AES 密钥的 Base64 表示，与前端 JSEncrypt 协议保持一致
        aes_key_b64 = base64.b64encode(aes_key)
        encrypted_aes_key = RSACrypto.encrypt_with_public_key(aes_key_b64, public_key_pem)

        return {
            "encrypted_key": base64.b64encode(encrypted_aes_key).decode('utf-8'),
            "encrypted_data": aes_result["ciphertext"],
            "iv": aes_result["iv"]
        }

    @staticmethod
    def decrypt_payload(
        encrypted_key_b64: str,
        encrypted_data: str,
        iv: str,
        private_key_pem: str
    ) -> dict:
        """
        混合解密：RSA 解密 AES 密钥 + AES 解密数据
        
        Args:
            encrypted_key_b64: Base64 编码的 RSA 加密后的 AES 密钥
            encrypted_data: AES 加密后的数据（ciphertext）
            iv: AES 初始化向量
            private_key_pem: RSA 私钥
            
        Returns:
            解密后的业务数据（字典）
        """
        # 1. 使用 RSA 私钥解密 AES 密钥
        encrypted_aes_key = base64.b64decode(encrypted_key_b64)
        logger.debug(f"开始解密请求数据")
        logger.debug(f"接收到的 encrypted_key 长度: {len(encrypted_aes_key)} 字节")
        
        aes_key_decoded = RSACrypto.decrypt_with_private_key(encrypted_aes_key, private_key_pem)
        logger.debug(f"RSA 解密后的数据长度: {len(aes_key_decoded)} 字节")
        
        # JSEncrypt 加密前我们将二进制数据转为了 Base64 字符串
        # 所以 RSA 解密后得到的是 Base64 字符串的 bytes，需要再次解码
        try:
            aes_key_base64_str = aes_key_decoded.decode('utf-8')
            logger.debug(f"UTF-8 解码后的 Base64 字符串长度: {len(aes_key_base64_str)}")
            
            # Base64 解码得到原始 16 字节密钥
            aes_key = base64.b64decode(aes_key_base64_str)
            logger.debug(f"二次 Base64 解码后的 aes_key 长度: {len(aes_key)} 字节")
        except Exception as e:
            logger.error(f"AES 密钥解码失败: {e}")
            raise
        
        # 验证 AES 密钥长度
        if len(aes_key) != 16:
            raise ValueError(f"AES key must be 16 bytes, got {len(aes_key)} bytes")
        
        logger.debug("AES 密钥验证通过: 16 字节")

        # 2. 使用 AES 密钥解密数据
        decrypted_data = AESCrypto.decrypt(iv, encrypted_data, aes_key)
        
        logger.debug(f"AES 解密成功，数据长度: {len(decrypted_data)} 字节")

        # 3. 解析 JSON
        return json.loads(decrypted_data.decode('utf-8'))

    @staticmethod
    def aes_encrypt(data: dict, key_b64: str) -> dict:
        """
        纯 AES 加密（用于登录）
        
        Args:
            data: 要加密的业务数据（字典）
            key_b64: Base64 编码的 AES 密钥（16 字节）
            
        Returns:
            包含 encrypted_data 和 iv 的字典
        """
        # 解码 Base64 密钥
        key = base64.b64decode(key_b64)
        if len(key) != 16:
            raise ValueError(f"AES key must be 16 bytes, got {len(key)} bytes")
        
        # 将数据转为 JSON 字符串
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        
        # 使用 AES 加密
        result = AESCrypto.encrypt(json_data, key)
        
        return {
            "encrypted_data": result["ciphertext"],
            "iv": result["iv"]
        }
    
    @staticmethod
    def aes_decrypt(encrypted_data: str, key_b64: str, iv: str) -> dict:
        """
        纯 AES 解密（用于登录）
        
        Args:
            encrypted_data: AES 加密后的数据（ciphertext，Base64）
            key_b64: Base64 编码的 AES 密钥（16 字节）
            iv: AES 初始化向量（Base64）
            
        Returns:
            解密后的业务数据（字典）
        """
        # 解码 Base64 密钥
        key = base64.b64decode(key_b64)
        if len(key) != 16:
            raise ValueError(f"AES key must be 16 bytes, got {len(key)} bytes")
        
        # 使用 AES 解密
        decrypted_data = AESCrypto.decrypt(iv, encrypted_data, key)
        
        # 解析 JSON
        return json.loads(decrypted_data.decode('utf-8'))
