# Lemon Kami JavaScript SDK

小柠檬网络验证 JavaScript SDK，用于 Web 应用的卡密验证、设备绑定和行为上报。

## 📁 项目结构

```
js_sdk/
├── README.md                    # 本文档
├── package.json                 # NPM 包配置
├── js_example.html             # 完整示例页面
├── lemon-kami-complete.js      # ✅ 推荐 - 完整可读版本
├── lemon-kami.js               # ✅ 浏览器入口版本（与完整版本保持一致）
```

### 📦 文件说明

| 文件 | 类型 | 大小 | 说明 |
|------|------|------|------|
| `lemon-kami-complete.js` | 完整版 | ~12KB | **推荐使用**，代码清晰，易于调试和二次开发 |
| `lemon-kami.js` | 浏览器入口 | ~12KB | 与完整版本保持一致，便于业务直接引用 |
| `js_example.html` | 示例 | ~14KB | 完整的使用示例，包含所有功能演示 |

### 🎯 如何选择？

#### 推荐方式 - 使用 `lemon-kami.js`

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.3.2/jsencrypt.min.js"></script>
<!-- 使用可审计 SDK -->
<script src="lemon-kami.js"></script>
```

**优点：**
- ✅ 代码可读性好
- ✅ 易于调试和排查问题
- ✅ 方便查看源码和修改
- ✅ 体积小，加载快

#### SDK 入口

`lemon-kami-complete.js` 和 `lemon-kami.js` 当前保持同一套可读实现。

### 对接流程

1. 客户端启动后可先请求 `GET /api/v1/sdk/apps/{app_id}/notice` 读取公告，并请求 `GET /api/v1/sdk/apps/{app_id}/updates/check` 检查版本更新。
2. 用户输入卡密后调用 `sdk.verify(kamiCode)`，验证接口只检查授权、激活和绑定，不扣次数。
3. 次数卡在用户实际完成一次业务动作后，业务端再调用 `POST /api/v1/sdk/consume` 扣减次数。
4. 行为、心跳或业务日志使用 `sdk.reportEvent(kamiCode, eventType, extraData)` 上报。

当前 JavaScript SDK 入口只保留 Lemon 命名：`lemon-kami.js` 和 `lemon-kami-complete.js`。

---

## 📦 快速开始

### 1. 安装依赖

在 HTML 中引入必需的库：

```html
<!-- CryptoJS - 用于加密 -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>

<!-- JSEncrypt - 用于 RSA 加密 -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.3.2/jsencrypt.min.js"></script>

<!-- Lemon Kami SDK -->
<script src="lemon-kami.js"></script>
```

### 2. 初始化 SDK

```javascript
const sdk = new LemonKamiSDK({
    appId: 'your_app_id',           // 从后台管理获取
    appSecret: 'your_app_secret',   // 从后台管理获取
    serverUrl: 'http://localhost:8000'  // 服务器地址
});

// 等待公钥和设备指纹加载（约1-2秒）
await new Promise(resolve => setTimeout(resolve, 1500));
```

### 3. 验证卡密

```javascript
const result = await sdk.verify('YOUR_KAMI_CODE');

if (result.success) {
    console.log('✅ 验证成功');
    console.log('卡密类型:', result.kami_type);
    console.log('到期时间:', result.expire_time || '永久');
} else {
    console.log('❌ 验证失败:', result.message);
}
```

### 4. 行为上报

```javascript
// 上报用户行为事件
const result = await sdk.reportEvent(kamiCode, 'login', {
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent
});

if (result.success) {
    console.log('✅ 事件上报成功');
}
```

### 5. 心跳保持

```javascript
// 每30秒发送一次心跳
const heartbeatInterval = setInterval(async () => {
    const result = await sdk.heartbeat(kamiCode);
    
    if (result.success) {
        console.log('💓 心跳成功');
    } else {
        console.log('❌ 心跳失败:', result.message);
    }
}, 30000);

// 停止心跳
clearInterval(heartbeatInterval);
```

---

## 🔧 API 参考

### 构造函数

```javascript
new LemonKamiSDK(options)
```

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| appId | string | ✅ | 应用 ID，从后台管理获取 |
| appSecret | string | ✅ | 应用密钥，从后台管理获取 |
| serverUrl | string | ❌ | 服务器地址，默认 `http://localhost:8000` |
| publicKey | string | ❌ | RSA 公钥（可选，会自动从服务器获取） |

**示例：**

```javascript
const sdk = new LemonKamiSDK({
    appId: 'app_123456',
    appSecret: 'secret_abcdef',
    serverUrl: 'https://api.example.com'
});
```

### verify(kamiCode)

验证卡密有效性。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| kamiCode | string | ✅ | 卡密代码 |

**返回值：** `Promise<Object>`

```javascript
{
    success: true/false,
    message: "验证结果描述",
    kami_type: "month/times/points/lifetime",  // 卡密类型
    expire_time: "2026-12-31 23:59:59",  // 到期时间，永久卡为 null
    times_remaining: 100,  // 次数卡剩余次数
    authorization_owner: "device/user/auto",
    user_bind_mode: "none/auto/required"
}
```

**示例：**

```javascript
try {
    const result = await sdk.verify('KAMI123456');
    
    if (result.success) {
        switch(result.kami_type) {
            case 'time':
                console.log(`计时卡密，到期时间: ${result.expire_time}`);
                break;
            case 'count':
                console.log(`计次卡密，剩余次数: ${result.remaining_count}`);
                break;
            case 'device':
                console.log(`设备卡密，绑定设备: ${result.bound_device}`);
                break;
            case 'unlimited':
                console.log('无限卡密');
                break;
        }
    } else {
        alert('卡密无效: ' + result.message);
    }
} catch (error) {
    console.error('验证异常:', error);
}
```

### reportEvent(kamiCode, eventType, eventData)

上报用户行为事件。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| kamiCode | string | ✅ | 卡密代码 |
| eventType | string | ✅ | 事件类型（如：login, level_up, purchase） |
| eventData | object | ❌ | 事件附加数据 |

**返回值：** `Promise<Object>`

```javascript
{
    success: true/false,
    message: "上报结果描述"
}
```

**示例：**

```javascript
// 上报登录事件
await sdk.reportEvent(kamiCode, 'login', {
    loginTime: new Date().toISOString(),
    ip: '192.168.1.1'
});

// 上报升级事件
await sdk.reportEvent(kamiCode, 'level_up', {
    fromLevel: 10,
    toLevel: 11,
    timestamp: Date.now()
});

// 上报购买事件
await sdk.reportEvent(kamiCode, 'purchase', {
    itemId: 'item_001',
    amount: 99.99,
    currency: 'CNY'
});
```

### heartbeat(kamiCode)

发送心跳，保持在线状态。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| kamiCode | string | ✅ | 卡密代码 |

**返回值：** `Promise<Object>`

```javascript
{
    success: true/false,
    message: "心跳结果描述"
}
```

**示例：**

```javascript
// 简单心跳
const result = await sdk.heartbeat(kamiCode);

// 定时心跳
let heartbeatTimer = null;

function startHeartbeat(kamiCode) {
    // 立即发送一次
    sdk.heartbeat(kamiCode);
    
    // 每30秒发送一次
    heartbeatTimer = setInterval(() => {
        sdk.heartbeat(kamiCode).then(result => {
            if (!result.success) {
                console.warn('心跳失败:', result.message);
            }
        });
    }, 30000);
}

function stopHeartbeat() {
    if (heartbeatTimer) {
        clearInterval(heartbeatTimer);
        heartbeatTimer = null;
    }
}

// 页面关闭时停止心跳
window.addEventListener('beforeunload', stopHeartbeat);
```

---

## 📝 完整示例

### 基础用法

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>卡密验证示例</title>
</head>
<body>
    <input type="text" id="kamiCode" placeholder="请输入卡密">
    <button onclick="verify()">验证</button>
    <div id="result"></div>

    <!-- 引入依赖库 -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.3.2/jsencrypt.min.js"></script>
    <script src="lemon-kami.js"></script>
    
    <script>
        let sdk = null;
        
        // 初始化 SDK
        async function init() {
            sdk = new LemonKamiSDK({
                appId: 'your_app_id',
                appSecret: 'your_app_secret',
                serverUrl: 'http://localhost:8000'
            });
            
            // 等待加载
            await new Promise(resolve => setTimeout(resolve, 1500));
            console.log('SDK 初始化完成');
        }
        
        // 验证卡密
        async function verify() {
            const code = document.getElementById('kamiCode').value;
            
            if (!sdk) {
                alert('SDK 未初始化');
                return;
            }
            
            try {
                const result = await sdk.verify(code);
                
                if (result.success) {
                    document.getElementById('result').innerHTML = 
                        `<p style="color:green">✅ 验证成功！</p>
                         <p>卡密类型: ${result.kami_type}</p>
                         <p>到期时间: ${result.expire_time || '永久'}</p>`;
                    
                    // 开始心跳
                    startHeartbeat(code);
                } else {
                    document.getElementById('result').innerHTML = 
                        `<p style="color:red">❌ 验证失败: ${result.message}</p>`;
                }
            } catch (error) {
                console.error('验证异常:', error);
            }
        }
        
        // 心跳
        let heartbeatTimer = null;
        
        function startHeartbeat(kamiCode) {
            heartbeatTimer = setInterval(() => {
                sdk.heartbeat(kamiCode).catch(err => {
                    console.error('心跳失败:', err);
                });
            }, 30000);
        }
        
        // 页面加载时初始化
        window.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
```

### Vue 3 集成

```javascript
// composables/useLemonKami.js
import { ref, onMounted, onUnmounted } from 'vue'

export function useLemonKami(appId, appSecret, serverUrl = 'http://localhost:8000') {
    const sdk = ref(null)
    const initialized = ref(false)
    const currentKami = ref(null)
    let heartbeatTimer = null

    // 初始化 SDK
    async function init() {
        if (initialized.value) return
        
        // 动态加载依赖
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js')
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.3.2/jsencrypt.min.js')
        await loadScript('/path/to/lemon-kami.js')
        
        sdk.value = new window.LemonKamiSDK({
            appId,
            appSecret,
            serverUrl
        })
        
        // 等待加载
        await new Promise(resolve => setTimeout(resolve, 1500))
        initialized.value = true
    }

    // 验证卡密
    async function verify(kamiCode) {
        if (!sdk.value) throw new Error('SDK 未初始化')
        
        const result = await sdk.value.verify(kamiCode)
        
        if (result.success) {
            currentKami.value = kamiCode
            startHeartbeat(kamiCode)
        }
        
        return result
    }

    // 上报事件
    async function reportEvent(eventType, eventData = {}) {
        if (!sdk.value || !currentKami.value) {
            throw new Error('请先验证卡密')
        }
        
        return await sdk.value.reportEvent(currentKami.value, eventType, eventData)
    }

    // 开始心跳
    function startHeartbeat(kamiCode) {
        stopHeartbeat()
        
        heartbeatTimer = setInterval(() => {
            sdk.value.heartbeat(kamiCode).catch(console.error)
        }, 30000)
    }

    // 停止心跳
    function stopHeartbeat() {
        if (heartbeatTimer) {
            clearInterval(heartbeatTimer)
            heartbeatTimer = null
        }
    }

    // 加载脚本
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${src}"]`)) {
                resolve()
                return
            }
            
            const script = document.createElement('script')
            script.src = src
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
        })
    }

    onMounted(init)
    onUnmounted(stopHeartbeat)

    return {
        sdk,
        initialized,
        verify,
        reportEvent,
        startHeartbeat,
        stopHeartbeat
    }
}
```

```vue
<!-- App.vue -->
<template>
    <div>
        <input v-model="kamiCode" placeholder="请输入卡密" />
        <button @click="handleVerify" :disabled="!initialized">
            验证
        </button>
        
        <div v-if="verifyResult">
            <p v-if="verifyResult.success" style="color: green">
                ✅ 验证成功
            </p>
            <p v-else style="color: red">
                ❌ {{ verifyResult.message }}
            </p>
        </div>
    </div>
</template>

<script setup>
import { ref } from 'vue'
import { useLemonKami } from '@/composables/useLemonKami'

const kamiCode = ref('')
const verifyResult = ref(null)

const { initialized, verify } = useLemonKami(
    'your_app_id',
    'your_app_secret',
    'http://localhost:8000'
)

async function handleVerify() {
    try {
        verifyResult.value = await verify(kamiCode.value)
    } catch (error) {
        console.error('验证失败:', error)
    }
}
</script>
```

### React 集成

```jsx
// hooks/useLemonKami.js
import { useState, useEffect, useRef } from 'react'

export function useLemonKami(appId, appSecret, serverUrl = 'http://localhost:8000') {
    const [sdk, setSdk] = useState(null)
    const [initialized, setInitialized] = useState(false)
    const currentKamiRef = useRef(null)
    const heartbeatTimerRef = useRef(null)

    // 初始化 SDK
    useEffect(() => {
        async function init() {
            // 动态加载依赖
            await loadScript('https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js')
            await loadScript('https://cdnjs.cloudflare.com/ajax/libs/jsencrypt/3.3.2/jsencrypt.min.js')
            await loadScript('/path/to/lemon-kami.js')
            
            const newSdk = new window.LemonKamiSDK({
                appId,
                appSecret,
                serverUrl
            })
            
            // 等待加载
            await new Promise(resolve => setTimeout(resolve, 1500))
            
            setSdk(newSdk)
            setInitialized(true)
        }
        
        init()
        
        return () => {
            stopHeartbeat()
        }
    }, [appId, appSecret, serverUrl])

    // 验证卡密
    async function verify(kamiCode) {
        if (!sdk) throw new Error('SDK 未初始化')
        
        const result = await sdk.verify(kamiCode)
        
        if (result.success) {
            currentKamiRef.current = kamiCode
            startHeartbeat(kamiCode)
        }
        
        return result
    }

    // 上报事件
    async function reportEvent(eventType, eventData = {}) {
        if (!sdk || !currentKamiRef.current) {
            throw new Error('请先验证卡密')
        }
        
        return await sdk.reportEvent(currentKamiRef.current, eventType, eventData)
    }

    // 开始心跳
    function startHeartbeat(kamiCode) {
        stopHeartbeat()
        
        heartbeatTimerRef.current = setInterval(() => {
            sdk.heartbeat(kamiCode).catch(console.error)
        }, 30000)
    }

    // 停止心跳
    function stopHeartbeat() {
        if (heartbeatTimerRef.current) {
            clearInterval(heartbeatTimerRef.current)
            heartbeatTimerRef.current = null
        }
    }

    // 加载脚本
    function loadScript(src) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${src}"]`)) {
                resolve()
                return
            }
            
            const script = document.createElement('script')
            script.src = src
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
        })
    }

    return {
        sdk,
        initialized,
        verify,
        reportEvent
    }
}
```

```jsx
// App.jsx
import React, { useState } from 'react'
import { useLemonKami } from './hooks/useLemonKami'

function App() {
    const [kamiCode, setKamiCode] = useState('')
    const [verifyResult, setVerifyResult] = useState(null)
    
    const { initialized, verify } = useLemonKami(
        'your_app_id',
        'your_app_secret',
        'http://localhost:8000'
    )

    async function handleVerify() {
        try {
            const result = await verify(kamiCode)
            setVerifyResult(result)
        } catch (error) {
            console.error('验证失败:', error)
        }
    }

    return (
        <div>
            <input 
                value={kamiCode}
                onChange={(e) => setKamiCode(e.target.value)}
                placeholder="请输入卡密"
            />
            <button onClick={handleVerify} disabled={!initialized}>
                验证
            </button>
            
            {verifyResult && (
                <div>
                    {verifyResult.success ? (
                        <p style={{ color: 'green' }}>✅ 验证成功</p>
                    ) : (
                        <p style={{ color: 'red' }}>❌ {verifyResult.message}</p>
                    )}
                </div>
            )}
        </div>
    )
}

export default App
```

---

## 🔐 安全说明

### 1. 加密机制

SDK 使用多层加密保护通信安全：

- **RSA 加密**：用于加密 AES 密钥和敏感数据
- **AES 加密**：用于加密请求和响应内容
- **HMAC-SHA256**：用于签名验证，防止篡改
- **时间戳 + 随机数**：防止重放攻击

### 2. 设备指纹

SDK 会自动生成唯一的设备指纹，包括：

- Canvas 指纹
- WebGL 指纹
- 浏览器特征
- 屏幕信息
- 系统信息

设备指纹用于：
- 设备绑定卡密的验证
- 防止多设备共享同一卡密
- 异常行为检测

### 3. 注意事项

⚠️ **重要提示：**

1. **不要在客户端暴露 App Secret**
   - 建议通过后端代理调用 SDK
   - 或使用环境变量配置

2. **HTTPS 推荐**
   - 生产环境务必使用 HTTPS
   - 避免中间人攻击

3. **心跳间隔**
   - 建议 30-60 秒
   - 过短会增加服务器压力
   - 过长可能导致会话超时

4. **错误处理**
   - 始终捕获异步操作的异常
   - 向用户显示友好的错误提示

---

## 🌐 浏览器兼容性

| 浏览器 | 版本 | 支持 |
|--------|------|------|
| Chrome | 60+ | ✅ |
| Firefox | 55+ | ✅ |
| Safari | 11+ | ✅ |
| Edge | 79+ | ✅ |
| Opera | 47+ | ✅ |

**注意：** 需要支持以下特性：
- ES6 Promise
- Fetch API
- Crypto API
- Canvas
- WebGL

---

## 📦 NPM 安装（可选）

如果您使用构建工具，可以通过 npm 安装：

```bash
npm install crypto-js jsencrypt
```

然后手动下载 `lemon-kami.js` 并导入：

```javascript
import CryptoJS from 'crypto-js'
import JSEncrypt from 'jsencrypt'
import LemonKamiSDK from './lemon-kami.js'

// 将库挂载到全局
window.CryptoJS = CryptoJS
window.JSEncrypt = JSEncrypt

// 使用 SDK
const sdk = new LemonKamiSDK({
    appId: 'your_app_id',
    appSecret: 'your_app_secret'
})
```

---

## ❓ 常见问题

### Q1: 初始化后无法立即使用？

**A:** SDK 需要从服务器获取 RSA 公钥并生成本地设备指纹，这个过程需要 1-2 秒。建议：

```javascript
const sdk = new LemonKamiSDK({...});
await new Promise(resolve => setTimeout(resolve, 1500));
// 现在可以使用了
```

### Q2: 如何知道 SDK 是否初始化完成？

**A:** 检查 `sdk.publicKey` 和 `sdk.fingerprint` 是否存在：

```javascript
if (sdk.publicKey && sdk.fingerprint) {
    console.log('SDK 已就绪');
}
```

### Q3: 心跳失败怎么办？

**A:** 可能的原因：
- 网络问题
- 卡密已过期
- 设备被拉黑

建议重新验证卡密或提示用户联系客服。

### Q4: 可以在 Node.js 中使用吗？

**A:** 当前版本仅支持浏览器环境。如需服务端使用，请使用 Python SDK 或 Java SDK。

### Q5: 如何自定义服务器地址？

**A:** 在初始化时指定 `serverUrl`：

```javascript
const sdk = new LemonKamiSDK({
    appId: 'xxx',
    appSecret: 'xxx',
    serverUrl: 'https://api.yourdomain.com'
});
```

---

## 📞 技术支持

如有问题，请联系：
- 邮箱：support@example.com
- 文档：https://docs.example.com
- GitHub：https://github.com/yourusername/lemon-kami

---

## 📄 许可证

MIT License
