from typing import Optional

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import or_
from sqlmodel import Session, select

import routes_admin
import routes_merchant
from audit_service import (
    CONFIRM_TEXT_BY_SCOPE,
    audit_log_payload,
    record_admin_audit,
    require_sensitive_confirmation,
)
from commercial_service import (
    approve_recharge_order,
    calculate_recharge_preview,
    clear_payment_channel_qrcode,
    cleanup_recharge_proofs,
    create_bonus_rule,
    create_recharge_option,
    delete_or_archive_bonus_rule,
    delete_or_archive_recharge_option,
    delete_payment_qrcode_by_url_if_safe,
    expire_recharge_order,
    get_recharge_order_or_404,
    payment_channel_payload,
    payment_qrcode_file_path,
    payment_qrcode_media_type,
    recharge_bonus_rule_payload,
    recharge_config_payload,
    recharge_option_payload,
    recharge_order_payload,
    save_payment_qrcode_upload,
    update_recharge_order_status,
    upsert_payment_channel,
    user_quota_transactions_payload,
)
from database import get_session
from datetime_utils import to_api_beijing_iso
from finance_service import (
    finance_summary_payload,
    merchant_recharge_ranking_payload,
    quota_transactions_csv,
    recharge_orders_csv,
)
from issue_pricing_service import (
    issue_pricing_rule_payload,
    list_issue_pricing_rules,
    upsert_issue_pricing_rule,
)
from models import (
    AdminAuditLog,
    App,
    EndUser,
    IssueQuotaPricingRule,
    RechargeBonusRule,
    RechargeOrder,
    RechargeOrderStatus,
    RechargePaymentChannel,
    UserAppAuthorization,
    UserQuotaAccount,
    UserQuotaTransaction,
)


router = APIRouter(prefix="/api/v1/admin/commercial", tags=["Admin Commercial"])
public_router = APIRouter(prefix="/api/v1/commercial", tags=["Commercial Public"])
get_current_user = routes_admin.get_current_user


class PaymentChannelRequest(BaseModel):
    channel: str = PydanticField(..., pattern="^(wechat|alipay|bank|other)$")
    display_name: str = PydanticField(..., min_length=1, max_length=64)
    qr_code_url: Optional[str] = None
    account_name: Optional[str] = PydanticField(None, max_length=128)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class RechargeOptionRequest(BaseModel):
    amount: int | float | str
    credit_quota: int = PydanticField(..., gt=0)
    label: Optional[str] = PydanticField(None, max_length=64)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class BonusRuleRequest(BaseModel):
    threshold_amount: int | float | str
    bonus_quota: int = PydanticField(..., gt=0)
    enabled: bool = True
    sort_order: int = 0
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class IssuePricingRuleRequest(BaseModel):
    target_type: str = PydanticField(..., max_length=32)
    user_id: Optional[int] = None
    spec_id: Optional[int] = None
    unit_cost: int = PydanticField(..., gt=0, le=100000000)
    enabled: bool = True
    remark: Optional[str] = None
    confirm_text: Optional[str] = None


class OrderReviewRequest(BaseModel):
    remark: Optional[str] = None
    reject_reason: Optional[str] = None
    confirm_text: Optional[str] = None


class RechargeProofCleanupRequest(BaseModel):
    older_than_days: int = PydanticField(..., ge=1, le=3650)
    dry_run: bool = True
    confirm_text: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    routes_admin._require_admin(current_user)


def _record_sensitive_business_failure(
    session: Session,
    *,
    admin: dict,
    action: str,
    resource_type: str,
    request: Request,
    error: Exception,
    resource_id: Optional[str] = None,
    target_user_id: Optional[int] = None,
    target_username: Optional[str] = None,
    before: Optional[dict] = None,
    metadata: Optional[dict] = None,
    status_code: int = 400,
) -> None:
    if isinstance(error, HTTPException):
        detail = error.detail
        status_code = error.status_code
    else:
        detail = str(error)
    error_message = detail if isinstance(detail, str) else str(detail)
    session.rollback()
    record_admin_audit(
        session,
        admin=admin,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        target_user_id=target_user_id,
        target_username=target_username,
        status="failed",
        request=request,
        before=before,
        metadata=metadata,
        error_message=error_message,
        summary=f"敏感操作失败：{action}",
    )
    if isinstance(error, HTTPException):
        raise error
    raise HTTPException(status_code=status_code, detail=error_message)


def _merchant_user_payload(user: EndUser, account: Optional[UserQuotaAccount]) -> dict:
    return {
        "id": user.id,
        "app_id": user.app_id,
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "kami_issue_balance": account.kami_issue_balance if account else 0,
        "total_kami_issue_granted": account.total_kami_issue_granted if account else 0,
        "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
        "last_login": to_api_beijing_iso(user.last_login, naive="civil") if user.last_login else None,
    }


def _merchant_detail_app_payload(app: App, *, source: str, authorization: Optional[UserAppAuthorization] = None) -> dict:
    is_owned = source == "self_owned"
    capabilities = {
        "can_view": True,
        "can_generate_kamis": True,
        "can_manage_batches": True,
        "can_rename": is_owned,
        "can_delete": is_owned,
        "can_manage_interfaces": is_owned,
    }
    payload = {
        "id": app.id,
        "app_id": app.app_id,
        "name": app.name,
        "source": source,
        "is_owned": is_owned,
        "status": app.status,
        "created_by": app.created_by,
        "owner_user_id": app.owner_user_id,
        "created_at": to_api_beijing_iso(app.created_at, naive="civil") if app.created_at else None,
        "authorization_id": authorization.id if authorization else None,
        "granted_by": authorization.granted_by if authorization else None,
        "authorized_at": (
            to_api_beijing_iso(authorization.created_at, naive="civil")
            if authorization and authorization.created_at
            else None
        ),
        "can_view_kamis": True,
        "capabilities": capabilities,
        **capabilities,
    }
    return payload


def _usage_user_payload(user: EndUser, app_name_by_id: dict[str, str]) -> dict:
    return {
        "id": user.id,
        "app_id": user.app_id,
        "app_name": app_name_by_id.get(user.app_id or "", user.app_id),
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "status": user.status,
        "created_at": to_api_beijing_iso(user.created_at, naive="civil"),
        "last_login": to_api_beijing_iso(user.last_login, naive="civil") if user.last_login else None,
    }


@public_router.get("/payment-qrcodes/{filename}", summary="Get payment QR code")
async def get_payment_qrcode(filename: str):
    try:
        path = payment_qrcode_file_path(filename)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payment QR code not found")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Payment QR code not found")
    return FileResponse(path, media_type=payment_qrcode_media_type(filename))


@router.get("/merchants", summary="List merchant/card issuer users")
async def list_merchants(
    keyword: Optional[str] = Query(None),
    status: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(EndUser).where(EndUser.app_id.is_(None))
    count_statement = select(EndUser).where(EndUser.app_id.is_(None))
    conditions = []
    if keyword:
        conditions.append(or_(EndUser.username.contains(keyword), EndUser.email.contains(keyword)))
    if status is not None:
        conditions.append(EndUser.status == status)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    merchants = session.exec(
        statement.order_by(EndUser.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total = len(session.exec(count_statement).all())
    user_ids = [user.id for user in merchants if user.id is not None]
    accounts = session.exec(
        select(UserQuotaAccount).where(UserQuotaAccount.user_id.in_(user_ids))
    ).all() if user_ids else []
    account_map = {account.user_id: account for account in accounts}
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                _merchant_user_payload(user, account_map.get(user.id))
                for user in merchants
            ],
        },
    }


@router.get("/merchants/{merchant_id}/detail", summary="Get merchant/card issuer detail")
async def get_merchant_detail(
    merchant_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    merchant = session.get(EndUser, merchant_id)
    if not merchant or merchant.app_id is not None:
        raise HTTPException(status_code=404, detail="Merchant not found")

    account = session.exec(select(UserQuotaAccount).where(UserQuotaAccount.user_id == merchant.id)).first()
    self_apps = session.exec(
        select(App)
        .where((App.owner_user_id == merchant.id) | (App.created_by == merchant.username))
        .order_by(App.id.desc())
    ).all()
    authorizations = session.exec(
        select(UserAppAuthorization)
        .where(UserAppAuthorization.user_id == merchant.id)
        .order_by(UserAppAuthorization.id.desc())
    ).all()
    authorized_app_ids = [authorization.app_id for authorization in authorizations]
    authorized_apps = session.exec(
        select(App).where(App.app_id.in_(authorized_app_ids)).order_by(App.id.desc())
    ).all() if authorized_app_ids else []
    app_by_id = {app.app_id: app for app in authorized_apps}

    visible_app_ids = sorted({app.app_id for app in self_apps}.union(authorized_app_ids))
    usage_users = session.exec(
        select(EndUser)
        .where(EndUser.app_id.in_(visible_app_ids))
        .order_by(EndUser.id.desc())
    ).all() if visible_app_ids else []
    visible_apps = {app.app_id: app.name for app in self_apps}
    visible_apps.update({app.app_id: app.name for app in authorized_apps})

    return {
        "success": True,
        "data": {
            "profile": _merchant_user_payload(merchant, account),
            "quota": {
                "kami_issue_balance": account.kami_issue_balance if account else 0,
                "total_kami_issue_granted": account.total_kami_issue_granted if account else 0,
            },
            "self_owned_apps": [
                _merchant_detail_app_payload(app, source="self_owned")
                for app in self_apps
            ],
            "authorized_apps": [
                _merchant_detail_app_payload(app_by_id[authorization.app_id], source="admin_authorized", authorization=authorization)
                for authorization in authorizations
                if authorization.app_id in app_by_id
            ],
            "usage_users": [_usage_user_payload(user, visible_apps) for user in usage_users],
        },
    }


def _get_admin_scoped_merchant_or_404(
    session: Session,
    merchant_id: int,
    current_user: dict,
) -> EndUser:
    _require_admin(current_user)
    merchant = session.get(EndUser, merchant_id)
    if not merchant or merchant.app_id is not None:
        raise HTTPException(status_code=404, detail="Merchant not found")
    return merchant


def _merchant_batch_apps(session: Session, merchant: EndUser) -> list[dict]:
    self_apps = session.exec(
        select(App)
        .where((App.owner_user_id == merchant.id) | (App.created_by == merchant.username))
        .order_by(App.id.desc())
    ).all()
    authorizations = session.exec(
        select(UserAppAuthorization)
        .where(UserAppAuthorization.user_id == merchant.id)
        .order_by(UserAppAuthorization.id.desc())
    ).all()
    authorized_app_ids = [authorization.app_id for authorization in authorizations]
    authorized_apps = session.exec(
        select(App).where(App.app_id.in_(authorized_app_ids)).order_by(App.id.desc())
    ).all() if authorized_app_ids else []
    app_by_id = {app.app_id: app for app in authorized_apps}

    items = [_merchant_detail_app_payload(app, source="self_owned") for app in self_apps]
    items.extend(
        _merchant_detail_app_payload(
            app_by_id[authorization.app_id],
            source="admin_authorized",
            authorization=authorization,
        )
        for authorization in authorizations
        if authorization.app_id in app_by_id
    )
    return items


@router.get("/merchants/{merchant_id}/batch-apps", summary="List batch-manageable apps for a merchant")
async def list_admin_scoped_merchant_batch_apps(
    merchant_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    items = _merchant_batch_apps(session, merchant)
    return {"success": True, "data": items, "items": items}


@router.delete("/merchants/{merchant_id}/apps/{app_id}", summary="Delete merchant self-owned app as admin")
async def delete_admin_scoped_merchant_app(
    merchant_id: int,
    app_id: str,
    request: Request,
    payload: Optional[routes_admin.SensitiveConfirmRequest] = None,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    effective_confirm_text = (
        payload.confirm_text
        if payload is not None and payload.confirm_text is not None
        else confirm_text
    )
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="delete_app",
        confirm_text=effective_confirm_text,
        resource_type="app",
        resource_id=app_id,
        request=request,
    )

    app = session.exec(
        select(App).where(
            App.app_id == app_id,
            (App.owner_user_id == merchant.id) | (App.created_by == merchant.username),
        )
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Merchant app not found")

    request.state.skip_delete_app_confirmation = True
    return await routes_admin.delete_app(
        app_id=app_id,
        request=request,
        payload=None,
        confirm_text=effective_confirm_text,
        current_user=current_user,
        session=session,
    )


@router.put("/merchants/{merchant_id}/apps/{app_id}", summary="Rename merchant self-owned app as admin")
async def update_admin_scoped_merchant_app(
    merchant_id: int,
    app_id: str,
    payload: routes_merchant.MerchantAppUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.update_merchant_app(
        app_id=app_id,
        payload=payload,
        current_user=merchant,
        session=session,
    )


@router.get("/merchants/{merchant_id}/quotas", summary="Get merchant quota as admin")
async def get_admin_scoped_merchant_quotas(
    merchant_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.get_merchant_quotas(current_user=merchant, session=session)


@router.get("/merchants/{merchant_id}/apps/{app_id}/specs", summary="List merchant app specs as admin")
async def list_admin_scoped_merchant_app_specs(
    merchant_id: int,
    app_id: str,
    kami_type: Optional[str] = Query(None),
    spec_group: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_app_specs(
        app_id,
        kami_type=kami_type,
        spec_group=spec_group,
        keyword=keyword,
        current_user=merchant,
        session=session,
    )


@router.post("/merchants/{merchant_id}/apps/{app_id}/specs", summary="Create merchant app spec as admin")
async def create_admin_scoped_merchant_app_spec(
    merchant_id: int,
    app_id: str,
    payload: routes_merchant.MerchantSpecCreateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.create_merchant_app_spec(app_id, payload, current_user=merchant, session=session)


@router.put("/merchants/{merchant_id}/apps/{app_id}/specs/{spec_id}", summary="Update merchant app spec as admin")
async def update_admin_scoped_merchant_app_spec(
    merchant_id: int,
    app_id: str,
    spec_id: int,
    payload: routes_merchant.MerchantSpecUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.update_merchant_app_spec(app_id, spec_id, payload, current_user=merchant, session=session)


@router.delete("/merchants/{merchant_id}/apps/{app_id}/specs/{spec_id}", summary="Delete merchant app spec as admin")
async def delete_admin_scoped_merchant_app_spec(
    merchant_id: int,
    app_id: str,
    spec_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.delete_merchant_app_spec(app_id, spec_id, current_user=merchant, session=session)


@router.post("/merchants/{merchant_id}/apps/{app_id}/kamis/preview", summary="Preview merchant kami issue as admin")
async def preview_admin_scoped_merchant_kamis(
    merchant_id: int,
    app_id: str,
    payload: routes_merchant.MerchantKamiIssueRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.preview_merchant_kamis(app_id, payload, current_user=merchant, session=session)


@router.post("/merchants/{merchant_id}/apps/{app_id}/kamis/batch", summary="Issue merchant kamis as admin")
async def issue_admin_scoped_merchant_kamis(
    merchant_id: int,
    app_id: str,
    payload: routes_merchant.MerchantKamiIssueRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.issue_merchant_kamis(app_id, payload, current_user=merchant, session=session)


@router.get("/merchants/{merchant_id}/apps/{app_id}/batches", summary="List merchant batches as admin")
async def list_admin_scoped_merchant_batches(
    merchant_id: int,
    app_id: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_batches(app_id, current_user=merchant, session=session)


@router.get("/merchants/{merchant_id}/kamis/export", summary="Export merchant kamis as admin")
async def export_admin_scoped_merchant_kamis(
    merchant_id: int,
    app_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    spec_id: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.export_merchant_kamis(
        app_id=app_id,
        keyword=keyword,
        status=status,
        batch_no=batch_no,
        spec_id=spec_id,
        current_user=merchant,
        session=session,
    )


@router.get("/merchants/{merchant_id}/kamis", summary="List merchant kamis as admin")
async def list_admin_scoped_merchant_kamis(
    merchant_id: int,
    app_id: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    spec_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_global_kamis(
        app_id=app_id,
        keyword=keyword,
        status=status,
        batch_no=batch_no,
        spec_id=spec_id,
        page=page,
        page_size=page_size,
        current_user=merchant,
        session=session,
    )


@router.post("/merchants/{merchant_id}/kamis/delete", summary="Delete merchant kamis as admin")
async def delete_admin_scoped_merchant_kamis(
    merchant_id: int,
    payload: routes_merchant.MerchantKamiDeleteRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    result = await routes_merchant.delete_merchant_kamis(payload, current_user=merchant, session=session)
    deleted_codes = (result.get("data") or {}).get("deleted_codes") or []
    if deleted_codes:
        admin_username = current_user.get("sub") or current_user.get("username")
        for code in deleted_codes:
            transaction = session.exec(
                select(UserQuotaTransaction).where(
                    UserQuotaTransaction.user_id == merchant.id,
                    UserQuotaTransaction.biz_id == f"kami_delete:{code}",
                )
            ).first()
            if not transaction:
                continue
            metadata = {}
            if transaction.metadata_json:
                try:
                    metadata = json.loads(transaction.metadata_json)
                except Exception:
                    metadata = {}
            metadata.update(
                {
                    "admin_scoped_merchant_id": merchant.id,
                    "admin_operator": admin_username,
                }
            )
            transaction.operator = admin_username
            transaction.metadata_json = json.dumps(metadata, ensure_ascii=False)
            session.add(transaction)
        session.commit()
    return result


@router.get("/merchants/{merchant_id}/kami-specs/{spec_id}/batches", summary="List merchant spec batches as admin")
async def list_admin_scoped_merchant_spec_batches(
    merchant_id: int,
    spec_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_spec_batches(spec_id, current_user=merchant, session=session)


@router.get("/merchants/{merchant_id}/kami-specs/{spec_id}/kamis", summary="List merchant spec kamis as admin")
async def list_admin_scoped_merchant_spec_kamis(
    merchant_id: int,
    spec_id: int,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    batch_no: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_spec_kamis(
        spec_id,
        keyword=keyword,
        status=status,
        batch_no=batch_no,
        page=page,
        page_size=page_size,
        current_user=merchant,
        session=session,
    )


@router.get("/merchants/{merchant_id}/batches/{batch_id}/kamis", summary="List merchant batch kamis as admin")
async def list_admin_scoped_merchant_batch_kamis(
    merchant_id: int,
    batch_id: int,
    keyword: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.list_merchant_batch_kamis(
        batch_id,
        keyword=keyword,
        status=status,
        page=page,
        page_size=page_size,
        current_user=merchant,
        session=session,
    )


@router.put("/merchants/{merchant_id}/batches/{batch_id}", summary="Update merchant batch as admin")
async def update_admin_scoped_merchant_batch(
    merchant_id: int,
    batch_id: int,
    payload: routes_merchant.MerchantBatchUpdateRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.update_merchant_batch(batch_id, payload, current_user=merchant, session=session)


@router.delete("/merchants/{merchant_id}/batches/{batch_id}", summary="Delete merchant batch as admin")
async def delete_admin_scoped_merchant_batch(
    merchant_id: int,
    batch_id: int,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.delete_merchant_batch(batch_id, current_user=merchant, session=session)


@router.post("/merchants/{merchant_id}/batches/{batch_id}/append", summary="Append merchant batch as admin")
async def append_admin_scoped_merchant_batch_kamis(
    merchant_id: int,
    batch_id: int,
    payload: routes_merchant.MerchantBatchAppendRequest,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    merchant = _get_admin_scoped_merchant_or_404(session, merchant_id, current_user)
    return await routes_merchant.append_merchant_batch_kamis(batch_id, payload, current_user=merchant, session=session)


@router.get("/overview", summary="Commercial operations overview")
async def commercial_overview(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    orders = session.exec(select(RechargeOrder)).all()
    pending = [order for order in orders if order.status == RechargeOrderStatus.pending_review]
    approved = [order for order in orders if order.status == RechargeOrderStatus.approved]
    return {
        "success": True,
        "data": {
            "orders_total": len(orders),
            "orders_pending_review": len(pending),
            "orders_approved": len(approved),
            "approved_amount": sum(order.amount_cents for order in approved) // 100,
            "credited_issue_quota": sum(order.credit_quota for order in approved),
        },
    }


@router.get("/recharge-config", summary="Get recharge configuration")
async def get_recharge_config(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {"success": True, "data": recharge_config_payload(session, enabled_only=False)}


@router.get("/issue-pricing/rules", summary="List issue quota pricing rules")
async def get_issue_pricing_rules(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    rules = list_issue_pricing_rules(session)
    data = {
        "items": [issue_pricing_rule_payload(rule) for rule in rules],
        "total": len(rules),
        "confirmation_text": CONFIRM_TEXT_BY_SCOPE["change_issue_pricing"],
    }
    return {"success": True, "data": data, **data}


@router.post("/issue-pricing/rules", summary="Create or update issue quota pricing rule")
async def save_issue_pricing_rule(
    payload: IssuePricingRuleRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_issue_pricing",
        confirm_text=payload.confirm_text,
        resource_type="issue_pricing_rule",
        request=request,
        metadata=payload.model_dump(exclude={"confirm_text"}),
    )
    try:
        rule = upsert_issue_pricing_rule(
            session,
            target_type=payload.target_type,
            user_id=payload.user_id,
            spec_id=payload.spec_id,
            unit_cost=payload.unit_cost,
            enabled=payload.enabled,
            remark=payload.remark,
            created_by=current_user.get("sub") or current_user.get("username"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
    session.refresh(rule)
    data = issue_pricing_rule_payload(rule)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_issue_pricing",
        resource_type="issue_pricing_rule",
        resource_id=rule.rule_key,
        target_user_id=rule.user_id,
        target_username=rule.username,
        request=request,
        after=data,
        summary=f"修改发卡额度规则 {rule.rule_key}",
    )
    return {"success": True, "data": data, **data}


@router.delete("/issue-pricing/rules/{rule_id}", summary="Delete issue quota pricing rule")
async def delete_issue_pricing_rule(
    rule_id: int,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    rule = session.get(IssueQuotaPricingRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Issue pricing rule not found")
    before = issue_pricing_rule_payload(rule)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_issue_pricing",
        confirm_text=payload.confirm_text,
        resource_type="issue_pricing_rule",
        resource_id=rule.rule_key,
        target_user_id=rule.user_id,
        target_username=rule.username,
        request=request,
    )
    session.delete(rule)
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="change_issue_pricing",
        resource_type="issue_pricing_rule",
        resource_id=before["rule_key"],
        target_user_id=before["user_id"],
        target_username=before["username"],
        request=request,
        before=before,
        summary=f"删除发卡额度规则 {before['rule_key']}",
    )
    return {"success": True, "data": {"deleted": True, "id": rule_id}}


@router.get("/payment-channels", summary="List payment channels")
async def list_payment_channels_route(
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {"success": True, "data": recharge_config_payload(session, enabled_only=False)["channels"]}


@router.post("/payment-channels", summary="Create or update payment channel")
async def save_payment_channel(
    payload: PaymentChannelRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="payment_channel",
        resource_id=payload.channel,
        request=request,
    )
    payload_data = payload.model_dump(exclude={"confirm_text"})
    try:
        row = upsert_payment_channel(session, **payload_data)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=payload.channel,
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="payment_channel",
        resource_id=payload.channel,
        request=request,
        after=payment_channel_payload(row),
        summary=f"保存收款渠道 {payload.channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_save",
        payload=payment_channel_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新充值收款渠道 {payload.channel}",
    )
    return {"success": True, "message": "payment channel saved", "data": payment_channel_payload(row)}


@router.post("/payment-channels/upload", summary="Create or update payment channel with QR upload")
async def save_payment_channel_with_upload(
    request: Request,
    channel: str = Form(..., pattern="^(wechat|alipay|bank|other)$"),
    display_name: str = Form(..., min_length=1, max_length=64),
    qr_code_url: Optional[str] = Form(None),
    account_name: Optional[str] = Form(None, max_length=128),
    enabled: bool = Form(True),
    sort_order: int = Form(0),
    remark: Optional[str] = Form(None),
    confirm_text: Optional[str] = Form(None),
    qr_code_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
    )
    existing = session.exec(
        select(RechargePaymentChannel).where(RechargePaymentChannel.channel == channel)
    ).first()
    old_qr_code_url = existing.qr_code_url if existing else None
    saved_qr_code_url = None
    try:
        if qr_code_file and qr_code_file.filename:
            saved_qr_code_url = await save_payment_qrcode_upload(qr_code_file, channel)
            qr_code_url = saved_qr_code_url
        elif existing and qr_code_url is None:
            qr_code_url = existing.qr_code_url
        row = upsert_payment_channel(
            session,
            channel=channel,
            display_name=display_name,
            qr_code_url=qr_code_url,
            account_name=account_name,
            enabled=enabled,
            sort_order=sort_order,
            remark=remark,
        )
        session.commit()
        session.refresh(row)
    except ValueError as error:
        if saved_qr_code_url:
            delete_payment_qrcode_by_url_if_safe(saved_qr_code_url)
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
        )
    except Exception as error:
        if saved_qr_code_url:
            delete_payment_qrcode_by_url_if_safe(saved_qr_code_url)
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
            status_code=500,
        )

    if saved_qr_code_url and old_qr_code_url and old_qr_code_url != saved_qr_code_url:
        delete_payment_qrcode_by_url_if_safe(old_qr_code_url)

    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
        after=payment_channel_payload(row),
        summary=f"保存收款渠道 {channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_save",
        payload=payment_channel_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新充值收款渠道 {channel}",
    )
    return {"success": True, "message": "payment channel saved", "data": payment_channel_payload(row)}


@router.delete("/payment-channels/{channel}/qrcode", summary="Delete payment channel QR code")
async def delete_payment_channel_qrcode(
    channel: str,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="delete_payment_qrcode",
        confirm_text=confirm_text,
        resource_type="payment_channel",
        resource_id=channel,
        request=request,
    )
    try:
        row, deleted_file = clear_payment_channel_qrcode(session, channel)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="delete_payment_qrcode",
            resource_type="payment_channel",
            resource_id=channel,
            request=request,
            error=error,
            status_code=404,
        )
    session.commit()
    session.refresh(row)
    payload = {**payment_channel_payload(row), "deleted_file": deleted_file}
    record_admin_audit(
        session,
        admin=current_user,
        action="delete_payment_qrcode",
        resource_type="payment_channel_qrcode",
        resource_id=channel,
        request=request,
        after=payload,
        summary=f"删除收款二维码 {channel}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_payment_channel_qrcode_delete",
        payload=payload,
        message=f"管理员 {current_user.get('sub')} 删除充值收款渠道 {channel} 的二维码",
    )
    return {"success": True, "message": "payment QR code deleted", "data": payload}


@router.post("/recharge-options", summary="Create or update fixed recharge option")
async def save_recharge_option(
    payload: RechargeOptionRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="recharge_option",
        request=request,
    )
    try:
        row = create_recharge_option(session, **payload.model_dump(exclude={"confirm_text"}))
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_option",
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_option",
        resource_id=row.id,
        request=request,
        after=recharge_option_payload(row),
        summary="保存固定充值档位",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_option_save",
        payload=recharge_option_payload(row),
        message=f"管理员 {current_user.get('sub')} 更新固定充值额度",
    )
    return {"success": True, "message": "recharge option saved", "data": recharge_option_payload(row)}


@router.delete("/recharge-options/{option_id}", summary="Delete or archive fixed recharge option")
async def delete_recharge_option(
    option_id: int,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="recharge_option",
        resource_id=option_id,
        request=request,
    )
    try:
        row, archived = delete_or_archive_recharge_option(session, option_id)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_option",
            resource_id=str(option_id),
            request=request,
            error=error,
            status_code=404,
        )
    data = {"id": option_id, "deleted": not archived, "archived": archived}
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_option",
        resource_id=option_id,
        request=request,
        after=data,
        summary=f"删除或归档固定充值档位 {option_id}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_option_delete",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 删除或归档固定充值额度 {option_id}",
    )
    return {"success": True, "message": "recharge option archived" if archived else "recharge option deleted", "data": data}


@router.post("/recharge-bonus-rules", summary="Create custom amount bonus rule")
async def save_bonus_rule(
    payload: BonusRuleRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=payload.confirm_text,
        resource_type="recharge_bonus_rule",
        request=request,
    )
    try:
        row = create_bonus_rule(session, **payload.model_dump(exclude={"confirm_text"}))
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_bonus_rule",
            request=request,
            error=error,
        )
    session.commit()
    session.refresh(row)
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_bonus_rule",
        resource_id=row.id,
        request=request,
        after=recharge_bonus_rule_payload(row),
        summary="保存充值赠送规则",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_bonus_rule_save",
        payload=recharge_bonus_rule_payload(row),
        message=f"管理员 {current_user.get('sub')} 新增自定义充值赠送规则",
    )
    return {"success": True, "message": "bonus rule saved", "data": recharge_bonus_rule_payload(row)}


@router.delete("/recharge-bonus-rules/{rule_id}", summary="Delete or archive custom recharge bonus rule")
async def delete_bonus_rule(
    rule_id: int,
    request: Request,
    confirm_text: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="change_recharge_config",
        confirm_text=confirm_text,
        resource_type="recharge_bonus_rule",
        resource_id=rule_id,
        request=request,
    )
    try:
        row, archived = delete_or_archive_bonus_rule(session, rule_id)
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="change_recharge_config",
            resource_type="recharge_bonus_rule",
            resource_id=str(rule_id),
            request=request,
            error=error,
            status_code=404,
        )
    data = {"id": rule_id, "deleted": not archived, "archived": archived}
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="change_recharge_config",
        resource_type="recharge_bonus_rule",
        resource_id=rule_id,
        request=request,
        after=data,
        summary=f"删除或归档充值赠送规则 {rule_id}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_bonus_rule_delete",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 删除或归档自定义充值赠送规则 {rule_id}",
    )
    return {"success": True, "message": "bonus rule archived" if archived else "bonus rule deleted", "data": data}


@router.post("/recharge-preview", summary="Preview recharge crediting")
async def preview_recharge_as_admin(
    amount: int | float | str,
    mode: str = "custom",
    option_id: Optional[int] = None,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        data = calculate_recharge_preview(session, amount=amount, mode=mode, option_id=option_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data}


@router.get("/audit-logs", summary="List admin audit logs")
async def list_admin_audit_logs(
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(AdminAuditLog)
    count_statement = select(AdminAuditLog)
    conditions = []
    if action:
        conditions.append(AdminAuditLog.action == action)
    if status:
        conditions.append(AdminAuditLog.status == status)
    if keyword:
        like_conditions = [
            AdminAuditLog.admin_username.contains(keyword),
            AdminAuditLog.target_username.contains(keyword),
            AdminAuditLog.resource_id.contains(keyword),
            AdminAuditLog.summary.contains(keyword),
            AdminAuditLog.error_message.contains(keyword),
        ]
        conditions.append(or_(*like_conditions))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = len(session.exec(count_statement).all())
    logs = session.exec(
        statement.order_by(AdminAuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {
            "items": [audit_log_payload(log) for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
            "confirmation_texts": CONFIRM_TEXT_BY_SCOPE,
        },
    }


@router.get("/recharge-orders", summary="List recharge orders")
async def list_recharge_orders(
    status: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    statement = select(RechargeOrder)
    count_statement = select(RechargeOrder)
    conditions = []
    if status:
        try:
            conditions.append(RechargeOrder.status == RechargeOrderStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if user_id is not None:
        conditions.append(RechargeOrder.user_id == user_id)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    total = len(session.exec(count_statement).all())
    orders = session.exec(
        statement.order_by(RechargeOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [recharge_order_payload(order, include_user=True) for order in orders],
        },
    }


@router.get("/finance/summary", summary="Commercial finance summary")
async def finance_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        data = finance_summary_payload(session, start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data, **data}


@router.get("/finance/merchant-ranking", summary="Commercial merchant recharge ranking")
async def finance_merchant_ranking(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        data = merchant_recharge_ranking_payload(session, start_date, end_date, limit=limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return {"success": True, "data": data, **data}


@router.get("/recharge-orders/export", summary="Export recharge orders CSV")
async def export_recharge_orders(
    status: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        content = recharge_orders_csv(
            session,
            status=status,
            username=username,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="recharge-orders.csv"'},
    )


@router.get("/recharge-orders/{order_no}", summary="Get recharge order detail")
async def get_recharge_order(
    order_no: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    return {"success": True, "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-proofs/cleanup", summary="Clean old terminal recharge proof files")
async def cleanup_old_recharge_proofs(
    payload: RechargeProofCleanupRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
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
        data = cleanup_recharge_proofs(
            session,
            older_than_days=payload.older_than_days,
            dry_run=payload.dry_run,
        )
    except ValueError as error:
        if not payload.dry_run:
            _record_sensitive_business_failure(
                session,
                admin=current_user,
                action="cleanup_proof_files",
                resource_type="recharge_proof",
                request=request,
                error=error,
                metadata={"older_than_days": payload.older_than_days},
            )
        raise HTTPException(status_code=400, detail=str(error))
    session.commit()
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
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_proof_cleanup",
        payload=data,
        message=f"管理员 {current_user.get('sub')} 清理充值凭证 dry_run={payload.dry_run}",
    )
    return {"success": True, "message": "proof cleanup checked" if payload.dry_run else "proof cleanup completed", "data": data}


@router.get("/recharge-orders/{order_no}/proof", summary="Get recharge proof image")
async def get_recharge_order_proof(
    order_no: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    if not order.proof_file_path or not Path(order.proof_file_path).exists():
        raise HTTPException(status_code=404, detail="Proof image not found")
    return FileResponse(order.proof_file_path, media_type=order.proof_content_type or "application/octet-stream")


@router.post("/recharge-orders/{order_no}/approve", summary="Approve recharge order")
async def approve_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="approve_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order, transaction = approve_recharge_order(
            session,
            order=order,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="approve_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    after = {**recharge_order_payload(order, include_user=True), "transaction": transaction}
    record_admin_audit(
        session,
        admin=current_user,
        action="approve_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=after,
        summary=f"审核通过充值订单 {order_no}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_order_approve",
        payload={"order_no": order_no, "transaction": transaction},
        message=f"管理员 {current_user.get('sub')} 审核通过充值订单 {order_no}",
    )
    return {
        "success": True,
        "message": "order approved",
        "data": {**recharge_order_payload(order, include_user=True), "transaction": transaction},
    }


@router.post("/recharge-orders/{order_no}/reject", summary="Reject recharge order")
async def reject_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="reject_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = update_recharge_order_status(
            session,
            order=order,
            status=RechargeOrderStatus.rejected,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
            reject_reason=payload.reject_reason,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="reject_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="reject_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"驳回充值订单 {order_no}",
    )
    return {"success": True, "message": "order rejected", "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-orders/{order_no}/expire", summary="Expire recharge order")
async def expire_order(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="expire_recharge_order",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = expire_recharge_order(
            session,
            order=order,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="expire_recharge_order",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="expire_recharge_order",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"关闭充值订单 {order_no}",
    )
    routes_admin.log_admin_action(
        session=session,
        username=current_user.get("sub"),
        event_type="commercial_recharge_order_expire",
        payload={"order_no": order_no, "remark": payload.remark},
        message=f"管理员 {current_user.get('sub')} 标记充值订单 {order_no} 已过期",
    )
    return {"success": True, "message": "order expired", "data": recharge_order_payload(order, include_user=True)}


@router.post("/recharge-orders/{order_no}/abnormal", summary="Mark recharge order abnormal")
async def mark_order_abnormal(
    order_no: str,
    payload: OrderReviewRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    order = get_recharge_order_or_404(session, order_no)
    before = recharge_order_payload(order, include_user=True)
    require_sensitive_confirmation(
        session,
        admin=current_user,
        action="mark_recharge_abnormal",
        confirm_text=payload.confirm_text,
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
    )
    try:
        order = update_recharge_order_status(
            session,
            order=order,
            status=RechargeOrderStatus.abnormal,
            reviewer=current_user.get("sub"),
            remark=payload.remark,
        )
    except ValueError as error:
        _record_sensitive_business_failure(
            session,
            admin=current_user,
            action="mark_recharge_abnormal",
            resource_type="recharge_order",
            resource_id=order_no,
            target_user_id=before.get("user_id"),
            target_username=before.get("username"),
            request=request,
            before=before,
            error=error,
        )
    session.commit()
    record_admin_audit(
        session,
        admin=current_user,
        action="mark_recharge_abnormal",
        resource_type="recharge_order",
        resource_id=order_no,
        target_user_id=order.user_id,
        target_username=order.username,
        request=request,
        before=before,
        after=recharge_order_payload(order, include_user=True),
        summary=f"标记充值订单异常 {order_no}",
    )
    return {"success": True, "message": "order marked abnormal", "data": recharge_order_payload(order, include_user=True)}


@router.get("/quota-transactions/export", summary="Export issue quota transactions CSV")
async def export_quota_transactions(
    username: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    try:
        content = quota_transactions_csv(
            session,
            username=username,
            transaction_type=transaction_type,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="quota-transactions.csv"'},
    )


@router.get("/quota-transactions", summary="List issue quota transactions")
async def list_quota_transactions(
    user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    _require_admin(current_user)
    return {
        "success": True,
        "data": user_quota_transactions_payload(
            session,
            user_id=user_id,
            page=page,
            page_size=page_size,
        ),
    }
