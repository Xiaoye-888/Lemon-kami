from pathlib import Path
from typing import Optional
import re
import uuid

from fastapi import UploadFile


AVATAR_ROOT = Path("uploads") / "avatars"
PUBLIC_AVATAR_PREFIX = "/api/v1/profile/avatars"
SUPPORTED_AVATAR_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}
UPLOAD_CHUNK_BYTES = 1024 * 1024
MAX_AVATAR_BYTES = 2 * 1024 * 1024


def ensure_avatar_directories() -> None:
    AVATAR_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_file_prefix(prefix: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "_", (prefix or "").strip())
    return normalized.strip("_-") or "avatar"


def _image_extension(content_type: Optional[str], label: str) -> tuple[str, str]:
    normalized = (content_type or "").lower()
    extension = SUPPORTED_AVATAR_TYPES.get(normalized)
    if not extension:
        raise ValueError(f"unsupported {label} image type")
    return normalized, extension


async def save_avatar_upload(
    upload: UploadFile,
    *,
    file_prefix: str,
    max_bytes: int = MAX_AVATAR_BYTES,
) -> tuple[str, str, str]:
    content_type, extension = _image_extension(upload.content_type, "avatar")
    ensure_avatar_directories()
    filename = f"{_safe_file_prefix(file_prefix)}_{uuid.uuid4().hex[:12]}{extension}"
    final_path = AVATAR_ROOT / filename
    temp_path = AVATAR_ROOT / f".{filename}.tmp"
    size = 0
    try:
        with temp_path.open("wb") as target:
            while True:
                chunk = await upload.read(UPLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("avatar image is too large")
                target.write(chunk)
        if size <= 0:
            raise ValueError("avatar image is empty")
        temp_path.replace(final_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    finally:
        await upload.close()
    return final_path.as_posix(), filename, content_type


def avatar_public_url(filename: str) -> str:
    return f"{PUBLIC_AVATAR_PREFIX}/{filename}"


def avatar_file_path(filename: str) -> Path:
    if not filename or filename != Path(filename).name:
        raise ValueError("invalid avatar filename")
    path = AVATAR_ROOT / filename
    if not path.resolve().is_relative_to(AVATAR_ROOT.resolve()):  # pragma: no cover - defensive
        raise ValueError("invalid avatar filename")
    return path


def avatar_media_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"
