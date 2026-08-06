---
name: merchant-register-two-char-username
description: Merchant registration accepts two-character Chinese usernames and frontend parses FastAPI validation arrays into Chinese prompts.
type: project
created: 2026-08-06
updated: 2026-08-06
---

Merchant self-registration and merchant profile editing allow usernames from 2 to 64 characters, so short Chinese merchant names such as two-character display names can register successfully. FastAPI validation array responses on the shared login/register page should be converted into Chinese field-specific prompts instead of surfacing raw Axios status text.

Why: Mobile merchant registration previously showed a generic 422 error when a two-character username failed backend validation before route logic.

How to apply: When touching shared auth or merchant account profile validation, keep backend, frontend validation, and static/backend tests aligned around merchant usernames being 2-64 characters; admin profile usernames still use the stricter admin-side rule unless explicitly changed.
