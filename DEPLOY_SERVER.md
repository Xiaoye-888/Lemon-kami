# Lemon Kami GitHub Actions Deployment

This project deploys as a Docker Compose stack:

- Backend: Python FastAPI and Uvicorn
- Frontend: Vue 3, Vite, and Nginx
- Database: MySQL 8
- Cache: Redis 7

The local Windows project path is not used by GitHub Actions. Actions checks out the repository on GitHub-hosted Linux runners, builds Docker images there, uploads a deployment bundle over SSH, and runs Docker Compose on the server.

## Server Prerequisites

Install these on the VPS before the first deployment:

- Docker Engine
- Docker Compose v2 plugin, available as `docker compose`
- An SSH user that can run Docker commands
- Write permission for the deployment app directory

Default remote paths:

- App directory: `/opt/lemon-kami`
- Temporary upload directory: `/tmp/lemon-kami-deploy`

You can override both paths with GitHub Secrets. Custom deployment paths must be absolute Linux paths, must not be `/`, and must not contain whitespace.

## Required GitHub Secrets

Set these in GitHub repository settings under **Secrets and variables > Actions**.

SSH:

- `SERVER_USER`: SSH username
- `SERVER_SSH_KEY`: private key used by GitHub Actions to SSH into the server

Runtime:

- `MYSQL_ROOT_PASSWORD`
- `MYSQL_PASSWORD`
- `DATABASE_URL`
- `SECRET_KEY`
- `LOGIN_AES_KEY`
- `BOOTSTRAP_ADMIN_PASSWORD`

Do not commit real secret values to the repository. Use `.env.example` only as a template.

## Optional GitHub Secrets

- `SERVER_HOST`: VPS hostname or IP address, defaults to `154.12.26.231`
- `SERVER_PORT`: SSH port, defaults to `22`
- `DEPLOY_APP_DIR`: server app directory, defaults to `/opt/lemon-kami`
- `DEPLOY_DIR`: temporary upload directory, defaults to `/tmp/lemon-kami-deploy`
- `HTTP_PORT`: public frontend port, defaults to `80`
- `CORS_ALLOWED_ORIGINS`: CORS origin list, defaults to `http://154.12.26.231`
- `MYSQL_DATABASE`: defaults to `lemon_kami`
- `MYSQL_USER`: defaults to `lemon_user`
- `REDIS_URL`: defaults to `redis://redis:6379/0`
- `ALGORITHM`: defaults to `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES`: defaults to `1440`
- `DEBUG`: defaults to `false`
- `ENABLE_API_DOCS`: defaults to `false`
- `TIMESTAMP_TOLERANCE`: defaults to `60`
- `NONCE_TTL`: defaults to `60`
- `RATE_LIMIT_MAX`: defaults to `1000`
- `RATE_LIMIT_WINDOW`: defaults to `60`
- `TZ`: defaults to `Asia/Shanghai`

## Deployment Flow

Pushing to `main` triggers `.github/workflows/ci-cd.yml`:

1. Install and test backend dependencies.
2. Install and build the admin frontend.
3. Build backend and frontend Docker images.
4. Save both images into `lemon-kami-images.tar.gz`.
5. Create `runtime.env` from GitHub Secrets.
6. Upload the image archive, compose file, runtime env, and remote deploy script over SSH.
7. Run `scripts/remote_deploy.sh` on the server.

The remote script loads the images, installs `runtime.env` as `${DEPLOY_APP_DIR}/.env`, updates `APP_IMAGE_TAG`, validates the Compose config, and starts the stack.

## Public URLs

- Admin frontend: `http://SERVER_IP/`
- API through Nginx: `http://SERVER_IP/api/...`
- Swagger docs: `http://SERVER_IP/docs` when `ENABLE_API_DOCS=true`
- Health check: `http://SERVER_IP/health`

## Manual Server Check

On the server, the SSH user should pass:

```bash
docker --version
docker compose version
docker ps
```

If `docker ps` fails with a permission error, add the SSH user to the Docker group or use a deployment user with Docker access.
