## Handoff

Handoff helps you see who is on the hook across all your projects. It is a local
to‑do app for juggling tasks across different engagements (projects). The app is
designed for personal use and runs locally with SQLite.

## Quickstart

- **Prerequisites**: Python 3.13+ and [uv](https://docs.astral.sh/uv/).
- **Install and run**:

```bash
uv sync
uv run handoff
```

You get a local, single-user to-do app backed by SQLite, with a unified view
across projects and helpers, and an in-app update flow.

## Who is this for?

Handoff is designed for a single person managing multiple projects and helpers,
not for a multi-user team deployment. Typical use cases include:

- Tracking work across several client engagements or internal projects.
- Seeing, at a glance, what you owe to different people (helpers) this week.
- Planning near-term deadlines without maintaining multiple spreadsheets.

The app is intentionally simple and local-only: you run it on your own machine
and keep control of your data.

## Why this over a spreadsheet?

Unlike an ad-hoc Excel or Sheets tracker, this app is opinionated around
**multi-project, helper-centric work**:

- **Cross-project view**: All todos live in a single table so you can see your
  entire workload across engagements at once, without maintaining separate tabs.
- **Helper dimension**: The `helper` field treats "who is on the hook" as a
  first-class axis for filtering and planning (for example, "what have I
  delegated to Alice this week?").
- **Deadlines & focus presets**: Deadline filters (today, tomorrow, this week,
  custom ranges) are tuned for short-horizon planning rather than long-term
  Gantt charts.
- **Lightweight history & backups**: Todos and projects are stored in a local
  SQLite database with a built-in JSON/CSV export, so you can safely experiment
  without losing data.
- **Streamlit-native UX**: The UI is optimised for quick inline editing,
  filtering, and saving, not for cell-by-cell formulas or complex formatting.

If you find yourself stitching together multiple sheets or constantly
re-filtering to answer "what must ship this week across all projects?", this app
aims to make that view a single click instead.

## Limitations and non-goals

To keep the app simple and robust, some things are intentionally out of scope:

- No multi-user sync or shared team workspace.
- No mobile or web-hosted version; the app runs on your own machine.
- No complex reporting or Gantt-style project planning.
- No external integrations (e.g. calendars, issue trackers) beyond what you
  manage manually in notes.

## Features

1. **Projects** — Create and manage engagements/projects on the Projects page.
2. **Todos per project** — Each project has many todos. Each todo has:
   - Name
   - Next check (optional follow-up date)
   - Deadline (optional)
   - Creation timestamp (auto)
   - Status: `handoff` | `done` | `canceled`
   - Helper (assignee)
   - Notes (text; you can paste links, file paths, etc.)
3. **Now page** — Control-tower view for action-required handoffs. Shows items
   that need attention (next check due today or earlier, or deadline at risk).
   Add new handoffs, edit existing ones, Snooze to a specific follow-up date
   using a date picker, or Close when done. Upcoming section lists handoffs not
   yet due. Filter by project, helper, or search.
4. **Dashboard** — At-a-glance metrics: open handoffs, completed this week vs
   last, median cycle time, and on-time rate. Plus a weekly throughput chart
   and current helper load.
5. **Updates and backups** — An in-app Settings page lets you apply code-only
   patch zips and restore from backups created before each update.

## Where your data lives

By default, the SQLite database is stored in your per-user data directory so app
updates do not overwrite your data (for example on Windows:
`%APPDATA%\handoff\todo.db`). You can override the location by setting the
`HANDOFF_DB_PATH` environment variable before starting the app.

> **Migrating from `TODO_APP_DB_PATH`:** The legacy `TODO_APP_DB_PATH`
> environment variable is no longer recognised. If you were using it to point
> the app at a custom database location, rename the variable to
> `HANDOFF_DB_PATH` (same value) and restart the app.

`app.py` is intentionally kept thin and delegates version handling to
`src/handoff/version.py`, which exposes a single `__version__` constant used by
the UI and tooling (for example the updater panel and build scripts).

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies (creates .venv and installs packages)
uv sync

# Run the app
uv run handoff
```

## Logging and debugging

The app uses **loguru** for logging, configured to write to:

- **Standard output** (what you see in the terminal when running the app).
- **Rotating log file** under your user data directory (for example on Windows:
  `%APPDATA%\handoff\logs\handoff.log`).

The configuration lives in `src/handoff/logging.py` and is initialised from
`handoff.ui.setup()`.

During development, run the app from a terminal to see logs live as you
interact:

```bash
uv run handoff
```

What gets logged (non-exhaustive):

- Database initialisation and file location.
- Project creation, rename, and delete operations.
- Creating, updating, and deleting todos (with context, row number, and todo
  id).
- Save summary counts and high-level query info.

For deeper diagnostics you can extend the existing `loguru` calls in
`src/handoff/data.py`, `src/handoff/db.py`, or `src/handoff/pages/todos.py`.

## Windows embedded zip build and obfuscated patches

On Windows you can build a self-contained zip that bundles an embedded Python
runtime, dependencies, and the app code. The build uses **PyArmor** to
obfuscate the `src/handoff` package so that distributed code is protected;
`app.py` stays readable. You need PyArmor in your dev environment
(`uv sync` installs it):

```bash
uv run handoff build --full
```

This produces a zip under `dist/` (named like
`handoff-<version>-windows-embed.zip`). Extract it, then double-click `handoff.bat`
to start the app. The SQLite database is still stored in your user data
directory, not inside the extracted folder.

For small logic-only changes you can ship a **code-only patch** zip instead of
a full embedded bundle. For production usage, always use the obfuscated patch
flow:

- Run `uv run handoff build --full` to produce the embedded app build.
- Then run `uv run handoff build --patch` to create
  `dist/handoff-<version>-patch.zip` from the obfuscated build output so that
  the in-app updater can apply it to PyArmor-built installs.

### Updating the app (user flow)

1. Get a patch zip (for example from a Handoff release or your team).
2. Run the app as usual (for example double‑click `handoff.bat`).
3. In the app, open **Settings** → **Update app**, upload the patch zip, and
   click **Apply and Restart**.
4. The app creates a backup of files that will be overwritten, extracts the
   patch to `./update/`, then exits after a few seconds.
5. Run the launcher again (`handoff.bat`). It copies the update from
   `./update/` into the app folder (without starting Python first, so locked
   files can be replaced), removes `./update/`, and starts the app. You are now
   on the new version.

### Backups and rollback

Backups are created **before** the update is applied (when you click
**Apply and Restart**), under `backup/<YYYYMMDD-HHMMSS>-version<version>/` in
the app root. The next time you open **Settings**, the app shows where the
backup was saved.

To restore from a bad patch:

1. Open **Settings** → **Restore from backup** (under **Update app**).
2. Pick a snapshot (listed by date and version).
3. Click **Restore and Restart**.

The app copies the backed-up files back, clears caches, and exits; run the
launcher again to use the restored version.

## Support and issues

The project lives at
[`https://gitee.com/kipyt/handoff`](https://gitee.com/kipyt/handoff). At the
moment it is a personal project; treat issues and requests as best-effort.

For **user-facing docs** (how to run, update the app, backups), stay in this
README. For **developer docs** (CLI commands, layout, release workflow, and
code style), see [`AGENTS.md`](AGENTS.md). You can also read the README and
release notes inside the app via the Docs navigation entry.

**Contributing:** Run `uv run handoff ci` before submitting changes. See
AGENTS.md for commands, style, and workflow.