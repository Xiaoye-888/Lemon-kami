from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, or_, select

from database import get_session
from models import ApiInterface
from routes_admin import _ensure_builtin_interfaces, _interface_payload


router = APIRouter(prefix="/api/v1/docs", tags=["Public API Docs"])


def _browser_prefers_html(accept_header: str) -> bool:
    accept = accept_header.lower()
    return "text/html" in accept and "application/json" not in accept


@router.get("/interfaces", summary="公开接口文档列表")
async def list_public_interface_docs(
    request: Request,
    category: Optional[str] = Query(None, description="接口分类"),
    keyword: Optional[str] = Query(None, description="接口名称、标识、说明或地址关键字"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """获取公开 API 文档需要的接口定义，不要求管理员登录。"""
    if _browser_prefers_html(request.headers.get("accept", "")):
        return RedirectResponse(url="/docs/api#basic-info")

    _ensure_builtin_interfaces(session)
    statement = select(ApiInterface).where(ApiInterface.status == 1)
    count_statement = select(ApiInterface).where(ApiInterface.status == 1)
    conditions = []
    if category:
        conditions.append(ApiInterface.category == category)
    if keyword:
        keyword_like = f"%{keyword}%"
        conditions.append(or_(
            ApiInterface.name.like(keyword_like),
            ApiInterface.interface_key.like(keyword_like),
            ApiInterface.path.like(keyword_like),
            ApiInterface.description.like(keyword_like),
        ))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)

    total = len(session.exec(count_statement).all())
    interfaces = session.exec(
        statement.order_by(ApiInterface.sort_order, ApiInterface.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_interface_payload(item) for item in interfaces],
        },
    }
