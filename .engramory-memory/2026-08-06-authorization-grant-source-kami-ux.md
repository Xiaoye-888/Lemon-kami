---
name: authorization-grant-source-kami-ux
description: Manual user authorization grants should make source kami optional and show clear errors when a non-existent source kami is entered.
type: project
created: 2026-08-06
updated: 2026-08-06
---

In the admin end-user authorization dialog, `source_kami_code` is only for a real existing kami code. Operational notes such as "personal use" belong in `remark`.

Why: A free-text value in `source_kami_code` used to return a generic 404, which looked like the grant endpoint was missing.

How to apply: Keep the source kami field optional, label it as a real card number, return a clear 400 for unknown source cards, and let the global request handler display server detail for 404 responses.
