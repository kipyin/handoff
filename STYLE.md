## Coding style

This is the short, opinionated style guide for Handoff. It is written for both
human contributors and coding agents.

The goal is not maximal abstraction or maximal cleverness. The goal is code
that is small, calm, readable, and hard to break.

### Aesthetic

- Prefer **boring code over surprising code**.
- Keep modules **small in concept count**, even when they are not tiny in line
  count.
- Use **clear names** that match the product language. If the UI says
  "handoff", the code should usually say `handoff` too.
- Make the **main flow easy to scan**:
  - read input
  - normalize/validate it
  - perform one clear action
  - return a simple result
- Prefer a **single obvious representation** for a piece of data. Avoid bouncing
  between ORM models, dicts, DataFrames, widget payloads, and ad hoc tuples
  unless there is a strong reason.
- Keep comments sparse. Add them when they explain **why** something exists or a
  non-obvious constraint, not to narrate obvious code.
- Avoid "magic helper" sprawl. A helper should either simplify the reader's
  job, or it should not exist.

### Hygienic

- Keep **boundaries explicit**:
  - models define persisted shape
  - data-layer functions implement behavior and queries
  - page/UI modules translate UI state into typed app-level inputs
  - UI-specific concerns should not leak into core modules
- Prefer **typed contracts** for non-trivial flows:
  - query objects
  - mutation inputs
  - serialized backup/import payloads
- Do not create abstractions just to move code around. A new module or type
  should reduce ambiguity, coupling, or duplication.
- Preserve **one source of truth** for important behavior. Filtering,
  validation, and serialization should not be reimplemented differently in
  multiple layers.
- Keep public APIs and docstrings in sync. If behavior changes, update the
  docs/tests in the same change.
- When touching old names or legacy compatibility paths, prefer a **clear
  primary name** plus a compatibility shim rather than letting both concepts
  coexist indefinitely.

### Robust

- Validate inputs **before destructive actions**.
- Fail with **clean, actionable messages** for users and **specific logs** for
  developers.
- Prefer code that is easy to test with **targeted unit tests** and a few
  integration/smoke tests over code that only works when driven through the UI.
- Make hidden global state explicit when practical. Lazy factories or narrow
  context helpers are preferred to import-time side effects.
- Handle real edge cases:
  - missing ids on not-yet-persisted models
  - malformed backup files
  - path traversal in patch zips
  - schema drift in lightweight migrations
- If a refactor changes behavior in a subtle UI path, add or update a test so
  the intended behavior is locked in.

### Practical preferences for this repo

- Streamlit is the current UI, but the app should stay **portable in shape**.
  Favor patterns that would still make sense in a future CLI or Textual
  frontend.
- SQLite + SQLModel is intentionally simple. Keep migrations lightweight unless
  complexity truly demands more.
- Ruff is the formatter/linter authority. Pyright is the type-checking
  authority.
- When in doubt, choose:
  - fewer layers
  - fewer representations
  - fewer special cases
  - more explicit names
  - more local reasoning

### One-sentence summary

Write code that looks calm, says exactly what it means, and keeps behavior in
the smallest sensible number of places.
