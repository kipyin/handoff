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

Three PRs for implementation by a medium-intelligence AI agent (e.g. Composer 1.5). Each is scoped to a coherent goal, with concrete steps and verification. PRs must be merged in order.

---

### PR 1: Cleanup removals (handoff.ui + instrumentation)

**Branch:** `refactor/cleanup-removals`  
**Effort:** ~25 min

**Goal:** Remove `handoff.ui` shim and `instrumentation.py`; simplify codebase.

**Steps:**

*Handoff.ui:*
1. Update `app.py` docstring if it mentions `handoff.ui`. Imports already use `handoff.interfaces.streamlit`.
2. Update `tests/test_app_integration.py`: `import handoff.ui as ui` → `import handoff.interfaces.streamlit.ui as ui` (all occurrences).
3. Update `tests/test_app_import_paths.py` and `tests/test_interfaces_shim.py`: remove tests that import/assert on `handoff.ui`; keep tests for `handoff.interfaces.streamlit`.
4. Update `README.md`: `handoff.ui.setup()` → `handoff.interfaces.streamlit.ui.setup()`.
5. Delete `src/handoff/ui.py`.

*Instrumentation:*
6. In `src/handoff/interfaces/streamlit/pages/now.py`: remove `from handoff.instrumentation import time_action`; remove `with time_action("now_render"):` and unindent its block.
7. In `src/handoff/interfaces/streamlit/pages/now_forms.py`: remove instrumentation import; replace each `with time_action("...")` block with its inner body (unindent).
8. Delete `src/handoff/instrumentation.py` and `tests/test_instrumentation.py`.
9. In `tests/test_pages_now.py`: remove or simplify tests that mock/assert on instrumentation logging.

**Verification:**
- `uv run handoff ci` passes.
- `rg "handoff\.ui|instrumentation|time_action" --type py src/` returns no matches.

---

### PR 2: Bootstrap decoupling (logging, Streamlit config, log re-export)

**Branch:** `refactor/bootstrap-decoupling`  
**Depends on:** PR 1  
**Effort:** ~40 min

**Goal:** Bootstrap has no db or Streamlit dependencies. Single source of truth for `log_application_action`.

**Steps:**

*Bootstrap logging → no db:*
1. In `src/handoff/bootstrap/logging.py`: add `db_path: str | None = None` to `log_application_action`; if None, use `"(unknown)"`. Remove `from handoff.db import get_db_path` entirely.
2. Update callers to pass `db_path=str(get_db_path())`: `data/io.py`, `updater.py` (in `_log_app_action`), `services/settings_service.py` (in its pass-through).

*Streamlit config → interfaces:*
3. Create `src/handoff/interfaces/streamlit/runtime_config.py` with the `os.environ.setdefault("STREAMLIT_*", ...)` block from `bootstrap/config.py`.
4. In `src/handoff/__main__.py`: `import handoff.bootstrap.config` → `import handoff.interfaces.streamlit.runtime_config`.
5. In `src/handoff/bootstrap/config.py`: remove Streamlit env block; leave placeholder or empty.

*log_application_action direct import:*
6. In `src/handoff/interfaces/streamlit/pages/dashboard.py`: import `log_application_action` from `handoff.bootstrap.logging` (not settings_service).
7. In `src/handoff/services/settings_service.py`: remove the `log_application_action` pass-through.
8. In `src/handoff/services/__init__.py`: remove `log_application_action` from exports.
9. Update tests: `test_settings_service`, `test_settings_coverage`, `test_dashboard_render`, `test_logging_module`.

**Verification:**
- `uv run handoff ci` passes.
- `rg "from handoff.db|STREAMLIT|log_application_action" src/handoff/bootstrap/` returns no matches.
- `rg "log_application_action" src/handoff/services/` returns no matches.
- `python -c "import handoff.bootstrap.logging; handoff.bootstrap.logging.configure_logging()"` succeeds without importing db.

---

### PR 3: CLI separation + docs

**Branch:** `refactor/cli-separation`  
**Depends on:** PR 2  
**Effort:** ~35 min

**Goal:** `handoff` = run the app; `handoff-dev` = all dev/build commands. Document `__main__.py`.

**Steps:**

*CLI split:*
1. Create `scripts/dev_cli.py` with dev commands: sync, check, typecheck, test, ci, bump, build, sizecheck, db-path, format, lint. Copy logic from `scripts/cli.py`.
2. Slim `scripts/cli.py` to app commands only: `run` (default), `cli` (stub).
3. In `pyproject.toml`: `handoff = "scripts.cli:main"`, `handoff-dev = "scripts.dev_cli:main"`.
4. Update `AGENTS.md` Quick reference: `uv run handoff` for app; `uv run handoff-dev check`, `uv run handoff-dev test`, etc.
5. Update `.github/workflows/ci.yml`: use `handoff-dev ci` (or `handoff-dev check` + `handoff-dev test`).

*Docs:*
6. Add comment at top of `src/handoff/__main__.py`: "Entrypoint for Streamlit. For CLI/TUI, replace or add dispatch. See AGENTS.md."
7. In AGENTS.md: add line under Project layout about `__main__.py` being replaceable for template projects.

**Verification:**
- `uv run handoff` starts the app.
- `uv run handoff-dev check`, `uv run handoff-dev test`, `uv run handoff-dev build --full --dry-run` succeed.
- CI workflow passes.

---

## 9. PR Summary Table

| PR | Title | Depends on | Est. effort |
|----|-------|------------|-------------|
| 1 | Cleanup removals (handoff.ui + instrumentation) | — | ~25 min |
| 2 | Bootstrap decoupling | 1 | ~40 min |
| 3 | CLI separation + docs | 2 | ~35 min |

**Merge order:** 1 → 2 → 3.

**Agent guidance:** Each PR in one session. After each, run `uv run handoff ci` (PR 1–2) or `uv run handoff-dev ci` (PR 3). Fix failures before merging.
