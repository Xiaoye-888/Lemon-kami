# Commercial Phase 1 Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct phase 1 commercial console scope so merchant/card-issuer users are clearly separated from application end users, only issue-card quota is exposed, and admin navigation matches the confirmed commercial backend.

**Architecture:** Keep the existing `EndUser` table for compatibility, but treat `EndUser.app_id IS NULL` as merchant/card-issuer accounts and `EndUser.app_id IS NOT NULL` as application usage users. Add shared merchant registration beside shared login, guard shared login and merchant APIs against application users, and constrain phase 1 UI to issue-card quota only.

**Tech Stack:** FastAPI, SQLModel, Vue 3, Pinia, Element Plus, pytest, Vite.

---

### Task 1: Backend Identity Boundary And Merchant Registration

**Files:**
- Modify: `routes_auth.py`
- Modify: `routes_merchant.py`
- Test: `tests/test_commercial_phase1.py`

- [ ] Add failing tests proving `/api/v1/auth/register` creates a merchant with `app_id=None`, returns role `merchant`, rejects duplicate admin usernames, and shared login rejects application end users with `app_id != None`.
- [ ] Add shared merchant registration request handling in `routes_auth.py`.
- [ ] Update shared login to only route `EndUser` rows with `app_id is None` into the merchant console.
- [ ] Add a merchant guard helper in `routes_merchant.py` so all merchant console APIs reject application end users.
- [ ] Run `pytest tests/test_commercial_phase1.py -q`.

### Task 2: Backend Admin Lists Split Merchant Users From Application Users

**Files:**
- Modify: `routes_admin.py`
- Modify: `routes_admin_advanced.py`
- Test: `tests/test_commercial_phase1.py`
- Test: `tests/test_unified_entitlements.py`

- [ ] Add failing tests proving admin end-user list/stats exclude merchant accounts by default and advanced quota/application authorization endpoints reject application users when used for merchant-only operations.
- [ ] Keep existing `/api/v1/admin/end-users` focused on application usage users by adding `EndUser.app_id != None` to default list/stats/export queries.
- [ ] Ensure merchant/user quota grant in phase 1 only accepts `kami_issue` for commercial workflows.
- [ ] Run `pytest tests/test_commercial_phase1.py tests/test_unified_entitlements.py -q`.

### Task 3: Frontend Login, Menu, And Quota Scope Corrections

**Files:**
- Modify: `admin/src/api/auth.js`
- Modify: `admin/src/stores/user.js`
- Modify: `admin/src/views/Login.vue`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/views/MerchantDashboard.vue`
- Modify: `admin/src/views/EndUsers.vue`
- Test: `tests/test_frontend_static.py`

- [ ] Add failing static tests proving the login page has merchant registration, admin menu has no standalone commercial backend item, admin issue quota transactions route is distinct, merchant dashboard hides app-create/recharge quota, and end-user management no longer renders quota/application authorization controls.
- [ ] Add frontend auth API and store support for merchant registration.
- [ ] Add login page registration toggle/dialog for merchant accounts only.
- [ ] Update admin navigation to match confirmed phase 1 entries and route issue quota transactions to `/admin/commercial/quota-transactions`.
- [ ] Add the missing admin quota transactions route/view wiring or reuse the existing commercial overview view only for overview, not transactions.
- [ ] Hide `app_create` and `recharge` quota fields from merchant dashboard and all phase 1 admin commercial UI.
- [ ] Remove quota management and app authorization controls from application end-user management.
- [ ] Run `pytest tests/test_frontend_static.py -q`.

### Task 4: Verification, Memory, Commit, Push, And Production Check

**Files:**
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [ ] Run full backend verification: `pytest -q`.
- [ ] Run frontend production build: `npm run build` in `admin`.
- [ ] Update Engramory with the corrected phase 1 identity boundary, visible UI scope, commands run, and deployment status.
- [ ] Stage only files touched for this correction, leaving unrelated `admin/package-lock.json` untouched.
- [ ] Commit with message `fix: correct commercial phase one boundaries`.
- [ ] Push to `origin main`, using one-command Git proxy overrides if the local proxy remains unavailable.
- [ ] Wait for GitHub Actions to complete.
- [ ] Verify production health and route behavior:
  - `GET http://154.12.26.231/health` returns 200.
  - `GET /api/v1/auth/login/public-key` returns 200.
  - Protected admin and merchant endpoints return 401 rather than 404.
  - Shared registration route is present.
