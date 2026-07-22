from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_admin_entry_does_not_block_on_external_cdn_scripts():
    index = read_text("admin/index.html")

    assert "cdnjs.cloudflare.com" not in index
    assert "http://" not in index
    assert "https://" not in index
    assert "jsencrypt.min.js" not in index


def test_frontend_nginx_compresses_and_caches_static_assets():
    nginx = read_text("admin/nginx.conf")

    assert "gzip on;" in nginx
    assert "gzip_types" in nginx
    assert "application/javascript" in nginx
    assert "text/css" in nginx
    assert "location ^~ /assets/" in nginx
    assert 'Cache-Control "public, max-age=31536000, immutable"' in nginx
    assert 'Cache-Control "no-cache, no-store, must-revalidate"' in nginx
    assert "proxy_buffering on;" in nginx
    assert "proxy_read_timeout 30s;" in nginx


def test_admin_api_client_has_timeout_and_retry_resilience():
    request_source = read_text("admin/src/utils/request.js")

    assert "const REQUEST_TIMEOUT" in request_source
    assert "20000" in request_source
    assert "const REQUEST_RETRIES" in request_source
    assert "function isRetryableRequestError" in request_source
    assert "retryableMethods" in request_source
    assert "setTimeout(resolve, REQUEST_RETRY_DELAY)" in request_source
    assert "请求超时，请稍后重试" in request_source


def test_fastapi_runtime_uses_configurable_multiple_workers():
    dockerfile = read_text("Dockerfile")
    compose = read_text("docker-compose.prod.yml")

    assert "UVICORN_WORKERS=2" in dockerfile
    assert "--workers ${UVICORN_WORKERS:-2}" in dockerfile
    assert "UVICORN_WORKERS: ${UVICORN_WORKERS:-2}" in compose
