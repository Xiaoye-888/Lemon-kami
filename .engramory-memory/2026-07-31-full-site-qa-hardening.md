---
name: full-site-qa-hardening
description: Full-site QA now requires router/page-contract/browser-route coverage gates and dynamic production browser contexts for role-bound pages.
type: project
created: 2026-07-31
updated: 2026-07-31
---

Why: Recent online issues were missed because tests verified isolated APIs or source tokens, but did not guarantee every routed page had a page contract and production browser coverage.

How to apply: When adding or moving frontend routes, update `scripts/page_contracts.py` and `scripts/production_e2e_browser_qa.py`; `tests/test_page_contracts.py` should fail if a component route lacks a contract or a static page is missing from production browser sweep. For dynamic admin pages, pass real IDs through the production QA context so browser routes use real URLs instead of placeholder parameters.
