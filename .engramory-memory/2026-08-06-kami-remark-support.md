---
name: kami-remark-support
description: Single kami remarks are first-class data across admin and merchant generation, listing, editing, searching, and CSV export.
type: project
created: 2026-08-06
updated: 2026-08-06
---

Single-card remarks are stored on `Kami.remark`, not only on specs or batches. Admin and merchant generation flows, batch append flows, lists, keyword search, CSV export, and remark edit endpoints should preserve it.

Why: The production system needs per-card customer/order/channel notes, and batch remarks are too coarse for actual operations.

How to apply: When touching card creation or listing surfaces, include `remark` in the payload, API response, search/export rows, and both admin and merchant scoped permission paths.
