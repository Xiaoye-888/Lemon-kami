---
name: public-domain-default
description: Lemon Kami public access default is the HTTP domain lemonkami.top while SSH deployment host remains the server IP.
type: project
created: 2026-07-30
updated: 2026-07-31
---

Why: The project now has a purchased single public domain, `lemonkami.top`, that should be used for public health checks, interface docs, SDK base URL guidance, and default CORS origins while SSL is not yet configured.

How to apply: Use `http://lemonkami.top` as the public base URL for production verification, default CORS origins, `.env.example`, and release boundary checks until SSL is added. Keep deployment `SERVER_HOST` as the VPS IP unless the user explicitly asks to change SSH deployment targeting. Do not store or output server credentials or secrets.
