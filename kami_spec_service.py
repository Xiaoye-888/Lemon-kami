from typing import Optional

from sqlmodel import Session, select

from models import (
    AuthorizationOwnerMode,
    Kami,
    KamiBatch,
    KamiSpec,
    KamiSpecGroup,
    KamiType,
    MachineBindMode,
    UserBindMode,
    get_now_naive,
)


COMMON_POINT_VALUES = {100, 300, 500}
COMMON_TIMES_VALUES = {10, 30, 100}
TIME_CARD_LABELS = {
    KamiType.hour: "小时卡",
    KamiType.day: "天卡",
    KamiType.week: "周卡",
    KamiType.month: "月卡",
    KamiType.quarter: "季卡",
    KamiType.year: "年卡",
    KamiType.lifetime: "永久卡",
}


def enum_value(value):
    return value.value if hasattr(value, "value") else value


def build_spec_name(
    kami_type: KamiType,
    points_amount: Optional[int],
    points_valid_days: Optional[int],
    times_total: Optional[int],
    time_value: Optional[int],
    time_unit: Optional[str],
) -> str:
    if kami_type == KamiType.points:
        return f"{points_amount or 0}积分"
    if kami_type == KamiType.times:
        return f"{times_total or 0}次"
    return TIME_CARD_LABELS.get(kami_type, enum_value(kami_type))


def infer_spec_group(
    kami_type: KamiType,
    points_amount: Optional[int],
    points_valid_days: Optional[int],
    times_total: Optional[int],
    time_value: Optional[int],
    time_unit: Optional[str],
) -> str:
    if kami_type == KamiType.points:
        return KamiSpecGroup.common.value if points_amount in COMMON_POINT_VALUES else KamiSpecGroup.custom.value
    if kami_type == KamiType.times:
        return KamiSpecGroup.common.value if times_total in COMMON_TIMES_VALUES else KamiSpecGroup.custom.value
    return KamiSpecGroup.common.value


def build_spec_key(
    kami_type: KamiType,
    points_amount: Optional[int],
    points_valid_days: Optional[int],
    times_total: Optional[int],
    time_value: Optional[int],
    time_unit: Optional[str],
    machine_bind_mode: MachineBindMode,
    max_bind_devices: int,
    authorization_owner: AuthorizationOwnerMode,
    user_bind_mode: UserBindMode,
) -> str:
    benefit_part = "|".join([
        f"type={enum_value(kami_type)}",
        f"points={points_amount or 0}",
        f"points_valid_days={points_valid_days or 0}",
        f"times={times_total or 0}",
        f"time_value={time_value or 0}",
        f"time_unit={time_unit or ''}",
    ])
    policy_part = "|".join([
        f"machine={enum_value(machine_bind_mode)}",
        f"max_devices={max_bind_devices or 0}",
        f"owner={enum_value(authorization_owner)}",
        f"user_bind={enum_value(user_bind_mode)}",
    ])
    return f"{benefit_part}|{policy_part}"


def find_or_create_spec_for_batch(session: Session, batch: KamiBatch) -> KamiSpec:
    spec_key = build_spec_key(
        kami_type=batch.kami_type,
        points_amount=batch.points_amount,
        points_valid_days=batch.points_valid_days,
        times_total=batch.times_total,
        time_value=batch.time_value,
        time_unit=batch.time_unit,
        machine_bind_mode=batch.machine_bind_mode,
        max_bind_devices=batch.max_bind_devices,
        authorization_owner=batch.authorization_owner,
        user_bind_mode=batch.user_bind_mode,
    )
    existing = session.exec(
        select(KamiSpec).where(KamiSpec.app_id == batch.app_id, KamiSpec.spec_key == spec_key)
    ).first()
    if existing:
        return existing

    now = get_now_naive()
    spec = KamiSpec(
        app_id=batch.app_id,
        spec_key=spec_key,
        spec_name=build_spec_name(
            batch.kami_type,
            batch.points_amount,
            batch.points_valid_days,
            batch.times_total,
            batch.time_value,
            batch.time_unit,
        ),
        spec_group=infer_spec_group(
            batch.kami_type,
            batch.points_amount,
            batch.points_valid_days,
            batch.times_total,
            batch.time_value,
            batch.time_unit,
        ),
        kami_type=batch.kami_type,
        points_amount=batch.points_amount,
        points_valid_days=batch.points_valid_days,
        times_total=batch.times_total,
        time_value=batch.time_value,
        time_unit=batch.time_unit,
        machine_bind_mode=batch.machine_bind_mode,
        max_bind_devices=batch.max_bind_devices,
        authorization_owner=batch.authorization_owner,
        user_bind_mode=batch.user_bind_mode,
        status=batch.status,
        created_at=now,
        updated_at=now,
    )
    session.add(spec)
    session.commit()
    session.refresh(spec)
    return spec


def backfill_specs_for_session(session: Session) -> int:
    changed = 0
    batches = session.exec(select(KamiBatch)).all()
    for batch in batches:
        if not batch.spec_id:
            spec = find_or_create_spec_for_batch(session, batch)
            batch.spec_id = spec.id
            session.add(batch)
            changed += 1

        cards = session.exec(
            select(Kami).where(
                Kami.app_id == batch.app_id,
                Kami.batch_no == batch.batch_no,
                Kami.spec_id.is_(None),
            )
        ).all()
        for kami in cards:
            kami.spec_id = batch.spec_id
            session.add(kami)
            changed += 1

    if changed:
        session.commit()
    return changed
