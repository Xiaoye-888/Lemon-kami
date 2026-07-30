---
name: admin-audit-target-user
description: Admin audit logs should record the target merchant user when an admin operates on merchant-owned resources.
type: project
created: 2026-07-30
updated: 2026-07-31
---

Why: The admin audit table has separate columns for the acting administrator and the target user. Merchant-owned app, batch, card, quota, and authorization operations become hard to understand when `target_username` is left empty.

How to apply: When an admin operation acts on a merchant-owned resource, derive the target user from the resource owner, preferably `App.owner_user_id`, and pass both `target_user_id` and `target_username` to `record_admin_audit` and `require_sensitive_confirmation`. Admin-owned resources can leave the target user blank unless a specific merchant/end-user is the business object. The admin audit UI should render target user through a fallback helper so blank values display as `-` instead of an empty cell.
