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

echo "Resetting production runtime data; preserving admin_users only..."

mysql_exec() {
  docker compose -f docker-compose.prod.yml exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"'
}

mysql_query() {
  local query="$1"
  printf '%s\n' "${query}" | docker compose -f docker-compose.prod.yml exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -N -B -uroot "$MYSQL_DATABASE"'
}

active_admin_count="$(mysql_query 'SELECT COUNT(*) FROM admin_users WHERE status = 1;')"
active_admin_count="${active_admin_count//[[:space:]]/}"
if ! [[ "${active_admin_count}" =~ ^[0-9]+$ ]] || [ "${active_admin_count}" -lt 1 ]; then
  echo "Refusing data reset because no active admin user exists." >&2
  exit 1
fi

mapfile -t reset_tables < <(mysql_query "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME <> 'admin_users' ORDER BY TABLE_NAME;")
if [ "${#reset_tables[@]}" -gt 0 ]; then
  {
    printf 'SET FOREIGN_KEY_CHECKS=0;\n'
    for table in "${reset_tables[@]}"; do
      safe_table="${table//\`/\`\`}"
      printf 'TRUNCATE TABLE `%s`;\n' "${safe_table}"
    done
    printf 'SET FOREIGN_KEY_CHECKS=1;\n'
  } | mysql_exec
fi

non_empty_tables=()
for table in "${reset_tables[@]}"; do
  safe_table="${table//\`/\`\`}"
  row_count="$(mysql_query "SELECT COUNT(*) FROM \`${safe_table}\`;")"
  row_count="${row_count//[[:space:]]/}"
  if [ "${row_count}" != "0" ]; then
    non_empty_tables+=("${table}=${row_count}")
  fi
done

if [ "${#non_empty_tables[@]}" -gt 0 ]; then
  echo "Data reset verification failed: ${non_empty_tables[*]}" >&2
  exit 1
fi

docker compose -f docker-compose.prod.yml exec -T fastapi sh -c '
  set -eu
  for dir in /app/uploads /app/logs; do
    mkdir -p "$dir"
    case "$dir" in
      /app/uploads|/app/logs) find "$dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + ;;
      *) echo "Refusing to clean unexpected directory: $dir" >&2; exit 1 ;;
    esac
  done
'

docker compose -f docker-compose.prod.yml exec -T redis redis-cli FLUSHDB >/dev/null || true
docker compose -f docker-compose.prod.yml restart fastapi >/dev/null
echo "Runtime data reset completed; admin_users preserved and all other tables are empty."
docker compose -f docker-compose.prod.yml ps
