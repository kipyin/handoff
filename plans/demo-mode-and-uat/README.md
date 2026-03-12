# Demo Mode and UAT — Per-PR Agent Instructions

## Plan

**Full plan:** [../demo-mode-and-uat.md](../demo-mode-and-uat.md)

Read the plan before starting any PR. It defines scope, files, and acceptance criteria.

## PR Instructions

| PR | File | Summary |
|----|------|---------|
| 1 | [PR-01-agent.md](PR-01-agent.md) | Seed script and demo path |
| 2 | [PR-02-agent.md](PR-02-agent.md) | `handoff seed-demo` CLI |
| 3 | [PR-03-agent.md](PR-03-agent.md) | `handoff run --demo` |
| 4 | [PR-04-agent.md](PR-04-agent.md) | UAT fixture |
| 5 | [PR-05-agent.md](PR-05-agent.md) | UAT test cases |
| 6 | [PR-06-agent.md](PR-06-agent.md) | Documentation |

## Escalation

When you hit any of these, ask for review from a higher-capability agent (e.g. GPT-5.4, Opus 4.6):

- Date logic or `reference_date` feels brittle (PR 1, 4)
- Subprocess / env handling unclear (PR 3)
- AppTest selectors or UI coupling fragile (PR 5)
- Architecture or boundary decisions unclear (any PR)
