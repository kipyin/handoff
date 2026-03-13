# Template Readiness — Handoff Decoupling Plan

Handoff will not become the template repo. The goal is to **refactor Handoff so its modules are decoupled**, making it structurally ready for future template extraction. When the time comes, modules can be copied out with minimal changes.

This document identifies coupling issues and proposes concrete refactors.

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

### 2.5 scripts/cli.py → app-specific commands (Medium)

**Problem:** `build`, `db-path` are Handoff-specific. The core-dev module should have: check, typecheck, test, ci, bump, sync, run. Build and db-path belong to distribution and data layers.

**Impact:** When extracting core-dev, you'd carry build/db-path or manually strip them. Better: structure CLI so app-specific commands are clearly separated.

**Fix:**
- Keep generic commands in `scripts/cli.py`: sync, check, typecheck, test, ci, bump, run.
- Move `build` and `db-path` to a separate submodule or "plugins" that are registered when distribution/db exist. Or: keep them in cli.py but document them as "app-specific"; a template would delete those commands. Structural separation (e.g. `scripts/cli_app.py` with `app.add_typer(app_commands)`) makes deletion easier.

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

### 2.8 handoff.ui compatibility shim (Low)

**Problem:** `handoff.ui` re-exports Streamlit UI. Exists for backward compatibility. Creates a top-level namespace that implies "there is one UI."

**Fix:** Keep for Handoff (backward compat), but when templating: the shim would not exist in a "streamlit-simple" template. Document that `handoff.ui` is a Handoff-specific shim; template uses `handoff.interfaces.streamlit.ui` directly.

---

### 2.9 scripts/__init__.py injects SRC into path

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
| P3 | CLI app-specific commands | Separate or document for removal | Small |
| P4 | __main__.py | Document as replaceable for template | Doc only |
| P5 | Hardcoded "handoff" in paths | Add APP_NAME config (or defer) | Small |

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
