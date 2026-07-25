import gzip
import json
import tarfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from commercial_service import UPLOAD_ROOT, ensure_upload_directories
from config import settings
from models import OpsBackupRecord, get_now_naive


def ops_health_payload(session: Session) -> dict:
    database = {"ok": True, "message": "connected"}
    try:
        session.execute(text("SELECT 1")).first()
    except Exception as error:
        database = {"ok": False, "message": str(error)}

    uploads_path = UPLOAD_ROOT
    uploads_error = None
    try:
        ensure_upload_directories()
    except OSError as error:
        uploads_error = str(error)
    uploads = {"ok": uploads_path.exists() and uploads_path.is_dir(), "path": str(uploads_path)}
    if uploads_error:
        uploads["message"] = uploads_error

    backups_path = Path(settings.BACKUP_ROOT)
    logs_path = Path("logs")
    recent_errors = recent_error_logs(max_lines=settings.OPS_RECENT_LOG_LINES)
    return {
        "database": database,
        "uploads": uploads,
        "backups": {"ok": backups_path.exists(), "path": str(backups_path)},
        "logs": {"ok": logs_path.exists(), "path": str(logs_path)},
        "recent_errors": recent_errors["error_count"],
    }


def create_database_backup(
    session: Session,
    *,
    created_by: str,
    backup_root: Optional[str] = None,
) -> OpsBackupRecord:
    root = _ensure_backup_root(backup_root)
    backup_no = _backup_no("DB")
    file_path = root / f"{backup_no}.jsonl.gz"
    record = OpsBackupRecord(
        backup_no=backup_no,
        backup_type="database",
        status="created",
        file_path=str(file_path),
        file_name=file_path.name,
        created_by=created_by,
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    table_counts: dict[str, int] = {}
    try:
        engine = session.get_bind()
        inspector = inspect(engine)
        with gzip.open(file_path, "wt", encoding="utf-8") as handle:
            for table_name in sorted(inspector.get_table_names()):
                rows = session.execute(text(f"SELECT * FROM {_quoted_identifier(table_name)}")).mappings().all()
                table_counts[table_name] = len(rows)
                for row in rows:
                    handle.write(
                        json.dumps(
                            {"table": table_name, "row": dict(row)},
                            ensure_ascii=False,
                            default=_json_default,
                        )
                    )
                    handle.write("\n")
        record.status = "succeeded"
        record.file_size = file_path.stat().st_size
        record.table_counts_json = json.dumps(table_counts, ensure_ascii=False)
        record.completed_at = get_now_naive()
    except Exception as error:
        record.status = "failed"
        record.error_message = str(error)
        record.completed_at = get_now_naive()
        if file_path.exists():
            file_path.unlink()
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def create_uploads_backup(
    *,
    created_by: str,
    backup_root: Optional[str] = None,
    uploads_root: Optional[str] = None,
) -> OpsBackupRecord:
    root = _ensure_backup_root(backup_root)
    source_root = Path(uploads_root) if uploads_root else UPLOAD_ROOT
    backup_no = _backup_no("UP")
    file_path = root / f"{backup_no}.tar.gz"
    record = OpsBackupRecord(
        backup_no=backup_no,
        backup_type="uploads",
        status="created",
        file_path=str(file_path),
        file_name=file_path.name,
        created_by=created_by,
    )
    try:
        with tarfile.open(file_path, "w:gz") as archive:
            if source_root.exists():
                archive.add(source_root, arcname=source_root.name)
        record.status = "succeeded"
        record.file_size = file_path.stat().st_size
        record.table_counts_json = json.dumps({"files": _count_files(source_root)})
        record.completed_at = get_now_naive()
    except Exception as error:
        record.status = "failed"
        record.error_message = str(error)
        record.completed_at = get_now_naive()
        if file_path.exists():
            file_path.unlink()
    return record


def list_backup_records(session: Session, *, page: int = 1, page_size: int = 20) -> dict:
    statement = select(OpsBackupRecord).order_by(OpsBackupRecord.id.desc())
    records = session.exec(statement).all()
    total = len(records)
    offset = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [backup_record_payload(record) for record in records[offset:offset + page_size]],
    }


def backup_record_payload(record: OpsBackupRecord) -> dict:
    return {
        "id": record.id,
        "backup_no": record.backup_no,
        "backup_type": record.backup_type,
        "status": record.status,
        "file_name": record.file_name,
        "file_size": record.file_size,
        "table_counts": _json_loads(record.table_counts_json),
        "error_message": record.error_message,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }


def safe_backup_path(record: OpsBackupRecord, backup_root: Optional[str] = None) -> Path:
    if not record.file_path:
        raise ValueError("Backup file path is empty")
    root = _ensure_backup_root(backup_root)
    path = Path(record.file_path).resolve(strict=False)
    if path != root and root not in path.parents:
        raise ValueError("Backup path is outside backup root")
    if not path.exists() or not path.is_file():
        raise FileNotFoundError("Backup file not found")
    return path


def recent_error_logs(log_root: str = "logs", max_lines: int = 200) -> dict:
    root = Path(log_root)
    if not root.exists():
        return {"error_count": 0, "items": []}
    log_files = sorted(root.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)
    lines: list[str] = []
    for file_path in log_files[:5]:
        try:
            file_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line in file_lines[-max_lines:]:
            if any(marker in line for marker in (" ERROR ", " CRITICAL ", "Traceback")):
                lines.append(line)
    return {"error_count": len(lines), "items": lines[-max_lines:]}


def _ensure_backup_root(backup_root: Optional[str] = None) -> Path:
    root = Path(backup_root or settings.BACKUP_ROOT).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _backup_no(prefix: str) -> str:
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def _quoted_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _json_loads(value: Optional[str]) -> Optional[dict]:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _count_files(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if path.is_file())
