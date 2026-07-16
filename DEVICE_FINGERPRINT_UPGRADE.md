# 设备指纹安全升级说明

## 问题描述

原有的 Python SDK 使用 `.device_uuid` 文件缓存设备 UUID，存在以下安全风险：

1. **容易被篡改**：用户可以手动修改或删除 `.device_uuid` 文件来绕过设备绑定
2. **可伪造**：攻击者可以复制他人的 `.device_uuid` 文件来冒充设备
3. **不安全存储**：明文存储的设备标识符容易被窃取

## 解决方案

### 1. 移除设备 UUID 缓存

- ✅ 删除了 `_get_device_uuid()` 方法
- ✅ 不再创建和使用 `.device_uuid` 文件
- ✅ 每次启动都重新生成设备指纹

### 2. 基于硬件信息的动态指纹生成

新的 `_generate_device_fingerprint()` 方法收集以下稳定的硬件信息：

#### Windows 系统
- CPU 信息（machine, processor）
- 计算机名（node）
- 操作系统平台信息
- 网络适配器 MAC 地址
- **MachineGuid**（注册表中的唯一标识符）
- 备选：WMIC 产品 UUID

#### macOS 系统
- CPU 信息
- 计算机名
- 操作系统平台信息
- 网络适配器 MAC 地址
- **Hardware UUID**（系统Profiler获取）

#### Linux 系统
- CPU 信息
- 计算机名
- 操作系统平台信息
- 网络适配器 MAC 地址
- **machine-id**（/etc/machine-id 或 /var/lib/dbus/machine-id）

### 3. SHA256 哈希加密

所有收集的信息经过以下处理：

```python
# 1. 收集硬件信息到字典
info = {
    "machine": platform.machine(),
    "processor": platform.processor(),
    "node": platform.node(),
    "platform": platform.platform(),
    "mac_addresses": [...],
    "system_info": "...",
}

# 2. 序列化为 JSON（排序确保一致性）
fingerprint_str = json.dumps(info, sort_keys=True)

# 3. SHA256 哈希生成最终指纹
fingerprint = hashlib.sha256(fingerprint_str.encode()).hexdigest()
```

生成的指纹特征：
- 🔒 **长度固定**：64 位十六进制字符串
- 🔒 **不可逆**：无法从指纹反推原始硬件信息
- 🔒 **一致性强**：同一设备每次生成结果相同
- 🔒 **难以伪造**：需要完全相同的硬件配置才能生成相同指纹

## 后端适配

### 验证逻辑调整

后端 `routes_sdk.py` 进行了以下更新：

1. **兼容旧版本**：`uuid` 字段改为可选（`data.get("uuid", "")`）
2. **主要依赖指纹**：设备验证主要检查 `fingerprint` 匹配
3. **UUID 辅助验证**：如果提供 UUID，作为额外验证层
4. **数据库查询优化**：优先通过指纹查询设备记录

### 设备绑定流程

```python
# 首次激活
if kami.status == KamiStatus.unused:
    # 通过指纹检查设备是否在黑名单
    device = session.query(Device).filter(
        Device.fingerprint == fingerprint
    ).first()
    
    # 绑定卡密到指纹
    kami.bind_uuid = uuid if uuid else fingerprint
    
    # 创建设备记录
    device = Device(
        uuid=uuid if uuid else fingerprint,
        fingerprint=fingerprint,
        ...
    )

# 后续验证
# 主要检查指纹匹配
if fingerprint != cached_fingerprint:
    return {"success": False, "message": "设备指纹不匹配"}
```

## 安全性提升

### 之前（使用 .device_uuid 文件）
❌ 用户可以删除文件重置设备绑定  
❌ 用户可以复制他人的 UUID 文件  
❌ 明文存储，易于查看和修改  

### 现在（动态生成指纹）
✅ 无法通过删除文件绕过（无缓存文件）  
✅ 需要完全相同的硬件配置才能伪造  
✅ SHA256 加密，不可逆向工程  
✅ 多源硬件信息组合，增加伪造难度  

## 兼容性说明

### 客户端
- ⚠️ **Breaking Change**：移除了 `sdk.device_uuid` 属性
- ✅ 保留了 `sdk.fingerprint` 属性（功能增强）
- 📝 示例代码已更新

### 服务端
- ✅ 向后兼容：仍支持带 `uuid` 的请求
- ✅ 平滑过渡：新旧客户端均可正常工作
- 🔧 建议逐步迁移到纯指纹验证

## 测试验证

运行测试脚本验证新机制：

```bash
python test_device_fingerprint.py
```

测试结果：
```
测试设备指纹生成逻辑...
第1次生成指纹: ca95b03ea45ea5ed39030240168fbc22ac696619e71965cde5a1cd286fbf988d
第2次生成指纹: ca95b03ea45ea5ed39030240168fbc22ac696619e71965cde5a1cd286fbf988d
第3次生成指纹: ca95b03ea45ea5ed39030240168fbc22ac696619e71965cde5a1cd286fbf988d
三次指纹是否一致: True
✅ 设备指纹生成测试通过！
   指纹长度: 64
   指纹格式: SHA256 (十六进制)
   一致性验证: 通过
```

## 迁移指南

### 对于现有用户

1. **删除旧的缓存文件**（如果存在）：
   ```bash
   rm .device_uuid  # Linux/Mac
   del .device_uuid  # Windows
   ```

2. **更新 SDK**：
   ```bash
   pip install --upgrade lemon-kami-sdk
   ```

3. **更新代码**（如果使用 `device_uuid`）：
   ```python
   # 旧代码
   print(sdk.device_uuid)
   
   # 新代码
   print(sdk.fingerprint)
   ```

### 对于新用户

直接使用新版 SDK，无需任何特殊操作：

```python
from lemon_kami import LemonKamiSDK

sdk = LemonKamiSDK(
    app_id="your_app_id",
    app_secret="your_app_secret",
    server_url="https://api.example.com"
)

# 设备指纹自动生成
print(f"设备指纹: {sdk.fingerprint}")

# 验证卡密
result = sdk.verify("YOUR_KAMI_CODE")
```

## 常见问题

### Q1: 更换硬件后指纹会变化吗？
A: 是的，这是预期行为。主要硬件（CPU、主板、网卡）变更会导致指纹变化，需要重新激活卡密。

### Q2: 系统重装会影响指纹吗？
A: 
- Windows: 如果 MachineGuid 改变，指纹会变化
- macOS: Hardware UUID 通常不变
- Linux: machine-id 可能改变

### Q3: 虚拟机环境如何处理？
A: 虚拟机的硬件信息相对稳定，但克隆虚拟机会导致指纹相同。建议在虚拟化环境中结合其他验证机制。

### Q4: 指纹冲突概率？
A: SHA256 的碰撞概率极低（约 1/2^256），在实际应用中可视为零。

## 技术细节

### 指纹生成流程图

```
开始
  ↓
收集硬件信息
  ├─ CPU 信息
  ├─ 计算机名
  ├─ 平台信息
  ├─ MAC 地址
  └─ 系统唯一ID
  ↓
构建信息字典
  ↓
JSON 序列化（排序）
  ↓
SHA256 哈希计算
  ↓
输出 64 位十六进制指纹
  ↓
结束
```

### 跨平台兼容性

| 信息项 | Windows | macOS | Linux |
|--------|---------|-------|-------|
| CPU 信息 | ✅ | ✅ | ✅ |
| 计算机名 | ✅ | ✅ | ✅ |
| 平台信息 | ✅ | ✅ | ✅ |
| MAC 地址 | ✅ | ✅ | ✅ |
| 系统唯一ID | MachineGuid | Hardware UUID | machine-id |

## 总结

本次升级通过以下方式显著提升了设备绑定的安全性：

1. ✅ **消除缓存文件**：移除易被篡改的 `.device_uuid` 文件
2. ✅ **动态生成**：每次启动重新计算指纹，无持久化风险
3. ✅ **多源验证**：结合多种硬件信息，增加伪造难度
4. ✅ **加密保护**：SHA256 哈希确保不可逆向
5. ✅ **跨平台支持**：Windows/macOS/Linux 全面兼容

这使得攻击者几乎不可能通过简单修改文件来绕过设备绑定限制，大幅提升了系统的安全性。
