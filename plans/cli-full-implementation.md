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
├── handoff_cmds.py           # add, list, show, edit, delete, on-track, delayed, conclude, reopen, check-in, trail
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
- **Self-update:** `handoff update` runs `pip install --upgrade handoff` (PyPI path)

---

## 2a. Deployment: Template Decision Matrix

Shipment method is driven by two factors: **open source vs proprietary** and **technical vs non-technical audience**. These choices are mutually exclusive in practice — trying to support both paths dilutes focus.

### Core conflicts

| Conflict | Why |
|----------|-----|
| **Standalone ⇄ CLI** | Standalone targets non-technical users who won't use a terminal. CLI targets technical users who have Python. Pick one primary interface. |
| **Open source ⇄ PyArmor** | If code is open source, obfuscation is pointless (source is visible). PyArmor only makes sense for proprietary builds. |
| **Proprietary ⇄ Public PyPI** | Proprietary usually means "not on public PyPI." Use private index or direct download instead. |

### Decision matrix

| | **Technical** (devs, power users) | **Non-technical** (end users, point-and-click) |
|---|-----------------------------------|------------------------------------------------|
| **Open source** | **PyPI.** `pip install handoff`. CLI + Streamlit. No obfuscation. Self-update via `pip install --upgrade`. | **Standalone (non-obfuscated).** Zip/tar.gz with embedded Python. Streamlit UI only. No CLI. No obfuscation. |
| **Proprietary** | **Private PyPI** or **obfuscated wheel from your URL.** CLI + Streamlit. Obfuscate to protect IP. Or ship **obfuscated standalone** if you prefer no Python dependency. | **Obfuscated standalone.** Zip with PyArmor. Streamlit UI only. No CLI. |

### Refinements

**Proprietary + technical:**
- **Can you put obfuscated code on PyPI?** Yes — PyPI doesn't care. You can upload an obfuscated wheel. But "proprietary" usually implies *not* on *public* PyPI. Options:
  1. **Private PyPI** (Artifactory, Nexus, AWS CodeArtifact) — obfuscated or not
  2. **Direct download** — `pip install handoff` from your URL (obfuscated wheel)
  3. **Obfuscated standalone** — no Python on client; CLI still works if you bundle it
- If you want to hide source from customers: obfuscate. If it's internal-only and IP isn't a concern: skip obfuscation.

**Open source + non-technical:**
- Standalone without obfuscation. Users get a zip, extract, run. No CLI — they use the UI. Build script produces clean (readable) bundled app.

**Proprietary + non-technical:**
- Obfuscated standalone. PyArmor protects the code. UI-only. This is the "shrink-wrap" desktop app model.

### Template implication

For a **template** (e.g. Handoff as modular starter): document this matrix and let the consumer **choose one cell**. The template provides:
- Core app + services + data
- Streamlit UI (always)
- CLI (only when technical audience)
- Build scripts for PyPI **or** standalone (not both as primary)
- Obfuscation step (only when proprietary)

Don't try to be all four. Pick the cell that matches your product, then build for that path.

**This plan assumes:** Open source + technical → PyPI, CLI, Streamlit. If Handoff (or a fork) targets a different cell, adjust: drop CLI for non-technical, add obfuscation for proprietary.

---

## 3. Feature Breakdown

### 3.1 Handoff (first-class commands)
| Action      | CLI command(s)              | Service calls                    |
|-------------|-----------------------------|----------------------------------|
| Create      | `handoff add`               | `create_handoff`                 |
| List (full snapshot) | `handoff list`     | `get_now_snapshot`               |
| List Risk only       | `handoff list risk`| `query_risk_handoffs`            |
| List Concluded only  | `handoff list concluded`| `query_concluded_handoffs`   |
| List Action/Upcoming | `handoff list action`, `handoff list upcoming` | (optional) |
| Add on-track check-in | `handoff on-track ID`  | `add_check_in(..., on_track)`     |
| Add delayed check-in  | `handoff delayed ID`   | `add_check_in(..., delayed)`      |
| Conclude    | `handoff conclude ID`       | `conclude_handoff`               |
| Reopen      | `handoff reopen ID`         | `reopen_handoff`                 |
| Add check-in (interactive) | `handoff check-in ID` | Interactive menu → `add_check_in` |
| Edit        | `handoff edit ID`          | `update_handoff`                 |
| Delete      | `handoff delete ID`         | `delete_handoff`                 |
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

### 3.4 App update
| Action     | CLI command(s)     | Implementation                |
|------------|-------------------|-------------------------------|
| Self-update (PyPI) | `handoff update`  | `pip install --upgrade handoff` |
| Restore (standalone only) | `handoff update restore LABEL` | `stage_restore_from_snapshot` |

See **§2a Deployment** for when each path applies.

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
- `print_now_snapshot(snapshot)` — Section counts header; Risk, Action, Upcoming tables; Concluded count only (no table). Use `print_concluded_table` for `handoff list concluded`.

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

### 4.4 `handoff list` mock (Rich output)

Full Now snapshot. All sections show a count. Concluded is hidden in the default view (count only). Use `handoff list risk`, `handoff list concluded` for filtered views.

```
  Risk: 2    Action: 2    Upcoming: 2    Concluded: 2
─────────────────────────────────────────────────────

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Risk (2) — deadline near + delayed                                   ┃
┣━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┫
┃ ID  ┃ Need back                ┃ Who    ┃ Project┃ Next   ┃ Deadline┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ 12  │ API design review        │ Jane   │ Alpha  │ 3/10   │ 3/14    │
│ 8   │ Q1 budget sign-off       │ Bob    │ Beta   │ 3/11   │ 3/15    │
└─────┴──────────────────────────┴────────┴────────┴────────┴─────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Action (2) — next check due                                           ┃
┣━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┫
┃ ID  ┃ Need back                ┃ Who    ┃ Project┃ Next   ┃ Deadline┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ 5   │ Spec doc v2              │ Jane   │ Alpha  │ 3/14   │ 3/20    │
│ 9   │ Security review          │ Carol  │ Beta   │ today  │ —       │
└─────┴──────────────────────────┴────────┴────────┴────────┴─────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Upcoming (2)                                                          ┃
┣━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┫
┃ ID  ┃ Need back                ┃ Who    ┃ Project┃ Next   ┃ Deadline┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ 3   │ Design mockups           │ Dave   │ Alpha  │ 3/18   │ 3/25    │
│ 7   │ Stakeholder demo         │ Bob    │ Gamma  │ 3/22   │ —       │
└─────┴──────────────────────────┴────────┴────────┴────────┴─────────┘

  Concluded: 2  (run `handoff list concluded` to view)
```

**`handoff list risk`** — single table, Risk section only (same columns).
**`handoff list concluded`** — single table, Concluded section (ID, Need back, Who, Project, Closed).

### 4.4a Filter and search

**Flags (non-interactive):**
```
handoff list [--project NAME] [--who PITCHMAN] [--search TEXT]
handoff list risk [--project NAME] [--who PITCHMAN] [--search TEXT]
handoff list concluded [--project NAME] [--who PITCHMAN] [--search TEXT]
```
- `--project` — filter by project name (repeatable: `--project Alpha --project Beta`)
- `--who` — filter by pitchman (repeatable)
- `--search` — text search over need_back, notes, check-in notes (uses existing `parse_search_query` for @today, @due, date ranges)

**Interactive filter:**
- `handoff list --filter` or `handoff list -f` — run `handoff list` then questionary prompts for project (multiselect), who (multiselect), search text before fetching/displaying
- Or: main menu "Handoffs → List" could always show filter prompts first

**Recommendation:** Support both. Flags for scripts/automation; `--filter` for ad-hoc narrowing. Reuse the same query params the Streamlit Now page uses (`project_ids`, `pitchman_names`, `search_text`). (handoff detail + trail + interactive menu)

First, display the handoff and its trail:

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Handoff #5 — Spec doc v2                                               ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Project:  Alpha                                                        ┃
┃ Who:      Jane                                                         ┃
┃ Next:     2026-03-14    Deadline: 2026-03-20                          ┃
┃ Notes:    Blocked on legal review.                                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check-in trail                                                         ┃
┣━━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ Date       ┃ Type          ┃ Note                                    ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2026-03-01 │ on_track      │ Kicked off, on schedule                  │
│ 2026-03-08 │ delayed       │ Waiting on legal feedback                 │
│ 2026-03-14 │ (current)     │ —                                        │
└────────────┴───────────────┴──────────────────────────────────────────┘
```

Then, interactive menu (select a check-in to view details, or add one):

```
? What next?
  ❯ Add check-in (on-track / delayed / concluded)
    Select check-in for details
    Edit this handoff
    Conclude
    Reopen (if concluded)
    Delete
    Back
```

If "Select check-in for details":
```
? Select check-in
  ❯ 2026-03-14 — (current)
    2026-03-08 — delayed: Waiting on legal feedback
    2026-03-01 — on_track: Kicked off, on schedule
    Back
```

If "Add check-in":
```
? Add check-in for handoff #5: "Spec doc v2"
  ❯ On track
    Delayed
    Concluded
  Note: [________________]
  Next check date (if on-track/delayed): [date picker]
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
7. `handoff_cmds.py`: add, list (full + risk + concluded), show, edit, delete, on-track, delayed, conclude, reopen, check-in, trail; list supports --project, --who, --search, --filter
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
├── list [risk|concluded]        # Full snapshot; risk/concluded = filtered view
│   [--project NAME] [--who NAME] [--search TEXT] [--filter]
├── show ID
├── edit ID
├── delete ID
├── on-track ID
├── delayed ID
├── conclude ID
├── reopen ID
├── check-in ID                  # Interactive menu
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
