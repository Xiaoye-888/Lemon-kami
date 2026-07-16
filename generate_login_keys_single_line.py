"""
将 RSA 密钥转换为单行格式（适合 .env 文件）
"""
from crypto import RSACrypto

# 生成新的密钥对
key_pair = RSACrypto.generate_key_pair()

# 转换为单行（将换行符替换为 \n）
private_key_single_line = key_pair['private_key'].replace('\n', '\\n')
public_key_single_line = key_pair['public_key'].replace('\n', '\\n')

print("=" * 80)
print("RSA 密钥对已转换为单行格式")
print("=" * 80)
print("\n请将以下配置添加到 .env 文件中：\n")
print(f"LOGIN_RSA_PRIVATE_KEY={private_key_single_line}")
print()
print(f"LOGIN_RSA_PUBLIC_KEY={public_key_single_line}")
print("\n" + "=" * 80)
