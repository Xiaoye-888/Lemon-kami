from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlmodel import Session, select

from datetime_utils import to_api_beijing_iso
from models import App, AppNotice, AppVersion, get_now_naive


NOTICE_LEVELS = {"normal", "important", "urgent"}
UPDATE_PLATFORMS = {"all", "windows", "macos", "android"}
UPDATE_STATUSES = {"draft", "published", "archived"}
URL_TYPES = {"direct", "external"}


def normalize_notice_level(value: Optional[str]) -> str:
    level = (value or "normal").strip().lower()
    return level if level in NOTICE_LEVELS else "normal"


def normalize_update_platform(value: Optional[str]) -> str:
    platform = (value or "all").strip().lower()
    return platform if platform in UPDATE_PLATFORMS else "all"


def normalize_update_status(value: Optional[str]) -> str:
    status = (value or "draft").strip().lower()
    return status if status in UPDATE_STATUSES else "draft"


def normalize_url_type(value: Optional[str]) -> str:
    url_type = (value or "direct").strip().lower()
    return url_type if url_type in URL_TYPES else "direct"


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value and value.tzinfo:
        return value.replace(tzinfo=None)
    return value


def next_notice_revision(session: Session, app_id: str) -> int:
    notices = session.exec(select(AppNotice).where(AppNotice.app_id == app_id)).all()
    return max((notice.revision or 0 for notice in notices), default=0) + 1


def notice_payload(notice: AppNotice) -> dict:
    return {
        "id": notice.id,
        "app_id": notice.app_id,
        "title": notice.title,
        "content": notice.content,
        "level": normalize_notice_level(notice.level),
        "enabled": bool(notice.enabled),
        "popup": bool(notice.popup),
        "show_once": bool(notice.show_once),
        "revision": notice.revision,
        "starts_at": to_api_beijing_iso(notice.starts_at, naive="civil") if notice.starts_at else None,
        "ends_at": to_api_beijing_iso(notice.ends_at, naive="civil") if notice.ends_at else None,
        "created_by": notice.created_by,
        "created_at": to_api_beijing_iso(notice.created_at, naive="civil") if notice.created_at else None,
        "updated_at": to_api_beijing_iso(notice.updated_at, naive="civil") if notice.updated_at else None,
    }


def sdk_notice_payload(notice: Optional[AppNotice]) -> dict:
    if not notice:
        return {
            "notice_enabled": False,
            "notice_id": None,
            "notice_revision": None,
            "notice_title": None,
            "notice": None,
            "notice_level": "normal",
            "notice_popup": False,
            "show_once": True,
        }
    return {
        "notice_enabled": bool(notice.enabled),
        "notice_id": notice.id,
        "notice_revision": notice.revision,
        "notice_title": notice.title,
        "notice": notice.content,
        "notice_level": normalize_notice_level(notice.level),
        "notice_popup": bool(notice.popup),
        "show_once": bool(notice.show_once),
    }


def current_notice(session: Session, app: App) -> Optional[AppNotice]:
    now = get_now_naive()
    return session.exec(
        select(AppNotice)
        .where(
            AppNotice.app_id == app.app_id,
            AppNotice.enabled == True,  # noqa: E712
            or_(AppNotice.starts_at.is_(None), AppNotice.starts_at <= now),
            or_(AppNotice.ends_at.is_(None), AppNotice.ends_at >= now),
        )
        .order_by(AppNotice.revision.desc(), AppNotice.updated_at.desc(), AppNotice.id.desc())
    ).first()


def version_payload(version: AppVersion) -> dict:
    return {
        "id": version.id,
        "app_id": version.app_id,
        "platform": normalize_update_platform(version.platform),
        "version": version.version,
        "version_code": version.version_code,
        "title": version.title,
        "notes": version.notes,
        "force_update": bool(version.force_update),
        "download_url": version.download_url,
        "url_type": normalize_url_type(version.url_type),
        "button_text": version.button_text or "立即下载",
        "status": normalize_update_status(version.status),
        "created_by": version.created_by,
        "published_at": to_api_beijing_iso(version.published_at, naive="civil") if version.published_at else None,
        "created_at": to_api_beijing_iso(version.created_at, naive="civil") if version.created_at else None,
        "updated_at": to_api_beijing_iso(version.updated_at, naive="civil") if version.updated_at else None,
    }


def latest_published_version(
    session: Session,
    app: App,
    platform: Optional[str] = None,
) -> Optional[AppVersion]:
    normalized_platform = normalize_update_platform(platform)
    platform_values = {"all", normalized_platform}
    return session.exec(
        select(AppVersion)
        .where(
            AppVersion.app_id == app.app_id,
            AppVersion.status == "published",
            AppVersion.platform.in_(list(platform_values)),
        )
        .order_by(AppVersion.version_code.desc(), AppVersion.published_at.desc(), AppVersion.id.desc())
    ).first()


def _version_tuple(version: Optional[str]) -> tuple[int, ...]:
    if not version:
        return tuple()
    parts = []
    for part in version.replace("-", ".").split("."):
        number = ""
        for char in part:
            if not char.isdigit():
                break
            number += char
        if number:
            parts.append(int(number))
    return tuple(parts)


def has_client_update(
    latest: AppVersion,
    current_version_code: Optional[int],
    current_version: Optional[str],
) -> bool:
    if current_version_code is not None:
        return int(current_version_code) < int(latest.version_code)
    if current_version:
        return _version_tuple(current_version) < _version_tuple(latest.version)
    return True


def update_check_payload(
    latest: Optional[AppVersion],
    current_version_code: Optional[int],
    current_version: Optional[str],
) -> dict:
    if not latest or not has_client_update(latest, current_version_code, current_version):
        return {"has_update": False}
    return {
        "has_update": True,
        "latest_version": latest.version,
        "latest_version_code": latest.version_code,
        "platform": normalize_update_platform(latest.platform),
        "force_update": bool(latest.force_update),
        "update_title": latest.title,
        "update_notes": latest.notes,
        "download_url": latest.download_url,
        "url_type": normalize_url_type(latest.url_type),
        "button_text": latest.button_text or "立即下载",
    }


def normalize_notice_times(notice: AppNotice) -> None:
    notice.starts_at = _normalize_datetime(notice.starts_at)
    notice.ends_at = _normalize_datetime(notice.ends_at)
