"""
生成适合 Docker .env 文件的单行 RSA 密钥配置
"""
from crypto import RSACrypto

# 生成密钥对
key_pair = RSACrypto.generate_key_pair()

# 转换为真正的单行（用 \n 字符串替换换行符）
private_key_env = key_pair['private_key'].replace('\n', '\\n')
public_key_env = key_pair['public_key'].replace('\n', '\\n')

# 写入文件
with open('login_keys.env', 'w', encoding='utf-8') as f:
    f.write("# 登录加密 RSA 密钥对（单行格式，适合 Docker .env）\n")
    f.write(f"LOGIN_RSA_PRIVATE_KEY={private_key_env}\n\n")
    f.write(f"LOGIN_RSA_PUBLIC_KEY={public_key_env}\n")

print("✅ 已生成 login_keys.env 文件")
print("\n请将以下内容复制到服务器的 .env 文件中：")
print("=" * 80)
with open('login_keys.env', 'r', encoding='utf-8') as f:
    print(f.read())
print("=" * 80)
