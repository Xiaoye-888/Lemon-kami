# 登录加密部署指南

本文只说明部署步骤，不保存任何真实私钥、服务器地址或生产凭据。

## 1. 生成登录密钥

在部署机器或安全的本地环境执行：

```bash
python generate_login_keys_single_line.py
```

将输出中的 `LOGIN_RSA_PRIVATE_KEY` 和 `LOGIN_RSA_PUBLIC_KEY` 写入服务器 `.env`。私钥只能保存到运行环境的密钥配置中，不要提交到代码仓库。

## 2. 配置 .env

示例：

```env
LOGIN_RSA_PRIVATE_KEY=<single-line-private-key>
LOGIN_RSA_PUBLIC_KEY=<single-line-public-key>
LOGIN_AES_KEY=<base64-16-byte-aes-key>
```

`LOGIN_AES_KEY` 可用以下命令生成：

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(16)).decode())"
```

## 3. 重启服务

更新环境变量后重启后端服务，并确认接口可用：

```bash
curl http://127.0.0.1:8000/api/v1/admin/login/public-key
```

返回中应包含 `success: true` 和 `aes_key`。

## 4. 安全要求

- 不要把生成出的 `login_keys*.env`、`login_keys*.txt`、`*.pem` 或 `*.key` 提交到仓库。
- 不要在日志中打印登录请求体、解密后的账号密码、RSA 私钥或 AES 密钥。
- 生产环境应通过密钥管理系统、容器 Secret 或服务器环境变量注入密钥。
