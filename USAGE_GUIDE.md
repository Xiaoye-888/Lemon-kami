# 新版设备指纹使用指南

## 🚀 快速开始

### Python SDK

```python
from lemon_kami import LemonKamiSDK

# 初始化 SDK（设备指纹自动生成）
sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="https://api.example.com"
)

# 查看设备指纹
print(f"设备指纹: {sdk.fingerprint}")
# 输出: ca95b03ea45ea5ed39030240168fbc22ac696619e71965cde5a1cd286fbf988d

# 验证卡密
result = sdk.verify("YOUR_KAMI_CODE")
if result["success"]:
    print("✅ 验证成功")
else:
    print(f"❌ 验证失败: {result['message']}")
```

### JavaScript SDK

```javascript
// 初始化 SDK
const sdk = new LemonKamiSDK({
    appId: 'your_app_id',
    appSecret: 'your_app_secret',
    serverUrl: 'https://api.example.com'
});

// 等待指纹生成（异步）
await new Promise(resolve => setTimeout(resolve, 1000));

// 查看设备指纹
console.log('设备指纹:', sdk.fingerprint);

// 验证卡密
const result = await sdk.verify('YOUR_KAMI_CODE');
if (result.success) {
    console.log('✅ 验证成功');
} else {
    console.log('❌ 验证失败:', result.message);
}
```

---

## 💡 核心特性

### 1. 无需手动管理设备 ID
- ❌ 不再需要处理 `.device_uuid` 文件
- ❌ 不再需要管理 localStorage
- ✅ 设备指纹自动生成和管理

### 2. 高安全性
- 🔒 基于真实硬件信息
- 🔒 SHA256 加密哈希
- 🔒 无法通过修改文件绕过
- 🔒 难以伪造和复制

### 3. 稳定一致
- ✅ 同一设备每次生成相同指纹
- ✅ 跨会话保持一致
- ✅ 不受缓存清理影响

---

## 🔍 设备指纹组成

### Python（桌面应用）

| 信息项 | 说明 | 稳定性 |
|--------|------|--------|
| CPU 架构 | platform.machine() | ⭐⭐⭐⭐⭐ |
| 处理器信息 | platform.processor() | ⭐⭐⭐⭐⭐ |
| 计算机名 | platform.node() | ⭐⭐⭐⭐ |
| 平台信息 | platform.platform() | ⭐⭐⭐⭐ |
| MAC 地址 | 网络适配器地址 | ⭐⭐⭐⭐⭐ |
| 系统唯一ID | MachineGuid/UUID | ⭐⭐⭐⭐⭐ |

### JavaScript（Web 应用）

| 信息项 | 说明 | 稳定性 |
|--------|------|--------|
| 浏览器平台 | navigator.platform | ⭐⭐⭐⭐ |
| User Agent | navigator.userAgent | ⭐⭐⭐ |
| 语言设置 | navigator.language | ⭐⭐⭐⭐ |
| 屏幕分辨率 | screen.width x height | ⭐⭐⭐⭐ |
| Canvas 指纹 | Canvas 渲染结果 | ⭐⭐⭐⭐⭐ |
| WebGL 信息 | GPU 渲染器信息 | ⭐⭐⭐⭐⭐ |
| 硬件并发数 | navigator.hardwareConcurrency | ⭐⭐⭐⭐⭐ |
| 设备内存 | navigator.deviceMemory | ⭐⭐⭐⭐ |

---

## ⚠️ 注意事项

### 何时指纹会变化？

#### Python SDK
- ✅ **正常情况**（指纹不变）：
  - 重启应用
  - 系统更新/补丁
  - 安装新软件
  
- ⚠️ **可能变化**：
  - 更换网卡（MAC 地址改变）
  - 系统重装（MachineGuid 可能改变）
  - 更换主板/CPU

#### JavaScript SDK
- ✅ **正常情况**（指纹不变）：
  - 刷新页面
  - 清除浏览器缓存
  - 关闭/重新打开浏览器
  
- ⚠️ **可能变化**：
  - 更换浏览器
  - 浏览器大版本升级
  - 更改屏幕分辨率
  - 禁用/启用硬件加速
  - 隐私模式 vs 正常模式

---

## 🛠️ 常见问题

### Q1: 如何查看当前设备的指纹？

**Python:**
```python
print(sdk.fingerprint)
```

**JavaScript:**
```javascript
console.log(sdk.fingerprint);
```

### Q2: 可以自定义设备指纹吗？

❌ **不可以**。设备指纹必须基于真实的硬件信息，以确保安全性和一致性。

### Q3: 指纹冲突怎么办？

SHA256 的碰撞概率约为 1/2^256，在实际应用中可视为**零**。如果遇到冲突，请联系技术支持。

### Q4: 虚拟机环境有问题吗？

虚拟机可以使用，但注意：
- ⚠️ 克隆虚拟机会导致相同指纹
- ✅ 建议结合 IP 地址等其他验证方式
- ✅ 在后台管理系统中标记虚拟机设备

### Q5: 用户更换硬件后如何处理？

1. 联系管理员解绑旧设备
2. 使用新设备重新激活卡密
3. 或在后台管理系统中手动更新设备绑定

### Q6: 如何测试指纹生成？

**Python:**
```bash
python test_device_fingerprint.py
```

**JavaScript:**
打开 `sdk/js_sdk/js_example.html` 在浏览器中查看

---

## 📊 调试技巧

### Python - 查看详细硬件信息

```python
import platform
import json

info = {
    "machine": platform.machine(),
    "processor": platform.processor(),
    "node": platform.node(),
    "platform": platform.platform(),
}

print(json.dumps(info, indent=2))
```

### JavaScript - 查看浏览器信息

```javascript
const info = {
    platform: navigator.platform,
    userAgent: navigator.userAgent,
    language: navigator.language,
    screen: `${screen.width}x${screen.height}`,
    cores: navigator.hardwareConcurrency,
    memory: navigator.deviceMemory
};

console.table(info);
```

---

## 🔐 安全最佳实践

### 1. 保护 App Secret
```python
# ❌ 错误：硬编码在代码中
sdk = LemonKamiSDK(
    app_id="app_123",
    app_secret="secret_456"  # 不要这样做！
)

# ✅ 正确：从环境变量读取
import os
sdk = LemonKamiSDK(
    app_id=os.getenv("APP_ID"),
    app_secret=os.getenv("APP_SECRET")
)
```

### 2. 错误处理
```python
try:
    result = sdk.verify(kami_code)
    if not result["success"]:
        print(f"验证失败: {result['message']}")
except Exception as e:
    print(f"网络错误: {e}")
```

### 3. 定期心跳
```python
import time

while True:
    result = sdk.heartbeat(kami_code)
    if not result["success"]:
        print("心跳异常，请检查网络")
        break
    time.sleep(300)  # 每5分钟
```

---

## 📞 技术支持

如遇到问题，请提供以下信息：

1. **SDK 版本**
   ```python
   # Python
   import lemon_kami
   print(lemon_kami.__version__)
   ```

2. **设备指纹**（前16位）
   ```python
   print(sdk.fingerprint[:16])
   ```

3. **错误信息**
   - 完整的错误堆栈
   - 操作步骤
   - 预期行为 vs 实际行为

4. **环境信息**
   ```python
   # Python
   import platform
   print(platform.platform())
   
   # JavaScript
   console.log(navigator.userAgent);
   ```

---

## 🎓 进阶阅读

- [设备指纹升级详细说明](DEVICE_FINGERPRINT_UPGRADE.md)
- [升级完成总结](UPGRADE_SUMMARY.md)
- [Python SDK API 文档](sdk/python_sdk/README.md)

---

**最后更新**: 2026-04-27  
**文档版本**: v2.0.0
