# Kami Spec Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change batch management from a flat batch list into an app-scoped card specification view: application -> card type -> common/custom specification -> batch records -> cards.

**Architecture:** Add a `kami_specs` layer while keeping existing `kami_batches`, `kamis`, SDK verify, and SDK consume behavior compatible. New admin endpoints aggregate cards by specification; existing batch endpoints remain available and attach batches/cards to a specification automatically.

**Tech Stack:** FastAPI, SQLModel, SQLite/MySQL migration helpers, Vue 3, Element Plus, Vite, pytest.

**UI Constraint:** Follow the current admin UI style: existing page card shell, filter strip, Element Plus table, colored type badges, icon action buttons, restrained pale blue background, and the current spacing/radius language. Do not introduce a new visual system.

**Repository Note:** This release folder is not a git repository. Plan steps therefore omit real commit commands for this workspace. If the implementation is executed inside a git repo, commit after each task.

---

## File Structure

**Create**
- `kami_spec_service.py`: deterministic spec-key builder, spec payload helpers, find/create logic, migration helpers used by admin routes.
- `tests/test_kami_specs.py`: backend regression tests for spec creation, grouping, generation, legacy batch compatibility, and non-integer-like custom values such as 68/143/150.

**Modify**
- `models.py`: add `KamiSpecGroup`, `KamiSpec`, and nullable `spec_id` on `KamiBatch` and `Kami`.
- `database.py`: create `kami_specs`, add `spec_id` columns/indexes, and backfill specs for existing batches/cards for both MySQL and SQLite paths.
- `routes_admin.py`: add spec request models/endpoints; wire existing batch create/generate/list/card-list paths to `spec_id`.
- `admin/src/api/kami.js`: add spec API helpers while keeping existing batch/card helpers.
- `admin/src/utils/kamiDisplay.js`: add spec display helpers and grouping labels.
- `admin/src/views/KamiBatches.vue`: replace default flat batch table with spec view, add spec detail view, preserve batch detail view.
- `admin/src/views/Kamis.vue`: add optional spec filter and keep `batch_no` compatibility.
- `KAMI_CORE_API.md`: document admin-facing spec management behavior and clarify that SDK clients do not call spec endpoints.
- `scripts/release_check.ps1`: add a static check for `kami_specs` migrations and frontend spec helpers.

---

### Task 1: Backend Model And Migration Shape

**Files:**
- Modify: `models.py`
- Modify: `database.py`
- Test: `tests/test_kami_specs.py`

- [ ] **Step 1: Create the failing model/migration test**

Create `tests/test_kami_specs.py` with this first test. It verifies that the new table and columns exist after `SQLModel.metadata.create_all`.

```python
from sqlalchemy import inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from models import App, Kami, KamiBatch, KamiSpec


def make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_kami_spec_schema_exists():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "kami_specs" in inspector.get_table_names()

    batch_columns = {column["name"] for column in inspector.get_columns("kami_batches")}
    kami_columns = {column["name"] for column in inspector.get_columns("kamis")}
    spec_columns = {column["name"] for column in inspector.get_columns("kami_specs")}

    assert "spec_id" in batch_columns
    assert "spec_id" in kami_columns
    assert {
        "app_id",
        "spec_key",
        "spec_name",
        "spec_group",
        "kami_type",
        "points_amount",
        "points_valid_days",
        "times_total",
        "time_value",
        "time_unit",
        "machine_bind_mode",
        "max_bind_devices",
        "authorization_owner",
        "user_bind_mode",
        "status",
        "sort_order",
    }.issubset(spec_columns)
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_kami_spec_schema_exists -q
```

Expected: fail because `KamiSpec` and `spec_id` do not exist yet.

- [ ] **Step 3: Add model definitions**

In `models.py`, add this enum near the existing card enums:

```python
class KamiSpecGroup(str, Enum):
    common = "common"
    custom = "custom"
```

Add this model before `class Kami`:

```python
class KamiSpec(SQLModel, table=True):
    __tablename__ = "kami_specs"
    __table_args__ = (
        UniqueConstraint("app_id", "spec_key", name="uk_kami_spec_app_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    app_id: str = Field(max_length=64, foreign_key="apps.app_id", index=True, description="App ID")
    spec_key: str = Field(max_length=255, index=True, description="Deterministic spec identity")
    spec_name: str = Field(max_length=128, index=True, description="Display name")
    spec_group: KamiSpecGroup = Field(default=KamiSpecGroup.custom, index=True, description="common/custom")
    kami_type: KamiType = Field(index=True, description="Card type")
    points_amount: Optional[int] = Field(default=None, description="Points face value")
    points_valid_days: Optional[int] = Field(default=None, description="Points validity days after redeem")
    time_value: Optional[int] = Field(default=None, description="Time-card duration value")
    time_unit: Optional[str] = Field(default=None, max_length=32, description="Time-card duration unit")
    times_total: Optional[int] = Field(default=None, description="Total allowed uses for times cards")
    machine_bind_mode: MachineBindMode = Field(default=MachineBindMode.one_card_one_device, index=True)
    max_bind_devices: int = Field(default=1, description="Max bound devices, 0 means unlimited")
    authorization_owner: AuthorizationOwnerMode = Field(default=AuthorizationOwnerMode.device, index=True)
    user_bind_mode: UserBindMode = Field(default=UserBindMode.none, index=True)
    status: int = Field(default=1, index=True, description="1 enabled, 0 disabled")
    sort_order: int = Field(default=0, index=True)
    remark: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=get_now_naive, index=True)
    updated_at: datetime = Field(default_factory=get_now_naive)
```

Add nullable `spec_id` to both `Kami` and `KamiBatch`:

```python
spec_id: Optional[int] = Field(default=None, foreign_key="kami_specs.id", index=True)
```

- [ ] **Step 4: Add MySQL migrations**

In `database.py`, in the MySQL schema section before `kami_batches` creation, create `kami_specs`:

```sql
CREATE TABLE kami_specs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    app_id VARCHAR(64) NOT NULL,
    spec_key VARCHAR(255) NOT NULL,
    spec_name VARCHAR(128) NOT NULL,
    spec_group VARCHAR(32) DEFAULT 'custom',
    kami_type ENUM('hour', 'day', 'week', 'month', 'quarter', 'year', 'lifetime', 'points', 'times') NOT NULL,
    points_amount INT DEFAULT NULL,
    points_valid_days INT DEFAULT NULL,
    time_value INT DEFAULT NULL,
    time_unit VARCHAR(32) DEFAULT NULL,
    times_total INT DEFAULT NULL,
    machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device',
    max_bind_devices INT DEFAULT 1,
    authorization_owner VARCHAR(32) DEFAULT 'device',
    user_bind_mode VARCHAR(32) DEFAULT 'none',
    status INT DEFAULT 1,
    sort_order INT DEFAULT 0,
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_app_id (app_id),
    INDEX idx_spec_key (spec_key),
    INDEX idx_spec_group (spec_group),
    INDEX idx_kami_type (kami_type),
    INDEX idx_status (status),
    INDEX idx_sort_order (sort_order),
    UNIQUE KEY uk_kami_spec_app_key (app_id, spec_key),
    FOREIGN KEY (app_id) REFERENCES apps(app_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Kami specifications'
```

For existing tables, add:

```sql
ALTER TABLE kami_batches ADD COLUMN spec_id INT DEFAULT NULL;
CREATE INDEX idx_kami_batches_spec_id ON kami_batches (spec_id);
ALTER TABLE kamis ADD COLUMN spec_id INT DEFAULT NULL;
CREATE INDEX idx_kamis_spec_id ON kamis (spec_id);
```

- [ ] **Step 5: Add SQLite migrations**

In the SQLite migration section, create the same `kami_specs` table using SQLite-compatible types:

```sql
CREATE TABLE IF NOT EXISTS kami_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id VARCHAR(64) NOT NULL,
    spec_key VARCHAR(255) NOT NULL,
    spec_name VARCHAR(128) NOT NULL,
    spec_group VARCHAR(32) DEFAULT 'custom',
    kami_type VARCHAR(32) NOT NULL,
    points_amount INTEGER DEFAULT NULL,
    points_valid_days INTEGER DEFAULT NULL,
    time_value INTEGER DEFAULT NULL,
    time_unit VARCHAR(32) DEFAULT NULL,
    times_total INTEGER DEFAULT NULL,
    machine_bind_mode VARCHAR(32) DEFAULT 'one_card_one_device',
    max_bind_devices INTEGER DEFAULT 1,
    authorization_owner VARCHAR(32) DEFAULT 'device',
    user_bind_mode VARCHAR(32) DEFAULT 'none',
    status INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(app_id, spec_key)
)
```

Add indexes for `app_id`, `spec_key`, `spec_group`, `kami_type`, `status`, and `sort_order`. Add nullable `spec_id` to `kami_batches` and `kamis`.

- [ ] **Step 6: Run the schema test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_kami_spec_schema_exists -q
```

Expected: pass.

---

### Task 2: Spec Service And Grouping Rules

**Files:**
- Create: `kami_spec_service.py`
- Modify: `routes_admin.py`
- Test: `tests/test_kami_specs.py`

- [ ] **Step 1: Add failing spec-key tests**

Append these tests to `tests/test_kami_specs.py`:

```python
from models import AuthorizationOwnerMode, KamiType, MachineBindMode, UserBindMode
from kami_spec_service import build_spec_key, build_spec_name, infer_spec_group


def test_points_specs_group_same_custom_value_with_same_policy():
    key_a = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )
    key_b = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )

    assert key_a == key_b
    assert build_spec_name(KamiType.points, 150, None, None, None, None) == "150积分"
    assert infer_spec_group(KamiType.points, 150, None, None, None, None) == "custom"


def test_points_specs_do_not_merge_different_policy():
    one_device_key = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.one_card_one_device,
        max_bind_devices=1,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )
    no_limit_key = build_spec_key(
        kami_type=KamiType.points,
        points_amount=150,
        points_valid_days=None,
        times_total=None,
        time_value=None,
        time_unit=None,
        machine_bind_mode=MachineBindMode.no_limit,
        max_bind_devices=0,
        authorization_owner=AuthorizationOwnerMode.auto,
        user_bind_mode=UserBindMode.auto,
    )

    assert one_device_key != no_limit_key


def test_common_values_are_classified_as_common():
    assert infer_spec_group(KamiType.points, 100, None, None, None, None) == "common"
    assert infer_spec_group(KamiType.points, 68, None, None, None, None) == "custom"
    assert infer_spec_group(KamiType.times, None, None, 10, None, None) == "common"
    assert infer_spec_group(KamiType.times, None, None, 143, None, None) == "custom"
    assert infer_spec_group(KamiType.month, None, None, None, 1, "month") == "common"
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py -q
```

Expected: fail because `kami_spec_service.py` does not exist.

- [ ] **Step 3: Implement spec helper functions**

Create `kami_spec_service.py` with:

```python
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from models import (
    AuthorizationOwnerMode,
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
```

- [ ] **Step 4: Implement find/create from batch**

Add to `kami_spec_service.py`:

```python
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
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py -q
```

Expected: all tests in `tests/test_kami_specs.py` pass.

---

### Task 3: Backfill Existing Batches And Cards

**Files:**
- Modify: `kami_spec_service.py`
- Modify: `database.py`
- Test: `tests/test_kami_specs.py`

- [ ] **Step 1: Add failing backfill test**

Append:

```python
from models import KamiStatus
from kami_spec_service import backfill_specs_for_session


def test_backfill_groups_existing_batches_by_value_and_policy():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        app = App(app_id="app_demo", app_name="Demo", app_secret="secret")
        session.add(app)
        session.commit()

        batch_a = KamiBatch(
            app_id="app_demo",
            batch_no="p150-a",
            kami_type=KamiType.points,
            points_amount=150,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        batch_b = KamiBatch(
            app_id="app_demo",
            batch_no="p150-b",
            kami_type=KamiType.points,
            points_amount=150,
            machine_bind_mode=MachineBindMode.one_card_one_device,
            max_bind_devices=1,
            authorization_owner=AuthorizationOwnerMode.auto,
            user_bind_mode=UserBindMode.auto,
        )
        session.add(batch_a)
        session.add(batch_b)
        session.commit()

        backfill_specs_for_session(session)
        session.refresh(batch_a)
        session.refresh(batch_b)

        assert batch_a.spec_id is not None
        assert batch_a.spec_id == batch_b.spec_id
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_backfill_groups_existing_batches_by_value_and_policy -q
```

Expected: fail because `backfill_specs_for_session` does not exist or does not update batches.

- [ ] **Step 3: Implement backfill helper**

Add to `kami_spec_service.py`:

```python
def backfill_specs_for_session(session: Session) -> int:
    changed = 0
    batches = session.exec(select(KamiBatch)).all()
    for batch in batches:
        if batch.spec_id:
            continue
        spec = find_or_create_spec_for_batch(session, batch)
        batch.spec_id = spec.id
        session.add(batch)
        changed += 1
    if changed:
        session.commit()
    return changed
```

- [ ] **Step 4: Call backfill from database init**

In `database.py`, after MySQL and SQLite schema migration blocks complete and after `SQLModel.metadata.create_all(engine)`, import and call:

```python
from kami_spec_service import backfill_specs_for_session

with Session(engine) as session:
    backfill_specs_for_session(session)
```

Place the import inside the function to avoid circular import during module load.

- [ ] **Step 5: Run backfill tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py -q
```

Expected: pass.

---

### Task 4: Admin Spec API

**Files:**
- Modify: `routes_admin.py`
- Modify: `kami_spec_service.py`
- Test: `tests/test_kami_specs.py`

- [ ] **Step 1: Add API tests for list and generate**

Append tests that use `TestClient` with dependency overrides. Use the existing `routes_admin.get_current_user` and `database.get_session` overrides:

```python
from fastapi.testclient import TestClient

import database
import routes_admin
from main import app as fastapi_app


def override_user():
    return {"sub": "admin", "is_admin": True}


def test_admin_spec_list_and_generate_flow():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[database.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(App(app_id="app_demo", app_name="Demo", app_secret="secret"))
        session.commit()

    create_response = client.post(
        "/api/v1/admin/kami-specs",
        json={
            "app_id": "app_demo",
            "kami_type": "points",
            "points_amount": 150,
            "machine_bind_mode": "one_card_one_device",
            "max_bind_devices": 1,
            "authorization_owner": "auto",
            "user_bind_mode": "auto",
            "spec_group": "custom",
            "status": 1,
        },
    )
    assert create_response.status_code == 200
    spec_id = create_response.json()["data"]["id"]

    generate_response = client.post(
        f"/api/v1/admin/kami-specs/{spec_id}/generate",
        json={"count": 2, "batch_no": "p150-test", "code_length": 8, "charset": "upper_numeric"},
    )
    assert generate_response.status_code == 200
    assert generate_response.json()["data"]["count"] == 2

    list_response = client.get("/api/v1/admin/kami-specs", params={"app_id": "app_demo", "kami_type": "points"})
    assert list_response.status_code == 200
    items = list_response.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["spec_name"] == "150积分"
    assert items[0]["batch_count"] == 1
    assert items[0]["total_count"] == 2
    assert items[0]["unused_count"] == 2

    fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run failing API test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_admin_spec_list_and_generate_flow -q
```

Expected: fail because `/api/v1/admin/kami-specs` endpoints do not exist.

- [ ] **Step 3: Add request models**

In `routes_admin.py`, add:

```python
class KamiSpecCreateRequest(BaseModel):
    app_id: str = PydanticField(..., max_length=64)
    kami_type: str
    spec_group: str = PydanticField("custom", max_length=32)
    points_amount: Optional[int] = PydanticField(None, gt=0)
    points_valid_days: Optional[int] = PydanticField(None, ge=1)
    times_total: Optional[int] = PydanticField(None, gt=0)
    time_value: Optional[int] = PydanticField(None, gt=0)
    time_unit: Optional[str] = PydanticField(None, max_length=32)
    machine_bind_mode: str = PydanticField(MachineBindMode.one_card_one_device.value, max_length=32)
    max_bind_devices: Optional[int] = PydanticField(None, ge=0, le=1000)
    authorization_owner: str = PydanticField(AuthorizationOwnerMode.device.value, max_length=32)
    user_bind_mode: str = PydanticField(UserBindMode.none.value, max_length=32)
    status: int = PydanticField(1, ge=0, le=1)
    sort_order: int = PydanticField(0, ge=0)
    remark: Optional[str] = None


class KamiSpecUpdateRequest(BaseModel):
    spec_group: Optional[str] = PydanticField(None, max_length=32)
    status: Optional[int] = PydanticField(None, ge=0, le=1)
    sort_order: Optional[int] = PydanticField(None, ge=0)
    remark: Optional[str] = None


class KamiSpecGenerateRequest(BaseModel):
    count: int = PydanticField(..., ge=1, le=1000)
    batch_no: Optional[str] = PydanticField(None, min_length=1, max_length=64)
    code_prefix: Optional[str] = PydanticField(None, max_length=32)
    code_length: int = PydanticField(16, ge=4, le=64)
    charset: str = PydanticField("upper_numeric", max_length=32)
```

- [ ] **Step 4: Import spec service and model**

In `routes_admin.py`, import `KamiSpec`, `KamiSpecGroup`, and service helpers:

```python
from kami_spec_service import (
    build_spec_key,
    build_spec_name,
    find_or_create_spec_for_batch,
    infer_spec_group,
)
```

- [ ] **Step 5: Add payload helper**

Add helper:

```python
def _kami_spec_payload(spec: KamiSpec, stats: Optional[dict] = None) -> dict:
    payload = {
        "id": spec.id,
        "app_id": spec.app_id,
        "spec_key": spec.spec_key,
        "spec_name": spec.spec_name,
        "spec_group": _enum_value(spec.spec_group),
        "kami_type": spec.kami_type.value,
        "points_amount": spec.points_amount,
        "points_valid_days": spec.points_valid_days,
        "time_value": spec.time_value,
        "time_unit": spec.time_unit,
        "times_total": spec.times_total,
        "machine_bind_mode": get_machine_bind_mode_value(spec.machine_bind_mode),
        "max_bind_devices": spec.max_bind_devices,
        "authorization_owner": get_authorization_owner_value(spec.authorization_owner),
        "user_bind_mode": get_user_bind_mode_value(spec.user_bind_mode),
        "status": spec.status,
        "sort_order": spec.sort_order,
        "remark": spec.remark,
        "created_at": to_api_beijing_iso(spec.created_at, naive="civil") if spec.created_at else None,
        "updated_at": to_api_beijing_iso(spec.updated_at, naive="civil") if spec.updated_at else None,
    }
    payload.update(stats or {
        "batch_count": 0,
        "total_count": 0,
        "unused_count": 0,
        "active_count": 0,
        "frozen_count": 0,
        "redeemed_count": 0,
        "times_remaining_total": 0,
        "points_remaining_total": 0,
    })
    return payload
```

- [ ] **Step 6: Add endpoints**

Add endpoints before existing `/kamis/batches` routes:

```python
@router.get("/kami-specs", summary="获取卡密规格列表")
async def list_kami_specs(...):
    ...

@router.post("/kami-specs", summary="创建卡密规格")
async def create_kami_spec(...):
    ...

@router.put("/kami-specs/{spec_id}", summary="更新卡密规格")
async def update_kami_spec(...):
    ...

@router.post("/kami-specs/{spec_id}/generate", summary="按规格生成卡密")
async def generate_kamis_for_spec(...):
    ...

@router.get("/kami-specs/{spec_id}/batches", summary="获取规格下批次")
async def list_kami_spec_batches(...):
    ...

@router.get("/kami-specs/{spec_id}/kamis", summary="获取规格下卡密")
async def list_kami_spec_kamis(...):
    ...
```

Implement `generate_kamis_for_spec` by creating a `KamiBatch` with the spec's card benefit and policy fields, setting `batch.spec_id`, and then reusing the same generation code path as `/admin/kamis/batch`. Do not duplicate validation logic for charset, count, and permissions.

- [ ] **Step 7: Run API test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_admin_spec_list_and_generate_flow -q
```

Expected: pass.

---

### Task 5: Existing Batch Compatibility

**Files:**
- Modify: `routes_admin.py`
- Modify: `kami_spec_service.py`
- Test: `tests/test_kami_specs.py`

- [ ] **Step 1: Add compatibility test**

Append:

```python
def test_legacy_batch_create_and_generate_attach_spec():
    engine = make_engine()
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    fastapi_app.dependency_overrides[database.get_session] = override_session
    fastapi_app.dependency_overrides[routes_admin.get_current_user] = override_user
    client = TestClient(fastapi_app)

    with Session(engine) as session:
        session.add(App(app_id="app_demo", app_name="Demo", app_secret="secret"))
        session.commit()

    batch_response = client.post(
        "/api/v1/admin/kamis/batches",
        json={
            "app_id": "app_demo",
            "batch_no": "p68-batch",
            "kami_type": "points",
            "points_amount": 68,
            "machine_bind_mode": "one_card_one_device",
            "max_bind_devices": 1,
            "authorization_owner": "auto",
            "user_bind_mode": "auto",
            "status": 1,
        },
    )
    assert batch_response.status_code == 200
    assert batch_response.json()["data"]["spec_id"] is not None

    generate_response = client.post(
        "/api/v1/admin/kamis/batch",
        params={"app_id": "app_demo", "batch_no": "p68-batch", "count": 1},
    )
    assert generate_response.status_code == 200

    with Session(engine) as session:
        batch = session.exec(select(KamiBatch).where(KamiBatch.batch_no == "p68-batch")).first()
        kami = session.exec(select(Kami).where(Kami.batch_no == "p68-batch")).first()
        assert batch.spec_id is not None
        assert kami.spec_id == batch.spec_id

    fastapi_app.dependency_overrides.clear()
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py::test_legacy_batch_create_and_generate_attach_spec -q
```

Expected: fail until existing batch routes set `spec_id`.

- [ ] **Step 3: Attach specs in existing create/update routes**

In `create_kami_batch`, after constructing the `KamiBatch`, call `find_or_create_spec_for_batch(session, batch)` after the first commit/refresh, set `batch.spec_id`, and commit again. Include `spec_id` in `_kami_batch_payload`.

In `update_kami_batch`, if editable fields change and the batch has no generated cards, recompute spec assignment. If the batch already has generated cards, keep benefit fields locked by existing validation and only allow status/remark/batch number changes.

- [ ] **Step 4: Attach spec_id to generated cards**

In `/admin/kamis/batch`, after loading `batch`, ensure:

```python
if not batch.spec_id:
    spec = find_or_create_spec_for_batch(session, batch)
    batch.spec_id = spec.id
    session.add(batch)
    session.commit()
else:
    spec = session.get(KamiSpec, batch.spec_id)
```

Set `Kami(spec_id=batch.spec_id, ...)` for every generated card.

- [ ] **Step 5: Keep old batch list output compatible**

In `list_kami_batches`, include `spec_id`, `spec_name`, and `spec_group` in each batch payload, but do not remove existing keys. Existing frontend calls must still receive `batch_no`, `kami_type`, `total_count`, `unused_count`, and all policy fields.

- [ ] **Step 6: Run compatibility tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_kami_specs.py -q
```

Expected: pass.

---

### Task 6: Frontend API And Display Helpers

**Files:**
- Modify: `admin/src/api/kami.js`
- Modify: `admin/src/utils/kamiDisplay.js`

- [ ] **Step 1: Add API helpers**

In `admin/src/api/kami.js`, add:

```javascript
export function getKamiSpecs(params) {
  return request({
    url: '/admin/kami-specs',
    method: 'get',
    params
  })
}

export function createKamiSpec(data) {
  return request({
    url: '/admin/kami-specs',
    method: 'post',
    data
  })
}

export function updateKamiSpec(specId, data) {
  return request({
    url: `/admin/kami-specs/${specId}`,
    method: 'put',
    data
  })
}

export function generateKamisForSpec(specId, data) {
  return request({
    url: `/admin/kami-specs/${specId}/generate`,
    method: 'post',
    data
  })
}

export function getKamiSpecBatches(specId, params) {
  return request({
    url: `/admin/kami-specs/${specId}/batches`,
    method: 'get',
    params
  })
}

export function getKamiSpecKamis(specId, params) {
  return request({
    url: `/admin/kami-specs/${specId}/kamis`,
    method: 'get',
    params
  })
}
```

- [ ] **Step 2: Add display helpers**

In `admin/src/utils/kamiDisplay.js`, add:

```javascript
export function getSpecGroupText(group) {
  return group === 'common' ? '常用规格' : '自定义规格'
}

export function getSpecBenefitText(row) {
  if (!row) return '-'
  if (row.kami_type === 'points') return `${row.points_amount || 0}积分`
  if (row.kami_type === 'times') return `${row.times_total || 0}次`
  return getValidityText(row)
}

export function getSpecPolicyText(row) {
  if (!row) return '-'
  return [
    getMachineBindModeText(row.machine_bind_mode, row.max_bind_devices),
    getAuthorizationOwnerText(row.authorization_owner),
    getUserBindModeText(row.user_bind_mode)
  ].filter(Boolean).join(' / ')
}
```

- [ ] **Step 3: Build frontend**

Run:

```powershell
cd admin
npm run build
```

Expected: build passes. It may still show the existing Vite chunk size warning if unrelated chunks remain large.

---

### Task 7: Batch Management Spec View

**Files:**
- Modify: `admin/src/views/KamiBatches.vue`

- [ ] **Step 1: Replace default list state**

Keep the existing page shell and header. Replace the default flat `batchStats` table with a spec list view:

```text
Header: 批次管理
Primary button: 生成卡密
Secondary button: 新建规格
Filters: 应用 / 类型 / 搜索规格 / 刷新
Tabs: 全部 / 时间卡 / 积分卡 / 次数卡
Sections: 常用规格, 自定义规格
```

Use the existing `yz-clean-table`, `.filter-strip`, `.type-badge`, `.icon-action`, and page-card styling.

- [ ] **Step 2: Add spec table columns**

For points specs:

```text
规格 / 类型 / 积分面额 / 批次 / 总数/已用/剩余 / 剩余积分 / 绑定策略 / 状态 / 操作
```

For times specs:

```text
规格 / 类型 / 每卡次数 / 批次 / 总数/已用/剩余 / 剩余次数 / 绑定策略 / 状态 / 操作
```

For time specs:

```text
规格 / 类型 / 有效期 / 批次 / 总数/已用/剩余 / 机器码限制 / 授权策略 / 状态 / 操作
```

- [ ] **Step 3: Add section behavior**

Common specs are visible by default. Custom specs are visible by default when there are 8 or fewer custom specs; when there are more than 8, render the custom section collapsed with a count:

```text
自定义规格 12个
```

The expand/collapse control uses a text link button in the section header, matching current Element Plus style.

- [ ] **Step 4: Add spec create dialog**

Use the current batch dialog style. Fields:

```text
应用
卡密类型
积分面额 or 可用次数 or 时间卡类型
规格分组: 常用规格 / 自定义规格
机器码绑定
授权归属
用户绑定
状态
备注
```

When entering custom values like `68`, `143`, or `150`, show a small help line:

```text
相同应用、类型、权益和绑定策略会自动归入同一规格。
```

- [ ] **Step 5: Add generate dialog**

When opened from a spec row, lock the spec fields and only ask for:

```text
生成数量
批次名称
卡密前缀
卡密长度
字符集
```

Default `batch_no` should be deterministic and readable:

```javascript
`${row.spec_name}-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}`
```

If the backend returns duplicate batch name, surface the backend message and let the user change the batch name.

- [ ] **Step 6: Preserve detail navigation**

Add routes through query string only, no new router path:

```text
/kamis/batches?app_id=xxx
/kamis/batches?app_id=xxx&spec_id=1
/kamis/batches?app_id=xxx&batch_no=batch-name
```

Spec detail shows spec summary, batch records, and a button to view all cards under the spec. Batch detail keeps the existing type-specific card table.

- [ ] **Step 7: Build frontend**

Run:

```powershell
cd admin
npm run build
```

Expected: build passes.

---

### Task 8: Global Card List Compatibility

**Files:**
- Modify: `admin/src/views/Kamis.vue`

- [ ] **Step 1: Add optional spec filter**

Add `spec_id` to `queryParams` and route query parsing. Keep `batch_no` filter working.

- [ ] **Step 2: Load specs after app selection**

When `queryParams.app_id` changes, call `getKamiSpecs({ app_id })` and populate a `specOptions` select:

```text
全部规格
100积分
150积分
10次
月卡
```

The option label includes policy text if duplicate display names exist.

- [ ] **Step 3: Update export and delete payload compatibility**

When exporting or deleting from a spec-filtered list, pass `spec_id` if present. Keep `batch_no` higher priority when both are present because batch detail should export/delete only that batch.

- [ ] **Step 4: Build frontend**

Run:

```powershell
cd admin
npm run build
```

Expected: build passes.

---

### Task 9: API Documentation And Release Checks

**Files:**
- Modify: `KAMI_CORE_API.md`
- Modify: `scripts/release_check.ps1`

- [ ] **Step 1: Document admin spec behavior**

Add an admin section:

```markdown
## 卡密规格管理

后台按规格管理卡密库存。规格属于应用，批次属于规格，卡密属于批次。

SDK 客户端不需要调用规格接口。客户端仍然只使用验证、消耗、应用配置、公告和下载接口。
```

Document:

```text
GET /api/v1/admin/kami-specs
POST /api/v1/admin/kami-specs
PUT /api/v1/admin/kami-specs/{id}
POST /api/v1/admin/kami-specs/{id}/generate
GET /api/v1/admin/kami-specs/{id}/batches
GET /api/v1/admin/kami-specs/{id}/kamis
```

- [ ] **Step 2: Extend release static checks**

In `scripts/release_check.ps1`, add checks that fail when these strings are missing:

```text
class KamiSpec
kami_specs
spec_id
/kami-specs
getKamiSpecs
generateKamisForSpec
```

- [ ] **Step 3: Run release check**

Run:

```powershell
.\scripts\release_check.ps1
```

Expected: release check completes without missing spec-management markers.

---

### Task 10: Full Verification

**Files:**
- No new implementation files.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Python compile check**

Run:

```powershell
.venv\Scripts\python.exe -m py_compile main.py routes_sdk.py routes_admin.py models.py authorization_service.py database.py interface_catalog.py routes_docs.py kami_spec_service.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run frontend build**

Run:

```powershell
cd admin
npm run build
```

Expected: build passes.

- [ ] **Step 4: Smoke test core flows**

Start backend and frontend on the existing local dev ports used in this workspace, or another free port:

```powershell
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8001
cd admin
npm run dev -- --host 127.0.0.1 --port 3001
```

Verify:

```text
登录后台成功
进入批次管理默认看到规格视图
常用规格和自定义规格分区展示
创建 150积分规格成功
同一 150积分规格追加生成新批次成功
68积分和143积分出现在自定义规格
进入规格详情能看到批次记录
进入批次详情能看到原有按类型字段表格
全局卡密列表能按规格筛选
SDK verify 不扣次数
SDK consume 扣次数
删除卡密仍记录事件日志
删除非空批次仍显示中文错误
```

- [ ] **Step 5: Run release smoke check**

Run:

```powershell
.\scripts\release_check.ps1 -Smoke -ApiBase http://127.0.0.1:8001 -FrontendBase http://127.0.0.1:3001
```

Expected: release smoke check passes.

---

## Execution Order

1. Backend model, migration, and spec service.
2. Admin spec endpoints and existing batch compatibility.
3. Frontend API helpers and display helpers.
4. Batch management spec view using the existing UI style.
5. Global card list compatibility.
6. Documentation, release checks, full verification.

This order keeps SDK behavior stable while gradually moving the admin UI from batch-first management to specification-first management.
