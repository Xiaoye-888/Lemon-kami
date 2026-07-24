#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/lemon-kami}"
DEPLOY_DIR="${DEPLOY_DIR:-/tmp/lemon-kami-deploy}"
IMAGE_ARCHIVE="${IMAGE_ARCHIVE:-${DEPLOY_DIR}/lemon-kami-images.tar.gz}"
APP_IMAGE_TAG="${APP_IMAGE_TAG:?APP_IMAGE_TAG is required}"

validate_absolute_dir() {
  local name="$1"
  local value="$2"

  case "${value}" in
    /*) ;;
    *)
      echo "${name} must be an absolute Linux path." >&2
      exit 1
      ;;
  esac

  if [ "${value}" = "/" ]; then
    echo "${name} must not be /." >&2
    exit 1
  fi

  case "${value}" in
    *[[:space:]]*)
      echo "${name} must not contain whitespace." >&2
      exit 1
      ;;
  esac
}

validate_absolute_dir "APP_DIR" "${APP_DIR}"
validate_absolute_dir "DEPLOY_DIR" "${DEPLOY_DIR}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not available in PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is not available. Install the docker compose plugin on the server." >&2
  exit 1
fi

if [ ! -f "${DEPLOY_DIR}/docker-compose.prod.yml" ]; then
  echo "Missing ${DEPLOY_DIR}/docker-compose.prod.yml." >&2
  exit 1
fi

if [ ! -f "${IMAGE_ARCHIVE}" ]; then
  echo "Missing Docker image archive: ${IMAGE_ARCHIVE}." >&2
  exit 1
fi

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

docker compose -f docker-compose.prod.yml config >/dev/null
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker image prune -f >/dev/null || true
rm -f "${DEPLOY_DIR}/runtime.env" "${IMAGE_ARCHIVE}" || true
docker compose -f docker-compose.prod.yml ps
