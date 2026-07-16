# 登录加密部署指南

本文只说明部署步骤，不保存任何真实密钥、服务器地址或生产凭据。

## 1. 生成登录 AES 密钥

在部署机器或安全的本地环境执行：

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(16)).decode())"
```

将输出值写入服务器 `.env`：

```env
LOGIN_AES_KEY=<base64-16-byte-aes-key>
```

## 2. 配置首次管理员密码

首次部署时显式配置引导密码：

```env
BOOTSTRAP_ADMIN_PASSWORD=<strong-initial-admin-password>
```

系统只会在不存在 `admin` 用户时使用该值创建首个管理员。完成首次登录后应立即轮换密码，并从运行环境中移除或清空该引导变量。

## 3. 重启服务

更新环境变量后重启后端服务，并确认接口可用：

```bash
curl http://127.0.0.1:8000/api/v1/admin/login/public-key
```

返回中应包含 `success: true` 和 `aes_key`。

## 4. 安全要求

- 不要把 `.env`、生成出的密钥文件、`*.pem` 或 `*.key` 提交到仓库。
- 不要在日志中打印登录请求体、解密后的账号密码或 AES 密钥。
- 生产环境应通过密钥管理系统、容器 Secret 或服务器环境变量注入密钥。
