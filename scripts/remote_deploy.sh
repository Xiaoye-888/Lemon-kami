#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/lemon-kami}"
DEPLOY_DIR="${DEPLOY_DIR:-/tmp/lemon-kami-deploy}"
IMAGE_ARCHIVE="${IMAGE_ARCHIVE:-${DEPLOY_DIR}/lemon-kami-images.tar.gz}"
APP_IMAGE_TAG="${APP_IMAGE_TAG:?APP_IMAGE_TAG is required}"

mkdir -p "${APP_DIR}"

cp "${DEPLOY_DIR}/docker-compose.prod.yml" "${APP_DIR}/docker-compose.prod.yml"

if [ -f "${DEPLOY_DIR}/runtime.env" ]; then
  install -m 600 "${DEPLOY_DIR}/runtime.env" "${APP_DIR}/.env"
fi

if [ ! -f "${APP_DIR}/.env" ]; then
  echo "Missing ${APP_DIR}/.env. Create it before deploying." >&2
  exit 1
fi

docker load -i "${IMAGE_ARCHIVE}"

cd "${APP_DIR}"

if grep -q '^APP_IMAGE_TAG=' .env; then
  sed -i "s/^APP_IMAGE_TAG=.*/APP_IMAGE_TAG=${APP_IMAGE_TAG}/" .env
else
  printf '\nAPP_IMAGE_TAG=%s\n' "${APP_IMAGE_TAG}" >> .env
fi

docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker image prune -f >/dev/null || true
rm -f "${DEPLOY_DIR}/runtime.env" "${IMAGE_ARCHIVE}" || true
docker compose -f docker-compose.prod.yml ps
