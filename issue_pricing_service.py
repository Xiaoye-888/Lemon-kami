from typing import Optional

from sqlmodel import Session, select

from models import App, EndUser, IssueQuotaPricingRule, KamiSpec, get_now_naive


TARGET_GLOBAL_SELF_APP = "global_self_app"
TARGET_GLOBAL_AUTHORIZED_APP = "global_authorized_app"
TARGET_SPEC_DEFAULT = "authorized_spec"
TARGET_USER_SELF_APP = "user_self_app"
TARGET_USER_AUTHORIZED_SPEC = "user_authorized_spec"

ISSUE_PRICING_TARGETS = {
    TARGET_GLOBAL_SELF_APP,
    TARGET_GLOBAL_AUTHORIZED_APP,
    TARGET_SPEC_DEFAULT,
    TARGET_USER_SELF_APP,
    TARGET_USER_AUTHORIZED_SPEC,
}


def app_is_self_owned_by_user(app: App, user: EndUser) -> bool:
    return app.owner_user_id == user.id or (bool(app.created_by) and app.created_by == user.username)


def issue_pricing_rule_key(target_type: str, *, user_id: Optional[int] = None, spec_id: Optional[int] = None) -> str:
    if target_type == TARGET_GLOBAL_SELF_APP:
        return "self:global"
    if target_type == TARGET_GLOBAL_AUTHORIZED_APP:
        return "authorized:global"
    if target_type == TARGET_SPEC_DEFAULT:
        if not spec_id:
            raise ValueError("spec_id is required")
        return f"authorized:spec:{spec_id}"
    if target_type == TARGET_USER_SELF_APP:
        if not user_id:
            raise ValueError("user_id is required")
        return f"self:user:{user_id}"
    if target_type == TARGET_USER_AUTHORIZED_SPEC:
        if not user_id:
            raise ValueError("user_id is required")
        if not spec_id:
            raise ValueError("spec_id is required")
        return f"authorized:user:{user_id}:spec:{spec_id}"
    raise ValueError("invalid pricing target type")


def issue_pricing_rule_payload(rule: IssueQuotaPricingRule) -> dict:
    return {
        "id": rule.id,
        "rule_key": rule.rule_key,
        "target_type": rule.target_type,
        "user_id": rule.user_id,
        "username": rule.username,
        "app_id": rule.app_id,
        "spec_id": rule.spec_id,
        "unit_cost": rule.unit_cost,
        "enabled": rule.enabled,
        "remark": rule.remark,
        "created_by": rule.created_by,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def list_issue_pricing_rules(session: Session) -> list[IssueQuotaPricingRule]:
    return session.exec(
        select(IssueQuotaPricingRule).order_by(
            IssueQuotaPricingRule.target_type,
            IssueQuotaPricingRule.user_id,
            IssueQuotaPricingRule.spec_id,
            IssueQuotaPricingRule.id,
        )
    ).all()


def upsert_issue_pricing_rule(
    session: Session,
    *,
    target_type: str,
    unit_cost: int,
    enabled: bool = True,
    user_id: Optional[int] = None,
    spec_id: Optional[int] = None,
    remark: Optional[str] = None,
    created_by: Optional[str] = None,
) -> IssueQuotaPricingRule:
    if target_type not in ISSUE_PRICING_TARGETS:
        raise ValueError("invalid pricing target type")
    if unit_cost <= 0:
        raise ValueError("unit_cost must be greater than 0")

    user = _merchant_or_none(session, user_id) if user_id else None
    spec = _spec_or_none(session, spec_id) if spec_id else None
    key = issue_pricing_rule_key(target_type, user_id=user_id, spec_id=spec_id)

    if target_type in {TARGET_GLOBAL_SELF_APP, TARGET_GLOBAL_AUTHORIZED_APP}:
        user = None
        spec = None
    if target_type == TARGET_SPEC_DEFAULT and not spec:
        raise ValueError("spec_id is required")
    if target_type == TARGET_USER_SELF_APP and not user:
        raise ValueError("user_id is required")
    if target_type == TARGET_USER_AUTHORIZED_SPEC and (not user or not spec):
        raise ValueError("user_id and spec_id are required")

    now = get_now_naive()
    rule = session.exec(select(IssueQuotaPricingRule).where(IssueQuotaPricingRule.rule_key == key)).first()
    if rule:
        rule.target_type = target_type
        rule.user_id = user.id if user else None
        rule.username = user.username if user else None
        rule.app_id = spec.app_id if spec else None
        rule.spec_id = spec.id if spec else None
        rule.unit_cost = unit_cost
        rule.enabled = enabled
        rule.remark = remark
        rule.updated_at = now
    else:
        rule = IssueQuotaPricingRule(
            rule_key=key,
            target_type=target_type,
            user_id=user.id if user else None,
            username=user.username if user else None,
            app_id=spec.app_id if spec else None,
            spec_id=spec.id if spec else None,
            unit_cost=unit_cost,
            enabled=enabled,
            remark=remark,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
    session.add(rule)
    session.flush()
    return rule


def resolve_issue_pricing(
    session: Session,
    *,
    user: EndUser,
    app: App,
    spec: Optional[KamiSpec] = None,
) -> dict:
    if app_is_self_owned_by_user(app, user):
        candidates = [
            (TARGET_USER_SELF_APP, issue_pricing_rule_key(TARGET_USER_SELF_APP, user_id=user.id)),
            (TARGET_GLOBAL_SELF_APP, issue_pricing_rule_key(TARGET_GLOBAL_SELF_APP)),
        ]
    else:
        candidates = []
        if spec and spec.id:
            candidates.extend(
                [
                    (
                        TARGET_USER_AUTHORIZED_SPEC,
                        issue_pricing_rule_key(
                            TARGET_USER_AUTHORIZED_SPEC,
                            user_id=user.id,
                            spec_id=spec.id,
                        ),
                    ),
                    (TARGET_SPEC_DEFAULT, issue_pricing_rule_key(TARGET_SPEC_DEFAULT, spec_id=spec.id)),
                ]
            )
        candidates.append((TARGET_GLOBAL_AUTHORIZED_APP, issue_pricing_rule_key(TARGET_GLOBAL_AUTHORIZED_APP)))

    for source, key in candidates:
        rule = session.exec(
            select(IssueQuotaPricingRule).where(
                IssueQuotaPricingRule.rule_key == key,
                IssueQuotaPricingRule.enabled == True,  # noqa: E712
            )
        ).first()
        if rule:
            return {
                "unit_cost": rule.unit_cost,
                "pricing_source": source,
                "pricing_rule_id": rule.id,
                "pricing_rule_key": rule.rule_key,
            }
    return {
        "unit_cost": 1,
        "pricing_source": "default",
        "pricing_rule_id": None,
        "pricing_rule_key": None,
    }


def _merchant_or_none(session: Session, user_id: Optional[int]) -> Optional[EndUser]:
    if not user_id:
        return None
    user = session.get(EndUser, user_id)
    if not user:
        raise ValueError("user_id is not found")
    if user.app_id is not None:
        raise ValueError("user_id must belong to a merchant account")
    return user


def _spec_or_none(session: Session, spec_id: Optional[int]) -> Optional[KamiSpec]:
    if not spec_id:
        return None
    spec = session.get(KamiSpec, spec_id)
    if not spec:
        raise ValueError("spec_id is not found")
    return spec
