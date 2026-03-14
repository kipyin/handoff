# CLI Full Implementation Plan

Plan for replacing the `handoff cli` stub with a complete CLI that replicates Streamlit functionality. Uses **questionary** for interactive prompts and **rich** for pretty output.

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
| Questionary| Interactive prompts (select, text)| ❌ Add to main (optional dep?) |

**Dependency strategy:** Add `questionary` and `rich` as main dependencies. `rich` is already used by CLI; `questionary` enables interactive flows. Both are lightweight and widely used.

---

## 2. Architecture

### Module layout
```
scripts/
├── cli.py                    # Main Typer app; delegates to cli/ modules
└── cli/
    ├── __init__.py
    ├── db_context.py         # HANDOFF_DB_PATH resolution, --db-path support
    ├── handoff_commands.py   # handoff add/list/show/update/delete/conclude/reopen/check-in
    ├── project_commands.py   # project add/list/archive/unarchive/rename/delete
    ├── trail_commands.py     # trail show (check-in history)
    ├── backup_commands.py    # export, import
    ├── update_commands.py   # apply-patch, restore
    ├── rulebook_commands.py  # rulebook show/reset (minimal)
    ├── dashboard_commands.py# dashboard (summary metrics)
    └── output.py             # Rich tables/panels/formatting helpers
```

### Invocation model
- **Entry:** `handoff cli` → interactive menu (questionary) or `handoff cli <subcommand>` for direct usage
- **Alternative:** `handoff handoff add`, `handoff project list`, etc. as top-level groups (Typer add_typer)

Recommendation: Use **Typer groups** so users can run `handoff handoff add`, `handoff project list`, etc. The existing `handoff cli` stub becomes the interactive entry that uses questionary to choose a subcommand.

---

## 3. Feature Breakdown

### 3.1 Handoff CRUD
| Action      | Streamlit source         | CLI command(s)              | Service calls                    |
|-------------|---------------------------|-----------------------------|----------------------------------|
| Create      | Now page add form         | `handoff handoff add`       | `create_handoff`                 |
| List        | Now page sections         | `handoff handoff list`      | `get_now_snapshot` or `query_handoffs` |
| Show one    | Now item expand           | `handoff handoff show ID`   | `query_handoffs` + filter by id  |
| Update      | Now item edit             | `handoff handoff update ID` | `update_handoff`                 |
| Delete      | Now item delete           | `handoff handoff delete ID` | `delete_handoff`                 |
| Conclude    | Check-in form             | `handoff handoff conclude ID`| `conclude_handoff`               |
| Reopen      | Reopen form               | `handoff handoff reopen ID` | `reopen_handoff`                 |
| Add check-in| Check-in form             | `handoff handoff check-in ID`| `add_check_in`                   |
| Snooze      | Snooze control            | `handoff handoff snooze ID` | `snooze_handoff`                 |

**Data gap:** No `get_handoff(handoff_id)` in services. Options:
1. Add `get_handoff(handoff_id)` to data layer and expose via handoff_service
2. Use `query_handoffs` with a filter (would need handoff_id filter in query)

Recommendation: Add `get_handoff(handoff_id)` to `handoff.data` and `handoff_service` for single-item operations (show, update, delete, etc.).

**Interactive flow (handoff add):** questionary prompts for project (select from list), need_back, pitchman, next_check, deadline, notes. Non-interactive: `--project`, `--need-back`, etc.

---

### 3.2 Project CRUD
| Action   | Streamlit source | CLI command(s)           | Service calls     |
|----------|------------------|--------------------------|-------------------|
| Create   | Projects form    | `handoff project add`    | `create_project`  |
| List     | Projects table   | `handoff project list`   | `get_projects_with_handoff_summary` |
| Rename   | Projects edit    | `handoff project rename ID`| `rename_project` |
| Archive  | Projects edit    | `handoff project archive ID`| `archive_project` |
| Unarchive| Projects edit    | `handoff project unarchive ID`| `unarchive_project` |
| Delete   | Projects edit    | `handoff project delete ID`| `delete_project` |

**Interactive flow (project add):** questionary text prompt for name. List shows project name, archived, open count, concluded count (Rich table).

---

### 3.3 Check-in trails
| Action | Streamlit source     | CLI command(s)       | Service calls      |
|--------|----------------------|----------------------|--------------------|
| View   | Now item expand      | `handoff trail show HANDOFF_ID`| `get_handoff` + check_ins |

**Output:** Rich table with columns: date, type, note. Or Rich tree/panel showing handoff header + trail.

**Data:** Handoff model has `check_ins` relationship. `get_handoff` must load it (selectinload).

---

### 3.4 App update / restore
| Action     | Streamlit source   | CLI command(s)              | Implementation                |
|------------|-------------------|-----------------------------|-------------------------------|
| Apply patch| Update panel      | `handoff update apply FILE` | `stage_patch_with_backup`     |
| List backups| Restore dropdown | `handoff update list-backups`| `_iter_backup_snapshots`     |
| Restore    | Restore dropdown  | `handoff update restore LABEL`| `stage_restore_from_snapshot`|

**Notes:**
- Updater lives in `handoff.updater`; must be invoked with file path (CLI: `--file` or positional)
- Restore needs to list available snapshots; `_iter_backup_snapshots` returns (label, path) or similar
- After apply/restore, app will exit (or instruct user to restart)

**Interactive flow:** `handoff update apply` → questionary.filepath to pick zip; confirm. `handoff update restore` → questionary.select from snapshot labels.

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
- Add `cli/db_context.py`: `get_cli_db_path() -> Path` that respects `--db-path` and falls back to `get_db_path()`.

### 4.2 Output helpers (`cli/output.py`)
- `print_handoff_table(handoffs)` — Rich Table
- `print_project_table(projects)` — Rich Table with open/concluded
- `print_trail(handoff)` — Rich table or tree for check-ins
- `print_success(msg)`, `print_error(msg)` — Rich console
- `print_now_snapshot(snapshot)` — Sections (Risk, Action, Upcoming, Concluded) as Rich panels

### 4.3 Interactive mode
- `handoff cli` with no subcommand → questionary.select to pick: Handoffs, Projects, Trail, Backup, Update, Rulebook, Dashboard, Exit
- Each choice leads to submenu or direct prompt (e.g. "Handoffs" → Add / List / Show / …).

---

## 5. Implementation Phases

### Phase 1: Foundation
1. Add `questionary` and move `rich` to main deps in pyproject.toml
2. Create `scripts/cli/` package
3. Add `output.py` with basic Rich helpers
4. Add `db_context.py` and `--db-path` support to CLI
5. Add `get_handoff(handoff_id)` to data + handoff_service

### Phase 2: Core CRUD
6. `handoff_commands.py`: add, list, show, update, delete, conclude, reopen, check-in, snooze
7. `project_commands.py`: add, list, rename, archive, unarchive, delete
8. `trail_commands.py`: show

### Phase 3: Backup and update
9. `backup_commands.py`: export (json/csv), import
10. `update_commands.py`: apply, list-backups, restore

### Phase 4: Second-class features
11. `rulebook_commands.py`: show, reset
12. `dashboard_commands.py`: summary

### Phase 5: Interactive menu
13. Wire `handoff cli` to questionary main menu
14. Ensure all subcommands work both as `handoff <group> <cmd>` and from menu

---

## 6. CLI surface (final)

```
handoff
├── run
├── cli                          # Interactive menu (or handoff <group> <cmd>)
│   ├── [interactive menu]
│   └── (delegates to groups)
├── handoff
│   ├── add
│   ├── list
│   ├── show ID
│   ├── update ID
│   ├── delete ID
│   ├── conclude ID
│   ├── reopen ID
│   ├── check-in ID
│   └── snooze ID
├── project
│   ├── add
│   ├── list
│   ├── rename ID
│   ├── archive ID
│   ├── unarchive ID
│   └── delete ID
├── trail
│   └── show HANDOFF_ID
├── backup
│   ├── export [--format json|csv] [--output FILE]
│   └── import FILE [--confirm]
├── update
│   ├── apply FILE
│   ├── list-backups
│   └── restore LABEL
├── rulebook
│   ├── show
│   └── reset
├── dashboard
│   └── (default: summary)
└── (existing: check, typecheck, test, ci, build, bump, seed-demo, db-path, …)
```

---

## 7. Clarification Questions for Product Owner

1. **Interactive vs non-interactive default:** Should `handoff cli` with no args always show the interactive menu, or should `handoff cli` require a subcommand and offer `handoff cli --interactive` / `handoff cli -i` for the menu?

2. **Now-page view:** For `handoff handoff list`, should we replicate the full Now snapshot (Risk | Action | Upcoming | Concluded) or a simpler flat list of open handoffs? The full snapshot requires rulebook evaluation and is richer but heavier.

3. **questionary optional:** Should questionary be an optional dependency so users who only want non-interactive CLI can run without it? (Would require try/import and graceful fallback when questionary is missing.)

4. **Dashboard detail level:** For the CLI dashboard, is a single summary (e.g. 4–6 key numbers) sufficient, or do you want per-project/per-pitchman breakdowns available as subcommands?

5. **Rulebook export/import:** Do you want `rulebook show` to support `--output FILE` for exporting the current rulebook to JSON (for backup or inspection), even though edits stay in Streamlit?
