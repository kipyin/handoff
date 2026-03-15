# Modular Template Project — Planning Document

Planning how to turn Handoff into a modular template with a minimal core and optional add-on features. The goal is to support: (1) a bare-bones dev skeleton that minimizes AI slop and human error, (2) optional interfaces (Streamlit, CLI, TUI), (3) optional distribution (embedded Python, in-app updater, obfuscation), and (4) clear separation so consumers can pick only what they need.

---

## 1. Module Overview

| Module | Purpose | Dependencies | Template scope |
|--------|---------|--------------|----------------|
| **core-dev** | Style guide, tooling, guardrails | — | Always included |
| **bootstrap** | Paths, logging, config | core-dev, platformdirs | Optional (needed for any real app) |
| **streamlit-simple** | Pure Streamlit app, no layering | core-dev, bootstrap | Optional |
| **streamlit-arch** | Model–data–service–page architecture | core-dev, bootstrap, sqlmodel | Optional |
| **distribution** | Embedded Python, updater, obfuscation | core-dev, bootstrap | Optional |
| **cli** | Typer CLI interface | core-dev, bootstrap | Optional |
| **tui** | Textual TUI interface | core-dev, bootstrap | Optional |

---

## 2. Core Dev Module (`core-dev`)

**The very core: style guide and modern dev essentials.**

If there is no real function at all, the template should still provide a strong skeleton that minimizes AI slop and human error.

### Contents

| Component | Purpose |
|-----------|---------|
| AGENTS.md | Style section (aesthetic, hygienic, robust, practical), quick reference, non-obvious caveats |
| uv + pyproject.toml | Dependency management, tool config (Ruff, pyright, pytest), entrypoints |
| Ruff | Format + lint; single source of config in pyproject.toml |
| Pyright | Type checking; single source of config in pyproject.toml |
| Pytest | Test runner; pythonpath, testpaths, coverage in pyproject.toml |
| Dev CLI | Minimal Typer CLI: `check`, `typecheck`, `test`, `ci` |
| Version bump | `bump` command + `version.py`; test enforces sync with pyproject.toml |
| Loguru | Structured logging; configured in bootstrap, but listed as core if used early |
| Guardrail tests | Import-path tests, architecture tests (e.g. pages → services only) |

### Guardrail Tests (Auto-Style Enforcement)

- **Import-path tests**: Ensure app entrypoints and relocated modules import from canonical paths; fail if old paths are reintroduced.
- **Architecture tests**: e.g. `test_pages_do_not_import_data_layer_directly` — enforce boundaries without manual review.
- **Version sync test**: `test_version_sync` — `version.py` and `pyproject.toml` must match.

### Deliverables

```
core-dev/
├── AGENTS.md              # Style section only (no app-specific content)
├── pyproject.toml         # Minimal: uv, ruff, pyright, pytest, typer, loguru
├── scripts/
│   ├── cli.py             # check, typecheck, test, ci, bump
│   └── subprocess_utils.py
├── src/<pkg>/
│   └── version.py
├── tests/
│   ├── conftest.py
│   ├── test_version_sync.py
│   └── test_app_import_paths.py  # Generic: "entrypoint imports work"
└── .github/workflows/ci.yml
```

### Dependencies (core-dev)

- Python 3.13+
- uv
- ruff, pyright, pytest, pytest-cov
- typer, rich (for CLI)
- loguru (optional in core; can move to bootstrap)

---

## 3. Bootstrap Module (`bootstrap`)

**Startup, paths, config, logging.**

Provides platform-agnostic paths (platformdirs), structured logging (loguru), and config. Used by any real app (Streamlit, CLI, TUI, distribution).

### Contents

| Component | Purpose |
|-----------|---------|
| paths | `get_app_root()` and similar; uses platformdirs for user data dir |
| logging | `configure_logging()`, `log_application_action()` |
| config | Streamlit headless, env overrides (e.g. `*_DB_PATH`) |
| docs | `read_markdown_from_app_root()`, `get_readme_intro()` for About/docs page |

### Dependencies

- core-dev
- platformdirs
- loguru

### Separation from Interface

Bootstrap should not depend on Streamlit. It provides generic helpers; Streamlit (or CLI/TUI) consumes them.

---

## 4. Interface Modules

### 4a. Streamlit Simple (`streamlit-simple`)

**Pure Streamlit app, no model–data–service layering.**

- Single `app.py` or thin `src/<pkg>/interfaces/streamlit/` with pages.
- No services layer; pages may call data/model directly (or no DB at all).
- Main page + docs page (About).
- Minimal app testing: `test_app_loads`, `test_pages_importable`.

### Contents

```
streamlit-simple/
├── app.py
├── src/<pkg>/interfaces/streamlit/
│   ├── ui.py           # setup, page wiring
│   └── pages/
│       ├── main.py
│       └── docs.py
└── tests/
    └── test_app_simple.py
```

### Dependencies

- core-dev, bootstrap, streamlit

---

### 4b. Streamlit Architecture (`streamlit-arch`)

**Well-structured model–data–service–page layout.**

- Model: ORM, page models, DTOs.
- Data: persistence, queries.
- Service: orchestration; pages never import `handoff.data`.
- Pages: main (e.g. Now), docs (About), settings.

### Contents

```
streamlit-arch/
├── src/<pkg>/
│   ├── core/            # models, page_models, schemas
│   ├── data/            # persistence, queries
│   ├── services/        # handoff_service, project_service, etc.
│   ├── db.py
│   ├── migrations/
│   └── interfaces/streamlit/
│       ├── ui.py
│       └── pages/
│           ├── main.py
│           ├── docs.py
│           └── settings.py
└── tests/
    ├── test_services_architecture.py
    ├── test_db.py
    └── test_data.py
```

### Guardrails

- `test_pages_do_not_import_data_layer_directly`
- `test_src_does_not_import_deprecated_*`

### Dependencies

- core-dev, bootstrap, streamlit, sqlmodel

---

### 4c. CLI Module (`cli`)

**Typer-based CLI interface.**

- Commands: run (if Streamlit), or domain-specific commands.
- Can coexist with Streamlit; `handoff run` vs `handoff <domain-cmd>`.

### Contents

```
cli/
├── src/<pkg>/interfaces/cli/
│   ├── __init__.py
│   └── commands.py
└── tests/
    └── test_cli.py
```

### Dependencies

- core-dev, bootstrap, typer, rich

---

### 4d. TUI Module (`tui`)

**Textual-based TUI (future).**

- Parallel to Streamlit/CLI.
- Reuses services/data if `streamlit-arch` is present; otherwise standalone.

### Contents

```
tui/
├── src/<pkg>/interfaces/tui/
│   ├── __init__.py
│   └── app.py
└── tests/
    └── test_tui.py
```

### Dependencies

- core-dev, bootstrap, textual

---

## 5. Distribution Module (`distribution`)

**Embedded Python, in-app updater, optional obfuscation.**

This is the "unique Handoff-style" distribution: ship with embedded Python, lightweight updater, optional PyArmor. It is somewhat coupled to the interface (e.g. Streamlit for update UI), but we can separate:

1. **Build scripts** (platform-agnostic): `build_full.py`, `build_patch.py`, sizecheck.
2. **Updater logic**: `updater.py` — patch zip validation, extract, backup, restore.
3. **Update UI**: Lives in `interfaces/streamlit/update_ui.py` — only included when both distribution and streamlit are present.

### Separation of Concerns

| Component | Location | Depends on |
|-----------|----------|------------|
| build_full.py | distribution | core-dev |
| build_patch.py | distribution | core-dev |
| updater.py | distribution | bootstrap |
| update_ui.py | streamlit (optional) | distribution, streamlit |
| platformdirs | bootstrap | — |

### Contents

```
distribution/
├── scripts/
│   ├── build_full.py
│   ├── build_patch.py
│   └── sizecheck.py
├── src/<pkg>/
│   └── updater.py
└── tests/
    ├── test_updater.py
    ├── test_build_dry_run.py
    └── test_updater_coverage.py
```

### Optional: Update UI in Streamlit

When both `distribution` and `streamlit-arch` (or `streamlit-simple`) are enabled, add:

- `interfaces/streamlit/update_ui.py`
- `interfaces/streamlit/pages/system_settings.py` (or a minimal settings page with update panel)

---

## 6. Page Separation (Main vs Docs vs Settings)

Within Streamlit modules, pages can be grouped:

| Group | Pages | Purpose |
|-------|-------|---------|
| Main | Now, Dashboard, etc. | Core app functionality |
| Docs | About | README, release notes, markdown |
| Settings | Projects, System Settings | Config, update panel |

For the template:

- **streamlit-simple**: main page + docs page.
- **streamlit-arch**: main page + docs page + settings page (with optional update panel when distribution is present).

---

## 7. Dependency Graph

```
                    core-dev
                        │
          ┌─────────────┼─────────────┐
          │             │             │
      bootstrap    (standalone)   (standalone)
          │             │             │
    ┌─────┴─────┬───────┼─────────────┼───────────┐
    │           │       │             │           │
streamlit-  streamlit-  cli          tui    distribution
  simple      arch
    │           │                         │
    └─────┬─────┘                         │
          │                               │
          └────────── optional: update_ui when both
```

---

## 8. Template Variants

Consumers could choose:

| Variant | Modules | Use case |
|---------|---------|----------|
| **Skeleton only** | core-dev | New project, no app yet |
| **Simple Streamlit** | core-dev, bootstrap, streamlit-simple | Quick prototype, no DB |
| **Structured Streamlit** | core-dev, bootstrap, streamlit-arch | Full app with DB, services |
| **CLI app** | core-dev, bootstrap, cli | Terminal-only tool |
| **Full Handoff-style** | core-dev, bootstrap, streamlit-arch, distribution | Shipped product with updater |

---

## 9. Additional Modules (Suggestions)

| Module | Purpose |
|--------|---------|
| **db-minimal** | SQLite + SQLModel init, migrations runner; used by streamlit-arch |
| **github-actions** | CI workflows (check, typecheck, test, build dry-run); optional add-on |
| **copilot-instructions** | `.github/copilot-instructions.md`, agent files; for AI-assisted development |
| **issue-templates** | Bug, feature, config, chore issue templates |
| **pre-commit** | Optional pre-commit hooks for Ruff, pyright |

---

## 10. Decoupling Distribution from Streamlit

The updater logic (`updater.py`) does not depend on Streamlit. It:

- Reads patch zips
- Validates paths (no traversal)
- Extracts to staging
- Backs up and swaps

The **update UI** (panel in System Settings) is Streamlit-specific. Options:

1. **Optional page**: Only add `update_ui.py` and wire it when both `distribution` and `streamlit` are selected.
2. **CLI fallback**: `handoff update --patch /path/to/patch.zip` for headless updates.
3. **Separate entrypoint**: A tiny script that runs the update without starting the full app.

---

## 11. Implementation Order (Suggested)

1. **Phase 1: Extract core-dev**
   - Create minimal `core-dev` with AGENTS.md (style only), pyproject.toml, scripts/cli (check, typecheck, test, ci, bump), version.py, guardrail tests.
   - Strip app-specific content from AGENTS.md.

2. **Phase 2: Extract bootstrap**
   - Move paths, logging, config, docs into a bootstrap package.
   - Ensure zero Streamlit dependency.

3. **Phase 3: Streamlit variants**
   - Define `streamlit-simple` (main + docs, no services).
   - Define `streamlit-arch` (main + docs + settings, model–data–service–page).

4. **Phase 4: Distribution**
   - Extract build scripts, updater, sizecheck into distribution module.
   - Make update UI conditional on streamlit + distribution.

5. **Phase 5: CLI and TUI stubs**
   - Add CLI module with Typer skeleton.
   - Add TUI stub (Textual) for future expansion.

---

## 12. File Layout for Modular Template

```
template/
├── core-dev/                 # Always present
│   ├── AGENTS.md
│   ├── pyproject.toml
│   ├── scripts/
│   ├── src/<pkg>/version.py
│   └── tests/
├── modules/
│   ├── bootstrap/
│   ├── streamlit-simple/
│   ├── streamlit-arch/
│   ├── distribution/
│   ├── cli/
│   └── tui/
├── compose.py or Makefile    # Compose chosen modules into final project
└── README.md                 # How to use the template
```

**Composition options:**

- **Cookiecutter / Copier**: Prompts for which modules to include; generates merged project.
- **Symlinks / includes**: Template repo has module dirs; tool copies selected ones into project root.
- **Monorepo with feature flags**: Single repo, `pyproject.toml` and tests conditionally include modules based on config.

---

## 13. Open Questions

1. **Package naming**: Should the template use a generic name (e.g. `app`, `project`) or keep `handoff` as the example and let consumers rename?
2. **Composition mechanism**: Cookie cutter, copier, or manual copy?
3. **Sizecheck and PyArmor**: Keep 32KB limit only when distribution+obfuscation is selected?
4. **AGENTS.md customization**: Should the template ship a parameterized AGENTS.md (e.g. `{{ project_name }}`) that gets filled during project creation?

---

## 14. Summary Table

| Module | Key files | Key tests |
|--------|-----------|-----------|
| core-dev | AGENTS.md, pyproject.toml, scripts/cli.py, version.py | test_version_sync, test_app_import_paths |
| bootstrap | paths, logging, config, docs | (minimal) |
| streamlit-simple | app.py, ui.py, pages/main, pages/docs | test_app_simple |
| streamlit-arch | core/, data/, services/, db, ui, pages | test_services_architecture, test_db, test_data |
| distribution | build_full, build_patch, updater, sizecheck | test_updater, test_build_dry_run |
| cli | interfaces/cli | test_cli |
| tui | interfaces/tui | test_tui |

---

## Appendix A: Handoff → Template Module Mapping

Mapping current Handoff files to proposed modules for extraction:

| Current location | Target module |
|------------------|---------------|
| AGENTS.md (style + quick ref only) | core-dev |
| pyproject.toml (tool config) | core-dev |
| scripts/cli.py (check, typecheck, test, ci, bump) | core-dev |
| scripts/subprocess_utils.py | core-dev |
| src/handoff/version.py | core-dev |
| tests/test_version_sync.py | core-dev |
| tests/test_app_import_paths.py | core-dev (generalized) |
| tests/test_services_architecture.py | streamlit-arch |
| src/handoff/bootstrap/* | bootstrap |
| platformdirs (dep) | bootstrap |
| loguru (dep) | bootstrap / core-dev |
| src/handoff/updater.py | distribution |
| scripts/build_full.py, build_patch.py | distribution |
| scripts/sizecheck.py | distribution |
| src/handoff/interfaces/streamlit/* | streamlit-arch or streamlit-simple |
| src/handoff/interfaces/cli/* | cli |
| app.py | streamlit-* (entrypoint) |

---

## Appendix B: Minimal core-dev AGENTS.md Outline

For the template, the core-dev AGENTS.md would contain only:

1. **Code style** — Aesthetic, Hygienic, Robust, Practical (unchanged principles)
2. **Quick reference** — uv sync, check, typecheck, test, ci, bump
3. **Guardrails** — What the auto-tests enforce (import paths, architecture, version sync)
4. **Tool authority** — Ruff, Pyright, pytest
5. **Non-obvious caveats** — uv on PATH, Python 3.13+, etc.

Application-specific sections (Handoff workflow, pages, deployment philosophy) move to the streamlit-arch or application docs.
