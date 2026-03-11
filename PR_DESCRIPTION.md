# PR 1.4 - Quick actions and low-risk interaction polish

## Goals/Scope

- Add small interaction wins on the Now page.
- Prioritize quick snooze presets and other low-risk action affordances.
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

### Snooze presets (segmented control)

- Added snooze presets **1d**, **3d**, **1w** (1 business day, 3 business days, 5 business days) using `st.segmented_control`.
- Presets appear next to the date picker in the Actions popover.
- Selecting a preset updates the snooze date immediately; the date picker remains for custom dates.
- Layout: Date picker | Presets (1d | 3d | 1w) | Snooze button.
- Added conftest patch for ButtonGroup.indices so AppTest works with segmented_control (Streamlit #11338).

### AI model suggestion

Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — small UI additions like snooze presets; low-risk, well-scoped changes.
