# Lemon Kami Server Deployment

This project is not PHP. It is a Python FastAPI backend plus a Vue 3 admin frontend.

## Technology Stack

- Backend: Python 3, FastAPI, Uvicorn, SQLModel, PyMySQL
- Frontend: Vue 3, Vite, Element Plus, Pinia, Vue Router, Axios
- Database: MySQL 8 in production; SQLite is only for local development
- Cache: Redis 7
- Deployment: Docker Compose, Nginx frontend reverse proxy

## Database State

The local SQLite development database has been cleaned. It now keeps only:

- one `admin` administrator account
- built-in API interface document definitions

All created business data has been removed: applications, card batches, cards, devices, end users, user authorizations, points records, app interface configs, and event logs.

## Deploy With Docker Compose

1. Upload the project directory to the server.
2. Review `.env` and replace the generated secrets if you want to rotate them.
3. Validate the deployment environment:

```bash
python scripts/validate_env.py --env-file .env
```

4. Start the stack:

```bash
docker compose up -d --build
```

5. Run public smoke checks:

```bash
python scripts/docker_smoke.py --base-url http://SERVER_IP
```

6. Open the admin UI:

```text
http://SERVER_IP/
```

7. Login with the bootstrap admin account configured by `BOOTSTRAP_ADMIN_PASSWORD`, then rotate it after first access:

```text
username: admin
password: <BOOTSTRAP_ADMIN_PASSWORD>
```

## Public URLs

- Admin frontend: `http://SERVER_IP/`
- API through Nginx: `http://SERVER_IP/api/...`
- Swagger docs: `http://SERVER_IP/docs` only when `ENABLE_API_DOCS=true`
- Health check: `http://SERVER_IP/health`

## Local Development

For local SQLite development, copy `.env.local.example` to `.env` and start the backend with Uvicorn. For server deployment, use the MySQL `.env` format.
