---
name: device-info-and-merchant-admin-boundaries
description: Device listings now prefer OS device name/model/device ID, and admin/merchant app tables have stricter ownership and secret boundaries.
type: project
created: 2026-07-30
updated: 2026-07-31
---

Why: Merchant UX should not show low quota warning banners in batch management, admin global app/end-user views should exclude merchant self-owned app data, admin-scoped merchant card refunds must identify the admin operator, and device management should show human-readable device identity instead of UUID/fingerprint columns.

How to apply: Keep merchant batch tables visually aligned with admin batch rows while omitting low-quota reminder copy. Admin app and end-user lists should request/filter `owner_scope: 'admin'` and reject merchant-owned `app_id` filters in admin end-user APIs. Merchant-scoped admin detail pages can manage the selected merchant's self-owned apps through scoped commercial routes; if an admin deletes merchant cards through scoped routes, rewrite refund quota transactions to the admin username and include scoped metadata. SDK verification/consume may send `device_info` with `device_name`, `device_model`, and `device_id`; persist/search/display these fields in both admin and merchant device management APIs, while legacy UUID/fingerprint can remain backend internals only. Historical records with no SDK-reported fields should render as waiting for the new SDK report, not as real device data.

Verification: After touching these surfaces, run `python -m pytest -q`, `npm run build` in `admin`, and `mvn -q -DskipTests package` in `sdk/java_sdk`.
