# PR 5: UAT test cases (checklist)

## Plan reference

**[plans/demo-mode-and-uat.md](../../plans/demo-mode-and-uat.md)** — Phase 3, PR 5

Read the full plan. Depends on **PR 4** (UAT fixture).

## Your task

1. Add UAT tests in `tests/test_uat_seeded.py` using `seeded_uat_db`.
2. Implement the checklist (one or more tests per item):
   - Now sections: Risk, Action required, Upcoming, Concluded present with expected seeded items.
   - Conclude: Conclude a handoff via UI, verify it moves to Concluded.
   - Reopen: Reopen a concluded handoff, verify it leaves Concluded.
   - Add handoff: Add via form, verify persistence and placement.
   - Archived toggle: Toggle "Include archived projects", verify archived items appear.
   - Dashboard: Renders without error with seeded data.
3. Use `AppTest.from_function` and page entry points like `tests/test_app_integration.py`.
4. Assert on UI (labels, expanders, sections) and data layer (`query_handoffs`, etc.) as in existing integration tests.

## Escalate when

- AppTest selectors break or are flaky.
- UI structure differs from assumptions in the plan.
- Seeded `need_back` strings or placement don't match expectations.
