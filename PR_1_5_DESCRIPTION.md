# PR 1.5 - Lightweight Now-page instrumentation

## Goals/Scope

- Add lightweight timing and action instrumentation for the Now page.
- Capture enough signal to compare before/after experience during rollout.
- Keep instrumentation local and simple.

## Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Do not add telemetry that requires external services.

## Acceptance criteria

### Observable behavior

- No user-visible behavior changes besides optional logs or internal metrics support.
- Timing data is available for render and key action flows.

### Test expectations

- Unit tests cover instrumentation helpers if added.
- Existing functional tests remain unchanged and green.

## Out-of-scope

- Dashboard surfacing of new metrics.
- Remote analytics.
- Rulebook logic.

## Rollback plan

- Remove the instrumentation helpers and log calls.
- No schema or persistent user-data rollback should be required.

## Implementation summary

- Added `handoff.instrumentation` module with `time_action` context manager for logging elapsed ms.
- Instrumented `get_now_snapshot` (render) and key action flows: conclude, check-in, reopen, edit, add.
- Timing logs use format `now_instrumentation {name} elapsed_ms={value}` at INFO level.
- Unit tests for `time_action` cover normal completion and exception propagation.
