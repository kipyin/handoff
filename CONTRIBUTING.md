## Contributing and local workflow

For **user-facing docs** (how to run, update the app, backups, and where your
data lives), see [`README.md`](README.md). For **developer docs** (CLI, layout,
deployment and release workflow, and code style), stay here.

This project is a personal app, but the repo is structured so future-you (or an
AI assistant) can work on it safely and consistently.

### Deployment philosophy

Handoff is built to ship as a self-contained Windows zip that bundles an
embedded Python runtime, dependencies, and the app code. The `src/handoff`
package is obfuscated with PyArmor, while `app.py` stays readable as a thin
entrypoint and launcher target. Patch zips update the obfuscated code in place,
with backups taken before each update.

This model (embedded Python + obfuscated source + thin `app.py` entrypoint +
launcher) is why the build scripts, updater logic, and docs are structured the
way they are.

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency and virtualenv management

Install dependencies:

```bash
uv sync
```

### Running the app and CLI commands

```bash
uv run handoff run
```

The Typer CLI under `scripts/cli.py` is exposed as the `handoff` command. These
are the canonical day-to-day commands for local development and CI:

- `uv run handoff run` – start the app (Streamlit UI).
- `uv run handoff sync` – sync dependencies with [uv](https://docs.astral.sh/uv/).
- `uv run handoff check` – run Ruff linting and formatting.
- `uv run handoff typecheck` – run type checking with pyright over `src/` and `scripts/`.
- `uv run handoff test` – run the pytest suite.
- `uv run handoff ci` – run lint, format, type checking, and tests together.
- `uv run handoff build --full` – build the embedded Windows zip (obfuscates `src/handoff` with PyArmor).
- `uv run handoff build --patch` – build a patch zip from the obfuscated build (run after `build --full`).
- `uv run handoff bump 2026.M.P` – bump version in `pyproject.toml` and `handoff.version`.

Version sync: `src/handoff/version.py` and `pyproject.toml` must match;
`tests/test_version_sync.py` enforces this. Use `bump` to update both.

Project layout: `app.py` (entrypoint), `src/handoff/` (package), `pages/`
(legacy), `tests/`.

### Branching, commits, and releases

For any **major feature or behavior change** (new UI, new tests for critical
code, type-checking setup, etc.), follow this flow:

1. **Branch from `main`**
   - `git checkout -b release/YYYY.M.MINOR` (for example `release/2026.3.4`).
2. **Make focused commits**
   - Keep each commit as small and coherent as practical.
3. **Bump the CalVer patch version when shipping user-visible changes**
   - Use the CLI helper so `pyproject.toml` and `src/handoff/version.py` stay in
     sync (see **Release workflow** below).
4. **Update documentation**
   - Add a new section to `RELEASE_NOTES.md` under the new version (see
     **Release notes** below).
   - Choose an impact tag for the release and include it in the heading in
     square brackets:
     - `[Breaking]` – schema changes, behaviour shifts, or anything that may
       require backups or manual intervention.
     - `[Recommended]` – new features, UX improvements, or important dependency
       updates most users should adopt.
     - `[Optional]` – internal-only cleanups or minor fixes that users can
       safely skip.
   - Update `README.md` if behavior, commands, or UX changed.

Releases use CalVer (`YYYY.M.MINOR`), for example `2026.3.4`.

### Release notes

When adding a new version block to `RELEASE_NOTES.md`:

- **When:** Add a new `## YYYY.M.MINOR [Tag]` section when you ship user-visible changes or notable internal work (e.g. after merging a feature branch or cutting a release).
- **Categories:** Group bullets under **Fix**, **Feature**, **Improvement**, and **Internal** so readers can scan by type:
  - **Fix** – Bug fixes, error handling, compatibility (e.g. WinError 32, backup behaviour).
  - **Feature** – New user-facing behaviour (e.g. calendar today column, new page).
  - **Improvement** – UX, docs, performance, refactors that don’t change behaviour.
  - **Internal** – Tests, tooling, code layout (optional; can be merged into Improvement).
- **Impact tag:** Keep the version heading tag (`[Breaking]` / `[Recommended]` / `[Optional]`) as above; categories only group the bullets under that version.

### Code style and tools

This project follows a small set of conventions so the codebase stays
consistent:

- **Ruff** is the single source of truth for linting and formatting. Run
  `uv run handoff check` to apply it.
- **Docstrings** for public modules, classes, and functions use Google style.
- **Type checking** is done with pyright over `src/` and `scripts/`. Run
  `uv run handoff typecheck` (or `uv run pyright src scripts`).

The `.cursor/rules/` directory contains more detailed guidance used by Cursor
and other automation; human contributors only need the summary above.

### Testing

Before merging or cutting a release, make sure tests and checks pass:

- Run the full CI-style suite:
  - `uv run handoff ci`
- Or run individual pieces:
  - `uv run handoff check`
  - `uv run handoff typecheck`
  - `uv run handoff test`

You can run targeted tests with pytest as usual, for example:

```bash
uv run pytest tests/path/to/test_module.py
```

### Release workflow checklist

When preparing a release (for example `2026.3.4`), use this checklist:

1. Branch from `main`:
   - `git checkout -b release/2026.3.4`
2. Ensure dependencies are in sync:
   - `uv sync` (if dependencies changed).
3. Bump the version using the CLI helper:
   - `uv run handoff bump 2026.3.4`
   - This keeps `pyproject.toml` and `src/handoff/version.py` in sync.
4. Update release notes:
   - Add `## 2026.3.4 [Tag]` to `RELEASE_NOTES.md`, using
     **Fix/Feature/Improvement/Internal** bullets as appropriate.
5. Update README if needed:
   - Only when user-visible behavior, commands, or updater flow changed.
6. Run checks and tests:
   - `uv run handoff ci` (or `check`, `typecheck`, and `test` separately).
7. Build artefacts (for Windows distribution):
   - `uv run handoff build --full`
   - `uv run handoff build --patch`
8. Merge back into `main` once everything passes and artefacts look correct.

### macOS support (planning)

On macOS today, run Handoff from source using the same uv + CLI workflow:

```bash
uv sync
uv run handoff
```

The app runs as a local [Streamlit](https://streamlit.io/) app with a SQLite
database stored under your per-user data directory (for example via
`platformdirs`, typically under `~/Library/Application Support/`). There is no
signed `.app` bundle yet; updates are applied via code changes or patch zips,
not via a macOS installer.

Future work may introduce a signed and notarized macOS bundle (or CLI binary)
built with PyInstaller or a platform-specific packager. When doing macOS
distribution work:

- Use a dedicated branch such as `develop/macos-bundle`.
- Plan for Gatekeeper, codesigning, notarization, and minimum macOS version.
- Prefer `arm64` builds for Apple Silicon while keeping `x86_64` in mind if
  useful.

### API documentation

There is no separate API doc build. The public API is documented via
**docstrings** (Google style) in the source. For a browsable view locally, you
can run `pdoc src/handoff` or use Sphinx if you add a config.

### Cursor rules and agent guidance

Cursor-specific rules live under `.cursor/rules/`:

- `python-project.mdc` – project-level expectations (uv, Ruff, pytest, layout).
- `python-code.mdc` – coding style and library conventions.
- `agent-planning.mdc` – branching, versioning, and release-notes workflow.

These files are primarily for Cursor and other automation. If you are using an
AI agent, point it at these rules before making significant changes so it
follows the same conventions. Human contributors can skim them once for extra
detail, but the essentials are summarized in this CONTRIBUTING guide.