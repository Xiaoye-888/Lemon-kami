# Engramory Memory

- [test-verification-discipline](2026-07-28-test-verification-discipline.md): After each code change, run the smallest relevant verification set for the touched surfaces before reporting completion.
- [merchant-batch-parity-qa](2026-07-28-merchant-batch-parity-qa.md): Merchant batch pages must stay admin-isomorphic for list/detail layout, batch ownership semantics, and browser visual regression targets.
- [qa-env-autofill-policy](2026-07-28-qa-env-autofill-policy.md): Production QA should auto-create missing local runtime environment without storing secrets in memory.
- [merchant-account-profile-edit](2026-07-29-merchant-account-profile-edit.md): Merchant account settings now edit only username, email, and phone; password/avatar stay separate, and merchant card/refund labels are localized in Chinese.
- [spec-delete-capability-guard](2026-07-29-spec-delete-capability-guard.md): Spec deletion is blocked unless no issued kamis remain; batch deletion defaults to non-empty protection unless an explicit cascade delete is confirmed.
- [centered-dialog-preference](2026-07-30-centered-dialog-preference.md): Prefer centered dialogs or standalone pages for admin/merchant detail and edit flows; avoid right-side drawer panels unless explicitly requested.
- [public-domain-default](2026-07-30-public-domain-default.md): Lemon Kami public access default is `http://lemonkami.top`, while SSH deployment host should remain the VPS IP unless explicitly changed.
- [device-info-and-merchant-admin-boundaries](2026-07-30-device-info-and-merchant-admin-boundaries.md): Device listings are grouped by kami, SDK requests use only `device_info.device_id`, and admin/merchant ownership boundaries stay strict.
- [admin-audit-target-user](2026-07-30-admin-audit-target-user.md): Admin audit logs should record the target merchant user when an admin operates on merchant-owned resources.
- [full-site-qa-hardening](2026-07-31-full-site-qa-hardening.md): Full-site QA now requires router/page-contract/browser-route coverage gates, real submenu navigation clicks, and dynamic production browser contexts for role-bound pages.
