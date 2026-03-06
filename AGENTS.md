# AGENTS.md

## Cursor Cloud specific instructions

**Handoff** is a single-user local to-do app built with Python 3.13+, Streamlit, and SQLite. No external services or Docker are needed.

### Quick reference

| Task | Command |
|---|---|
| Install deps | `uv sync` |
| Run app | `uv run handoff` (Streamlit on port 8501) |
| Lint + format | `uv run handoff check` |
| Type check | `uv run handoff typecheck` |
| Tests | `uv run handoff test` |
| Full CI suite | `uv run handoff ci` |

All commands are documented in `CONTRIBUTING.md`.

### Non-obvious caveats

- **Python 3.13+ required.** The VM may ship with an older Python. Use `uv python install 3.13` to get the right version; `uv sync` will then use it automatically.
- **`uv` must be on PATH.** Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` and ensure `~/.local/bin` is on PATH.
- **Streamlit headless mode.** When starting the app in a cloud/CI context, pass `--server.headless true` to avoid browser-open prompts. The CLI command `uv run handoff run` does not set this automatically — use `uv run python -m streamlit run app.py --server.headless true` directly, or set `STREAMLIT_SERVER_HEADLESS=true`.
- **SQLite DB location.** By default stored in the platform data dir (via `platformdirs`). Override with `HANDOFF_DB_PATH` env var for testing or isolation.
