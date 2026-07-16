# Release Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a practical first batch of release-readiness and product-experience improvements for Lemon Kami without changing public SDK compatibility routes.

**Architecture:** Keep the existing FastAPI + SQLModel backend and Vue 3 + Element Plus frontend structure. Add a small authenticated dashboard API, a dashboard page, an app-config preview panel, and release operation documents/scripts. Avoid introducing a heavy migration framework in this batch; document migration/backup expectations instead.

**Tech Stack:** FastAPI, SQLModel, Vue 3, Element Plus, Vite, PowerShell release checks.

---

### Task 1: Backend Dashboard Summary

**Files:**
- Modify: `routes_admin.py`

- [x] Add `GET /api/v1/admin/dashboard` behind the existing admin auth dependency.
- [x] Return global counts for apps, cards, batches, devices, event logs, end users, and authorization accounts.
- [x] Return today counters for SDK verify, SDK consume, failed events, and new cards.
- [x] Return recent event logs with Chinese timestamp formatting.
- [x] Verify with an inline Python route check and authenticated smoke call.

### Task 2: Frontend Dashboard Page

**Files:**
- Modify: `admin/src/api/admin.js`
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Create: `admin/src/views/Dashboard.vue`

- [x] Add `getDashboard()` API wrapper.
- [x] Make `/dashboard` the authenticated default route.
- [x] Add a sidebar menu item with a suitable icon.
- [x] Build a dense operational dashboard: overview metrics, today counters, risk/status panels, quick links, and recent events.
- [x] Verify with `npm run build`.

### Task 3: App Config Preview

**Files:**
- Modify: `admin/src/views/AppInterfaces.vue`

- [x] When configuring `sdk.app_config`, show a live client-style preview using existing config fields.
- [x] Preview notice title/content, current version, update description, force update state, update URL, download button text, and popup level.
- [x] Keep it visual only; do not change the saved API payload shape.
- [x] Verify with `npm run build`.

### Task 4: Release Check And Operations Docs

**Files:**
- Create: `scripts/release_check.ps1`
- Create: `docs/RELEASE_CHECKLIST.md`

- [x] Add a PowerShell release check script for Python compile, frontend build, Java SDK package, SDK zip stale-name scan, key route presence check, and optional local smoke checks.
- [x] Document release steps: environment variables, first-login password change requirement, database backup, Docker startup, SDK download verification, and rollback basics.
- [x] Ensure no secret values are recorded.

### Task 5: SDK And Public Docs Clarification

**Files:**
- Modify: `KAMI_CORE_API.md`
- Modify: `sdk/js_sdk/README.md`
- Modify: `sdk/python_sdk/README.md`
- Modify: `sdk/java_sdk/README.md`

- [x] Add a short integration flow: verify does not deduct, consume deducts times, app config returns announcement/update/download fields.
- [x] Clarify all current SDK entry names use Lemon only.
- [x] Avoid old SDK names and compatibility aliases.

### Task 6: Verification And Cleanup

**Files:**
- Modify: `.engramory-memory/project-release-optimization-2026-07-14.md`
- Modify: `.engramory-memory/MEMORY.md`

- [x] Update Engramory with durable new commands/routes.
- [x] Run Python compile, frontend build, Java SDK package, release check script, and source scans.
- [x] Remove generated `__pycache__` and Java `target`.
- [x] Report any residual warnings honestly.
