# Template Readiness — Handoff Decoupling Plan

Handoff will not become the template repo. The goal is to **refactor Handoff so its modules are decoupled**, making it structurally ready for future template extraction. When the time comes, modules can be copied out with minimal changes.

This document identifies coupling issues and proposes concrete refactors.

**Note:** This plan is documentation-only. Implementation is deferred until explicitly requested.

---

## 1. Current Module Boundaries (What Exists)

| Area | Contents | Intended independence |
|------|----------|------------------------|
| **core-dev** | AGENTS.md, pyproject.toml, scripts/cli (check, typecheck, test, ci, bump), version.py | Should work without app |
| **bootstrap** | paths, config, logging, docs | Should not depend on db/streamlit/core |
| **core** | models, handoff_lifecycle, page_models, backup_schema, rulebook | Domain only |
| **data** | activity, handoffs, io, projects, queries | Persistence only |
| **db** | init, session, engine | Depends on core + migrations |
| **services** | handoff, project, dashboard, settings | Orchestration |
| **streamlit** | ui, pages, autosave, update_ui | UI layer |
| **distribution** | updater, build_full, build_patch, sizecheck | Build + patch logic |
| **cli** | Typer commands | Dev + app commands mixed |

---

## 2. Coupling Issues (Blocking Template Readiness)

### 2.1 bootstrap → db (Critical)

**Problem:** `bootstrap.logging.log_application_action` imports `handoff.db.get_db_path`. Bootstrap is meant to be infra-only; importing db pulls in core, migrations, sqlmodel.

**Location:** `src/handoff/bootstrap/logging.py:28`

```python
def log_application_action(action: str, **details: Any) -> None:
    try:
        from handoff.db import get_db_path
        db_path = str(get_db_path())
```

**Impact:** Any code that uses bootstrap.logging (data/io, updater, settings_service, pages) transitively depends on db. Bootstrap cannot be extracted without db.

**Fix:** Remove db dependency from `log_application_action`:
- Option A: Accept optional `db_path: str | None` or `get_db_path: Callable[[], Path] | None`; caller passes it. Default to `"(unknown)"` when not provided.
- Option B: Move `log_application_action` to a layer that knows about db (e.g. a small `handoff.audit` module), and have bootstrap only export `configure_logging`. Callers that need audit logging import from audit.
- **Recommendation:** Option A — add optional parameter, keep API simple. Callers that have db (data/io, pages) pass `str(get_db_path())`; bootstrap stays pure.

---

### 2.2 bootstrap.config → Streamlit (Medium)

**Problem:** `bootstrap.config` sets `STREAMLIT_*` env vars. Bootstrap is meant to be interface-agnostic.

**Location:** `src/handoff/bootstrap/config.py`

**Impact:** A project with only CLI would still have Streamlit config in bootstrap.

**Fix:** Move Streamlit env setup to `handoff.interfaces.streamlit.config` (or `streamlit/runtime_config.py`). Import it from `__main__.py` before starting Streamlit. Bootstrap.config becomes empty or holds only generic config (e.g. log level).

---

### 2.3 bootstrap.logging → hardcoded "handoff" (Low)

**Problem:** `user_data_dir("handoff", "handoff")`, `handoff.log` are app-specific.

**Location:** `src/handoff/bootstrap/logging.py:44`, `:60`

**Impact:** When extracting bootstrap for a template, these names would need parameterization.

**Fix:** Add `handoff.bootstrap.config` or init-time config: `APP_NAME = "handoff"` (or read from version/package). Use it in paths. For Handoff today, keep `"handoff"` as the default; the abstraction enables templates.

---

### 2.4 db.py → hardcoded "handoff" (Low)

**Problem:** `user_data_dir("handoff", "handoff")` in db path resolution.

**Location:** `src/handoff/db.py:25`

**Impact:** When extracting db layer for a template, app name would need to be configurable.

**Fix:** Add configurable app name (e.g. from version/package metadata or bootstrap config). For Handoff, default remains `"handoff"`. Defer until template extraction if other refactors are higher priority.

---

### 2.5 CLI separation (Medium)

**Problem:** Three distinct CLIs are currently merged under `uv run handoff`:
1. **App CLI** (`src/handoff/interfaces/cli/`) — future interactive CLI for handoff operations (stub)
2. **Dev CLI** (`scripts/cli.py`) — lint, format, typecheck, test, ci, bump, sync
3. **Build CLI** — build --full, build --patch, sizecheck, db-path

**Proposed split:**

| Entrypoint | Purpose | Commands |
|------------|---------|----------|
| `uv run handoff` | Run the app | `handoff` or `handoff --web` → Streamlit (future: CLI/TUI) |
| `uv run handoff-dev` | Build and distribution | build --full, build --patch, sizecheck, db-path |
| `uv run handoff-ci` | Lint, format, test | check, typecheck, test, ci, bump, sync |

**Alternative:** Combine `handoff-dev` and `handoff-ci` into a single dev CLI. One entrypoint for all developer tooling (build + check + test + ci). CI would run `handoff-dev check`, `handoff-dev test`, or `handoff-dev ci`.

**Recommendation:** **Combine** into one dev CLI. Simpler mental model: `handoff` = run the product; `handoff-dev` = develop, build, and validate the product. Avoids proliferation of entrypoints.

**Fix (when implementing):**
- Add `handoff-dev` entrypoint → `scripts.cli:main` (or `scripts.dev_cli:main`)
- Move `handoff` entrypoint to app launcher only. May require splitting `scripts/cli.py`: app commands vs dev commands.

---

### 2.6 __main__.py → hardcoded Streamlit + app.py (Medium)

**Problem:** `__main__.py` imports bootstrap.config and runs `streamlit run app.py`. For a CLI-only or multi-interface project, this would differ.

**Impact:** Template extraction would need to replace __main__.py entirely.

**Fix:** Make entrypoint configurable. Options:
- A: `__main__.py` reads an env var or config (e.g. `HANDOFF_UI=streamlit`) and dispatches. Default: Streamlit. Enables future CLI/TUI.
- B: Keep as-is but document: "For template, replace __main__.py with your entrypoint." Handoff stays Streamlit-first; template gets a placeholder main.
- **Recommendation:** B for now. The entrypoint is one file; documenting it is sufficient. Over-abstracting now adds complexity. If we add CLI/TUI later, we'll refactor.

---

### 2.7 log_application_action re-export via services (Low)

**Problem:** `dashboard.py` imports `log_application_action` from `handoff.services.settings_service`. It's a pass-through to bootstrap.logging. Unnecessary indirection.

**Fix:** Have dashboard (and any page) import `log_application_action` from `handoff.bootstrap.logging` directly. Remove re-export from settings_service and services/__init__.py. Single source of truth: bootstrap.

---

### 2.8 handoff.ui compatibility shim — REMOVE (Planned)

**Decision:** Remove `handoff.ui` from Handoff. All imports will use `handoff.interfaces.streamlit.ui` directly. Reduces indirection and aligns with template (no shim).

**Implementation deferred.**

---

### 2.9 instrumentation.py — REMOVE (Planned)

**Decision:** Remove `instrumentation.py`. Lightweight timing for the Now page is not essential; simplifies codebase for template extraction.

**Implementation deferred.**

---

### 2.10 scripts/__init__.py injects SRC into path

**Problem:** `scripts/__init__.py` does `sys.path.insert(0, str(SRC))` so scripts can `import handoff`. That's fine for dev; build scripts also depend on it.

**Impact:** None for decoupling; scripts are dev-time only. Not extracted into template core-dev directly—template would have its own scripts.

---

## 3. Dependency Graph (Current)

```
                    bootstrap
                 /     |     \
                /      |      \
          logging   config   paths
               |        |       |
               |     (Streamlit) |
               |                |
               v                v
              db  <---------  updater
               |
         core, migrations
               |
           data, services
               |
        interfaces/streamlit
```

**Key cycle risk:** bootstrap.logging → db. Breaks the "bootstrap is infra-only" guarantee.

---

## 4. Refactoring Priorities

| Priority | Issue | Fix | Effort |
|----------|-------|-----|--------|
| P0 | bootstrap.logging → db | log_application_action: optional db_path param | Small |
| P1 | bootstrap.config → Streamlit | Move STREAMLIT_* to interfaces/streamlit | Small |
| P2 | log_application_action via services | Import from bootstrap in dashboard | Trivial |
| P3 | CLI separation | handoff = app; handoff-dev = build + check + test + ci | Medium |
| P4 | __main__.py | Document as replaceable for template | Doc only |
| P5 | Hardcoded "handoff" in paths | Add APP_NAME config (or defer) | Small |
| — | handoff.ui | Remove (use interfaces.streamlit.ui) | Planned |
| — | instrumentation.py | Remove | Planned |

---

## 5. Suggested Implementation Order

### Phase 1: Break bootstrap → db (P0)

1. Change `log_application_action(action, **details)` to optionally accept `db_path: str | None = None`.
2. If `db_path` is None, try `get_db_path()` inside the function and catch ImportError/other—use `"(unknown)"` on failure. This keeps the function in bootstrap but makes the db import lazy and best-effort. **Alternative:** pass db_path explicitly from callers. That removes the import entirely.
3. **Preferred:** Add optional param `db_path: str | None = None`. If None, use `"(unknown)"`. Update callers (data/io, updater, settings_service, pages) to pass `str(get_db_path())` when they have db access. This removes `from handoff.db import get_db_path` from bootstrap entirely.

### Phase 2: Move Streamlit config out of bootstrap (P1)

1. Create `handoff.interfaces.streamlit.runtime_config` (or `config.py` inside interfaces/streamlit).
2. Move the `os.environ.setdefault("STREAMLIT_*", ...)` block there.
3. In `__main__.py`, `import handoff.interfaces.streamlit.runtime_config` instead of `handoff.bootstrap.config`.
4. Remove or slim down `bootstrap.config` (can be empty or hold future generic config).

### Phase 3: Direct bootstrap imports for log_application_action (P2)

1. In `dashboard.py`, change `from handoff.services.settings_service import log_application_action` to `from handoff.bootstrap.logging import log_application_action`.
2. Remove `log_application_action` from settings_service and services/__init__.py.
3. Update any tests that mock or assert on the settings_service re-export.

### Phase 4: CLI structure (P3)

1. Group app-specific commands: either move to `scripts/cli_app.py` and `app.add_typer(app_commands)` or add a clear comment block "App-specific commands" in cli.py.
2. Document in AGENTS.md or a CONTRIBUTING note: "For template extraction, remove build, db-path, and app-specific options from the CLI."

### Phase 5: Document __main__.py and ui shim (P4, P8)

1. Add a short comment in __main__.py: "Entrypoint for Streamlit. For other interfaces (CLI, TUI), replace this file."
2. Add a note in the ui shim: "Compatibility shim for Handoff. Template projects import from interfaces.streamlit.ui directly."

---

## 6. Definition of "Template Ready"

Handoff is template-ready when:

1. **bootstrap** has no imports of `handoff.db`, `handoff.core`, `handoff.data`, `handoff.services`, or `handoff.interfaces`.
2. **bootstrap.config** has no Streamlit-specific setup (or is empty/generic).
3. **interfaces/streamlit** is the only place that wires Streamlit config and UI.
4. **distribution** (updater, build scripts) does not depend on Streamlit UI (update_ui is the only bridge, and it correctly lives in streamlit).
5. **CLI** structure makes it obvious which commands are generic vs app-specific.

---

## 7. Verification

After refactoring:

1. `uv run handoff ci` passes.
2. Run a quick import test: `python -c "import handoff.bootstrap; import handoff.bootstrap.logging; handoff.bootstrap.logging.configure_logging()"` — should succeed without importing db (if we use the "pass db_path from caller" approach, bootstrap never touches db).
3. Grep for `from handoff.db` in bootstrap: should be empty.
4. Grep for `STREAMLIT` in bootstrap: should be empty.

---

## 8. PR Breakdown (AI-Agent Implementation)

These PRs are designed for implementation by a medium-intelligence AI agent (e.g. Composer 1.5). Each PR is scoped to one concept, has concrete steps, and includes verification. PRs should be merged in order; some can be parallelized as noted.

### PR 1: Remove handoff.ui compatibility shim

**Branch:** `refactor/remove-handoff-ui`  
**Depends on:** —  
**Effort:** Small (~15 min)

**Goal:** Remove the `handoff.ui` shim; all imports use `handoff.interfaces.streamlit.ui` directly.

**Steps:**
1. Update `app.py`: change docstring if it mentions `handoff.ui`; imports already use `handoff.interfaces.streamlit`.
2. Update `tests/test_app_integration.py`: change `import handoff.ui as ui` to `import handoff.interfaces.streamlit.ui as ui` (all occurrences).
3. Update `tests/test_app_import_paths.py`: `test_integration_entry_functions_use_streamlit_ui` — use `handoff.interfaces.streamlit.ui`; remove any test that asserts on `handoff.ui`.
4. Update `tests/test_interfaces_shim.py`: remove all tests that import or assert on `handoff.ui`. Keep only tests for `handoff.interfaces.streamlit`.
5. Update `README.md`: replace `handoff.ui.setup()` with `handoff.interfaces.streamlit.ui.setup()`.
6. Delete `src/handoff/ui.py`.

**Verification:**
- `uv run handoff ci` passes.
- `rg "handoff\.ui" --type py` returns no matches (except in RELEASE_NOTES, plans).

---

### PR 2: Remove instrumentation.py

**Branch:** `refactor/remove-instrumentation`  
**Depends on:** —  
**Effort:** Small (~10 min)

**Goal:** Remove `instrumentation.py` and all `time_action` usages. Simplifies codebase.

**Steps:**
1. In `src/handoff/interfaces/streamlit/pages/now.py`: remove `from handoff.instrumentation import time_action`; remove `with time_action("now_render"):` and unindent the block inside it by one level.
2. In `src/handoff/interfaces/streamlit/pages/now_forms.py`: remove `from handoff.instrumentation import time_action`; replace each `with time_action("...")` block with its inner body (unindent).
3. Delete `src/handoff/instrumentation.py`.
4. Delete `tests/test_instrumentation.py`.
5. In `tests/test_pages_now.py`: remove or simplify tests that mock `handoff.instrumentation.logger` or assert on instrumentation logging (e.g. `test_save_check_in_submission_conclude_logs_instrumentation` and similar). Either delete those tests or remove the instrumentation-specific assertions.

**Verification:**
- `uv run handoff ci` passes.
- `rg "instrumentation|time_action" --type py src/` returns no matches.

---

### PR 3: Decouple bootstrap.logging from handoff.db

**Branch:** `refactor/bootstrap-logging-no-db`  
**Depends on:** —  
**Effort:** Small–medium (~20 min)

**Goal:** `log_application_action` must not import `handoff.db`. Bootstrap stays infra-only.

**Steps:**
1. In `src/handoff/bootstrap/logging.py`: change `log_application_action(action, **details)` to `log_application_action(action: str, *, db_path: str | None = None, **details)`. If `db_path` is None, use `"(unknown)"` in the log. Remove the `from handoff.db import get_db_path` block entirely.
2. Find all callers of `log_application_action`:
   - `src/handoff/data/io.py` — has db access
   - `src/handoff/updater.py` — `_log_app_action` delegates to bootstrap; add db_path in updater before delegating
   - `src/handoff/services/settings_service.py` — pass-through to bootstrap; add `db_path=str(get_db_path())` when calling `_logging.log_application_action`
   - `src/handoff/interfaces/streamlit/pages/dashboard.py` — imports from settings_service (PR 5 will change this); no change in PR 3
   - `src/handoff/interfaces/streamlit/pages/system_settings.py` — imports from services; no change in PR 3
3. Update io, updater, and settings_service to pass `db_path=str(get_db_path())` when calling `log_application_action`. Pages go through settings_service, which will pass db_path.
4. Update `tests/test_logging_module.py`: tests that assert on db_path — ensure they pass db_path explicitly or expect `"(unknown)"` when not passed.

**Verification:**
- `uv run handoff ci` passes.
- `rg "from handoff.db|import.*get_db_path" src/handoff/bootstrap/` returns no matches.
- `python -c "import handoff.bootstrap.logging; handoff.bootstrap.logging.configure_logging()"` succeeds without importing handoff.db.

---

### PR 4: Move Streamlit config from bootstrap to interfaces

**Branch:** `refactor/streamlit-config-to-interfaces`  
**Depends on:** —  
**Effort:** Small (~15 min)

**Goal:** Bootstrap has no Streamlit-specific setup. Streamlit config lives in `interfaces/streamlit`.

**Steps:**
1. Create `src/handoff/interfaces/streamlit/runtime_config.py` with the contents of the `os.environ.setdefault("STREAMLIT_*", ...)` block from `bootstrap/config.py`. Add a module docstring: "Streamlit runtime options. Import before any Streamlit process starts."
2. In `src/handoff/__main__.py`: change `import handoff.bootstrap.config` to `import handoff.interfaces.streamlit.runtime_config`.
3. In `src/handoff/bootstrap/config.py`: remove the Streamlit env block. Leave the file with a docstring and optional placeholder (e.g. `# Reserved for generic config`) or empty `__all__ = []`.
4. Update `bootstrap/__init__.py` if it re-exports config; remove config from exports if it no longer has meaningful content.
5. Update any tests that import or patch `handoff.bootstrap.config` to use `handoff.interfaces.streamlit.runtime_config` instead.

**Verification:**
- `uv run handoff ci` passes.
- `uv run handoff` starts the app; Streamlit options (e.g. no error details) still apply.
- `rg "STREAMLIT" src/handoff/bootstrap/` returns no matches.

---

### PR 5: Remove log_application_action re-export from services

**Branch:** `refactor/log-action-direct-import`  
**Depends on:** PR 3 (so dashboard can import from bootstrap)  
**Effort:** Trivial (~5 min)

**Goal:** `log_application_action` has a single source of truth in `bootstrap.logging`. No re-export via services.

**Steps:**
1. In `src/handoff/interfaces/streamlit/pages/dashboard.py`: change `from handoff.services.settings_service import log_application_action` to `from handoff.bootstrap.logging import log_application_action`.
2. In `src/handoff/services/settings_service.py`: remove the `log_application_action` function (the pass-through) and its delegation to `_logging.log_application_action`.
3. In `src/handoff/services/__init__.py`: remove `log_application_action` from imports and `__all__`.
4. Update `tests/test_settings_service.py`: remove or adjust `test_log_application_action_delegates_to_bootstrap_logging` (no longer applicable).
5. Update `tests/test_settings_coverage.py` and `tests/test_dashboard_render.py`: any references to `settings_service.log_application_action` or mocking — switch to `bootstrap.logging.log_application_action` or the page under test.

**Verification:**
- `uv run handoff ci` passes.
- `rg "log_application_action" src/handoff/services/` returns no matches.

---

### PR 6: CLI separation (handoff vs handoff-dev)

**Branch:** `refactor/cli-separation`  
**Depends on:** — (can run in parallel with PR 1–5)  
**Effort:** Medium (~30 min)

**Goal:** `handoff` = run the app; `handoff-dev` = all dev and build commands. Clear separation.

**Steps:**
1. In `pyproject.toml`: add `[project.scripts]` entry `handoff-dev = "scripts.cli:main"`. Keep `handoff = "scripts.cli:main"` for now (both point to same CLI).
2. Create `scripts/app_cli.py`: a minimal Typer app with one command `run` (or default) that does what `handoff run` does today — invokes `python -m handoff` or `streamlit run app.py`.
3. In `scripts/cli.py`: identify "app" commands vs "dev" commands.
   - App: `run` (default), `cli` (stub)
   - Dev: `sync`, `check`, `typecheck`, `test`, `ci`, `bump`, `build`, `sizecheck`, `db-path`, `format`, `lint`
4. Split: create `scripts/dev_cli.py` with all dev commands (copy from cli.py). `scripts/cli.py` becomes the app CLI only (run, cli stub).
5. Update `pyproject.toml`: `handoff = "scripts.cli:main"` (app), `handoff-dev = "scripts.dev_cli:main"` (dev).
6. Update `AGENTS.md` Quick reference: `uv run handoff` for app; `uv run handoff-dev check`, `uv run handoff-dev test`, `uv run handoff-dev build --full`, etc.
7. Update `.github/workflows/ci.yml`: replace `uv run handoff ci` with `uv run handoff-dev ci` (or `handoff-dev check` + `handoff-dev test`).

**Verification:**
- `uv run handoff` starts the app (unchanged).
- `uv run handoff-dev check` runs Ruff.
- `uv run handoff-dev test` runs pytest.
- `uv run handoff-dev build --full --dry-run` succeeds.
- CI workflow passes.

---

### PR 7: Document __main__.py as replaceable

**Branch:** `refactor/doc-main-entrypoint`  
**Depends on:** —  
**Effort:** Trivial (~2 min)

**Goal:** Document that `__main__.py` is the Streamlit entrypoint and can be replaced for other interfaces.

**Steps:**
1. Add a comment at the top of `src/handoff/__main__.py`: "Entrypoint for Streamlit. For CLI or TUI interfaces, replace this file or add a dispatch. See AGENTS.md."
2. In `AGENTS.md`, under "Non-obvious caveats" or "Project layout": add one line: "`__main__.py` is the Streamlit launcher; template projects may replace it for other UIs."

**Verification:**
- No behavior change. `uv run handoff ci` passes.

---

## 9. PR Summary Table

| PR | Title | Depends on | Est. effort | Parallelizable with |
|----|-------|------------|-------------|---------------------|
| 1 | Remove handoff.ui shim | — | ~15 min | 2, 4, 6, 7 |
| 2 | Remove instrumentation.py | — | ~10 min | 1, 4, 6, 7 |
| 3 | Bootstrap logging no db | — | ~20 min | 1, 2, 4, 7 |
| 4 | Streamlit config to interfaces | — | ~15 min | 1, 2, 3, 6, 7 |
| 5 | log_application_action direct import | 3 | ~5 min | — |
| 6 | CLI separation | — | ~30 min | 1, 2, 3, 4, 7 |
| 7 | Document __main__.py | — | ~2 min | All |

**Merge order:** 1, 2, 3, 4 in any order (or parallel) → 5 (after 3) → 6 when ready → 7 anytime.

**Agent guidance:** Each PR should be implemented in a single session. If a PR grows too large, split it rather than expanding scope. After each PR, run full CI: `uv run handoff ci` (before PR 6) or `uv run handoff-dev ci` (after PR 6). Fix any failures before merging.
