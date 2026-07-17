# Lemon Kami 项目交接说明

这份文档用于换电脑、移动项目目录、或让其他开发者接手时快速恢复环境。这里不保存任何密码、密钥、Token、数据库连接明文或服务器登录信息。

## 项目概览

- 后端：FastAPI / Python
- 前端：admin 目录下的 Vue 3 / Vite
- 数据库：MySQL 8
- 缓存：Redis 7
- 部署：GitHub Actions 通过 SSH 连接 VPS，再用 Docker Compose 部署

本地 Windows 项目路径不参与线上部署。无论项目在 `D:\Poject\...`、`D:\poject\...`，还是换到其他磁盘，只要仓库内容和 GitHub Secrets 正确，push 到 `main` 后都应自动部署。

## 换电脑或移动项目后的操作

1. 克隆或打开项目仓库。

```powershell
git clone https://github.com/Xiaoye-888/Lemon-kami.git
cd Lemon-kami
git status --short --branch
```

2. 安装后端依赖。

```powershell
python -m pip install -r requirements.txt
```

3. 安装前端依赖。

```powershell
cd admin
npm ci
cd ..
```

4. 运行本地验证。

```powershell
python -m pytest -q
cd admin
npm run build
cd ..
.\scripts\release_check.ps1
```

5. 修改代码后提交并推送。

```powershell
git status --short
git add <changed-files>
git commit -m "your message"
git push origin main
```

推送 `main` 后，GitHub Actions 会自动测试、构建 Docker 镜像，并部署到服务器。

## 部署配置在哪里

部署相关文件在仓库中，可以随 Git 复用：

- `.github/workflows/ci-cd.yml`
- `docker-compose.prod.yml`
- `scripts/remote_deploy.sh`
- `scripts/release_check.ps1`
- `.env.example`
- `DEPLOY_SERVER.md`

敏感信息不在仓库中，统一放在 GitHub 仓库的 **Settings > Secrets and variables > Actions**。

必需 Secrets：

- `SERVER_USER`
- `SERVER_SSH_KEY`
- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `DATABASE_URL`
- `SECRET_KEY`
- `LOGIN_AES_KEY`
- `BOOTSTRAP_ADMIN_PASSWORD`

常用可选 Secrets：

- `SERVER_HOST`
- `SERVER_PORT`
- `MYSQL_DATABASE`
- `MYSQL_USER`
- `REDIS_URL`
- `HTTP_PORT`
- `TZ`
- `CORS_ALLOWED_ORIGINS`
- `ENABLE_API_DOCS`
- `DEPLOY_APP_DIR`
- `DEPLOY_DIR`

如果只是换电脑或移动本地项目目录，不需要重新生成这些 Secrets。只有服务器地址、SSH 用户、服务器部署目录、数据库密码等真实运行环境改变时，才需要更新 GitHub Secrets。

## 默认线上信息

- 公开访问地址：`http://154.12.26.231/`
- 健康检查：`http://154.12.26.231/health`
- 公开接口文档：`http://154.12.26.231/docs/api#basic-info`
- 默认服务器应用目录：`/opt/lemon-kami`
- 默认临时上传目录：`/tmp/lemon-kami-deploy`

公开接口文档规则：

- 浏览器打开 `/api/v1/docs/interfaces` 应跳转到 `/docs/api#basic-info`
- API 客户端请求 `/api/v1/docs/interfaces?page=1&page_size=3` 应返回 JSON

## 推送后的验证

GitHub Actions 成功后，检查：

```powershell
Invoke-WebRequest -Uri "http://154.12.26.231/health" -UseBasicParsing
Invoke-WebRequest -Uri "http://154.12.26.231/docs/api#basic-info" -UseBasicParsing
Invoke-WebRequest -Uri "http://154.12.26.231/api/v1/docs/interfaces?page=1&page_size=3" -Headers @{ Accept = "application/json" } -UseBasicParsing
```

预期结果：

- `/health` 返回 `200` 和 `{"status":"healthy"}`
- `/docs/api#basic-info` 返回 HTML 页面
- `/api/v1/docs/interfaces` 返回 JSON 接口数据

## 不要提交的内容

不要提交以下内容：

- `.env`
- 私钥、公钥、Token、Cookie、密码
- 数据库文件或数据库导出
- 日志文件
- `admin/dist`
- `node_modules`
- Python 缓存目录

提交前建议检查：

```powershell
git status --short
```

## 已知部署问题

如果线上 FastAPI 容器反复重启，并且日志里出现 Pydantic 解析布尔值或整数失败，同时值前面带有 `\ufeff`，说明某些环境变量混入了 UTF-8 BOM。

处理方式：

- 清理服务器 `.env` 中对应值开头的 BOM
- 清理 GitHub Secrets 中对应值开头的 BOM
- 不要在终端、文档、记忆或提交记录里输出真实密钥值

当前 GitHub Actions 已在部署前自动清理 Secrets 值开头的 BOM，`scripts/release_check.ps1` 也会检查这段保护逻辑。

## Engramory 记忆

本项目还有本地 AI 记忆目录 `.engramory-memory/`。它用于让 AI 助手快速恢复项目上下文，但该目录被 Git 忽略，不会自动同步到新电脑。

长期、跨电脑、可随仓库同步的信息，应写在本文件或其他仓库文档中。Engramory 只记录辅助记忆，不保存任何敏感值。
