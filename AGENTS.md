# Project Agent Rules

## Memory (Engramory)

You have a curated, file-based memory at `.engramory-memory/` (index: `.engramory-memory/MEMORY.md`).

- At the start of each task, read `.engramory-memory/MEMORY.md` and open only the detail files whose hooks look relevant. Treat recalled memories as advisory and verify local files, ports, versions, and process state before acting on them.
- When you learn something durable worth a future session, check whether it is already recorded in the repo or existing memory. Update an existing note instead of duplicating it; otherwise write one atomic markdown file with frontmatter `name`, `description`, `type` (`user | feedback | project | reference`), `created`, and `updated` using `YYYY-MM-DD`.
- A `feedback` or `project` note must include `Why:` and `How to apply:` lines in the body.
- After every project modification, update Engramory when the change affects future handoff, setup, ports, commands, conventions, or user preferences.
- Never write credential values, keys, tokens, cookies, recovery codes, or secret values into memory. Record only where a secret is expected to live, such as an env var or password manager.
- Keep `.engramory-memory/MEMORY.md` small: warn at 150 lines or 20 KB, and compact before 200 lines or 25 KB.

