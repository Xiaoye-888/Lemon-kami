# 小柠檬网络验证发布检查清单

这份清单用于每次发布前后快速确认系统可上线。不要把真实密钥、数据库密码或服务器账号写入本文档。

## 1. 发布前检查

在项目根目录运行：

```powershell
.\scripts\release_check.ps1
```

如果本机已经启动后端和前端，可以增加本地冒烟检查：

```powershell
.\scripts\release_check.ps1 -Smoke -ApiBase http://127.0.0.1:8001 -FrontendBase http://127.0.0.1:3001
```

检查内容包括：

- 后端核心文件 Python 编译
- 前端 Vite 构建
- Java SDK Maven 打包检查
- SDK 压缩包旧入口扫描
- 核心路由存在性检查
- 可选的本地 HTTP 冒烟检查

## 2. 环境变量

生产环境使用 `.env` 配置，至少确认：

- `DATABASE_URL` 指向服务器 MySQL
- `REDIS_URL` 指向服务器 Redis
- `SECRET_KEY` 已独立生成
- `LOGIN_AES_KEY` 已独立生成
- 数据库密码、Redis 密码、密钥不提交到代码仓库

本地开发可使用 SQLite 和内存 Redis：

```powershell
$env:DATABASE_URL="sqlite:///./lemon_kami_dev.db"
$env:REDIS_URL="memory://local"
```

## 3. 数据库备份

发布前备份 MySQL：

```bash
mysqldump -h <host> -u <user> -p <database> > lemon_kami_backup_YYYYMMDD_HHMM.sql
```

建议保留：

- 最近 7 天每日备份
- 最近 4 周每周备份
- 每次大版本发布前的手动备份

恢复前先停止写入流量，再导入备份：

```bash
mysql -h <host> -u <user> -p <database> < lemon_kami_backup_YYYYMMDD_HHMM.sql
```

## 4. 首次登录安全

部署后立即执行：

- 使用默认管理员登录
- 进入账号管理重置管理员密码
- 确认 `.env` 中密钥不是示例值
- 确认服务器防火墙只暴露必要端口

## 5. Docker 发布

推荐生产环境使用：

```bash
docker compose up -d --build
```

发布后检查：

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 admin
```

浏览器访问：

- 管理后台首页
- 接口文档页
- 应用接口配置页

接口检查：

- `GET /health`
- `GET /api/v1/docs/interfaces`
- `GET /api/sdk/download?type=javascript`
- `GET /api/sdk/download?type=python`
- `GET /api/sdk/download?type=java`

## 6. SDK 对接检查

客户端软件接入时确认：

- `verify` 只验证授权，不扣次数
- 次数卡扣减必须调用 `consume`
- 公告读取 `GET /api/v1/sdk/apps/{app_id}/notice`
- 版本更新检查 `GET /api/v1/sdk/apps/{app_id}/updates/check`
- SDK 下载入口使用 `GET /api/sdk/download?type=python|javascript|java`

## 7. 回滚原则

如果发布后出现严重问题：

1. 停止新版本容器或服务
2. 恢复上一版镜像/代码
3. 如数据库结构已经变更，先评估是否需要恢复备份
4. 使用 `/health`、登录、SDK 验证、SDK 下载接口确认回滚状态

后续如果引入正式迁移工具，数据库结构变更必须先生成迁移文件，再进入发布流程。
