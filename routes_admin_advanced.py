from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_admin as legacy_admin
from commercial_service import delete_recharge_orders_for_users
from database import get_session
from datetime_utils import to_api_beijing_iso
from models import (
    App,
    EndUser,
    EventLog,
    Kami,
    KamiDeviceBinding,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
)
from user_quota_service import (
    grant_app_authorization,
    grant_user_quota,
    get_or_create_user_quota_account,
    user_quota_summary,
)


router = APIRouter(prefix="/api/v1/admin", tags=["Admin Advanced"])


class UserQuotaGrantRequest(BaseModel):
    quota_type: str = PydanticField(..., pattern="^(app_create|kami_issue|recharge)$")
    amount: int = PydanticField(..., gt=0)
    biz_id: Optional[str] = PydanticField(None, max_length=128)
    remark: Optional[str] = None
    metadata: Optional[dict] = None


class UserAppAuthorizationGrantRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    remark: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    legacy_admin._require_admin(current_user)


def _empty_quota_summary(user: EndUser) -> dict:
    return {
        "quota_account_id": None,
        "user_id": user.id,
        "username": user.username,
        "app_create_balance": 0,
        "kami_issue_balance": 0,
        "recharge_balance": 0,
        "total_app_create_granted": 0,
        "total_kami_issue_granted": 0,
        "total_recharge_granted": 0,
        "status": 1,
        "created_at": None,
        "updated_at": None,
    }


def _delete_kami_side_rows(session: Session, kami_codes: list[str]) -> None:
    if not kami_codes:
        return
    bindings = session.exec(
        select(KamiDeviceBinding).where(KamiDeviceBinding.kami_code.in_(kami_codes))
    ).all()
    for binding in bindings:
        session.delete(binding)

    logs = session.exec(
        select(EventLog).where(EventLog.kami_code.in_(kami_codes))
    ).all()
    for log in logs:
        session.delete(log)


@router.get("/end-users/{user_id}/quotas", summary="Get user quota summary")
async def get_end_user_quotas(
    user_id: int,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")
    account = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id == user_id)
    ).first()
    summary = user_quota_summary(account) if account else _empty_quota_summary(user)
    return {"success": True, "data": summary}


@router.post("/end-users/{user_id}/quotas/grant", summary="Grant user quota")
async def grant_end_user_quota(
    user_id: int,
    payload: UserQuotaGrantRequest,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")

    account = get_or_create_user_quota_account(session, user.id, user.username)
    try:
        transaction = grant_user_quota(
            session=session,
            account=account,
            quota_type=payload.quota_type,
            amount=payload.amount,
            operator=current_user.get("sub"),
            biz_id=payload.biz_id,
            remark=payload.remark,
            metadata=payload.metadata,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    session.commit()
    session.refresh(account)
    return {
        "success": True,
        "message": "quota granted",
        "data": {
            **user_quota_summary(account),
            "user": {"id": user.id, "username": user.username},
            "transaction": transaction,
        },
    }


@router.get("/end-users/{user_id}/app-authorizations", summary="List user app authorizations")
async def list_end_user_app_authorizations(
    user_id: int,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")

    authorizations = session.exec(
        select(UserAppAuthorization)
        .where(UserAppAuthorization.user_id == user_id)
        .order_by(UserAppAuthorization.id.desc())
    ).all()
    app_ids = [item.app_id for item in authorizations]
    apps = session.exec(select(App).where(App.app_id.in_(app_ids))).all() if app_ids else []
    app_map = {app.app_id: app for app in apps}
    return {
        "success": True,
        "data": [
            {
                "id": item.id,
                "app_id": item.app_id,
                "app_name": app_map[item.app_id].name if item.app_id in app_map else None,
                "user_id": item.user_id,
                "username": item.username,
                "granted_by": item.granted_by,
                "remark": item.remark,
                "created_at": to_api_beijing_iso(item.created_at, naive="civil"),
            }
            for item in authorizations
        ],
    }


@router.post("/end-users/{user_id}/app-authorizations", summary="Grant user app authorization")
async def grant_end_user_app_authorization(
    user_id: int,
    payload: UserAppAuthorizationGrantRequest,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    user = session.get(EndUser, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="End user not found")
    app = session.exec(select(App).where(App.app_id == payload.app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    authorization = grant_app_authorization(
        session=session,
        app_id=payload.app_id,
        user=user,
        granted_by=current_user.get("sub"),
        remark=payload.remark,
    )
    session.commit()
    return {
        "success": True,
        "message": "app authorization granted",
        "data": {
            "id": authorization.id,
            "app_id": authorization.app_id,
            "user_id": authorization.user_id,
            "username": authorization.username,
            "granted_by": authorization.granted_by,
            "remark": authorization.remark,
            "created_at": to_api_beijing_iso(authorization.created_at, naive="civil"),
        },
    }


@router.delete("/apps/{app_id}", summary="Delete app")
async def delete_app(
    app_id: str,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    app = session.exec(select(App).where(App.app_id == app_id)).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    auth_rows = session.exec(
        select(UserAppAuthorization).where(UserAppAuthorization.app_id == app_id)
    ).all()
    for row in auth_rows:
        session.delete(row)
    session.flush()

    result = await legacy_admin.delete_app(app_id, current_user=current_user, session=session)
    if isinstance(result.get("data"), dict):
        result["data"]["deleted_user_app_authorizations"] = len(auth_rows)
    else:
        result["deleted_user_app_authorizations"] = len(auth_rows)
    return result


@router.post("/end-users/delete", summary="Hard delete end users")
async def delete_end_users(
    payload: legacy_admin.EndUserDeleteRequest,
    current_user: dict = Depends(legacy_admin.get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    user_ids = list(dict.fromkeys(user_id for user_id in payload.user_ids if user_id))
    if not user_ids:
        raise HTTPException(status_code=400, detail="user_ids is required")

    users = session.exec(select(EndUser).where(EndUser.id.in_(user_ids))).all()
    if not users:
        return {
            "success": True,
            "message": "no users found",
            "data": {
                "deleted_users": 0,
                "deleted_user_quota_accounts": 0,
                "deleted_user_quota_transactions": 0,
                "deleted_user_app_authorizations": 0,
                "deleted_user_owned_apps": 0,
                "deleted_user_owned_kamis": 0,
                "deleted_recharge_orders": 0,
                "deleted_recharge_proofs": 0,
            },
        }

    found_user_ids = [user.id for user in users if user.id is not None]
    usernames = [user.username for user in users if user.username]
    owned_apps = session.exec(
        select(App).where(
            or_(
                App.owner_user_id.in_(found_user_ids),
                App.created_by.in_(usernames),
            )
        )
    ).all()
    owned_app_ids = [app.app_id for app in owned_apps if app.app_id]

    user_quota_accounts = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id.in_(found_user_ids))
    ).all()
    quota_account_ids = [account.id for account in user_quota_accounts if account.id is not None]
    user_quota_transactions = []
    if quota_account_ids:
        user_quota_transactions = session.exec(
            select(UserQuotaTransaction).where(UserQuotaTransaction.account_id.in_(quota_account_ids))
        ).all()

    user_app_authorizations = session.exec(
        select(UserAppAuthorization).where(
            or_(
                UserAppAuthorization.user_id.in_(found_user_ids),
                UserAppAuthorization.app_id.in_(owned_app_ids) if owned_app_ids else False,
            )
        )
    ).all()

    user_created_kamis = session.exec(
        select(Kami).where(Kami.created_by_user_id.in_(found_user_ids))
    ).all()
    user_created_kami_codes = [kami.kami_code for kami in user_created_kamis if kami.kami_code]
    _delete_kami_side_rows(session, user_created_kami_codes)
    for kami in user_created_kamis:
        session.delete(kami)

    for row in user_app_authorizations:
        session.delete(row)
    for tx in user_quota_transactions:
        session.delete(tx)
    session.flush()

    recharge_cleanup = delete_recharge_orders_for_users(session, found_user_ids)

    for account in user_quota_accounts:
        session.delete(account)
    session.flush()

    deleted_app_count = 0
    for app in owned_apps:
        if not app.app_id:
            continue
        await legacy_admin.delete_app(app.app_id, current_user=current_user, session=session)
        deleted_app_count += 1

    result = await legacy_admin.delete_end_users(payload, current_user=current_user, session=session)
    deleted_counts = result["data"]
    deleted_counts.update(
        {
            "deleted_user_quota_accounts": len(user_quota_accounts),
            "deleted_user_quota_transactions": len(user_quota_transactions),
            "deleted_user_app_authorizations": len(user_app_authorizations),
            "deleted_user_owned_apps": deleted_app_count,
            "deleted_user_owned_kamis": len(user_created_kamis),
            **recharge_cleanup,
        }
    )
    result["data"] = deleted_counts
    return result
