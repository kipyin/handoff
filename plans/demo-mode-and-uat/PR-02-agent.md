# PR 2: `handoff seed-demo` CLI command

## Plan reference

**[plans/demo-mode-and-uat.md](../../plans/demo-mode-and-uat.md)** — Phase 1, PR 2

Read the full plan. Depends on **PR 1** (seed script and demo path).

## Your task

1. Add `seed-demo` subcommand to `scripts/cli.py`.
2. Options: `--db-path PATH` (optional), `--force`.
3. Resolve path: `--db-path` if given, else `get_demo_db_path()`.
4. Call `seed_demo_db(db_path, force=force)` and print a short confirmation.
5. Extend `tests/test_cli.py` to run `handoff seed-demo` with a temp path and assert the DB is created and seeded.

## Escalate when

- CLI option wiring or Typer usage is unclear.
- Test needs to invoke `handoff` as a subprocess; check `tests/test_cli.py` for existing patterns.
