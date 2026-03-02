## Contributing and local workflow

For **user-facing docs** (how to run, update the app, backups), see **README.md**.
For **developer docs** (CLI, layout, deployment and release workflow), stay here.

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
uv run handoff run
```

The Typer CLI under `scripts/cli.py` is exposed as the `handoff` command:

- `uv run handoff run` – start the Streamlit app
- `uv run handoff sync` – sync dependencies
- `uv run handoff check` – Ruff lint + format
- `uv run handoff typecheck` – type checking with pyright over `src/` and `scripts/`
- `uv run handoff test` – run the pytest suite
- `uv run handoff ci` – run lint, format, type checking, and tests together
- `uv run handoff build-full` – build embedded Windows zip (obfuscates with PyArmor)
- `uv run handoff build-patch` – build patch from obfuscated build (run after build-full)
- `uv run handoff bump-version 2026.M.P` – bump version in pyproject.toml and handoff.version

Version sync: `src/handoff/version.py` and `pyproject.toml` must match; `tests/test_version_sync.py` enforces this. Use `bump-version` to update both.

Project layout: `app.py` (entrypoint), `src/handoff/` (package), `pages/` (legacy), `tests/`.

Type checking (optional but recommended for larger changes):

```bash
uv run handoff typecheck
```

### Branching, commits, and releases

For any **major feature or behavior change** (new UI, new tests for critical code,
type-checking setup, etc.), follow this flow:

1. Branch from `main`:
  - `git checkout -b release/YYYY.M.MINOR` (for example `release/2026.3.3`)
2. Make focused commits:
  - Keep each commit as small and coherent as practical.
3. Bump the CalVer patch version when shipping user-visible changes:
  - Use the CLI helper so `pyproject.toml` and `src/handoff/version.py` stay in sync:
4. Update documentation:
  - Add a new section to `RELEASE_NOTES.md` under the new version (see **Release notes** below).
  - Choose an impact tag for the release and include it in the heading in square brackets:
    - `[Breaking]` – schema changes, behaviour shifts, or anything that may require backups or manual intervention.
    - `[Recommended]` – new features, UX improvements, or important dependency updates most users should adopt.
    - `[Optional]` – internal-only cleanups or minor fixes that users can safely skip.
  - Update `README.md` if behavior, commands, or UX changed.

### Release notes

When adding a new version block to `RELEASE_NOTES.md`:

- **When:** Add a new `## YYYY.M.MINOR [Tag]` section when you ship user-visible changes or notable internal work (e.g. after merging a feature branch or cutting a release).
- **Categories:** Group bullets under **Fix**, **Feature**, **Improvement**, and **Internal** so readers can scan by type:
  - **Fix** – Bug fixes, error handling, compatibility (e.g. WinError 32, backup behaviour).
  - **Feature** – New user-facing behaviour (e.g. calendar today column, new page).
  - **Improvement** – UX, docs, performance, refactors that don’t change behaviour.
  - **Internal** – Tests, tooling, code layout (optional; can be merged into Improvement).
- **Impact tag:** Keep the version heading tag (`[Breaking]` / `[Recommended]` / `[Optional]`) as above; categories only group the bullets under that version.

1. Run checks before merging:
  - `uv run handoff check`
  - `uv run handoff typecheck` (or `uv run pyright src scripts`)
  - `uv run handoff test` (or `uv run handoff ci` to run everything together)
2. Merge back into `main` once tests pass.

### macOS support (planning)

On macOS today, run Handoff from source using the same uv + CLI workflow:

```bash
uv sync
uv run handoff
```

The app runs as a local Streamlit app with a SQLite database stored under your per-user
data directory (for example via `platformdirs`, typically under `~/Library/Application Support/`).
There is no signed `.app` bundle yet; updates are applied via code changes or patch zips,
not via a macOS installer.

Future work may introduce a signed and notarized macOS bundle (or CLI binary) built with
PyInstaller or a platform-specific packager. When doing macOS distribution work:

- Use a dedicated branch such as `develop/macos-bundle`.
- Plan for Gatekeeper, codesigning, notarization, and minimum macOS version.
- Prefer `arm64` builds for Apple Silicon while keeping `x86_64` in mind if useful.

### API documentation

There is no separate API doc build. The public API is documented via **docstrings** (Google style) in the source. For a browsable view locally, you can run `pdoc src/handoff` or use Sphinx if you add a config.

### Cursor rules and agent guidance

Cursor-specific rules live under `.cursor/rules/`:

- `python-project.mdc` – project-level expectations (uv, Ruff, pytest, layout).
- `python-code.mdc` – coding style and library conventions.
- `agent-planning.mdc` – branching, versioning, and release-notes workflow.

If you are using an AI agent, point it at these rules before making significant changes so
it follows the same conventions. Human contributors should skim them once to understand
the expected workflow and formatting.