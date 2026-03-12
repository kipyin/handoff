# Demo Mode and Automated UAT — Implementation Plan

## Overview

Add a demo-mode workflow for Handoff:

1. **Seed script** — Populates a DB with representative + edge-case data via the data layer.
2. **`run --demo`** — Run the app against a demo DB (default or custom path); seeds if needed.
3. **Automated UAT** — Pytest tests that use the seed and exercise a fixed checklist of user flows via AppTest.

Production DB is never touched when using demo mode.

---

## Phases and PRs

| Phase | PR | Title | Dependencies |
|-------|-----|-------|--------------|
| 1 | PR 1 | Add seed script and demo path | — |
| 1 | PR 2 | Add `handoff seed-demo` CLI command | PR 1 |
| 2 | PR 3 | Add `handoff run --demo [--db-path PATH]` | PR 1 |
| 3 | PR 4 | Add UAT fixture with seeded DB and reference date | PR 1 |
| 3 | PR 5 | Add UAT test cases for demo checklist | PR 4 |
| 4 | PR 6 | Document demo mode and UAT in AGENTS.md | — |

---

## Phase 1: Seed Infrastructure

### PR 1: Seed script and demo path

**Scope**

- Add `get_demo_db_path()` in `handoff.db` (or equivalent) returning default demo DB path (e.g. `user_data_dir("handoff", "handoff") / "handoff-demo.db"`).
- Add `scripts/seed_demo.py` with `seed_demo_db(db_path, *, force: bool = False, reference_date: date | None = None)`.
- Seed uses only `handoff.data` APIs (`create_project`, `create_handoff`, `create_check_in`).
- Data: 2–3 projects (one archived), 8–10 handoffs covering Risk, Action required, Upcoming, Concluded, and edge cases (no pitchman, long text, markdown notes). For Risk, the built-in rule requires deadline near and latest check-in == delayed, so Risk handoffs must include a delayed check-in in their trail.
- When `reference_date` is provided, all dates derive from it; otherwise use `date.today()`.

**Files**

- `src/handoff/db.py` (or new module)
- `scripts/seed_demo.py` (new)

**Tests**

- `tests/test_seed_demo.py`: run `seed_demo_db` on temp path, assert counts (projects ≥ 2, handoffs ≥ 5).

---

### PR 2: `handoff seed-demo` CLI command

**Scope**

- Add `seed-demo` subcommand to `scripts/cli.py`.
- Options: `--db-path PATH` (optional), `--force`.
- When `--db-path` omitted, use `get_demo_db_path()`.
- Invoke `seed_demo_db(db_path, force=force)` and print a confirmation.

**Files**

- `scripts/cli.py`

**Tests**

- Extend `tests/test_cli.py`: run `handoff seed-demo` with temp path, assert DB created and seeded.

---

## Phase 2: Run with Demo

### PR 3: `handoff run --demo [--db-path PATH]`

**Scope**

- Add `--demo` and `--db-path PATH` to the `run` command.
- When `--demo`:
  - Resolve path: `--db-path` if given, else `get_demo_db_path()`.
  - If DB is empty (no projects), call `seed_demo_db(..., force=False)`.
  - Run app with `HANDOFF_DB_PATH` set to that path.
- Without `--demo`, behavior unchanged, including the existing Typer extra-args passthrough (keep forwarding unknown/remaining args to `python -m handoff` so workflows that pass Streamlit flags continue to work).

**Files**

- `scripts/cli.py`

**Tests**

- CLI test: `run --demo --db-path /tmp/x.db` seeds (if needed) and subprocess receives correct `HANDOFF_DB_PATH`.

---

## Phase 3: Automated UAT

### PR 4: UAT fixture and reference-date support

**Scope**

- Ensure `seed_demo_db` accepts `reference_date` and uses it consistently.
- Add `seeded_uat_db` fixture (in `tests/conftest.py` or `tests/test_uat_seeded.py`):
  - Temp DB path, monkeypatch `HANDOFF_DB_PATH`.
  - Monkeypatch the `date` symbols in modules that call `date.today()` (e.g. `handoff.data.handoffs.date`, `handoff.data.queries.date`, and any relevant service/page modules) so they use a fixed reference date.
  - Call `seed_demo_db(..., reference_date=fixed_date)`.
  - Reuse `_reload_db_for_test` pattern from `test_app_integration.py`.
- Add one smoke test using the fixture (e.g. Now page renders without error).

**Files**

- `scripts/seed_demo.py` (if `reference_date` needs refinement)
- `tests/conftest.py` or `tests/test_uat_seeded.py`

**Tests**

- Smoke: page renders with seeded data.

---

### PR 5: UAT test cases (checklist)

**Scope**

- Add UAT tests using `seeded_uat_db` for a fixed checklist.
- Each test targets one workflow.

**Checklist (1+ test per item)**

1. Now sections: Risk, Action required, Upcoming, Concluded present with expected seeded items.
2. Conclude: Conclude a specific handoff via UI, verify it moves to Concluded.
3. Reopen: Reopen a concluded handoff, verify it leaves Concluded.
4. Add handoff: Add via form, verify persistence and placement.
5. Archived toggle: Toggle "Include archived projects", verify archived items appear.
6. Dashboard: Renders without error with seeded data.

**Files**

- `tests/test_uat_seeded.py`

**Tests**

- One test per checklist item (or grouped where sensible).

---

## Phase 4: Documentation

### PR 6: AGENTS.md and README updates

**Scope**

- **AGENTS.md**: demo mode (`run --demo`), seed command (`seed-demo`), UAT (how to run, what the seed contains).
- **README**: brief "Try with demo data" section.

**Files**

- `AGENTS.md`
- `README.md`

---

## Seed Data Design

### Projects (2–3)

| Name | Archived |
|------|----------|
| Acme Corp | No |
| Personal | No |
| Archived Project | Yes |

### Handoffs (~8–10)

| need_back | pitchman | deadline | next_check | Check-in trail | Bucket |
|-----------|----------|----------|------------|----------------|--------|
| Overdue deliverable | Alice | yesterday | yesterday | delayed | Risk |
| Due today | Alice | today | today | delayed | Risk |
| Action required item | Bob | tomorrow | today | on_track | Action required |
| Upcoming task | Carol | next week | next week | none | Upcoming |
| Concluded task | Bob | last week | — | on_track → concluded | Concluded |
| Reopened handoff | Alice | tomorrow | today | concluded → on_track | Action/Upcoming |
| No pitchman, no dates | — | None | None | none | Upcoming |
| Long description… | Dave | next month | next month | none | Upcoming |
| Notes with [markdown](url) | Carol | — | — | none | Upcoming |

Dates use `reference_date` or `date.today()` plus `add_business_days` from `handoff.dates`.

---

## Reviewer Guidance

| PR | Primary | Escalate to higher-cap agent (e.g. GPT-5.4, Opus 4.6) if |
|----|---------|----------------------------------------------------------|
| 1 | Copilot | Reference-date and date-handling logic feel brittle |
| 2 | Copilot | — |
| 3 | Copilot | Subprocess env injection or path resolution is unclear |
| 4 | Copilot | Date monkeypatching or module reload causes issues |
| 5 | Copilot | AppTest selectors or UI coupling are fragile |
| 6 | Copilot | — |

---

## Agent Instructions Per PR

Each PR has a short instruction file in `plans/demo-mode-and-uat/`:

- **PR-01-agent.md** through **PR-06-agent.md**

These point agents to this plan and state when to escalate.
