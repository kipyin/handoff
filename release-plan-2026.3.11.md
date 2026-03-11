# Release plan - 2026.3.11

## Release summary

This release focuses on two product themes:

1. Make the Now page feel fast, reliable, and smooth.
2. Make the Now page configurable through a rulebook for open-item sections.

This release does not include AI features. Those are explicitly deferred to a later release.

## AI model suggestions by PR

When implementing each PR, consider the suggested model tier. **Fast** for well-scoped, pattern-following work; **Harder** for finicky state, core logic, or critical integration.

| Tier | Models |
|------|--------|
| **Fast** | sonnet-4.6, gemini-3-flash, cursor composer 1.5 |
| **Harder** | gpt-5.4, opus-4.6, codex-5.3 |

| PR | Tier | PR | Tier | PR | Tier |
|----|------|----|------|----|------|
| 1.1 Snapshot contract | Fast | 1.2 Reduce reruns | Harder | 1.3 Keyboard shortcuts | Fast |
| 1.4 Quick actions | Fast | 1.5 Instrumentation | Fast | 2.1 Rulebook contracts | Harder |
| 2.2 Rule engine | Harder | 2.3 Persist settings | Fast | 3.1 Rulebook adoption | Harder |
| 3.2 Match explanations | Fast | 4.1 Preview/reset | Fast | 4.2 Editable rulebook | Harder |
| 4.3 Custom sections | Harder | 5.1 Parity coverage | Harder | 5.2 Release notes | Fast |

Each PR section below has a short rationale for its suggestion.

## Why this release now

The current product already has a strong core workflow:

- A handoff stays open until its latest check-in is concluded.
- The Now page is the main operational surface.
- The page/service/data boundary is already clean and should stay that way.
- The current four-section layout is useful, but the section logic is hard-coded.

That gives us a good base for an incremental release:

- Improve the speed and smoothness of the main page first.
- Turn existing implicit section logic into explicit, user-configurable rules.
- Keep the implementation boring, small, and reversible.

## Current-state summary

### What exists today

- The Now page renders four sections: Risk, Action required, Upcoming, and Concluded.
- Section membership is defined by hard-coded query logic.
- Risk is currently "near deadline" plus "latest check-in is delayed".
- Action required is currently "next check is due now" and not Risk.
- Upcoming is the open-item catch-all for items that are neither Risk nor Action.
- Concluded is lifecycle-based and depends on the latest check-in.
- System Settings already stores lightweight local settings in a JSON file next to the database.
- The Projects page already uses an autosave pattern that reduces disruptive reruns.

### Product and engineering implications

- The page already has the right architectural seams for a safer refactor.
- The most obvious UX gap is repeated full-page rerun behavior on the Now page.
- The most obvious product gap is that section logic is fixed rather than configurable.
- The cleanest release path is to improve the Now page foundation first, then layer rulebook support on top.

## Release goals

### Primary goals

- Reduce friction on the Now page for common daily actions.
- Preserve user context and focus better during edits and status updates.
- Add keyboard-first affordances for high-frequency actions where Streamlit supports them cleanly.
- Introduce a rulebook for open-item sections without breaking current behavior by default.
- Keep Upcoming and Concluded as stable catch-all sections.
- Ship the rulebook in a way that is easy to explain, test, and roll back.

### Secondary goals

- Improve observability around Now-page rendering and action latency.
- Make section membership easier to explain to the user.
- Make status transitions and transient UI feedback feel more consistent.
- Keep the system ready for future analytics and policy expansion.

## Release non-goals

- No AI-assisted form creation.
- No AI insights, predictive risk models, or delay clustering.
- No large redesign of the Dashboard page.
- No large database migration unless clearly required by rulebook complexity.
- No new dependency adoption unless a later release justifies it.

## Product principles for this release

- Favor boring code over clever code.
- Keep boundaries explicit: pages call services, services orchestrate, data owns query behavior.
- Prefer one obvious source of truth for section membership.
- Keep default behavior backward compatible.
- Prefer small, focused PRs that can be rolled back independently.
- Make behavior observable and testable, not just plausible.

## Recommended product decisions for this release

### Rulebook behavior

- The rulebook applies only to open handoffs.
- Concluded remains lifecycle-driven, not rule-driven.
- Upcoming remains the open-item fallback when no rule matches.
- Rules are exclusive and priority-based in v1.
- First matching enabled rule wins.
- Built-in default rules must reproduce current behavior at launch.
- Each matched handoff should expose a short "why this matched" explanation.

### Configuration scope

- Start with one global rulebook.
- Do not add per-project rulebooks in this release.
- Store the initial rulebook in the existing settings JSON file beside the database.
- Revisit a dedicated table only if the rulebook becomes meaningfully more complex.

### UI placement

- Keep the Now page focused on execution.
- Put rulebook editing in System Settings first.
- Add preview counts and a reset-to-defaults action in the rulebook editor.

## Release architecture direction

### UX foundation

The first part of the release should simplify how the Now page gets its data and updates its state:

- Introduce a single service-level "Now snapshot" shape for page rendering.
- Reduce repeated orchestration in the page module.
- Reuse the "save small edits without disruptive rerun" mindset that already exists on the Projects page.
- Add lightweight timing instrumentation for key user actions.

### Rulebook foundation

The second part of the release should turn hard-coded open-item section logic into a typed policy layer:

- Represent rules explicitly.
- Keep one source of truth for section membership.
- Preserve current defaults.
- Keep matching explainable.
- Keep the evaluation order explicit and deterministic.

## Implementation plan

The release is split into phases. Each phase is designed to ship value independently and reduce risk for the next one.

---

## Phase 1 - Now page foundation and smoothness

### Phase goals

- Make the Now page feel faster and less disruptive.
- Create a stable service contract for the page before adding rulebook complexity.
- Reduce page-level duplication and rerun-heavy behavior.
- Add low-risk keyboard and focus improvements for frequent actions.

### Phase exit criteria

- The page has a clearer service-level data contract.
- Common actions feel more stable and preserve context better.
- Existing behavior is still functionally unchanged for default users.

### PR 1.1 - Introduce a Now snapshot service contract

#### Goals/Scope

- Add a page-facing typed contract for the Now page snapshot.
- Add a service entry point that returns the full Now-page payload.
- Keep current section semantics unchanged.
- Move orchestration out of the page where practical.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Preserve page-to-service-to-data boundaries.

#### Acceptance criteria

- Observable behavior:
  - The Now page still shows Risk, Action required, Upcoming, and Concluded in the same order.
  - Default section membership remains unchanged.
- Test expectations:
  - Existing Now-page tests still pass.
  - Existing query semantics tests still pass.
  - New service-level tests cover the snapshot contract and default section counts.

#### Out-of-scope

- Rulebook configuration.
- New UI interactions.
- Keyboard shortcuts.
- Performance instrumentation beyond what is needed for this PR.

#### Rollback plan

- Revert the snapshot service and restore page-side orchestration.
- Keep the old query functions intact until this PR is fully validated.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — structural refactor with clear patterns; contract definition and orchestration move are straightforward.

### PR 1.2 - Reduce disruptive reruns in Now-page actions

#### Goals/Scope

- Improve state preservation for add, edit, snooze, check-in, and reopen flows.
- Reduce unnecessary full-page reruns where Streamlit patterns allow it.
- Align the Now page with the smoother interaction style already used on Projects.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Do not redesign the page layout.

#### Acceptance criteria

- Observable behavior:
  - Common actions do not unexpectedly drop user context more than today.
  - The page remains stable after saving a check-in or editing a handoff.
  - Existing flows still work end-to-end.
- Test expectations:
  - Existing integration tests for add, conclude, reopen, and snooze still pass.
  - Add focused tests for state preservation where feasible at the page or integration level.

#### Out-of-scope

- New sections.
- Rulebook behavior.
- Keyboard shortcuts.
- Larger visual redesign.

#### Rollback plan

- Revert the new state-management changes only.
- Fall back to the prior explicit rerun behavior if any focus/state regressions appear.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — Streamlit state and rerun behavior are finicky; preserving context across edits requires careful reasoning about session state and widget lifecycle.

### PR 1.3 - Keyboard shortcuts and focus navigation

#### Goals/Scope

- Add small, high-value keyboard shortcuts for common Now-page actions.
- Improve focus movement and keyboard-first interaction where Streamlit supports it cleanly.
- Keep shortcuts discoverable and optional.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Avoid brittle browser-specific shortcut behavior.

#### Acceptance criteria

- Observable behavior:
  - Users can trigger a small set of common actions with the keyboard.
  - Focus movement is more predictable after common actions.
  - Mouse-based flows remain unchanged and fully supported.
- Test expectations:
  - Add focused page or integration coverage for any shortcut-triggered behavior that is testable.
  - Add service coverage where shortcut handlers call existing actions.

#### Out-of-scope

- Broad command-palette behavior.
- Browser-extension-style shortcut handling.
- Large accessibility overhaul outside the Now page.

#### Rollback plan

- Revert shortcut bindings and focus-navigation changes only.
- Keep the underlying action services unchanged so rollback is isolated.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — wiring existing actions to keyboard events; mostly integration work with straightforward scope.

### PR 1.4 - Quick actions and low-risk interaction polish

#### Goals/Scope

- Add small interaction wins on the Now page.
- Prioritize quick snooze presets and other low-risk action affordances.
- Improve visible explanations and transition feedback where helpful.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep the page visually familiar.

#### Acceptance criteria

- Observable behavior:
  - Users can perform common follow-up actions in fewer clicks.
  - Existing action flows remain intact.
  - Explanatory copy remains clear and concise.
- Test expectations:
  - Add targeted page or integration coverage for new quick actions.
  - Existing action-flow tests continue to pass.

#### Out-of-scope

- Rulebook.
- Dashboard changes.

#### Rollback plan

- Revert the new quick-action controls only.
- Keep the underlying action services unchanged so rollback is low risk.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — small UI additions like snooze presets; low-risk, well-scoped changes.

### PR 1.5 - Lightweight Now-page instrumentation

#### Goals/Scope

- Add lightweight timing and action instrumentation for the Now page.
- Capture enough signal to compare before/after experience during rollout.
- Keep instrumentation local and simple.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Do not add telemetry that requires external services.

#### Acceptance criteria

- Observable behavior:
  - No user-visible behavior changes besides optional logs or internal metrics support.
  - Timing data is available for render and key action flows.
- Test expectations:
  - Unit tests cover instrumentation helpers if added.
  - Existing functional tests remain unchanged and green.

#### Out-of-scope

- Dashboard surfacing of new metrics.
- Remote analytics.
- Rulebook logic.

#### Rollback plan

- Remove the instrumentation helpers and log calls.
- No schema or persistent user-data rollback should be required.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — lightweight timing and logging; simple, local instrumentation.

---

## Phase 2 - Rulebook core engine

### Phase goals

- Introduce explicit, typed rule evaluation for open-item sections.
- Preserve current behavior with built-in defaults.
- Keep the matching logic deterministic and explainable.

### Phase exit criteria

- The application can evaluate open-item rules in a stable order.
- Default rules reproduce current behavior.
- Section explanations can be surfaced to the UI.

### PR 2.1 - Add typed rulebook contracts and default definitions

#### Goals/Scope

- Define typed models for rulebook settings, rule definitions, conditions, and match results.
- Define the built-in default rules that reproduce current Risk and Action required behavior.
- Define the fallback semantics for Upcoming and Concluded.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep data shapes simple and explicit.

#### Acceptance criteria

- Observable behavior:
  - No user-visible behavior changes yet.
  - Default definitions are clearly expressed in code and documentation.
- Test expectations:
  - Add unit tests for default rule definitions and validation.
  - Add tests that prove the default rules mirror current section semantics.

#### Out-of-scope

- Rulebook editor UI.
- Persistence changes beyond what is necessary for typed defaults.
- Switching the Now page to use the new engine.

#### Rollback plan

- Revert the typed rulebook contracts.
- Keep old query-driven behavior untouched and active.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — foundational design for a new subsystem; getting typed models, conditions, and defaults right affects all downstream work.

### PR 2.2 - Implement rule evaluation engine for open handoffs

#### Goals/Scope

- Implement exclusive, priority-based rule evaluation for open handoffs.
- Return both the matched section and a concise match explanation.
- Keep Concluded outside the rule engine.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Preserve one source of truth for matching behavior.

#### Acceptance criteria

- Observable behavior:
  - The engine can evaluate open handoffs against enabled rules in a stable order.
  - The engine produces deterministic section matches and reasons.
- Test expectations:
  - Add focused unit tests for rule evaluation order, exclusivity, and match explanation.
  - Add comparison tests showing default rules produce the same outcomes as current logic.

#### Out-of-scope

- UI integration.
- Rulebook editing.
- Per-project rules.
- Non-exclusive rule behavior.

#### Rollback plan

- Revert the evaluation engine.
- Continue using the old section query path unchanged.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — core logic for rule evaluation; deterministic matching, exclusivity, and match explanations require careful handling of edge cases.

### PR 2.3 - Persist global rulebook settings

#### Goals/Scope

- Persist the global rulebook in the existing settings JSON.
- Add validation, fallback behavior, and reset-to-default handling.
- Keep malformed settings from breaking the app.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Avoid a database schema change in this release phase.

#### Acceptance criteria

- Observable behavior:
  - Invalid or missing rulebook settings fall back cleanly to defaults.
  - The app remains usable even if the settings file contains bad data.
- Test expectations:
  - Add settings-service tests for load, save, invalid payload fallback, and reset behavior.

#### Out-of-scope

- Rulebook editor UI.
- Per-project settings.
- Import/export changes beyond local settings persistence.

#### Rollback plan

- Revert rulebook persistence support.
- Ignore saved rulebook data and use built-in defaults only.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — follows existing settings JSON patterns; validation and fallback are well-specified.

---

## Phase 3 - Rulebook adoption on the Now page

### Phase goals

- Make the Now page use the rulebook for open-item sections.
- Preserve current defaults for existing users.
- Make section membership easier to understand.

### Phase exit criteria

- The Now page renders rule-based open sections correctly.
- Match explanations are visible to users.
- Default users experience no unexpected behavior shift.

### PR 3.1 - Switch Now-page sectioning to rulebook-backed matching

#### Goals/Scope

- Replace hard-coded open-section orchestration with rulebook-backed results.
- Keep Upcoming as the unmatched open-item fallback.
- Keep Concluded lifecycle-driven.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Preserve the current default section names and order.

#### Acceptance criteria

- Observable behavior:
  - A default install still behaves like today.
  - Open handoffs are grouped through the rule engine rather than hard-coded page logic.
  - Concluded behavior remains unchanged.
- Test expectations:
  - Existing page and integration tests still pass after updates for new internals.
  - Add focused tests for default rulebook parity on the Now page.

#### Out-of-scope

- Rulebook editing UI.
- New custom sections enabled by the user.
- Dashboard integration.

#### Rollback plan

- Revert the Now-page integration layer.
- Restore the previous query-based grouping path.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — critical integration point; perfect parity with existing behavior and correct rulebook wiring require careful reasoning.

### PR 3.2 - Surface "why this matched" explanations in the UI

#### Goals/Scope

- Display concise explanations for why a handoff appears in a rulebook-driven section.
- Generalize the idea already used for Risk reasoning.
- Keep explanations short and operational.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Avoid noisy or verbose UI.

#### Acceptance criteria

- Observable behavior:
  - Users can understand why an item is in Risk or Action required.
  - Explanations remain concise and do not clutter the page.
- Test expectations:
  - Add page-level coverage for rendered explanations.
  - Existing section-render tests still pass.

#### Out-of-scope

- Full rule editor.
- Analytics on why-rules match.
- Advanced explanation customization.

#### Rollback plan

- Remove explanation rendering while keeping rulebook matching intact.
- Fall back to minimal section headers if needed.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — mostly presentation logic; displaying existing match explanations in the UI.

---

## Phase 4 - Rulebook editor in System Settings

### Phase goals

- Let users review and adjust global open-item rules.
- Keep editing safe, simple, and recoverable.
- Provide a clear path back to defaults.

### Phase exit criteria

- Users can inspect and update rules from System Settings.
- The editor prevents invalid or dangerous states.
- Users can reset to built-in defaults.

### PR 4.1 - Read-only rulebook preview and reset flow

#### Goals/Scope

- Add a read-only rulebook summary in System Settings.
- Show current rules, order, and basic match semantics.
- Add reset-to-default capability before enabling full editing.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep the settings page compact and understandable.

#### Acceptance criteria

- Observable behavior:
  - Users can see the active global rulebook.
  - Users can reset the rulebook safely to built-in defaults.
- Test expectations:
  - Add settings-page tests for preview rendering and reset behavior.
  - Add service tests for reset semantics.

#### Out-of-scope

- Full rule editing.
- Creating arbitrary new sections.
- Per-project overrides.

#### Rollback plan

- Remove the preview/reset UI.
- Keep the underlying persisted defaults and engine available.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — read-only preview and reset; straightforward UI with clear behavior.

### PR 4.2 - Minimal editable rulebook UI

#### Goals/Scope

- Allow editing of enabled state, priority/order, and supported conditions for global rules.
- Keep the editor intentionally small and constrained in v1.
- Validate all edits before applying them.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Do not expose advanced condition composition unless already supported cleanly by the engine.

#### Acceptance criteria

- Observable behavior:
  - Users can modify supported rule settings and save them.
  - Invalid configurations are rejected with clear messages.
  - The Now page reflects saved rulebook changes on refresh.
- Test expectations:
  - Add settings-page tests for save, validation, and error handling.
  - Add service tests for persistence and evaluation with user-edited rules.

#### Out-of-scope

- Arbitrary nested condition builders.
- Per-project rulebooks.
- Multi-match sections.

#### Rollback plan

- Revert the editing UI and keep read-only preview/reset support.
- Preserve fallback-to-default behavior if saved configs prove unstable.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — form handling, validation, and error states; more edge cases and interaction complexity.

### PR 4.3 - Support user-defined additional open sections

#### Goals/Scope

- Allow users to add more global open-item sections beyond the built-in defaults.
- Keep Upcoming as the unmatched fallback and Concluded as lifecycle-driven.
- Limit the scope to small, well-validated custom sections.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Preserve deterministic first-match-wins behavior.

#### Acceptance criteria

- Observable behavior:
  - Users can create, order, enable, disable, and remove custom open sections.
  - Default behavior remains available through reset.
- Test expectations:
  - Add service tests for custom-section creation and matching.
  - Add settings-page tests for add/remove/reorder flows.
  - Add Now-page tests for custom section rendering and fallback behavior.

#### Out-of-scope

- Per-project sections.
- Arbitrary free-form scripting.
- Advanced visual customization.

#### Rollback plan

- Revert custom-section creation while preserving built-in rule support.
- Reset all custom sections to defaults if rollback is needed in production-like environments.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — extends engine and UI with new capabilities; add/remove/reorder flows and matching semantics involve more moving parts.

---

## Phase 5 - Hardening and release readiness

### Phase goals

- Lock in behavior with focused tests.
- Confirm the release is stable under default and customized rulebook states.
- Prepare release notes and user-facing guidance.

### Phase exit criteria

- Default behavior is stable.
- Customized rulebook behavior is stable.
- Documentation and release notes are ready.

### PR 5.1 - Expand parity and regression coverage

#### Goals/Scope

- Add targeted tests that compare old default semantics to new rulebook-backed semantics.
- Add regression tests for customized rulebooks.
- Add coverage for settings corruption and fallback behavior.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep tests focused and high-signal.

#### Acceptance criteria

- Observable behavior:
  - No user-visible change beyond increased confidence and stability.
- Test expectations:
  - Focused data, service, page, and integration tests pass for default and customized rulebooks.
  - No broad, low-signal test expansion.

#### Out-of-scope

- New product features.
- New analytics views.
- AI features.

#### Rollback plan

- Revert new tests only if they are found to be incorrect.
- Keep functional code changes isolated from test-only changes where possible.

**AI model suggestion:** Harder (gpt-5.4, opus-4.6, codex-5.3) — parity and regression tests require understanding both old and new semantics; designing high-signal coverage benefits from deeper reasoning.

### PR 5.2 - Release notes and operator guidance

#### Goals/Scope

- Update release notes, README, and any operator-facing guidance needed for the new behavior.
- Explain the default rulebook, reset path, and customization scope.

#### Constraints

- Do not change public API.
- No new deps.
- Keep backward compatibility.
- Keep user-facing guidance concise and practical.

#### Acceptance criteria

- Observable behavior:
  - Users can understand what changed and how to return to defaults.
- Test expectations:
  - Documentation-only verification is sufficient.

#### Out-of-scope

- Additional feature work.
- New settings flows.
- AI features.

#### Rollback plan

- Revert documentation updates independently if needed.
- Functional code remains untouched.

**AI model suggestion:** Fast (sonnet-4.6, gemini-3-flash, cursor composer 1.5) — prose and explanation; straightforward documentation updates.

---

## Release-wide acceptance criteria

The release is successful when all of the following are true:

- The Now page feels more stable and less disruptive during common actions.
- Default users still get the same practical sectioning behavior they get today.
- Users can understand why an item is in a given rulebook-driven section.
- Users can safely review, edit, and reset global rulebook settings.
- Upcoming remains the fallback for unmatched open items.
- Concluded remains lifecycle-driven and stable.
- The system handles invalid settings safely by falling back to defaults.

## Release-wide constraints

- Do not change public API.
- No new deps unless a follow-up release makes a stronger case.
- Keep backward compatibility.
- Keep the current architecture boundary: pages -> services -> data.
- Keep rule evaluation deterministic and explicit.
- Avoid broad schema changes unless the implementation proves they are necessary.

## Release-wide rollback strategy

- Keep old query-driven semantics available until rulebook-backed defaults are validated.
- Land the release in small PRs so any one piece can be reverted independently.
- Prefer additive service contracts before replacement of existing page behavior.
- Keep default rule definitions versioned in code so the app can reset safely.
- Ensure invalid persisted settings cannot brick the UI.

## Testing strategy by phase

### Data and logic tests

- Use focused query and rule-evaluation tests for section semantics.
- Add parity tests for default rule behavior against current behavior.
- Add settings validation and fallback tests.

### Page and UI tests

- Extend Now-page tests for rulebook-backed rendering and explanations.
- Extend System Settings tests for preview, edit, validation, and reset flows.

### Integration tests

- Validate add, conclude, reopen, snooze, and edit flows still work after the UX changes.
- Validate default rulebook behavior end-to-end.
- Validate a customized rulebook end-to-end once editing ships.

## Risks and mitigations

### Risk: rulebook adds too much complexity too early

Mitigation:

- Keep v1 global only.
- Keep rules exclusive and priority-based.
- Keep the editor constrained.

### Risk: default behavior drifts from current semantics

Mitigation:

- Add parity tests before and during rulebook adoption.
- Preserve built-in defaults that intentionally mirror current logic.

### Risk: Streamlit state changes create new UX regressions

Mitigation:

- Ship Now-page smoothness improvements in small PRs.
- Keep integration coverage around check-in, reopen, snooze, and add flows.

### Risk: malformed local settings break the app

Mitigation:

- Validate on load.
- Fall back to defaults.
- Expose reset behavior in System Settings.

## Deferred items

The following items are intentionally excluded from this release:

- AI-assisted form creation.
- AI-generated insights or predictive risk detection.
- Per-project rulebooks.
- Multi-match section behavior.
- Large Dashboard feature expansion.
- Major visual redesign of the Now page.

## Suggested execution order

1. Phase 1 - Now page foundation and smoothness.
2. Phase 2 - Rulebook core engine.
3. Phase 3 - Rulebook adoption on the Now page.
4. Phase 4 - Rulebook editor in System Settings.
5. Phase 5 - Hardening and release readiness.

## Final recommendation

Ship this release as a deliberate UX-and-configuration release.

Start by making the Now page calmer and more stable. Then introduce the rulebook in a way that keeps current behavior as the default, keeps matching explainable, and keeps rollback simple. If execution stays disciplined and PRs stay small, this release should improve day-to-day usability without destabilizing the core handoff workflow.
