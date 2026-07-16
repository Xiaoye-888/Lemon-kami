# Lemon Kami Java SDK

小柠檬网络验证 Java 客户端 SDK，提供卡密验证、事件上报和心跳保持功能。

## 📋 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [安装方式](#安装方式)
- [快速开始](#快速开始)
- [API 文档](#api-文档)
- [使用示例](#使用示例)
- [常见问题](#常见问题)

---

## 功能特性

✅ **设备指纹生成**：基于硬件信息生成唯一设备标识  
✅ **RSA + AES 混合加密**：确保数据传输安全  
✅ **HMAC-SHA256 签名**：防止请求篡改  
✅ **卡密验证**：支持多种卡密类型验证  
✅ **事件上报**：自定义行为日志记录  
✅ **心跳保持**：维持在线状态  
✅ **跨平台兼容**：支持 Windows、macOS、Linux  

## 对接流程

1. 客户端启动后可请求 `GET /api/v1/sdk/apps/{app_id}/config`，读取公告、版本更新、下载外链和安全策略。
2. 用户输入卡密后调用 `sdk.verify(kamiCode)`。验证接口只做授权检查、激活和绑定，不扣次数。
3. 次数卡在用户实际完成一次业务动作后，由业务端调用 `POST /api/v1/sdk/consume` 扣减次数。
4. 行为、心跳或业务日志使用 `sdk.reportEvent(kamiCode, eventType, extraData)` 上报。

当前 Java SDK 入口只保留 Lemon 命名：`com.lemon.kami.LemonKamiSDK`。

---

## 环境要求

- Java 8 或更高版本
- Maven 3.x（用于构建）

---

## 安装方式

### 方式一：Maven 依赖（推荐）

将以下内容添加到你的 `pom.xml` 文件中：

```xml
<dependency>
    <groupId>com.lemon</groupId>
    <artifactId>lemon-kami-sdk</artifactId>
    <version>1.0.0</version>
</dependency>
```

### 方式二：手动编译

```bash
# 进入 SDK 目录
cd java_sdk

# 编译打包
mvn clean package

mvn install
# 生成的 JAR 文件位于 target/lemon-kami-sdk-1.0.0.jar
```

然后将 JAR 文件添加到你的项目中。

### 方式三：Gradle 依赖

```groovy
implementation 'com.lemon:lemon-kami-sdk:1.0.0'
```

---

## 快速开始

### 1. 初始化 SDK

```java
import com.lemon.kami.LemonKamiSDK;

// 初始化 SDK
LemonKamiSDK sdk = new LemonKamiSDK(
    "your_app_id",           // 替换为你的 app_id
    "your_app_secret",       // 替换为你的 app_secret
    "http://localhost:8000"  // 服务器地址
);
```

### 2. 验证卡密

```java
Map<String, Object> result = sdk.verify("KAMI_CODE_123");

if ((Boolean) result.getOrDefault("success", false)) {
    System.out.println("✅ 验证成功！");
    System.out.println("卡密类型: " + result.get("kami_type"));
    System.out.println("到期时间: " + result.get("expire_time"));
} else {
    System.out.println("❌ 验证失败: " + result.get("message"));
}
```

### 3. 上报事件

```java
// 构建额外数据
Map<String, Object> extraData = new HashMap<>();
extraData.put("username", "test_user");
extraData.put("level", 10);

// 上报事件
Map<String, Object> result = sdk.reportEvent("KAMI_CODE_123", "login", extraData);

if ((Boolean) result.getOrDefault("success", false)) {
    System.out.println("✅ 事件上报成功！");
}
```

### 4. 发送心跳

```java
Map<String, Object> result = sdk.heartbeat("KAMI_CODE_123");

if ((Boolean) result.getOrDefault("success", false)) {
    System.out.println("✅ 心跳发送成功！");
}
```

---

## API 文档

### 构造函数

#### LemonKamiSDK(String appId, String appSecret, String serverUrl)

初始化 SDK，自动从服务器获取 RSA 公钥。

**参数：**
- `appId`: 应用 ID
- `appSecret`: 应用密钥
- `serverUrl`: 服务器地址

**示例：**
```java
LemonKamiSDK sdk = new LemonKamiSDK("app_id", "app_secret", "http://localhost:8000");
```

#### LemonKamiSDK(String appId, String appSecret, String serverUrl, String rsaPublicKey)

初始化 SDK，手动指定 RSA 公钥。

**参数：**
- `appId`: 应用 ID
- `appSecret`: 应用密钥
- `serverUrl`: 服务器地址
- `rsaPublicKey`: RSA 公钥（PEM 格式）

**示例：**
```java
String publicKey = "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A...\n-----END PUBLIC KEY-----";
LemonKamiSDK sdk = new LemonKamiSDK("app_id", "app_secret", "http://localhost:8000", publicKey);
```

---

### verify(String kamiCode)

验证卡密。

**参数：**
- `kamiCode`: 卡密代码

**返回值：**
`Map<String, Object>` - 验证结果

**返回字段：**
- `success` (Boolean): 是否成功
- `message` (String): 消息
- `kami_type` (String): 卡密类型（day/month/permanent/points）
- `expire_time` (String): 到期时间
- `device_bound` (Boolean): 是否已绑定设备

**示例：**
```java
Map<String, Object> result = sdk.verify("KAMI_CODE_123");
```

---

### reportEvent(String kamiCode, String eventType, Map<String, Object> extraData)

上报行为事件。

**参数：**
- `kamiCode`: 卡密代码
- `eventType`: 事件类型（如：login, logout, level_up, purchase 等）
- `extraData`: 额外数据（可选）

**返回值：**
`Map<String, Object>` - 上报结果

**返回字段：**
- `success` (Boolean): 是否成功
- `message` (String): 消息

**示例：**
```java
Map<String, Object> extraData = new HashMap<>();
extraData.put("username", "test_user");
extraData.put("level", 10);

Map<String, Object> result = sdk.reportEvent("KAMI_CODE_123", "login", extraData);
```

---

### reportEvent(String kamiCode, String eventType)

上报行为事件（无额外数据）。

**参数：**
- `kamiCode`: 卡密代码
- `eventType`: 事件类型

**返回值：**
`Map<String, Object>` - 上报结果

**示例：**
```java
Map<String, Object> result = sdk.reportEvent("KAMI_CODE_123", "heartbeat");
```

---

### heartbeat(String kamiCode)

发送心跳。

**参数：**
- `kamiCode`: 卡密代码

**返回值：**
`Map<String, Object>` - 心跳结果

**示例：**
```java
Map<String, Object> result = sdk.heartbeat("KAMI_CODE_123");
```

---

## 使用示例

### 完整示例

查看 [Example.java](Example.java) 文件获取完整的使用示例。

运行示例：

```bash
# 编译
javac -cp "target/lemon-kami-sdk-1.0.0.jar:lib/*" Example.java

# 运行
java -cp ".:target/lemon-kami-sdk-1.0.0.jar:lib/*" Example
```

### Spring Boot 集成示例

```java
import com.lemon.kami.LemonKamiSDK;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class KamiConfig {
    
    @Value("${lemon.kami.app-id}")
    private String appId;
    
    @Value("${lemon.kami.app-secret}")
    private String appSecret;
    
    @Value("${lemon.kami.server-url}")
    private String serverUrl;
    
    @Bean
    public LemonKamiSDK lemonKamiSDK() {
        return new LemonKamiSDK(appId, appSecret, serverUrl);
    }
}
```

在 application.properties 中配置：

```properties
lemon.kami.app-id=your_app_id
lemon.kami.app-secret=your_app_secret
lemon.kami.server-url=http://localhost:8000
```

在服务中使用：

```java
@Service
public class KamiService {
    
    @Autowired
    private LemonKamiSDK sdk;
    
    public boolean verifyKami(String kamiCode) {
        Map<String, Object> result = sdk.verify(kamiCode);
        return (Boolean) result.getOrDefault("success", false);
    }
}
```

---

## 常见问题

### Q1: 如何获取 app_id 和 app_secret？

A: 登录管理后台 → 应用管理 → 创建应用，系统会自动生成并显示这些信息。

### Q2: 验证卡密时提示"RSA 公钥未初始化"怎么办？

A: 检查以下几点：
1. 网络连接是否正常
2. 服务器地址是否正确
3. app_id 是否正确
4. 服务器是否正在运行

也可以手动指定公钥：
```java
String publicKey = "-----BEGIN PUBLIC KEY-----\n...";
LemonKamiSDK sdk = new LemonKamiSDK(appId, appSecret, serverUrl, publicKey);
```

### Q3: 设备指纹是如何生成的？

A: 设备指纹基于以下信息生成：
- 操作系统名称和版本
- CPU 架构
- MAC 地址
- 系统唯一标识（Windows: MachineGuid, macOS: Hardware UUID, Linux: machine-id）

每次启动时都会重新计算，确保一致性且难以伪造。

### Q4: 支持哪些卡密类型？

A: 支持以下卡密类型：
- `day`: 天卡
- `month`: 月卡
- `permanent`: 永久卡
- `points`: 积分卡

### Q5: 如何处理网络异常？

A: SDK 会捕获网络异常并返回错误信息：
```java
Map<String, Object> result = sdk.verify(kamiCode);
if (!(Boolean) result.getOrDefault("success", false)) {
    System.err.println("错误: " + result.get("message"));
}
```

### Q6: 可以在多线程环境中使用吗？

A: 是的，SDK 是线程安全的。建议为每个应用创建一个单例实例：

```java
public class KamiClient {
    private static final LemonKamiSDK sdk = new LemonKamiSDK(
        "app_id", "app_secret", "http://localhost:8000"
    );
    
    public static LemonKamiSDK getInstance() {
        return sdk;
    }
}
```

---

## 项目结构

```
java_sdk/
├── pom.xml                              # Maven 配置文件
├── Example.java                         # 使用示例
├── README.md                            # 本文档
└── src/
    └── main/
        └── java/
            └── com/
                └── lemon/
                    └── kami/
                        └── LemonKamiSDK.java  # SDK 核心类
```

---

## 更新日志

### v1.0.0 (2026-04-27)

**初始版本**
- ✅ 设备指纹生成
- ✅ RSA + AES 混合加密
- ✅ HMAC-SHA256 签名
- ✅ 卡密验证
- ✅ 事件上报
- ✅ 心跳保持
- ✅ 跨平台兼容

---

## 许可证

MIT License

---

## 联系方式

如有问题或建议，请提交 Issue 或联系开发者。

**祝您使用愉快！** 🎉
