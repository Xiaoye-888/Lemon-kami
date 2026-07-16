"""
生成登录用的 RSA 密钥对
"""
from crypto import RSACrypto
import os

# 生成密钥对
key_pair = RSACrypto.generate_key_pair()

print("=" * 80)
print("RSA 密钥对生成成功！")
print("=" * 80)
print("\n请将以下配置添加到 .env 文件中：\n")
print("# 登录加密 RSA 密钥对")
print(f"LOGIN_RSA_PRIVATE_KEY=\"\"\"{key_pair['private_key']}\"\"\"")
print()
print(f"LOGIN_RSA_PUBLIC_KEY=\"\"\"{key_pair['public_key']}\"\"\"")
print("\n" + "=" * 80)
print("注意：")
print("1. 私钥必须保密，不要泄露")
print("2. 公钥可以公开，前端会使用它来加密登录信息")
print("3. 将上面的配置复制到 .env 文件中")
print("=" * 80)
