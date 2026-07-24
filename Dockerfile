ARG PYTHON_VERSION=3.12
ARG PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

FROM python:${PYTHON_VERSION}-slim AS builder

ARG PIP_INDEX_URL

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.prod.txt .

RUN python -m pip install --upgrade pip wheel setuptools \
    && python -m pip wheel \
        --wheel-dir /wheels \
        --index-url "${PIP_INDEX_URL}" \
        -r requirements.prod.txt

FROM python:${PYTHON_VERSION}-slim AS runtime

ENV DEBUG=false \
    UVICORN_WORKERS=2 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && python -m venv /opt/venv

COPY --from=builder /wheels /wheels
COPY requirements.prod.txt .

RUN python -m pip install \
        --no-index \
        --find-links=/wheels \
        --no-compile \
        -r requirements.prod.txt \
    && rm -rf /wheels

COPY --chown=app:app *.py ./
COPY --chown=app:app sdk/python_sdk/*.zip ./sdk/python_sdk/
COPY --chown=app:app sdk/js_sdk/*.zip ./sdk/js_sdk/
COPY --chown=app:app sdk/java_sdk/*.zip ./sdk/java_sdk/

RUN mkdir -p /app/logs /app/uploads \
    && chown -R app:app /app/logs /app/uploads

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2} --proxy-headers"]
