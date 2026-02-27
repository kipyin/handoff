## Contributing and local workflow

This project is a personal app, but the repo is structured so future-you (or an AI
assistant) can work on it safely and consistently.

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency and virtualenv management

Install dependencies:

```bash
uv sync
```

### Running the app

```bash
uv run todo run
```

The Typer CLI under `scripts/cli.py` is exposed as the `todo` command:

- `uv run todo run` – start the Streamlit app
- `uv run todo sync` – sync dependencies
- `uv run todo check` – Ruff lint + format
- `uv run todo test` – run the pytest suite

Type checking (optional but recommended for larger changes):

```bash
uv run pyright src scripts
```

### Branching, commits, and releases

For any **major feature or behavior change** (new UI, new tests for critical code,
type-checking setup, etc.), follow this flow:

1. Branch from `main`:
   - `git checkout -b develop/<feature-name>`
2. Make focused commits:
   - Keep each commit as small and coherent as practical.
3. Bump the CalVer patch version when shipping user-visible changes:
   - Use the CLI helper so `pyproject.toml` and `src/todo_app/version.py` stay in sync:
     ```bash
     uv run todo bump-version 2026.2.XY
     ```
4. Update documentation:
   - Add a new section to `RELEASE_NOTES.md` under the new version.
   - Update `README.md` if behavior, commands, or UX changed.
5. Run checks before merging:
   - `uv run todo check`
   - `uv run pyright src scripts`
   - `uv run todo test`
6. Merge back into `main` once tests pass.

### Cursor rules and agent guidance

Cursor-specific rules live under `.cursor/rules/`:

- `python-project.mdc` – project-level expectations (uv, Ruff, pytest, layout).
- `python-code.mdc` – coding style and library conventions.
- `agent-planning.mdc` – branching, versioning, and release-notes workflow.

If you are using an AI agent, point it at these rules before making significant changes so
it follows the same conventions. Human contributors should skim them once to understand
the expected workflow and formatting.
