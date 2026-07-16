# 🔐 设备指纹安全升级 - 快速参考

## 📌 一句话总结
**移除了易被篡改的设备 UUID 缓存文件，改为基于硬件信息动态生成 SHA256 设备指纹。**

---

## ✅ 核心改进

| 项目 | 之前 | 现在 |
|------|------|------|
| **存储方式** | `.device_uuid` 文件 / localStorage | 无缓存，动态生成 |
| **安全性** | ❌ 低（可篡改） | ✅ 高（难以伪造） |
| **一致性** | ⚠️ 依赖文件存在 | ✅ 基于硬件信息 |
| **加密** | ❌ 明文 UUID | ✅ SHA256 哈希 |

---

## 🚀 快速使用

### Python
```python
from lemon_kami import LemonKamiSDK

sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="https://api.example.com"
)

# 设备指纹自动生成，无需额外操作
result = sdk.verify("YOUR_KAMI_CODE")
```

### JavaScript
```javascript
const sdk = new LemonKamiSDK({
    appId: 'your_app_id',
    appSecret: 'your_app_secret',
    serverUrl: 'https://api.example.com'
});

// 等待指纹生成
await new Promise(r => setTimeout(r, 1000));

const result = await sdk.verify('YOUR_KAMI_CODE');
```

---

## 🔍 指纹组成

### Python（桌面应用）
- CPU 信息（machine, processor）
- 计算机名（node）
- 平台信息（platform）
- MAC 地址列表
- 系统唯一ID（MachineGuid/UUID/machine-id）

### JavaScript（Web 应用）
- 浏览器信息（platform, userAgent, language）
- 屏幕信息（resolution, colorDepth, pixelRatio）
- Canvas 指纹
- WebGL 渲染器信息
- 硬件信息（cores, memory）

---

## ⚠️ Breaking Changes

### 移除的属性
- ❌ Python: `sdk.device_uuid`
- ❌ JavaScript: `sdk.deviceUuid`

### 保留的属性
- ✅ Python: `sdk.fingerprint` （功能增强）
- ✅ JavaScript: `sdk.fingerprint` （功能增强）

---

## 🛠️ 迁移步骤

1. **更新 SDK 文件**
   ```bash
   # Python
   pip install --upgrade lemon-kami-sdk
   
   # JavaScript - 替换 lemon-kami.js 文件
   ```

2. **更新代码**（如果使用了 device_uuid）
   ```python
   # 旧代码
   print(sdk.device_uuid)
   
   # 新代码
   print(sdk.fingerprint)
   ```

3. **清理缓存**（可选）
   ```bash
   rm .device_uuid  # 删除旧的缓存文件
   ```

---

## 📊 测试结果

```
✅ 三次指纹生成一致: ca95b03ea45ea5ed...
✅ 指纹长度: 64 位（SHA256）
✅ 指纹格式: 十六进制字符串
✅ 未发现缓存文件
```

---

## 🔐 安全提升

### 攻击难度对比

| 攻击方式 | 之前 | 现在 |
|----------|------|------|
| 修改文件绕过 | ⭐ 极易 | ❌ 不可能 |
| 复制他人身份 | ⭐ 极易 | ⭐⭐⭐⭐⭐ 极难 |
| 重置设备绑定 | ⭐ 容易 | ❌ 不可能 |
| 伪造设备指纹 | ⭐⭐ 中等 | ⭐⭐⭐⭐⭐ 极难 |

---

## 📞 需要帮助？

查看详细文档：
- 📘 [使用说明](USAGE_GUIDE.md)
- 📗 [升级说明](DEVICE_FINGERPRINT_UPGRADE.md)
- 📙 [完整总结](UPGRADE_SUMMARY.md)

---

**版本**: v2.0.0  
**更新日期**: 2026-04-27  
**状态**: ✅ 已完成并测试通过
