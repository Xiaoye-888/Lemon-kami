---
name: qa-env-autofill-policy
description: Production QA should auto-create missing local runtime environment without storing secrets in memory.
type: user
created: 2026-07-28
updated: 2026-07-31
---

Why: The user wants production/browser QA to continue when local environment variables or required software are missing, instead of stopping at setup gaps.

How to apply: Before production QA, check required `LEMON_QA_*` variables, Python packages, Node, npm, Chrome/CDP, and frontend dependencies. Install missing non-secret tooling automatically when safe. The no-write `scripts/production_e2e_browser_qa.py --preflight` path must work with only public base URL variables and no admin credentials. Do not write admin passwords, merchant passwords, tokens, cookies, server passwords, or app secrets into Engramory or committed files. For credentials, use existing process/user environment variables or a gitignored local secret source, then inject them only into the test process and redact reports/logs. Password reset helpers must read secrets from env or secure prompts and avoid placing passwords in command-line arguments or output.
