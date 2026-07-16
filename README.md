# Lemon Kami - 小柠檬网络验证

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/fastapi-0.100+-orange.svg)](https://fastapi.tiangolo.com/)

Lemon Kami（小柠檬网络验证）是一个功能强大的多租户卡密分发与验证平台，专为软件授权、游戏激活、会员管理等场景设计。系统采用现代化的前后端分离架构，提供安全、高效、易用的卡密管理解决方案。

## 🌟 核心特性

- **多租户支持**：支持创建多个应用，每个应用拥有独立的卡密体系、设备管理和日志记录。
- **多种卡密类型**：支持天卡、月卡、永久卡、积分卡、次数卡等多种授权模式。
- **设备指纹绑定**：首次激活时自动绑定设备指纹，防止卡密共享和滥用。
- **高级安全防护**：采用 RSA + AES 混合加密传输，HMAC-SHA256 签名校验，确保通信安全。
- **实时风控系统**：内置 IP 限流、账号锁定、设备黑名单等多层风控策略。
- **精细化权限管理**：支持超级管理员、应用创建者、被授权用户三级权限体系。
- **完整日志审计**：详细记录卡密激活、验证、设备登录及管理员操作日志。
- **高性能缓存**：基于 Redis 的设备绑定缓存，大幅提升验证接口响应速度。
- **现代化 UI**：基于 Vue 3 + Element Plus 构建的响应式管理后台，支持深色模式。
- **可审计 SDK 接入**：提供可读、可调试的 SDK 与接口文档，便于业务系统稳定对接。

## ✨ 项目特色功能

### 1. 可审计接口与 SDK 接入
系统以服务端签名校验、RSA + AES 加密传输、接口开关和应用级独立配置作为核心安全边界：
- **接口可控**：应用可按接口开通或关闭，对外调用统一经过接口状态校验。
- **传输加密**：SDK 请求使用 RSA + AES 混合加密，响应使用签名校验防篡改。
- **文档明确**：管理端提供接口文档页面，方便业务系统按统一请求和响应结构对接。

### 2. 多应用授权管理体系
为了满足团队协作需求，系统设计了灵活的 RBAC 权限模型：
- **应用级隔离**：不同应用的卡密、设备数据完全隔离。
- **精细化授权**：应用创建者可以将特定应用的管理权限授予其他普通用户，实现“专人专管”。
- **权限继承**：超级管理员（Admin）拥有全平台最高权限，可查看所有应用数据并进行全局配置。

### 3. 智能设备风控
- **硬件指纹采集**：SDK 自动收集设备 CPU、MAC、主板等底层信息生成唯一 Hash。
- **风险等级划分**：支持将设备标记为“正常”、“警告”或“黑名单”，黑名单设备将无法激活任何新卡密。
- **异步行为上报**：采用 `BackgroundTasks` 异步处理海量行为日志，确保高并发下验证接口的毫秒级响应。

---

## 🚀 快速开始

### 第一步：准备运行环境
确保您的服务器已安装以下基础软件：
- [Python 3.9+](https://www.python.org/)
- [Node.js 16+](https://nodejs.org/)
- [MySQL 8.0+](https://www.mysql.com/)
- [Redis 6.0+](https://redis.io/)

### 第二步：启动后端服务
```bash
# 1. 克隆项目并进入目录
git clone https://github.com/Xiaoye-888/Lemon-kami.git
cd Lemon-kami

# 2. 安装 Python 依赖
pip install -r requirements.txt

# 3. 配置数据库连接 (复制 .env.example 为 .env 并填写 MySQL/Redis 信息)
cp .env.example .env

# 4. 初始化数据库表结构
python -c "from database import init_db; init_db()"

# 5. 启动 FastAPI 服务
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 第三步：启动前端管理后台
```bash
# 1. 进入前端目录
cd admin

# 2. 安装前端依赖
npm install

# 3. 启动开发服务器
npm run dev
```
启动成功后，访问 `http://localhost:5173` 即可进入管理后台。首次部署请通过 `BOOTSTRAP_ADMIN_PASSWORD` 显式设置 `admin` 初始密码。

### 第四步：Docker 一键部署（推荐生产环境）
如果您希望快速部署到生产环境，可以使用 Docker Compose：
```bash
docker-compose up -d
```

---

## 🛠️ 技术栈

### 后端 (Backend)
- **框架**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.9+)
- **数据库**: [SQLModel](https://sqlmodel.tiangolo.com/) + [MySQL](https://www.mysql.com/)
- **缓存**: [Redis](https://redis.io/)
- **认证**: JWT (JSON Web Tokens)
- **加密**: `cryptography` (RSA, AES), `hmac`, `hashlib`

### 前端 (Frontend - Admin)
- **框架**: [Vue 3](https://vuejs.org/) (Composition API)
- **UI 组件库**: [Element Plus](https://element-plus.org/)
- **状态管理**: [Pinia](https://pinia.vuejs.org/)
- **路由**: [Vue Router 4](https://router.vuejs.org/)
- **HTTP 客户端**: [Axios](https://axios-http.com/)
- **构建工具**: [Vite](https://vitejs.dev/)

### 部署 (Deployment)
- **容器化**: Docker & Docker Compose
- **Web 服务器**: Nginx (前端静态资源 & 反向代理)
- **ASGI 服务器**: Uvicorn

## 📂 项目结构

```text
Lemon-kami/
├── admin/                  # 前端管理后台 (Vue 3)
│   ├── src/
│   │   ├── api/            # API 请求封装
│   │   ├── views/          # 页面组件 (Apps, Kamis, Devices, Logs, Users)
│   │   ├── stores/         # Pinia 状态管理
│   │   └── router/         # 路由配置
│   └── public/sdk/         # 提供给用户的 SDK 示例
├── sdk/                    # SDK 开发包
│   ├── js_sdk/             # JavaScript SDK
│   └── python_sdk/         # Python SDK
├── main.py                 # FastAPI 应用入口
├── routes_sdk.py           # SDK 核心接口 (验证、上报)
├── routes_admin.py         # 管理后台接口 (应用、卡密、用户管理)
├── models.py               # 数据库模型 (SQLModel)
├── crypto.py               # 加密工具类 (RSA, AES, HMAC)
├── database.py             # 数据库连接与初始化
├── redis_client.py         # Redis 客户端配置
└── config.py               # 全局配置管理
```

## 🔐 安全架构

系统采用了多层安全防护机制：

1. **传输加密**：所有敏感数据通过 RSA 公钥加密 AES 密钥，再使用 AES 加密业务数据。
2. **签名校验**：使用 HMAC-SHA256 对请求参数进行签名，防止篡改。
3. **设备绑定**：卡密激活时采集硬件特征码（CPU、MAC、主板等），实现一机一码。
4. **风控拦截**：
   - 登录失败 3 次锁定账号 10 分钟。
   - 单 IP 每分钟限制 5 次登录请求。
   - 支持手动将设备加入黑名单。

## 📖 API 文档

启动后端服务后，访问以下地址查看交互式 API 文档：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Kami Core API: [`KAMI_CORE_API.md`](KAMI_CORE_API.md)
- Points System API: [`POINTS_API.md`](POINTS_API.md)
- Interface Management API: [`INTERFACE_MANAGEMENT_API.md`](INTERFACE_MANAGEMENT_API.md)

### 核心接口概览

| 接口路径 | 方法 | 描述 |
| :--- | :--- | :--- |
| `/api/v1/sdk/verify` | POST | 卡密验证与激活 |
| `/api/v1/sdk/report` | POST | 行为数据上报 |
| `/api/v1/admin/login` | POST | 管理员登录 |
| `/api/v1/admin/apps` | GET/POST | 应用管理 |
| `/api/v1/admin/kamis` | GET | 卡密列表查询 |
| `/api/v1/admin/devices` | GET | 设备列表查询 |

## 📦 SDK 集成

我们提供了 Python 和 JavaScript 版本的 SDK，方便开发者快速集成。

### Python 示例

```python
from lemon_kami import LemonKamiSDK

client = LemonKamiSDK(
    host="http://localhost:8000",
    app_id="your_app_id",
    app_secret="your_app_secret",
    public_key="-----BEGIN PUBLIC KEY-----\n..."
)

# 验证卡密
result = client.verify_kami("YOUR_KAMI_CODE")
if result["success"]:
    print(f"授权成功！到期时间：{result['expire_time']}")
else:
    print(f"验证失败：{result['message']}")
```


## 👥 联系与支持

如果您有任何问题、建议或需要商业合作，欢迎联系我们。

- **微信**: `981388`
- **GitHub Issues**: [提交问题](https://github.com/Xiaoye-888/Lemon-kami/issues)

## 📄 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

---

*Made with care by Lemon Kami Team*
