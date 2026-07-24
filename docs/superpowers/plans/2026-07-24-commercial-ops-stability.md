# Commercial Ops Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the next commercial-operations stability package: removable recharge config rows, order cancel/expire handling, proof retention cleanup, richer review detail data, and merchant issue-cost preview.

**Architecture:** Keep the existing phase 1 boundaries. Commercial business rules stay in `commercial_service.py`; admin-only operations stay in `routes_commercial.py`; merchant-facing operations stay in `routes_merchant.py`; Vue pages call the existing `admin/src/api/commercial.js` and `admin/src/api/merchant.js` clients. Do not introduce automatic payment callbacks or new quota types.

**Tech Stack:** FastAPI, SQLModel, pytest, Vue 3, Element Plus, Vite.

---

### Task 1: Recharge Config Delete/Archive

**Files:**
- Modify: `commercial_service.py`
- Modify: `routes_commercial.py`
- Modify: `tests/test_commercial_phase1.py`
- Modify: `admin/src/api/commercial.js`
- Modify: `admin/src/views/AdminRechargeSettings.vue`
- Modify: `tests/test_frontend_static.py`

- [x] **Step 1: Write failing backend tests**

Add tests proving:
- `DELETE /api/v1/admin/commercial/recharge-options/{option_id}` removes an unused fixed option.
- deleting a fixed option referenced by an order returns an archived result and disables the option instead of deleting it.
- `DELETE /api/v1/admin/commercial/recharge-bonus-rules/{rule_id}` removes an unused rule.
- deleting a rule referenced by an order returns an archived result and disables the rule instead of deleting it.

Run: `pytest tests\test_commercial_phase1.py::test_admin_can_delete_unused_recharge_config_and_archives_used_rows -q`
Expected: FAIL because delete routes do not exist.

- [x] **Step 2: Implement service helpers**

Add helpers:
- `delete_or_archive_recharge_option(session, option_id) -> tuple[RechargeOption, bool]`
- `delete_or_archive_bonus_rule(session, rule_id) -> tuple[RechargeBonusRule, bool]`

Rules:
- Missing row raises `ValueError`.
- If no recharge order references the row, delete it and return archived false.
- If any order references the row, set `enabled=False`, update `updated_at`, and return archived true.

- [x] **Step 3: Add admin routes**

Add:
- `DELETE /api/v1/admin/commercial/recharge-options/{option_id}`
- `DELETE /api/v1/admin/commercial/recharge-bonus-rules/{rule_id}`

Responses include `{ deleted: true, archived: false }` or `{ deleted: false, archived: true }`. Log admin action for both.

- [x] **Step 4: Add frontend controls**

Add delete buttons in recharge settings fixed-option and bonus-rule tables. Use confirmation text explaining that used rows are archived/disabled rather than removed.

- [x] **Step 5: Verify**

Run:
- `pytest tests\test_commercial_phase1.py::test_admin_can_delete_unused_recharge_config_and_archives_used_rows -q`
- `pytest tests\test_frontend_static.py::test_commercial_recharge_pages_expose_order_review_and_upload_flow -q`

Expected: PASS.

### Task 2: Order Cancel and Expire Handling

**Files:**
- Modify: `commercial_service.py`
- Modify: `routes_commercial.py`
- Modify: `routes_merchant.py`
- Modify: `tests/test_commercial_phase1.py`
- Modify: `admin/src/api/commercial.js`
- Modify: `admin/src/views/AdminRechargeOrders.vue`
- Modify: `admin/src/api/merchant.js`
- Modify: `admin/src/views/MerchantOrders.vue`

- [x] **Step 1: Write failing backend tests**

Add tests proving:
- Merchant can cancel own `pending_review` order.
- Merchant cannot cancel approved/rejected/abnormal orders.
- Admin can expire a pending order.
- Admin cannot approve canceled or expired orders.
- Order list supports `canceled` and `expired` status filters.

Run: `pytest tests\test_commercial_phase1.py::test_recharge_orders_can_be_canceled_and_expired_before_review -q`
Expected: FAIL because cancel/expire routes do not exist.

- [x] **Step 2: Implement service status transitions**

Add:
- `cancel_recharge_order(session, order, operator, remark=None)`
- `expire_recharge_order(session, order, reviewer, remark=None)`

Rules:
- Only `pending_review` can become `canceled` or `expired`.
- Approved orders remain immutable.
- Both transitions update `updated_at`; admin expire also sets reviewer/reviewed_at/admin_remark.

- [x] **Step 3: Add routes**

Add:
- Merchant: `POST /api/v1/merchant/recharge/orders/{order_no}/cancel`
- Admin: `POST /api/v1/admin/commercial/recharge-orders/{order_no}/expire`

- [x] **Step 4: Add frontend buttons and filters**

Add status labels/filters for canceled and expired in admin and merchant order pages. Merchant order rows get a cancel button for pending orders. Admin order rows get an expire button for pending orders.

- [x] **Step 5: Verify**

Run:
- `pytest tests\test_commercial_phase1.py::test_recharge_orders_can_be_canceled_and_expired_before_review -q`
- `pytest tests\test_frontend_static.py -q`

Expected: PASS.

### Task 3: Payment Proof Retention Cleanup

**Files:**
- Modify: `commercial_service.py`
- Modify: `routes_commercial.py`
- Modify: `tests/test_commercial_phase1.py`
- Modify: `admin/src/api/commercial.js`
- Modify: `admin/src/views/AdminRechargeOrders.vue`

- [x] **Step 1: Write failing backend tests**

Add a test proving admin cleanup deletes proof files older than N days for terminal orders only, leaves pending orders untouched, and clears file metadata on cleaned orders.

Run: `pytest tests\test_commercial_phase1.py::test_admin_cleanup_recharge_proofs_removes_only_terminal_old_files -q`
Expected: FAIL because cleanup route does not exist.

- [x] **Step 2: Implement cleanup helper**

Add `cleanup_recharge_proofs(session, older_than_days, dry_run=True)`. Terminal statuses are `approved`, `rejected`, `canceled`, `expired`, and `abnormal`. Dry run returns counts without deleting. Non-dry run deletes files safely under `UPLOAD_ROOT`, clears `proof_file_path`, `proof_file_name`, and `proof_content_type`, and updates `updated_at`.

- [x] **Step 3: Add admin route**

Add `POST /api/v1/admin/commercial/recharge-proofs/cleanup` with body `{ older_than_days: int, dry_run: bool }`. Default is dry run true.

- [x] **Step 4: Add admin UI action**

In recharge orders, add a toolbar action for proof cleanup. It first runs dry-run, shows counts, then allows confirmed cleanup.

- [x] **Step 5: Verify**

Run:
- `pytest tests\test_commercial_phase1.py::test_admin_cleanup_recharge_proofs_removes_only_terminal_old_files -q`
- `pytest tests\test_frontend_static.py -q`

Expected: PASS.

### Task 4: Review Detail Payload and UI

**Files:**
- Modify: `commercial_service.py`
- Modify: `admin/src/views/AdminRechargeOrders.vue`
- Modify: `tests/test_frontend_static.py`

- [x] **Step 1: Write failing static test**

Add assertions that admin recharge orders render an order detail drawer/dialog including order number, username, amount, base quota, bonus quota, credit quota, current status, user remark, admin remark, reject reason, payment snapshot, preview snapshot, reviewer, reviewed time, and proof action.

Run: `pytest tests\test_frontend_static.py::test_admin_recharge_orders_expose_review_detail_drawer -q`
Expected: FAIL because detail drawer is not present.

- [x] **Step 2: Ensure payload exposes snapshots**

If `recharge_order_payload` currently returns snapshot JSON strings only, parse them to `payment_snapshot` and `preview_snapshot` while preserving old string fields for compatibility.

- [x] **Step 3: Add admin detail drawer**

Add a row “详情” action. The drawer shows readonly details and keeps approve/reject/expire actions available for pending orders.

- [x] **Step 4: Verify**

Run:
- `pytest tests\test_frontend_static.py::test_admin_recharge_orders_expose_review_detail_drawer -q`
- `pytest tests\test_commercial_phase1.py -q`

Expected: PASS.

### Task 5: Merchant Issue Cost Preview

**Files:**
- Modify: `user_quota_service.py`
- Modify: `routes_merchant.py`
- Modify: `tests/test_commercial_phase1.py`
- Modify: `admin/src/api/merchant.js`
- Modify: `admin/src/views/MerchantBatches.vue`
- Modify: `tests/test_frontend_static.py`

- [x] **Step 1: Write failing backend tests**

Add a test proving `POST /api/v1/merchant/apps/{app_id}/kamis/preview` returns `{ count, unit_cost, total_cost, balance_before, balance_after, can_issue }` for self-owned and authorized apps, and rejects unauthorized apps.

Run: `pytest tests\test_commercial_phase1.py::test_merchant_issue_preview_returns_cost_and_balance_without_deducting -q`
Expected: FAIL because preview route does not exist.

- [x] **Step 2: Implement preview helper**

Add `preview_user_kami_issue(session, user, app, count, unit_cost=1)` in `user_quota_service.py`. It must not write quota transactions or cards.

- [x] **Step 3: Add merchant route**

Add `POST /api/v1/merchant/apps/{app_id}/kamis/preview`. Reuse the same app permission and spec requirements as issuing: authorized apps require `spec_id`; self-owned apps require `kami_type`.

- [x] **Step 4: Add merchant UI preview**

In batch management, show “本次预计扣 X 发卡额度，当前余额 Y，生成后余额 Z”. Disable submit when preview says `can_issue=false`. Refresh preview when app/spec/count changes.

- [x] **Step 5: Verify**

Run:
- `pytest tests\test_commercial_phase1.py::test_merchant_issue_preview_returns_cost_and_balance_without_deducting -q`
- `pytest tests\test_frontend_static.py -q`

Expected: PASS.

### Task 6: Final Verification and Handoff

**Files:**
- Modify: `.engramory-memory/2026-07-24-commercial-phase1-backend.md`

- [x] **Step 1: Run full local verification**

Run:
- `pytest -q`
- `npm run build` from `admin`

Expected: all tests pass and Vite build succeeds.

- [x] **Step 2: Update Engramory**

Record the new operations-stability features, verification commands, deployment caveats, and any remaining known limitations. Do not record credentials.

- [ ] **Step 3: Commit**

Stage only files changed for this feature. Do not stage unrelated `admin/package-lock.json` if it remains dirty.

Commit message: `feat: improve commercial ops controls`

- [ ] **Step 4: Deploy only if requested or continuing mainline release**

If pushing/deploying, push to `main`, wait for GitHub Actions, then validate `/health`, admin recharge settings, merchant batch preview, and recharge order cancel/expire endpoints on production with test-prefixed data and cleanup.
