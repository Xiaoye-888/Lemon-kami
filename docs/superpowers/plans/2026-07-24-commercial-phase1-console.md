# Commercial Phase 1 Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a visible commercial admin backend and merchant console with shared login, manual recharge review, issue-quota crediting, order/transaction visibility, and merchant card-issuing entry points.

**Architecture:** Keep the existing admin APIs stable, add commercial routes beside `routes_admin_advanced.py`, and expose merchant APIs under `/api/v1/merchant` while preserving `/api/v1/user` compatibility. Frontend keeps one Vite app and one login page, then routes by returned account role to `/admin/...` or `/merchant/...`.

**Tech Stack:** FastAPI, SQLModel, SQLite/MySQL bootstrap, Vue 3, Pinia, Element Plus, pytest, Vite.

---

### Task 1: Backend Commercial Foundation

**Files:**
- Modify: `models.py`
- Create: `commercial_service.py`
- Create: `routes_auth.py`
- Create: `routes_merchant.py`
- Create: `routes_commercial.py`
- Modify: `main.py`
- Test: `tests/test_commercial_phase1.py`

- [ ] Write failing tests for shared login role routing, recharge preview, order submit, admin approval, quota crediting, duplicate-review protection, and merchant transaction visibility.
- [ ] Add commercial models for payment channels, fixed recharge options, bonus rules, recharge orders, and order status/channel enums.
- [ ] Add commercial service helpers for amount normalization, quota preview calculation, proof image file storage, order creation, and transactional approval.
- [ ] Add `/api/v1/auth/login` shared login returning `role`, `redirect`, token, and normalized `user_info`.
- [ ] Add `/api/v1/merchant/...` routes for profile, quota, quota transactions, recharge config, recharge preview, recharge order creation/list/detail/proof, apps, batches, and cards.
- [ ] Add `/api/v1/admin/commercial/...` routes for overview, recharge configuration, payment channels, recharge orders, review actions, and quota transaction list.
- [ ] Include new routers in `main.py`.
- [ ] Run `pytest tests/test_commercial_phase1.py -q`.

### Task 2: Frontend Shared Login And Admin Commercial Entry

**Files:**
- Modify: `admin/src/stores/user.js`
- Create: `admin/src/api/auth.js`
- Create: `admin/src/api/commercial.js`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `admin/src/views/Login.vue`
- Create: `admin/src/views/AdminCommercialOverview.vue`
- Create: `admin/src/views/AdminRechargeOrders.vue`
- Create: `admin/src/views/AdminRechargeSettings.vue`
- Test: `tests/test_frontend_static.py`

- [ ] Write static frontend tests for shared login role storage, `/admin` and `/merchant` routes, admin commercial navigation, recharge orders page, and recharge settings page.
- [ ] Update login API/store to call `/auth/login`, persist `role`, and redirect by returned `redirect`.
- [ ] Move existing admin children under `/admin/...` while preserving old path redirects.
- [ ] Render admin navigation as commercial backend entry with user management, recharge orders, recharge config, app authorization, batches, cards, devices, logs, and settings.
- [ ] Add admin commercial overview/orders/settings views wired to `/admin/commercial/...`.

### Task 3: Frontend Merchant Console

**Files:**
- Create: `admin/src/api/merchant.js`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Create: `admin/src/views/MerchantDashboard.vue`
- Create: `admin/src/views/MerchantRecharge.vue`
- Create: `admin/src/views/MerchantOrders.vue`
- Create: `admin/src/views/MerchantTransactions.vue`
- Create: `admin/src/views/MerchantApps.vue`
- Create: `admin/src/views/MerchantBatches.vue`
- Create: `admin/src/views/MerchantCards.vue`
- Test: `tests/test_frontend_static.py`

- [ ] Add merchant navigation for dashboard, recharge, orders, quota transactions, my apps, batch management, my cards, devices, and account settings.
- [ ] Add merchant dashboard with issue-quota balance and quick links.
- [ ] Add recharge page with fixed amount options, custom amount preview, WeChat/Alipay QR display, remark, and image proof upload.
- [ ] Add order and transaction list pages.
- [ ] Add basic apps, batch/card listing, and card issue entry using merchant APIs.

### Task 4: Verification And Deployment

**Files:**
- Modify memory only after each completed stage.

- [ ] Run backend tests: `pytest -q`.
- [ ] Run frontend build: `npm run build` in `admin`.
- [ ] Fix any failing tests/build issues.
- [ ] Update Engramory with final implemented scope and verification commands.
- [ ] Commit all relevant changes on `main`.
- [ ] Push to `origin main`.
- [ ] Verify `http://154.12.26.231/health`.
- [ ] Verify key deployed API surfaces for auth, admin commercial config/orders, and merchant recharge/order visibility.
