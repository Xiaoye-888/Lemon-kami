---
name: device-info-and-merchant-admin-boundaries
description: Device listings are grouped by kami, SDK requests use only `device_info.device_id`, and admin/merchant ownership boundaries stay strict.
type: project
created: 2026-07-30
updated: 2026-07-31
---

Why: Merchant UX should not show low quota warning banners in batch management, admin global app/end-user views should exclude merchant self-owned app data, admin-scoped merchant card refunds must identify the admin operator, device management should show human-readable device identity, and business SDKs no longer send legacy identity request fields.

How to apply: Keep merchant batch tables visually aligned with admin batch rows while omitting low-quota reminder copy. Admin app and end-user lists should request/filter `owner_scope: 'admin'` and reject merchant-owned `app_id` filters in admin end-user APIs. Merchant-scoped admin detail pages can manage the selected merchant's self-owned apps through scoped commercial routes; if an admin deletes merchant cards through scoped routes, rewrite refund quota transactions to the admin username and include scoped metadata. SDK verify/consume/release/unbind requests must identify devices with `payload.device_info.device_id`; do not document or accept top-level `uuid`/`fingerprint` request fields. The database may still store that ID in historical `uuid`/`fingerprint` columns until a schema migration exists. Device management should collapse rows by card, show the first-bound machine on the main row, keep the main-row risk buttons for that first machine, and render policy text such as `不限制(2台)` with the count of detail machines only, excluding the first-bound machine. The centered detail dialog must exclude the first-bound machine, dedupe historical/new records for the same machine, and let admins manage each remaining machine by its own risk row. Blacklisting a row marks both the target device ID and current IP; SDK calls are rejected if either dimension is blacklisted, while other devices on other IPs under the same card remain usable. Risk labels in device management come from the effective max of `Device.risk_level` and `DeviceIpRisk.risk_level`; IP history count is only statistics and must not auto-mark warning or blacklist. Historical records with no SDK-reported fields should render as waiting for the new SDK report, not as real device data.

Verification: After touching these surfaces, run `python -m pytest -q`, `npm run build` in `admin`, and `mvn -q -DskipTests package` in `sdk/java_sdk`.
