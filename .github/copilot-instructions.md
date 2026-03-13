# Copilot Instructions

> Full developer and agent instructions live in [`AGENTS.md`](../AGENTS.md) at the repository root. Read that file first — it is the single source of truth for code style, architecture, CLI commands, testing workflows, and release process.

## Key facts for Copilot

- **Stack:** Python 3.13+, Streamlit, SQLite, SQLModel. No external services.
- **Entrypoint:** `python -m handoff` / `uv run handoff` (launcher that runs `streamlit run app.py` → `src/handoff/` package → `interfaces/streamlit/pages/`, `services/`).
- **Architecture rule:** Page modules must import from `handoff.services`, never from `handoff.data` directly (enforced by `tests/test_services_architecture.py`).
- **Linter/formatter:** Ruff (`uv run handoff check --fix`). **Type checker:** Pyright (`uv run handoff typecheck`).
- **Tests:** `uv run handoff test` (pytest). Full CI: `uv run handoff ci`.
- **DB migrations:** Add numbered scripts under `src/handoff/migrations/scripts/` **and** register them in `handoff.migrations.scripts.ALL`; `db.init_db()` then runs them automatically.
- **Version sync:** `src/handoff/version.py` and `pyproject.toml` must always match (enforced by `tests/test_version_sync.py`).
- **Dev DB:** `HANDOFF_DB_PATH=/tmp/handoff-dev.db uv run handoff run`.
