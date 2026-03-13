# Project Structure Restructure Plan

Consolidated plan for restructuring `src/handoff` into a functional layout. Each section is intended for AI agents implementing the work and for human/AI reviewers.

---

## 1. Rationale and Constraints

### Why Restructure

- **Module sprawl**: Many top-level modules under `src/handoff` with mixed purposes
- **Short helper modules**: `paths`, `config`, `docs`, `instrumentation` are very small
- **Scattered models**: ORM, page contracts, backup schemas, and DTOs are split across modules
- **Future CLI**: Need a clear place for a CLI that parallels the Streamlit UI

### Hard Constraints (MUST)

1. **PyArmor 32KB limit**: No `.py` file may exceed 32,768 bytes. Run `uv run handoff sizecheck` after each change.
2. **Architecture**: Pages import from `handoff.services` only, never `handoff.data` directly. `tests/test_services_architecture.py` enforces this.
3. **CI**: `uv run handoff ci` must pass (Ruff, pyright, pytest).
4. **One source of truth**: Filtering, validation, and serialization live in a single place; no duplicate logic across layers.

### Naming: `bootstrap` Instead of `platform`

"Platform" is ambiguous (business platforms, cloud infrastructure). The package holding paths, config, logging, and docs is about **startup and environment setup**, so `bootstrap` is used. Alternatives considered: `support` (generic), `shell` (collides with CLI), `runtime` (collides with Python runtime).

---

## 2. Target Layout

```
handoff/
├── core/                       # Domain models and rules (shared by all interfaces)
│   ├── __init__.py
│   ├── models.py               # Project, Handoff, CheckIn, CheckInType (ORM)
│   ├── page_models.py          # NowSnapshot, HandoffQuery, ProjectSummaryRow, etc.
│   ├── backup_schema.py        # BackupPayload, Backup*Record
│   ├── handoff_lifecycle.py    # open/closed semantics, _latest_check_in
│   └── rulebook.py             # RuleDefinition, conditions, sections
│
├── data/                       # Persistence and queries (layout unchanged)
│   ├── __init__.py
│   ├── activity.py
│   ├── handoffs.py
│   ├── io.py
│   ├── projects.py
│   └── queries.py
│
├── services/                   # Business orchestration (layout unchanged)
│   ├── __init__.py
│   ├── handoff_service.py
│   ├── dashboard_service.py
│   ├── project_service.py
│   └── settings_service.py
│
├── interfaces/                 # All user-facing interfaces
│   ├── __init__.py
│   ├── streamlit/              # Streamlit UI
│   │   ├── __init__.py
│   │   ├── ui.py               # setup, page wiring
│   │   ├── pages/              # about, dashboard, now, projects, system_settings
│   │   ├── autosave.py
│   │   └── update_ui.py        # update/restore panel
│   └── cli/                    # Future CLI (parallel to Streamlit)
│       ├── __init__.py
│       └── (stub for future commands)
│
├── bootstrap/                  # Startup, config, paths, logging
│   ├── __init__.py
│   ├── paths.py
│   ├── config.py
│   ├── logging.py
│   └── docs.py
│
├── migrations/
│   ├── __init__.py
│   ├── runner.py
│   └── scripts/
│
├── db.py                       # DB init, session context
├── updater.py                  # Patch/restore logic
├── search_parse.py             # Query parsing (used by handoff_service)
├── instrumentation.py          # Timing (used by now page)
├── version.py
├── __init__.py
└── __main__.py
```

---

## 3. PyArmor 32KB Limit

The PyArmor trial license refuses to obfuscate code objects over ~32KB. The project enforces this via `scripts/sizecheck.py` and `tests/test_module_size.py`.

**Rule:** No module may exceed 32,768 bytes of source.

**Files currently near the limit:**

| File                     | Size  | Status   |
|--------------------------|-------|----------|
| `pages/now.py`           | 29 KB | Under    |
| `data/queries.py`        | 26 KB | Under    |
| `pages/system_settings.py` | 23 KB | Under |
| `services/dashboard_service.py` | 22 KB | Under |

**During restructure:** Do not merge modules if the result would approach 32KB. Prefer splitting large modules. Run `uv run handoff sizecheck` after each PR.

---

## 4. PR Breakdown

Each PR is implemented by one agent, reviewed by GitHub Copilot, and optionally by a higher-intelligence model. PRs are merged in order; some may be parallelized as noted.

### PR 1: Create `bootstrap` package

**Branch:** `refactor/bootstrap-package`  
**Base:** `main`

**Scope:**
- Create `handoff/bootstrap/__init__.py`
- Move `paths.py` → `bootstrap/paths.py`
- Move `config.py` → `bootstrap/config.py`
- Move `logging.py` → `bootstrap/logging.py`
- Move `docs.py` → `bootstrap/docs.py`
- Update all imports: `updater.py`, `update_ui.py`, `ui.py`, `pages/about.py`, `pages/system_settings.py`, `scripts/cli.py`, tests
- Delete the old top-level module files

**Verification:** `uv run handoff ci` and `uv run handoff sizecheck`

---

### PR 2: Create `core` package – models and lifecycle

**Branch:** `refactor/core-models-lifecycle`  
**Base:** `main` (or branch with PR 1 merged)

**Scope:**
- Create `handoff/core/__init__.py`
- Move `models.py` → `core/models.py`
- Move `handoff_lifecycle.py` → `core/handoff_lifecycle.py`
- Update all imports in: `data/*`, `services/*`, `pages/*`, `backup_schema.py`, `page_models.py`, `rulebook.py`, `migrations/*`, `db.py`, tests
- Delete the old top-level module files

**Verification:** `uv run handoff ci` and `uv run handoff sizecheck`

---

### PR 3: Create `core` package – schemas and rulebook

**Branch:** `refactor/core-schemas-rulebook`  
**Base:** branch with PR 2 merged

**Scope:**
- Move `page_models.py` → `core/page_models.py`
- Move `backup_schema.py` → `core/backup_schema.py`
- Move `rulebook.py` → `core/rulebook.py`
- Update all imports in: `services/*`, `pages/*`, `data/io.py`, `data/queries.py`, tests
- Delete the old top-level module files

**Verification:** `uv run handoff ci` and `uv run handoff sizecheck`

---

### PR 4: Create `interfaces/streamlit` package

**Branch:** `refactor/interfaces-streamlit`  
**Base:** branch with PR 1, 2, 3 merged

**Scope:**
- Create `handoff/interfaces/__init__.py`
- Create `handoff/interfaces/streamlit/__init__.py`
- Move `ui.py` → `interfaces/streamlit/ui.py`
- Move `pages/` → `interfaces/streamlit/pages/`
- Move `autosave.py` → `interfaces/streamlit/autosave.py`
- Move `update_ui.py` → `interfaces/streamlit/update_ui.py`
- Update `app.py`, `__main__.py`, `scripts/cli.py` to import from new paths
- Update tests that import from pages, ui, autosave, update_ui
- Ensure `handoff.ui` references (e.g. `setup`) resolve to `handoff.interfaces.streamlit.ui`

**Verification:** `uv run handoff ci`, `uv run handoff sizecheck`, manual run of the app

---

### PR 5: Add `interfaces/cli` stub

**Branch:** `refactor/interfaces-cli-stub`  
**Base:** branch with PR 4 merged

**Scope:**
- Create `handoff/interfaces/cli/__init__.py`
- Add minimal stub (e.g. empty `__all__` or `def run_cli() -> None: ...`)
- Optionally wire into `scripts/cli.py` for future `handoff cli` subcommand

**Verification:** `uv run handoff ci`

---

### PR 6: Data layer cleanup

**Branch:** `refactor/data-layer-cleanup`  
**Base:** branch with PR 2, 3 merged (can run in parallel with PR 4 if needed)

**Scope:**
- In `data/handoffs.py`: remove `_latest_check_in` wrapper; import from `handoff.core.handoff_lifecycle` directly
- In `data/__init__.py`: remove re-exports of private symbols (`_latest_check_in`, `_Unset`, `_apply_handoff_filters`, etc.); keep only the public data API
- Update tests that depend on those private re-exports to import from the correct modules

**Verification:** `uv run handoff ci`, especially `tests/test_data.py` and `tests/test_todo_service.py`

---

### PR 7: Split `data/queries.py` (conditional)

**Branch:** `refactor/split-queries`  
**Base:** branch with PR 6 merged

**Condition:** Only implement if `uv run handoff sizecheck` fails due to `data/queries.py` exceeding 32KB.

**Scope:**
- Split `data/queries.py` into smaller modules (e.g. `queries_filter.py`, `queries_now.py`) so each stays under 32KB
- Update `data/__init__.py` and internal imports
- Add or adjust tests as needed

**Verification:** `uv run handoff ci` and `uv run handoff sizecheck`

---

## 5. PR Summary Table

| PR | Title                          | Depends on   | Est. files |
|----|--------------------------------|--------------|------------|
| 1  | Create `bootstrap` package    | —            | ~15        |
| 2  | Create `core` (models, lifecycle) | —         | ~35        |
| 3  | Create `core` (schemas, rulebook) | 2          | ~25        |
| 4  | Create `interfaces/streamlit` | 1, 2, 3      | ~30        |
| 5  | Add `interfaces/cli` stub     | 4            | ~5         |
| 6  | Data layer cleanup            | 2, 3         | ~10        |
| 7  | Split `data/queries.py`       | 6            | ~8         |

**Merge order:** 1 → 2 → 3 → (4 and 6 can run in parallel) → 4 → 5 → 6 → 7 (if needed).

---

## 6. Reviewer Checklist

For each PR, verify:

- [ ] No new imports of `handoff.data` from pages (architecture rule)
- [ ] `uv run handoff sizecheck` passes
- [ ] `uv run handoff ci` passes
- [ ] All import paths updated (no stale `handoff.paths`, `handoff.docs`, etc. unless intentionally re-exported)
- [ ] `app.py` and `handoff run` still start the app correctly (for PR 4+)

---

## 7. References

- **AGENTS.md**: Project rules, Quick reference, testing commands
- **tests/test_services_architecture.py**: Enforces pages → services only
- **scripts/sizecheck.py**, **tests/test_module_size.py**: Enforce 32KB limit
- **scripts/build_full.py**: Uses PyArmor; references 32KB limit in error messages
