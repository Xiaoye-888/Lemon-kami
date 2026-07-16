# Kami Batch Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split card management into batch and card pages, add machine-code binding policy per batch, and show card-type-specific usage fields.

**Architecture:** Keep the current `kamis` table as the source of truth for batches by storing batch-level settings on generated cards. Add a `kami_device_bindings` table only for multi-device card binding. Frontend pages use the existing Element Plus style and call the existing admin endpoints with a few new fields.

**Tech Stack:** FastAPI, SQLModel, SQLite/MySQL migration helpers, Vue 3, Element Plus, pytest, Vite.

---

### Task 1: Backend Machine Binding Model And Tests

**Files:**
- Modify: `models.py`
- Modify: `database.py`
- Test: `test_kami_batch_binding.py`

- [ ] Write failing tests for batch generation storing `machine_bind_mode`, batch summaries returning it, and one-card-multi-device SDK verification allowing multiple fingerprints.
- [ ] Run `pytest -q test_kami_batch_binding.py` and verify failures are caused by missing fields/models.
- [ ] Add `MachineBindMode`, `Kami.machine_bind_mode`, and `KamiDeviceBinding`.
- [ ] Add MySQL and SQLite schema migration helpers for `kamis.machine_bind_mode` and `kami_device_bindings`.
- [ ] Run the new test file and verify it passes.

### Task 2: Backend Admin List Payloads

**Files:**
- Modify: `routes_admin.py`
- Test: `test_kami_batch_binding.py`

- [ ] Extend `POST /api/v1/admin/kamis/batch` with `machine_bind_mode`.
- [ ] Include `machine_bind_mode`, `device_bind_count`, `created_at`, user display fields, and point balance fields in card and batch list payloads.
- [ ] Keep existing query parameters compatible with old frontend calls.
- [ ] Run `pytest -q test_kami_batch_binding.py test_user_points_api.py`.

### Task 3: SDK Binding Behavior

**Files:**
- Modify: `routes_sdk.py`
- Test: `test_kami_batch_binding.py`

- [ ] Make `no_limit` skip strict device binding while still recording devices and last verification.
- [ ] Keep `one_card_one_device` behavior compatible with existing `bind_uuid`.
- [ ] Add `one_card_multi_device` behavior backed by `KamiDeviceBinding`.
- [ ] Preserve blacklist and IP lock checks.
- [ ] Run `pytest -q test_kami_core_enhancements.py test_kami_batch_binding.py`.

### Task 4: Frontend Menu And Pages

**Files:**
- Modify: `admin/src/router/index.js`
- Modify: `admin/src/layouts/MainLayout.vue`
- Modify: `admin/src/views/Kamis.vue`
- Create: `admin/src/views/KamiBatches.vue`
- Modify: `admin/src/api/kami.js`

- [ ] Change the side menu to `卡密管理` submenu with `批次管理` and `卡密管理`.
- [ ] Move batch summary and generation dialog to `KamiBatches.vue`.
- [ ] Add machine binding select to new batch dialog: `不限制` / `一机一码` / `一卡多机`.
- [ ] Keep `Kamis.vue` focused on card list, quick filters, search, export, multi-select delete, and type-specific columns.
- [ ] Ensure routes preserve access through `/kamis` by redirecting to `/kamis/batches`.
- [ ] Run `npm run build`.

### Task 5: Final Verification

**Files:**
- No new implementation files.

- [ ] Run `pytest -q`.
- [ ] Run `npm run build`.
- [ ] Restart backend and frontend dev servers.
- [ ] Check `http://127.0.0.1:8000/docs` and `http://127.0.0.1:3000/`.
