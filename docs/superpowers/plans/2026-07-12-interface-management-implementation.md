# Interface Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the old SDK onboarding and app authorization UI, then add interface management plus per-app interface enable/config/document viewing.

**Architecture:** Keep the existing FastAPI + SQLModel admin API style. Add two backend tables: `api_interfaces` stores reusable interface definitions and documentation; `app_interface_configs` stores each app's enable/config state for each interface. The frontend adds an "接口管理" submenu and lets each App open an interface list from the application operation panel.

**Tech Stack:** FastAPI, SQLModel, SQLite/MySQL lightweight schema migrations, Vue 3, Element Plus, Vite, pytest.

---

### Task 1: Backend Tests

**Files:**
- Create: `test_interface_management.py`

- [ ] **Step 1: Write failing tests**

Cover these behaviors:

```python
def test_interface_can_be_created_listed_and_updated():
    # POST /api/v1/admin/interfaces creates an interface with path, method, params, response, and docs.
    # GET /api/v1/admin/interfaces returns it.
    # PUT /api/v1/admin/interfaces/{id} updates status and docs.
```

```python
def test_app_interfaces_can_be_enabled_and_configured():
    # GET /api/v1/admin/apps/{app_id}/interfaces returns all defined interfaces with enabled=False by default.
    # PUT /api/v1/admin/apps/{app_id}/interfaces/{interface_id} enables one interface with quota, expiry, config, and remark.
    # A second GET shows enabled=True and returns the interface doc.
```

```python
def test_authorization_is_no_longer_exposed():
    # GET /api/v1/admin/apps should not include authorized_users.
    # POST /api/v1/admin/apps/{app_id}/authorize should return 404.
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest -q test_interface_management.py`

Expected: failures because `ApiInterface`, `AppInterfaceConfig`, and routes do not exist yet.

### Task 2: Backend Models and Schema

**Files:**
- Modify: `models.py`
- Modify: `database.py`
- Modify: `routes_admin.py`

- [ ] **Step 1: Add SQLModel tables**

Create `ApiInterface` with fields:

```python
id, name, interface_key, method, path, category, status,
request_params_json, response_example_json, doc_markdown,
created_at, updated_at
```

Create `AppInterfaceConfig` with fields:

```python
id, app_id, interface_id, enabled, quota_limit, expires_at,
config_json, remark, created_at, updated_at
```

Add a unique constraint on `(app_id, interface_id)`.

- [ ] **Step 2: Add SQLite/MySQL schema creation**

Ensure new installs and existing databases get `api_interfaces` and `app_interface_configs`.

- [ ] **Step 3: Remove app authorization from permission checks**

Change `check_app_permission` to allow only super admin or the app creator.

- [ ] **Step 4: Remove authorization data from app list**

`GET /api/v1/admin/apps` should no longer return `authorized_users`.

### Task 3: Backend Interface APIs

**Files:**
- Modify: `routes_admin.py`

- [ ] **Step 1: Add interface request models**

Add Pydantic request models for creating/updating interface definitions and app interface configs.

- [ ] **Step 2: Add interface definition routes**

Implement:

```text
POST /api/v1/admin/interfaces
GET /api/v1/admin/interfaces
PUT /api/v1/admin/interfaces/{interface_id}
```

- [ ] **Step 3: Add app interface routes**

Implement:

```text
GET /api/v1/admin/apps/{app_id}/interfaces
PUT /api/v1/admin/apps/{app_id}/interfaces/{interface_id}
```

- [ ] **Step 4: Disable authorization routes**

Remove the old authorization route handlers so their paths return 404.

- [ ] **Step 5: Run backend tests**

Run: `pytest -q test_interface_management.py test_admin_app_filters.py`

Expected: all pass.

### Task 4: Frontend Removal and New Pages

**Files:**
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Delete: `admin/src/views/SDK.vue`
- Modify: `admin/src/views/Apps.vue`
- Modify: `admin/src/views/Kamis.vue`
- Modify: `admin/src/views/Devices.vue`
- Modify: `admin/src/views/EventLogs.vue`
- Modify: `admin/src/views/Login.vue`
- Modify: `admin/src/api/admin.js`
- Create: `admin/src/api/interfaces.js`
- Create: `admin/src/views/InterfaceCreate.vue`
- Create: `admin/src/views/InterfaceList.vue`

- [ ] **Step 1: Remove "立即接入"**

Delete the `/sdk` route and side-menu item. Delete `SDK.vue`.

- [ ] **Step 2: Remove app authorization UI**

Remove authorization buttons, dialogs, API imports, and authorized-user client filtering. App filtering should rely on backend app visibility.

- [ ] **Step 3: Add interface API client**

Create API wrappers for interface definition and app-interface config routes.

- [ ] **Step 4: Add interface pages**

Create "新增接口" form and "接口列表" table with document viewing.

- [ ] **Step 5: Add app operation interface list**

In `Apps.vue`, add an "接口列表" button. The dialog lists all interfaces, lets the admin enable/disable/configure each interface, and view docs.

- [ ] **Step 6: Build frontend**

Run: `npm run build` in `admin`.

Expected: build passes.

### Task 5: Documentation and Verification

**Files:**
- Create: `INTERFACE_MANAGEMENT_API.md`

- [ ] **Step 1: Document new APIs**

Document interface definition routes, app interface config routes, and field meanings.

- [ ] **Step 2: Run full verification**

Run:

```text
pytest -q
npm run build
```

Then verify:

```text
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:3000/
```

Expected: tests pass, build passes, both services return 200.

---

**Self-review:** The plan covers all four requested changes: immediate onboarding removal, app authorization removal, app operation interface list, and interface management submenu with create/list/docs. It intentionally keeps SDK download files and stale `app_authorizations` table data untouched to avoid destructive data loss while removing the feature from UI/API behavior.
