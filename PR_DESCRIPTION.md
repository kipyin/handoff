# PR 1.4 - Quick actions and low-risk interaction polish

Implements PR 1.4 from `release-plan-2026.3.11.md` plus **Issue #89**.

## Goals/Scope

- Add small interaction wins on the Now page.
- Prioritize quick action affordances (Issue #89: segmented control for check-in).
- Improve visible explanations and transition feedback where helpful.

## Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep the page visually familiar.

## Acceptance criteria

### Observable behavior

- Users can perform common follow-up actions in fewer clicks.
- Existing action flows remain intact.
- Explanatory copy remains clear and concise.

### Test expectations

- Add targeted page or integration coverage for new quick actions.
- Existing action-flow tests continue to pass.

## Out-of-scope

- Rulebook.
- Dashboard changes.

## Rollback plan

- Revert the new quick-action controls only.
- Keep the underlying action services unchanged so rollback is low risk.

## Implementation summary

### Issue #89 — Check-in segmented control and layout

- **On-track | Delayed | Conclude** replaced three buttons with `st.segmented_control`.
- **Edit** button moved to the same row: `( On-Track | Delayed | Conclude ) [Edit]`.
- **Snooze removed** — date picker, (+1d | +3d | +1w) presets, and Snooze button removed.
- Layout matches Issue #89 spec: segment control + Edit on one row; Current progress / Why? textarea; Next check-in date picker; Save / Cancel.

### Other changes

- Added conftest patch for ButtonGroup.indices so AppTest works with segmented_control (Streamlit #11338).
- Auto-expand expanders for due action items so check-in controls are visible without clicking.
- Add handoff collapse button when form is expanded (fix: button was gone, label stayed).

### AI model suggestion

Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — small UI additions; low-risk, well-scoped changes.
