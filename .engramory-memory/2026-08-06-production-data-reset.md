---
name: production-data-reset-2026-08-06
description: Production business data was reset on 2026-08-06; only the `admin` administrator login should remain.
type: project
created: 2026-08-06
updated: 2026-08-06
---

Why: The user requested a production data reset so the system can restart business operations from a clean state without old applications, users, kamis, devices, orders, logs, or cache data.

How to apply: Treat production as a fresh business instance after 2026-08-06. Do not assume previous apps, merchants, usage users, kamis, batches, device bindings, recharge configuration, audit/event logs, uploads, backups, or Redis cache entries still exist. The `admin` administrator login was intentionally preserved; do not record or infer its password here.
