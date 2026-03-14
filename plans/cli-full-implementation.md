# CLI Full Implementation Plan

Plan for a complete CLI that replicates Streamlit functionality. Uses **questionary** (required) for interactive prompts and **rich** for pretty output. Assumes PyPI distribution; `handoff --web` launches Streamlit.

---

## 1. Overview

### Goals
- Provide a fully functional CLI that mirrors Streamlit workflows
- Use **services** layer only (no direct `handoff.data` imports from CLI)
- Support both interactive (questionary) and non-interactive (flags/args) usage where practical
- Keep rulebook and dashboard as second-class: minimal surface, deferred refinement

### Dependencies
| Package   | Purpose                          | Status                          |
|-----------|----------------------------------|---------------------------------|
| Typer     | CLI scaffolding, subcommands      | ✅ Already used                 |
| Rich      | Tables, panels, markup, progress  | ✅ In dev deps; move to main    |
| Questionary| Interactive prompts (select, text)| ❌ Add to main (required) |

**Dependency strategy:** Add `questionary` and `rich` as main dependencies. **Questionary is required** — the CLI is designed around interactive flows. Rich for pretty output.

---

## 2. Architecture

### Current structure (as of plan update)

**Entrypoint:** `pyproject.toml` defines `handoff = "scripts.cli:main"`. The main Typer app lives in `scripts/cli.py`.

**Existing stubs (to replace):**
1. `scripts/cli.py` — `cli_command()` registered as `handoff cli`; prints "not implemented" and exits 1
2. `src/handoff/interfaces/cli/__init__.py` — `run_cli()` raises NotImplementedError.
3. New default: `handoff` (no args) → `run_cli()` main menu; `handoff --web` → Streamlit.

**Interface pattern:** `src/handoff/interfaces/` holds user-facing UIs: `streamlit/` (pages, ui, runtime_config) and `cli/` (stub today). CLI implementation should live under `interfaces/cli/` to mirror Streamlit.

### Module layout (revised)
```
scripts/
└── cli.py                    # Main Typer app; registers dev/build commands + mounts handoff CLI app

src/handoff/interfaces/cli/
├── __init__.py               # Exports run_cli, get_cli_app (or sub-apps)
├── app.py                    # Typer app for domain commands; mounted by scripts.cli
├── db_context.py             # HANDOFF_DB_PATH resolution, --db-path support
├── output.py                 # Rich tables/panels/formatting helpers
├── handoff_cmds.py           # add, list, show, edit, delete, on-track, delayed, conclude, reopen, check-in, snooze, trail
├── project_cmds.py           # project add/list/rename/archive/unarchive/delete; project menu
├── backup_cmds.py            # export, import
├── update_cmds.py            # apply, list-backups, restore
├── rulebook_cmds.py          # rulebook show/reset (minimal)
└── dashboard_cmds.py         # dashboard summary
```

### Wiring
- `scripts/cli.py` defines the main Typer app; domain commands (add, list, on-track, …) live in handoff.interfaces.cli. The default (no args) invokes `run_cli()` for the interactive menu.
- `run_cli()` runs the main menu; direct commands (`handoff add`, `handoff list`, etc.) are top-level.
- Dev/build commands (check, typecheck, test, ci, build, bump, seed-demo, db-path, …) stay in scripts.cli.py; domain commands live in handoff.interfaces.cli.

### Invocation model
- **Handoff first-class:** `handoff add`, `handoff list`, `handoff on-track ID`, `handoff delayed ID`, `handoff conclude ID`, `handoff reopen ID` — no `handoff handoff` prefix
- **Project:** `handoff project add` (explicit), `handoff project` (no args) → interactive menu
- **Check-in:** `handoff check-in ID` → interactive menu (type, note, next_check)
- **handoff list** shows full Now snapshot (Risk | Action | Upcoming | Concluded)
- **handoff** (no args) → main interactive menu

### PyPI distribution and Streamlit
- **Publish to PyPI:** handoff becomes installable via `pip install handoff`
- **handoff --web:** Launches the Streamlit UI (replaces/additional to `handoff run` for pip users)
- **Self-update:** Replace patch-zip updater with PyPI self-update: `handoff update` (or `handoff self-update`) runs `pip install --upgrade handoff` and reports new version

---

## 3. Feature Breakdown

### 3.1 Handoff (first-class commands)
| Action      | CLI command(s)              | Service calls                    |
|-------------|-----------------------------|----------------------------------|
| Create      | `handoff add`               | `create_handoff`                 |
| List (full snapshot) | `handoff list`     | `get_now_snapshot`               |
| Add on-track check-in | `handoff on-track ID`  | `add_check_in(..., on_track)`     |
| Add delayed check-in  | `handoff delayed ID`   | `add_check_in(..., delayed)`      |
| Conclude    | `handoff conclude ID`       | `conclude_handoff`               |
| Reopen      | `handoff reopen ID`         | `reopen_handoff`                 |
| Add check-in (interactive) | `handoff check-in ID` | Interactive menu → `add_check_in` |
| Edit        | `handoff edit ID`          | `update_handoff`                 |
| Delete      | `handoff delete ID`         | `delete_handoff`                 |
| Snooze      | `handoff snooze ID`         | `snooze_handoff`                 |
| Show one    | `handoff show ID`           | `get_handoff`                    |

**Naming:** Use verb forms: `conclude` (not concluded), `delayed` (state/type: "handoff delayed 5" = add delayed check-in). Both `delayed` and `delay` are plausible; `delayed` matches the CheckInType enum; `delay` reads as verb. Plan uses `delayed`; can revisit.

**Data gap:** No `get_handoff(handoff_id)` in services. Options:
1. Add `get_handoff(handoff_id)` to data layer and expose via handoff_service
2. Use `query_handoffs` with a filter (would need handoff_id filter in query)

Recommendation: Add `get_handoff(handoff_id)` to `handoff.data` and `handoff_service` for single-item operations (show, update, delete, etc.).

**Interactive flow (handoff add):** questionary prompts for project (select from list), need_back, pitchman, next_check, deadline, notes.

---

### 3.2 Project
| Action   | CLI command(s)           | Service calls     |
|----------|--------------------------|-------------------|
| Add      | `handoff project add`    | `create_project`  |
| Interactive menu | `handoff project` (no args) | questionary.select → add/list/rename/archive/… |
| List     | (from menu or) `handoff project list` | `get_projects_with_handoff_summary` |
| Rename   | `handoff project rename ID`| `rename_project` |
| Archive  | `handoff project archive ID`| `archive_project` |
| Unarchive| `handoff project unarchive ID`| `unarchive_project` |
| Delete   | `handoff project delete ID`| `delete_project` |

**handoff project** with no subcommand → interactive menu to pick action (add, list, rename, archive, etc.).

---

### 3.3 Check-in
| Action | CLI command(s)       | Service calls      |
|--------|----------------------|--------------------|
| Add (interactive) | `handoff check-in ID` | questionary menu → `add_check_in` |
| View trail | `handoff show ID` (includes trail) or `handoff trail ID` | `get_handoff` + check_ins |

**handoff check-in ID** → interactive menu: select type (on_track / delayed / concluded), note, next_check date (if not concluded). Designed with questionary in mind.

---

### 3.4 App update (PyPI self-update)
| Action     | CLI command(s)     | Implementation                |
|------------|-------------------|-------------------------------|
| Self-update| `handoff update`  | `pip install --upgrade handoff` (or equivalent for uv) |
| Restore (embedded builds) | `handoff update restore LABEL` | `stage_restore_from_snapshot` (for non-PyPI installs) |

**PyPI path:** When published to PyPI, `handoff update` runs self-update via pip/uv. Check PyPI for latest version, upgrade, report success.

**Embedded/patch path:** For Windows zip or macOS tar.gz (non-PyPI) installs, keep patch-zip flow and `handoff update restore` for code-backup rollback. PyPI and embedded are separate distribution channels.

---

### 3.5 Data import / export
| Action | Streamlit source    | CLI command(s)          | Service calls      |
|--------|--------------------|-------------------------|--------------------|
| Export JSON | Data export    | `handoff backup export --format json [--output FILE]`| `get_export_payload` |
| Export CSV  | Data export    | `handoff backup export --format csv [--output FILE]`| `get_export_payload` + pandas |
| Import      | Data import    | `handoff backup import FILE`| `BackupPayload.from_dict` + `import_payload`|

**Output:** Default to stdout for export; `--output FILE` writes to file. Import reads from file path.
**Safety:** Import should require `--confirm` or interactive confirmation (questionary.confirm) before overwrite.

---

### 3.6 Rulebook (second-class)
| Action | Streamlit source | CLI command(s)      | Service calls           |
|--------|-----------------|---------------------|--------------------------|
| Show   | Rulebook section| `handoff rulebook show`| `get_rulebook_settings` |
| Reset  | Reset button    | `handoff rulebook reset`| `reset_rulebook_settings`|

**Scope:** Read-only show (rules, priorities, conditions) and reset to defaults. No add/edit custom sections via CLI in v1; those stay in Streamlit.

---

### 3.7 Dashboard (second-class)
| Action | Streamlit source | CLI command(s)       | Service calls         |
|--------|-----------------|----------------------|-----------------------|
| Summary| Dashboard page  | `handoff dashboard`  | `get_dashboard_metrics`|

**Output:** Rich panel/cards with key metrics (open count, throughput, reopen rate, cycle time, etc.). No charts; text/summary only.

---

## 4. Shared infrastructure

### 4.1 DB context
- All data commands need DB path. Use `HANDOFF_DB_PATH` env or `--db-path` global option.
- Add `handoff.interfaces.cli.db_context`: `get_cli_db_path() -> Path` that respects `--db-path` and falls back to `get_db_path()`.

### 4.2 Output helpers (`handoff.interfaces.cli.output`)
- `print_handoff_table(handoffs)` — Rich Table
- `print_project_table(projects)` — Rich Table with open/concluded
- `print_trail(handoff)` — Rich table or tree for check-ins
- `print_success(msg)`, `print_error(msg)` — Rich console
- `print_now_snapshot(snapshot)` — Sections (Risk, Action, Upcoming, Concluded) as Rich panels

### 4.3 Interactive menus (questionary)

All interactive flows use questionary. Design with questionary in mind from the start.

**Main menu (`handoff` with no args):**
```
? What would you like to do?
  ❯ Handoffs (add, list, show, …)
    Projects
    Check-in (add to handoff)
    Backup (export/import)
    Update (self-update)
    Rulebook
    Dashboard
    Exit
```

**Project menu (`handoff project` with no args):**
```
? Project action
  ❯ Add project
    List projects
    Rename
    Archive / Unarchive
    Delete
    Back
```

**Check-in menu (`handoff check-in ID`):**
```
? Add check-in for handoff #5: "API design review"
  ❯ On track
    Delayed
    Concluded
  Note: [________________]
  Next check date (if on-track/delayed): [date picker / today+7]
```

---

## 5. Implementation Phases

### Phase 1: Foundation
1. Add `questionary` and move `rich` to main deps in pyproject.toml
2. Create `handoff.interfaces.cli` modules: `app.py`, `output.py`, `db_context.py`
3. Add `get_handoff(handoff_id)` to data layer and handoff_service
4. Wire default (no args) to call `run_cli()`; add `--web` for Streamlit
5. Update `run_cli()` in `handoff.interfaces.cli` to run main interactive menu
6. Update `tests/test_cli_interface.py` and `tests/test_cli.py` for new behaviour

### Phase 2: Core CRUD
7. `handoff_cmds.py`: add, list, show, edit, delete, on-track, delayed, conclude, reopen, check-in, snooze, trail
8. `project_cmds.py`: add, list, rename, archive, unarchive, delete; `handoff project` → project menu

### Phase 3: Backup and update
10. `backup_cmds.py`: export (json/csv), import
11. `update_cmds.py`: self-update (PyPI); restore (embedded builds)

### Phase 4: Second-class features
12. `rulebook_cmds.py`: show, reset
13. `dashboard_cmds.py`: summary

### Phase 5: Interactive menus
14. Implement full questionary menus: main (`handoff`), project (`handoff project`), check-in (`handoff check-in ID`)
15. Ensure all actions work both via direct command and from their respective menus

---

## 6. CLI surface (final)

```
handoff                          # No args → main interactive menu
├── --web                        # Launch Streamlit (PyPI installs)
├── add                          # Handoff first-class
├── list                         # Full Now snapshot (Risk|Action|Upcoming|Concluded)
├── show ID
├── edit ID
├── delete ID
├── on-track ID
├── delayed ID
├── conclude ID
├── reopen ID
├── check-in ID                  # Interactive menu
├── snooze ID
├── project                      # No args → project menu
│   ├── add
│   ├── list
│   ├── rename ID
│   ├── archive ID
│   ├── unarchive ID
│   └── delete ID
├── trail ID                     # View check-in history
├── backup
│   ├── export [--format json|csv] [--output FILE]
│   └── import FILE [--confirm]
├── update                       # PyPI self-update (or restore for embedded)
│   └── restore LABEL            # Embedded builds only
├── rulebook
│   ├── show
│   └── reset
├── dashboard
└── (dev: check, typecheck, test, ci, build, bump, seed-demo, db-path, run)
```

---

## 7. Test Impact

**tests/test_cli_interface.py** — currently expects `run_cli()` to raise NotImplementedError. When implemented:
- `run_cli()` will run the interactive menu (or exit cleanly if non-interactive)
- Tests should change to assert menu is shown or subcommand delegation works; remove NotImplementedError expectation

**tests/test_cli.py** — `test_cli_command_stub_*` tests: remove or rewrite for new behaviour (default = main menu; no separate `handoff cli` command).

---

## 8. Open questions

1. **delayed vs delay:** Use `handoff delayed ID` (state) or `handoff delay ID` (verb)? Plan uses `delayed` to match CheckInType; can switch to `delay` if preferred.

2. **Dashboard detail:** Single summary vs per-project/per-pitchman breakdowns as subcommands?

3. **Rulebook export:** Add `rulebook show --output FILE` for JSON backup?
