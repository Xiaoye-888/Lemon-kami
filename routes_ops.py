from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

import routes_admin
from audit_service import record_admin_audit, require_sensitive_confirmation
from commercial_service import cleanup_recharge_proofs
from config import settings
from database import get_session
from models import OpsBackupRecord
from ops_service import (
    backup_record_payload,
    create_database_backup,
    create_uploads_backup,
    list_backup_records,
    ops_health_payload,
    recent_error_logs,
    safe_backup_path,
)


router = APIRouter(prefix="/api/v1/admin/ops", tags=["Admin Ops"])
get_current_admin = routes_admin.get_current_user


class OpsBackupCreateRequest(BaseModel):
    backup_type: str = PydanticField("database", pattern="^(database|uploads)$")
    confirm_text: Optional[str] = None


class OpsBackupDownloadRequest(BaseModel):
    confirm_text: Optional[str] = None


class OpsProofCleanupRequest(BaseModel):
    older_than_days: int = PydanticField(..., ge=1, le=3650)
    dry_run: bool = True
    confirm_text: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    routes_admin._require_admin(current_user)


@router.get("/health", summary="Admin ops health")
async def get_ops_health(
    current_user: dict = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    data = ops_health_payload(session)
    return {"success": True, "data": data, **data}


@router.get("/backups", summary="List ops backups")
async def get_ops_backups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    data = list_backup_records(session, page=page, page_size=page_size)
    return {"success": True, "data": data, **data}


@router.post("/backups", summary="Create ops backup")
async def create_ops_backup(
    payload: OpsBackupCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="create_ops_backup",
        confirm_text=payload.confirm_text,
        resource_type="ops_backup",
        request=request,
        metadata={"backup_type": payload.backup_type},
    )
    if payload.backup_type == "database":
        record = create_database_backup(
            session,
            created_by=current_user.get("sub") or current_user.get("username") or "admin",
            backup_root=settings.BACKUP_ROOT,
        )
    else:
        record = create_uploads_backup(
            created_by=current_user.get("sub") or current_user.get("username") or "admin",
            backup_root=settings.BACKUP_ROOT,
        )
        session.add(record)
        session.flush()
    data = backup_record_payload(record)
    record_admin_audit(
        session,
        admin=current_user,
        action="create_ops_backup",
        resource_type="ops_backup",
        resource_id=record.backup_no,
        request=request,
        after=data,
        summary=f"创建运维备份 {record.backup_no}",
    )
    return {"success": True, "data": data, **data}


@router.post("/backups/{backup_no}/download", summary="Download ops backup")
async def download_ops_backup(
    backup_no: str,
    payload: OpsBackupDownloadRequest,
    request: Request,
    current_user: dict = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    record = session.exec(select(OpsBackupRecord).where(OpsBackupRecord.backup_no == backup_no)).first()
    if not record:
        raise HTTPException(status_code=404, detail="Backup not found")
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="download_ops_backup",
        confirm_text=payload.confirm_text,
        resource_type="ops_backup",
        resource_id=backup_no,
        request=request,
    )
    try:
        path = safe_backup_path(record, settings.BACKUP_ROOT)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    record_admin_audit(
        session,
        admin=current_user,
        action="download_ops_backup",
        resource_type="ops_backup",
        resource_id=backup_no,
        request=request,
        summary=f"下载运维备份 {backup_no}",
    )
    return FileResponse(path, filename=record.file_name or path.name, media_type="application/octet-stream")


@router.post("/uploads/proofs/cleanup", summary="Clean old recharge proof files")
async def cleanup_proof_uploads(
    payload: OpsProofCleanupRequest,
    request: Request,
    current_user: dict = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    if not payload.dry_run:
        require_sensitive_confirmation(
            session,
            admin=current_user,
            action="cleanup_proof_files",
            confirm_text=payload.confirm_text,
            resource_type="recharge_proof",
            request=request,
            metadata={"older_than_days": payload.older_than_days},
        )
    try:
        result = cleanup_recharge_proofs(
            session,
            older_than_days=payload.older_than_days,
            dry_run=payload.dry_run,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    data = {
        **result,
        "matched_count": result.get("matched_orders", 0),
        "deleted_count": result.get("deleted_proofs", 0),
    }
    if not payload.dry_run:
        record_admin_audit(
            session,
            admin=current_user,
            action="cleanup_proof_files",
            resource_type="recharge_proof",
            request=request,
            after=data,
            summary=f"清理超过 {payload.older_than_days} 天的充值凭证文件",
        )
    return {"success": True, "data": data, **data}


@router.get("/logs/recent-errors", summary="Read recent application errors")
async def get_recent_errors(
    max_lines: int = Query(settings.OPS_RECENT_LOG_LINES, ge=1, le=2000),
    current_user: dict = Depends(get_current_admin),
):
    _require_admin(current_user)
    data = recent_error_logs(max_lines=max_lines)
    return {"success": True, "data": data, **data}
