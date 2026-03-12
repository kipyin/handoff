# PR 3: `handoff run --demo [--db-path PATH]`

## Plan reference

**[plans/demo-mode-and-uat.md](../../plans/demo-mode-and-uat.md)** — Phase 2, PR 3

Read the full plan. Depends on **PR 1** (seed script and demo path).

## Your task

1. Add `--demo` and `--db-path PATH` to the `run` command in `scripts/cli.py`.
2. When `--demo`:
   - Resolve path: `--db-path` if given, else `get_demo_db_path()`.
   - If DB is empty (no projects), call `seed_demo_db(..., force=False)`.
   - Run the app with `HANDOFF_DB_PATH` set to that path (in the subprocess env).
3. Without `--demo`, behavior unchanged.
4. Add a CLI test that `run --demo --db-path /tmp/x.db` seeds (if needed) and that the subprocess receives the correct `HANDOFF_DB_PATH`.

## Escalate when

- Subprocess env handling or path injection is unclear.
- How to detect "empty DB" (e.g. no projects) is ambiguous.
