# PR 1: Seed script and demo path

## Plan reference

**[plans/demo-mode-and-uat.md](../../plans/demo-mode-and-uat.md)** — Phase 1, PR 1

Read the full plan for scope, seed data design, and file list.

## Your task

1. Add `get_demo_db_path()` that returns the default demo DB path (e.g. next to production DB, with a distinct filename like `handoff-demo.db`).
2. Add `scripts/seed_demo.py` with `seed_demo_db(db_path, *, force=False, reference_date=None)`.
3. Seed via `handoff.data` only. Create 2–3 projects, 8–10 handoffs covering Risk, Action, Upcoming, Concluded, and edge cases. For Risk, ensure at least one handoff has a delayed latest check-in (not just an overdue/near deadline), since the built-in Risk rule requires deadline near and latest check-in == delayed.
4. Use `reference_date` when provided; otherwise `date.today()`. Use `handoff.dates.add_business_days` for relative dates.
5. Add `tests/test_seed_demo.py` asserting project and handoff counts after seeding.

## Escalate when

- Reference-date wiring or date-derivation logic feels brittle.
- You're unsure where `get_demo_db_path` should live (`db.py` vs new module).
