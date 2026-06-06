# Copilot agent instructions

- Always use conventional commits with one of these types: `build`, `ci`, `chore`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`.
- Always include exactly one gitmoji in the commit subject line.
- Do not use a scope in the commit type.
- Commit subjects must match `type: :gitmoji: short description` or `type!: :gitmoji: short description`.
- Example format: `fix: :bug: short description`.
- After editing Python files, run `black .` (or `black <edited-files>`) before finalizing changes.
