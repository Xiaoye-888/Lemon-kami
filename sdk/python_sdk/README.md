# Lemon Kami Python SDK

小柠檬网络验证官方 Python SDK，提供卡密验证、事件上报、设备绑定等功能。

## 功能特性

- ✅ RSA + AES 混合加密通信
- ✅ 自动设备指纹生成与绑定
- ✅ 卡密验证与激活
- ✅ 行为事件上报
- ✅ 心跳保持
- ✅ 防重放攻击

## 安装

```bash
pip install lemon-kami-sdk
```

## 快速开始

```python
from lemon_kami import LemonKamiSDK

# 初始化 SDK
sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="http://localhost:8000"  # 替换为您的服务器地址
)

# 验证卡密
result = sdk.verify("YOUR_KAMI_CODE")
if result["success"]:
    print("✅ 验证成功")
    print(f"卡密类型: {result['kami_type']}")
    print(f"到期时间: {result['expire_time']}")
else:
    print(f"❌ 验证失败: {result['message']}")

# 上报事件
sdk.report_event("YOUR_KAMI_CODE", "login", {"username": "test_user"})

# 发送心跳
sdk.heartbeat("YOUR_KAMI_CODE")
```

## API 文档

### 初始化

```python
sdk = LemonKamiSDK(
    app_id: str,              # 应用ID（必填）
    app_secret: str,          # 应用密钥（必填）
    server_url: str,          # 服务器地址（可选，默认 http://localhost:8000）
    rsa_public_key: str       # RSA公钥（可选，会自动从服务器获取）
)
```

### verify(kami_code: str) -> Dict

验证卡密有效性。

**参数：**
- `kami_code`: 卡密代码

**返回：**
```python
{
    "success": True,
    "kami_type": "month",
    "expire_time": "2026-05-23 12:00:00",
    "device_uuid": "xxx",
    "message": "验证成功"
}
```

### report_event(kami_code, event_type, extra_data=None) -> Dict

上报行为事件。

**参数：**
- `kami_code`: 卡密代码
- `event_type`: 事件类型（如：login, level_up, purchase）
- `extra_data`: 额外数据字典（可选）

**返回：**
```python
{
    "success": True,
    "message": "事件上报成功"
}
```

### heartbeat(kami_code: str) -> Dict

发送心跳（内部调用 report_event）。

**参数：**
- `kami_code`: 卡密代码

**返回：** 同 report_event

## 高级用法

### 自定义服务器地址

```python
sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="https://api.yourdomain.com"
)
```

### 手动指定公钥

```python
sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="http://localhost:8000",
    rsa_public_key="-----BEGIN PUBLIC KEY-----\n..."
)
```

### 完整示例

```python
import time
from lemon_kami import LemonKamiSDK

# 初始化
sdk = LemonKamiSDK(
    app_id="app_123456",
    app_secret="secret_xxxxxx",
    server_url="https://api.example.com"
)

# 验证卡密
kami_code = "KAMI-XXXX-XXXX-XXXX"
result = sdk.verify(kami_code)

if not result["success"]:
    print(f"验证失败: {result['message']}")
    exit(1)

print(f"✅ 验证成功！")
print(f"卡密类型: {result['kami_type']}")
print(f"到期时间: {result['expire_time']}")

# 用户登录时上报事件
sdk.report_event(kami_code, "login", {
    "username": "user123",
    "ip": "192.168.1.1"
})

# 定期发送心跳
while True:
    hb_result = sdk.heartbeat(kami_code)
    if hb_result["success"]:
        print("❤️  心跳正常")
    else:
        print(f"⚠️  心跳异常: {hb_result['message']}")
    
    time.sleep(300)  # 每5分钟发送一次
```

## 错误处理

```python
try:
    result = sdk.verify(kami_code)
    if not result["success"]:
        print(f"验证失败: {result['message']}")
except Exception as e:
    print(f"网络错误: {e}")
```

## 设备指纹

SDK 会自动生成基于硬件信息的设备指纹，每次启动时都会重新计算，确保安全性。
设备指纹由以下信息组合生成：
- CPU 信息（machine, processor）
- 系统节点名（计算机名）
- 操作系统平台信息
- 网络适配器 MAC 地址
- 系统唯一标识符（如 Windows MachineGuid、macOS Hardware UUID、Linux machine-id）

所有信息经过 SHA256 哈希处理，生成唯一的设备标识符，难以伪造且每次执行结果一致。

## 安全说明

- 所有通信均采用 RSA-2048 + AES-256-CBC 加密
- 请求包含时间戳和随机数，防止重放攻击
- 每个请求都有 HMAC-SHA256 签名验证
- 请勿在客户端代码中硬编码 `app_secret`

## 依赖

- requests >= 2.31.0
- pycryptodome >= 3.19.0

## 许可证

MIT License

## 支持

如有问题或建议，请访问：
- GitHub: https://github.com/yourusername/lemon-kami
- Email: support@example.com
