import argparse
import base64
import os
from pathlib import Path
from typing import Mapping


PLACEHOLDER_MARKERS = (
    "CHANGE_ME",
    "your-secret-key",
    "CHANGE_ME_RANDOM",
    "CHANGE_ME_BASE64",
    "CHANGE_ME_STRONG",
)


REQUIRED_KEYS = (
    "DATABASE_URL",
    "REDIS_URL",
    "SECRET_KEY",
    "LOGIN_AES_KEY",
    "BOOTSTRAP_ADMIN_PASSWORD",
)


def _is_placeholder(value: str) -> bool:
    upper_value = value.upper()
    return any(marker.upper() in upper_value for marker in PLACEHOLDER_MARKERS)


def _decode_aes_key(value: str) -> bytes | None:
    try:
        decoded = base64.b64decode(value, validate=True)
    except Exception:
        return None
    return decoded


def parse_env_file(path: str | Path) -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return env
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def validate_environment(env: Mapping[str, str]) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED_KEYS:
        value = (env.get(key) or "").strip()
        if not value:
            errors.append(f"{key} is required")
        elif _is_placeholder(value):
            errors.append(f"{key} still contains a placeholder value")

    secret_key = (env.get("SECRET_KEY") or "").strip()
    if secret_key and not _is_placeholder(secret_key) and len(secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")

    login_aes_key = (env.get("LOGIN_AES_KEY") or "").strip()
    if login_aes_key and not _is_placeholder(login_aes_key):
        decoded = _decode_aes_key(login_aes_key)
        if decoded is None or len(decoded) != 16:
            errors.append("LOGIN_AES_KEY must be base64 for exactly 16 bytes")

    cors_origins = (env.get("CORS_ALLOWED_ORIGINS") or "").strip()
    if cors_origins == "*" or any(origin.strip() == "*" for origin in cors_origins.split(",")):
        errors.append("CORS_ALLOWED_ORIGINS must list concrete origins, not *")

    enable_api_docs = (env.get("ENABLE_API_DOCS") or "").strip().lower()
    debug = (env.get("DEBUG") or "").strip().lower()
    if enable_api_docs in {"1", "true", "yes", "on"} and debug not in {"1", "true", "yes", "on"}:
        errors.append("ENABLE_API_DOCS should remain false outside DEBUG environments")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Lemon Kami deployment environment.")
    parser.add_argument("--env-file", default=".env", help="Path to env file to validate.")
    args = parser.parse_args()

    merged = dict(os.environ)
    merged.update(parse_env_file(args.env_file))
    errors = validate_environment(merged)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Environment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
