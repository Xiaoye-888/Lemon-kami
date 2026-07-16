# User Points System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build end-user registration/login plus a full user-bound points balance, recharge, consumption, transaction ledger, admin visibility, and API documentation.

**Architecture:** Add focused models for end users, point accounts, and point transactions. Put balance mutation rules in a service module so API routes stay thin and tests can run without MySQL or Redis. Extend existing admin routes and Vue views without restructuring the project.

**Tech Stack:** FastAPI, SQLModel, JWT via python-jose, Vue 3, Element Plus, pytest.

---

### Task 1: Points Service Tests

**Files:**
- Create: `test_points_service.py`

- [ ] Write tests that construct an in-memory SQLite database with `SQLModel.metadata.create_all`.
- [ ] Add fixtures for an `App`, an `EndUser`, and a points `Kami`.
- [ ] Verify redeeming a points kami creates or updates the account, increases balance, marks the kami as redeemed, and writes a recharge transaction.
- [ ] Verify redeeming the same kami twice raises an `already_redeemed` service error.
- [ ] Verify consuming points decreases balance, writes a consume transaction, and increments total consumed.
- [ ] Verify replaying the same `biz_id` with the same amount returns the existing transaction and does not charge twice.
- [ ] Verify replaying the same `biz_id` with a different amount raises a `biz_id_conflict` service error.
- [ ] Verify consuming more than the balance raises an `insufficient_balance` service error.

### Task 2: Models and Database Migration

**Files:**
- Modify: `models.py`
- Modify: `database.py`
- Modify: `init.sql`

- [ ] Add `EndUser`, `UserPointAccount`, `PointTransactionType`, and `PointTransaction`.
- [ ] Add `points_amount`, `redeemed_by_user_id`, and `redeemed_at` fields to `Kami`.
- [ ] Add migration SQL that creates the new tables if missing.
- [ ] Add migration SQL that adds the new `kamis` columns if missing.
- [ ] Update `init.sql` to match a fresh install schema.

### Task 3: Points Service

**Files:**
- Create: `point_service.py`

- [ ] Add `PointServiceError` with `code`, `message`, and `status_code`.
- [ ] Add `get_or_create_account(session, user_id)`.
- [ ] Add `redeem_points_kami(session, user, kami_code)`.
- [ ] Add `consume_points(session, user_id, amount, biz_id, remark, metadata)`.
- [ ] Add `adjust_points(session, user_id, amount, biz_id, remark, metadata, admin_username)`.
- [ ] Keep all balance and transaction writes in one commit per operation.

### Task 4: User API

**Files:**
- Create: `routes_user.py`
- Modify: `main.py`

- [ ] Add request models for register, login, redeem, and consume.
- [ ] Add JWT helpers for end-user tokens.
- [ ] Add `POST /api/v1/user/register`.
- [ ] Add `POST /api/v1/user/login`.
- [ ] Add `GET /api/v1/user/me`.
- [ ] Add points balance, redeem, consume, and transaction endpoints.
- [ ] Register `routes_user.router` in `main.py`.

### Task 5: Admin API Extensions

**Files:**
- Modify: `routes_admin.py`

- [ ] Extend `batch_create_kamis` with `points_amount`.
- [ ] Include points fields in kami list responses.
- [ ] Add end-user stats and list endpoints.
- [ ] Add end-user status update endpoint.
- [ ] Add point account and transaction list endpoints.
- [ ] Add admin balance adjustment endpoint.

### Task 6: Admin Frontend

**Files:**
- Modify: `admin/src/api/kami.js`
- Create: `admin/src/api/points.js`
- Modify: `admin/src/views/Kamis.vue`
- Create: `admin/src/views/EndUsers.vue`
- Create: `admin/src/views/Points.vue`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`

- [ ] Add `points_amount` to points kami generation.
- [ ] Show face value and redeem info in the kami table.
- [ ] Add end-user stats/list page.
- [ ] Add points accounts/transactions page with manual adjustment.
- [ ] Add routes and side menu entries.

### Task 7: API Documentation

**Files:**
- Create: `POINTS_API.md`
- Modify: `README.md`

- [ ] Document end-user auth.
- [ ] Document redeem, balance, consume, and transaction APIs.
- [ ] Document admin points endpoints.
- [ ] Document idempotency and error codes.
- [ ] Link the new document from README.

### Task 8: Verification

**Files:**
- All changed files

- [ ] Run the points service tests.
- [ ] Compile Python files.
- [ ] Run the Vue production build.
- [ ] Report any unavailable verification separately.
