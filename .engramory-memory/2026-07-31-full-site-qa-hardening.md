---
name: full-site-qa-hardening
description: Full-site QA now requires router/page-contract/browser-route coverage gates, real submenu navigation clicks, current SDK payloads, and dynamic production browser contexts for role-bound pages.
type: project
created: 2026-07-31
updated: 2026-07-31
---

Why: Recent online issues were missed because tests verified isolated APIs or source tokens, but did not guarantee every routed page had a page contract and production browser coverage.

How to apply: When adding or moving frontend routes, update `scripts/page_contracts.py`, `scripts/production_e2e_browser_qa.py`, and `scripts/browser_cdp_sweep.mjs`; `tests/test_page_contracts.py` should fail if a component route lacks a contract or a static page is missing from production browser sweep. Browser QA must also click representative second-level sidebar menu items and fail on `menuNavigationFailures`, because direct route loading alone does not prove sidebar navigation works. For dynamic admin pages, pass real IDs through the production QA context so browser routes use real URLs instead of placeholder parameters. Production SDK smoke tests must use the current public contract only: `kami` plus `device_info.device_id` and related `device_info` fields, with no legacy `uuid` or `fingerprint`. Visual QA should select the most complete visible action group when a page has mixed read-only and owner rows, use exact route matching for nested pages, and ignore generic Element Plus repeated controls such as number steppers or repeated "all" options unless they block an actual workflow.
