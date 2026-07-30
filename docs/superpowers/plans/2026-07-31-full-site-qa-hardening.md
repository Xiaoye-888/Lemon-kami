# Full Site QA Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Lemon Kami's admin, merchant, public documentation, role-boundary, business semantics, and UI presentation surfaces testable end to end.

**Architecture:** Add coverage gates first, then fill the missing page contracts and business tests, then extend the existing production browser QA harness. Keep changes within existing pytest, FastAPI, Vue, and CDP helper patterns.

**Tech Stack:** Python pytest, FastAPI test client, Vue 3 source contracts, Vite build, Node CDP browser sweep, existing production QA scripts.

---

## Scope Check

This plan is one QA-hardening project. It does not redesign product behavior; it adds tests and only minimal implementation fixes discovered by those tests. Secrets must remain in environment variables and must never be printed, committed, or stored in Engramory.

## File Structure

- Modify `tests/test_page_contracts.py`: add route-to-contract and browser-sweep coverage gates.
- Modify `scripts/page_contracts.py`: add contracts for currently uncovered admin, merchant, and public pages.
- Modify `tests/test_frontend_static.py`: add generic formatting/localization/UI source guards.
- Modify `tests/test_commercial_phase1.py`, `tests/test_commercial_phase2.py`, `tests/test_unified_entitlements.py`, `tests/test_kami_specs.py`: add missing role, audit, quota, device, and app ownership tests where they best fit existing coverage.
- Modify `scripts/production_e2e_browser_qa.py`: add missing routes and dynamic context route generation.
- Modify `scripts/browser_cdp_sweep.mjs`: add route-level UI checks only if Python route additions expose missing layout signals.
- Modify `tests/test_production_e2e_browser_qa.py`: unit-test the expanded route list, context handling, and browser finding evaluation.
- Modify `.engramory-memory/`: update only durable handoff notes after code changes; no secrets.

## Task 1: Route Coverage Gates

- [ ] **Step 1: Write failing tests**

Add tests that parse the Vue router and assert every primary route has either a page contract, a production browser route, or an explicit documented exclusion for auth redirects and parameter-only aliases.

Run:

```powershell
python -m pytest tests/test_page_contracts.py -q
```

Expected before implementation: failure listing uncovered routes such as `/admin/commercial`, `/admin/apps/:app_id/interfaces`, `/merchant/apps/notices`, and `/merchant/apps/versions`.

- [ ] **Step 2: Add missing coverage declarations**

Add contracts and browser-route entries for every failed route. For dynamic routes, use a context placeholder such as `admin_app_interfaces`, `admin_merchant_detail`, and `admin_merchant_batches` instead of hard-coded IDs.

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest tests/test_page_contracts.py -q
```

Expected: route coverage tests pass.

## Task 2: Page Contract Expansion

- [ ] **Step 1: Write failing contract tests**

Extend contract assertions so each page defines route, component, title, at least one main region, expected table columns or empty state, and expected row actions when a table is central to the page.

- [ ] **Step 2: Add missing contracts**

Add contracts for admin dashboard, commercial overview, recharge settings, issue pricing, finance, audit logs, ops, quota transactions, app info, notices, versions, app interfaces, kami list, logs, users, end users, interfaces new/list, login, docs, interface docs, and 404.

- [ ] **Step 3: Verify**

Run:

```powershell
python -m pytest tests/test_page_contracts.py tests/test_frontend_static.py -q
```

Expected: contracts and static guards pass.

## Task 3: Business Semantic Matrix

- [ ] **Step 1: Add backend tests for audit target semantics**

Add table-driven tests for recharge approval/reject/abnormal/expire, issue pricing changes, merchant app authorization, scoped merchant batch delete, and admin-operated merchant batch/spec changes.

- [ ] **Step 2: Add backend tests for role data boundaries**

Assert admin app pages use `owner_scope=admin`, merchant pages use merchant scoped APIs, and admin merchant detail/scoped batch APIs require admin with target merchant context.

- [ ] **Step 3: Add backend tests for quota operators**

Assert admin-operated refunds or grants record `operator=admin`, while merchant self-service issue/refund records the merchant username.

- [ ] **Step 4: Add device chain tests**

Assert SDK payloads containing `device_name`, `device_model`, and `device_id` persist to devices and appear in admin and merchant list APIs.

- [ ] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_commercial_phase1.py tests/test_commercial_phase2.py tests/test_unified_entitlements.py tests/test_kami_specs.py -q
```

Expected: targeted business matrix passes.

## Task 4: Production Browser QA Expansion

- [ ] **Step 1: Add route list tests**

Extend `tests/test_production_e2e_browser_qa.py` to fail if production browser routes omit a router/menu page.

- [ ] **Step 2: Add dynamic browser contexts**

Extend `scripts/production_e2e_browser_qa.py` so the setup phase produces URLs for admin merchant detail, admin merchant scoped batches, admin app interfaces, merchant notices, and merchant versions.

- [ ] **Step 3: Add visual targets**

Add screenshot/visual targets for audit logs, devices, end users, app info, merchant detail, scoped batches, and quota transactions. Keep screenshots under ignored QA artifacts.

- [ ] **Step 4: Verify locally**

Run:

```powershell
python -m pytest tests/test_production_e2e_browser_qa.py -q
```

Expected: route/context/unit checks pass.

## Task 5: Full Verification and Deployment

- [ ] **Step 1: Run backend test suite**

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend build**

```powershell
cd admin
npm run build
```

Expected: Vite build succeeds.

- [ ] **Step 3: Commit and push**

Use existing repo push practices. Do not output secrets. Push `main` to GitHub.

- [ ] **Step 4: Verify deployment**

After GitHub Actions deploys, verify:

```powershell
Invoke-WebRequest http://154.12.26.231/health -UseBasicParsing
Invoke-WebRequest http://lemonkami.top/health -UseBasicParsing
Invoke-WebRequest http://lemonkami.top/docs/api -UseBasicParsing
Invoke-WebRequest http://lemonkami.top/api/v1/docs/interfaces -UseBasicParsing
```

Expected: all return HTTP 200. Production browser QA should report no P0/P1 findings.
