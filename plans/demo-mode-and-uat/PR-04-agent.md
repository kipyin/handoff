# PR 4: UAT fixture and reference-date support

## Plan reference

**[plans/demo-mode-and-uat.md](../../plans/demo-mode-and-uat.md)** — Phase 3, PR 4

Read the full plan. Depends on **PR 1** (seed script and demo path).

## Your task

1. Ensure `seed_demo_db` accepts and uses `reference_date` correctly (refine from PR 1 if needed).
2. Add `seeded_uat_db` fixture:
   - Temp DB path, monkeypatch `HANDOFF_DB_PATH`.
   - Monkeypatch the module-level `date` symbol in the modules that call `date.today()` (e.g. `handoff.data.handoffs`, `handoff.data.queries`) so they use a fixed date, following the pattern in `tests/test_todo_service.py` and `tests/test_data.py` (`_patch_date`).
   - Call `seed_demo_db(..., reference_date=fixed_date)`.
   - Reuse the `_reload_db_for_test` pattern from `tests/test_app_integration.py`.
3. Add one smoke test: Now page renders without error when using `seeded_uat_db`.

## Escalate when

- Date monkeypatching causes issues across handoff modules.
- `_reload_db_for_test` or module reload behavior is unclear.
- Fixture scope or test isolation problems arise.
