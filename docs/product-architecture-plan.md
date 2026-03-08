# Product Design & Architecture Plan

## Current State Summary

Handoff is a focused, single-user local to-do app (Python 3.13, Streamlit, SQLite)
with five pages (Todos, Projects, Dashboard, Settings, Docs), three todo statuses
(`handoff`/`done`/`canceled`), and first-class concepts for **projects**, **helpers**,
and **deadlines**. The architecture is clean: `models.py` → `data.py` → `pages/` with
typed contracts in `page_models.py` and `backup_schema.py`. Deployment targets Windows
via embedded Python + PyArmor, with a patch-based in-app update flow.

---

## A. Product Design Opportunities

### A.1 Bring Back Calendar View (Reimagined)

The Calendar page was removed in v2026.3.5 to focus on core stability. Now that the
core is solid, a re-introduction would be high-value:

- **Weekly calendar** with todos grouped by deadline day.
- **Drag-and-drop rescheduling** — adjust deadlines by dragging a todo to a different
  day. Streamlit's current widgets make this hard, but this motivates the architecture
  discussion in Section B.
- **"Today" focus panel** — a stripped-down daily view showing just overdue + today
  items. The old Focus page (removed in v2026.2.24) attempted this; a simpler
  card-based version inside the Calendar could work.

### A.2 Recurring Todos / Templates

Currently every todo is one-off. Many handoff-style tasks repeat (weekly check-ins,
recurring reports):

- Add a `recurrence` field to `Todo` (e.g., `weekly`, `biweekly`, `monthly`, `none`).
- When a recurring todo is marked `done`, auto-create the next instance with the
  deadline shifted forward.
- Alternatively: **todo templates** at the project level — "create from template"
  prefills name, helper, and relative deadline offset.

### A.3 Priority or Urgency Field

The app once had urgency buckets (overdue/today/soon) which were removed. A simpler
approach:

- Add an optional `priority` field (`high`/`normal`/`low`) to `Todo`.
- Use it for **sort order** within the table (high-priority items float up).
- Dashboard could surface a "high-priority items overdue" metric.

This is lighter than the old urgency system and doesn't duplicate deadline logic.

### A.4 Saved Filter Presets

Power users build the same filter combinations repeatedly ("Alice's overdue items
across Project X and Y"). Support:

- **Named filter presets** stored in a `filter_preset` table (name, serialized
  `TodoQuery`).
- A dropdown above the filter bar: "Load preset…"
- "Save current filters as…" action.

### A.5 Batch Operations

The current table supports single-row edits. For triage workflows:

- **Bulk status change** — select multiple rows, set all to `done` or `canceled`.
- **Bulk reassign** — select multiple rows, change helper.
- **Bulk reschedule** — shift deadlines by N days for selected items.

Streamlit's `data_editor` has limited multi-select support, so this may require custom
components or architecture changes (see Section B).

### A.6 Enhanced Dashboard Analytics

`docs/analytics-ideas.md` already lists some of these — here's a prioritized plan:

- **Per-project throughput breakdown** — completed per week, filterable by project.
- **Per-helper throughput** — who is completing the most, trending up or down.
- **Cycle time by project** — identify which projects have slow turnaround.
- **Deadline adherence trend** — on-time rate over time (not just the last 28 days).
- **Exportable metrics** — CSV/JSON of aggregated weekly stats for external reporting.

### A.7 Activity Log / Audit Trail

Track what happened and when:

- A lightweight `activity_log` table: `timestamp`, `entity_type`, `entity_id`,
  `action` (created/updated/completed/deleted), `details` (JSON).
- Surface as a "Recent Activity" section on the Dashboard or as a separate page.
- Useful for the user to see "what changed since yesterday" — especially after a busy
  day of delegation.

### A.8 Notes Enhancement

The `notes` field is plain text. Small improvements with high impact:

- **Markdown rendering** in a read-only detail view (links, checklists, emphasis).
- **Checklist sub-items** within a todo — simple `- [ ] step 1` / `- [x] step 2`
  parsing, with a progress indicator on the main table.
- **Clickable links** — detect URLs in notes and make them clickable.

---

## B. Architecture Opportunities

### B.1 Introduce a Service / Use-Case Layer

Currently, pages call `data.py` functions directly. As features grow (recurring todos,
activity logging, batch operations), a thin **service layer** would help:

```
pages/ (UI) → services/ (orchestration + business logic) → data.py (persistence)
```

For example, `complete_todo()` in a service module would: update the todo status, log
to the activity trail, check for recurrence and create the next instance, and update
metrics — all in one transaction. Today this logic would have to live in the page code.

### B.2 Decouple from Streamlit (Multi-Frontend Path)

`STYLE.md` already says: *"Favor patterns that would still make sense in a future CLI
or Textual frontend."* The codebase is mostly there, but some page files contain
interleaved business logic and Streamlit calls. A concrete plan:

- **Phase 1**: Extract all business logic from `pages/*.py` into the service layer
  (above). Pages become pure Streamlit renderers that call services and display results.
- **Phase 2**: Build a **Textual TUI** frontend using the same service layer. This
  gives a fast terminal-native experience and validates the abstraction.
- **Phase 3**: Optionally, build a **FastAPI + HTMX** or **Flask** web frontend for
  users who want a proper browser experience without Streamlit's rerun model.

The typed contracts in `page_models.py` are already a strong foundation for this —
they're framework-agnostic.

### B.3 Formalize Database Migrations

Currently, migrations are inline `PRAGMA table_info` checks in `db.py:init_db()`. This
works for simple additions but doesn't scale:

- Introduce a `migrations/` directory with numbered migration scripts (e.g.,
  `001_add_priority.py`, `002_add_recurrence.py`).
- A `schema_version` table tracks which migrations have been applied.
- `init_db()` runs pending migrations in order on startup.
- This is still SQLite-native (no Alembic needed), but provides a clear audit trail and
  makes multi-step schema changes safe.

### B.4 Fix Pyright Coverage Gaps

Three modules are excluded from type checking: `data.py`, `pages/analytics.py`,
`pages/todos.py`. A phased approach:

- **`pages/analytics.py`** — likely easiest; mostly read-only queries and metric
  computation. Add type annotations and remove from exclusion list.
- **`data.py`** — the core data layer. Annotating this properly would catch bugs early.
  May require some `TYPE_CHECKING` imports and explicit `Session` typing.
- **`pages/todos.py`** — heaviest Streamlit usage. Extracting business logic to a
  service layer (item B.1) would shrink the untyped surface area.

### B.5 CI/CD Pipeline

There's no `.github/` directory — no automated CI. Adding:

- **GitHub Actions** (or Gitee CI): Run `uv run handoff ci` on every push/PR.
- **Matrix testing**: Python 3.13 on Ubuntu + Windows.
- **Release automation**: Tag-based releases that build the Windows zip and publish
  artifacts.
- **Dependabot / Renovate**: Keep `streamlit`, `sqlmodel`, etc. up to date.

### B.6 Auto-Update Checker

Currently, patch updates are manual uploads. An optional auto-check:

- On app startup, hit a version endpoint (e.g., a JSON file on Gitee Releases or a
  simple HTTP endpoint) to check if a newer version exists.
- Show a non-intrusive banner on the Settings page: "Version 2026.4.0 is available."
- Keep the manual upload path as fallback (air-gapped environments).
- Respect a "disable update checks" toggle in Settings.

### B.7 Test Suite Consolidation

There is noticeable overlap between test files (`test_pages_todos.py`,
`test_todos_render.py`, `test_todos_coverage.py` cover similar ground). A cleanup pass:

- Merge overlapping files into one file per module (e.g., `test_pages_todos.py` covers
  all todos page logic).
- Establish a convention: `test_<module>.py` for unit tests,
  `test_<module>_integration.py` for integration tests.
- Add a `conftest.py` fixture for "app with sample data" to reduce boilerplate across
  page tests.

### B.8 macOS Build Support

`CONTRIBUTING.md` mentions macOS as a future target. Concrete steps:

- A `build_full.py` flag for macOS that produces a `.app` bundle or a shell-launchable
  directory.
- Code signing and notarization (required for modern macOS).
- A `.command` or `.sh` launcher analogous to `handoff.bat`.

---

## C. Prioritization

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| **High** | B.1 Service layer | Medium | Unlocks clean feature growth |
| **High** | A.6 Enhanced Dashboard | Low–Medium | Already partially planned |
| **High** | B.5 CI/CD Pipeline | Low | Prevents regressions |
| **High** | B.3 Formalize migrations | Low | Required before new schema changes |
| **Medium** | A.2 Recurring todos | Medium | High user value for repeat tasks |
| **Medium** | A.4 Saved filter presets | Low | Quality-of-life for power users |
| **Medium** | A.1 Calendar view | Medium | Brings back removed functionality |
| **Medium** | B.4 Fix pyright gaps | Medium | Code quality |
| **Medium** | B.7 Test consolidation | Low | Developer experience |
| **Low** | A.3 Priority field | Low | Nice-to-have |
| **Low** | A.7 Activity log | Medium | Useful but not urgent |
| **Low** | A.5 Batch operations | Medium–High | Blocked by Streamlit limitations |
| **Low** | B.2 Multi-frontend | High | Long-term vision |
| **Low** | B.6 Auto-update checker | Medium | Requires hosting |
| **Low** | B.8 macOS build | Medium | Expands user base |

---

## D. Suggested Sequencing

### Milestone 1 — Foundation & Analytics (v2026.4.x)

- Formalize migration framework (B.3)
- Add CI/CD pipeline (B.5)
- Consolidate test suite (B.7)
- Enhanced Dashboard: per-project/helper breakdowns, trend charts (A.6)

### Milestone 2 — Productivity Features (v2026.5.x)

- Introduce service layer, extract business logic from pages (B.1)
- Recurring todos / templates (A.2)
- Saved filter presets (A.4)
- Priority field (A.3)
- Begin pyright coverage expansion (B.4)

### Milestone 3 — Views & Reach (v2026.6.x)

- Reimagined Calendar / Focus view (A.1)
- Activity log (A.7)
- Auto-update checker (B.6)
- macOS build (B.8)
- Evaluate multi-frontend path: Textual TUI prototype (B.2)
