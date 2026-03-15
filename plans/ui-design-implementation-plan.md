# UI Design Implementation Plan

Implementation plan derived from the release plan (`plans/release-plan-2026.3.11.md`) and current codebase state. This document provides a structured, actionable implementation roadmap for the Now page UX and rulebook features.

---

## 1. Design Spec Summary

### Source document

- **Primary source:** `plans/release-plan-2026.3.11.md`
- **Scope:** Two product themes — (1) Now page speed/smoothness, (2) configurable rulebook for open-item sections

### Product goals

| Goal | Description |
|------|-------------|
| **Primary** | Reduce friction on the Now page; preserve user context; add keyboard shortcuts; introduce rulebook for sections; keep Upcoming and Concluded stable |
| **Secondary** | Improve observability; make section membership explainable; consistent status feedback |
| **Non-goals** | No AI features; no large Dashboard redesign; no new deps; no DB schema change unless necessary |

### Key design decisions

- **Rulebook:** Global only, exclusive first-match-wins, stored in settings JSON.
- **UI placement:** Rulebook editing in System Settings; Now page stays execution-focused.
- **Architecture:** Pages → services → data; single source of truth for section membership.

---

## 2. Current State vs Design Spec

### Already implemented (verified in codebase)

| Component | Location | Status |
|-----------|----------|--------|
| Now snapshot service | `handoff.services.get_now_snapshot` | ✅ Exists |
| Rulebook core | `handoff.core.rulebook`, `BuiltInSection` | ✅ Exists |
| Rulebook settings | `handoff.services.settings_service`, `get_rulebook_settings` | ✅ Exists |
| Now page uses snapshot | `now.py` calls `get_now_snapshot` | ✅ Exists |
| Section preview counts | `get_rulebook_section_preview_counts` | ✅ Exists |
| Projects autosave | `autosave.py` | ✅ Exists |

### Likely implemented (to confirm)

| Component | Location | Notes |
|-----------|----------|-------|
| Match explanations | `handoff.core.rulebook`, page models | Check if "why matched" is surfaced in UI |
| Rulebook editor UI | `system_settings.py` | Check for preview, edit, reset flows |
| Custom sections | Rulebook models/settings | Check if user-defined sections are supported |

### Not yet implemented / partial

| Component | Spec PR | Status |
|-----------|---------|--------|
| Reduced Now-page reruns | PR 1.2 | May need autosave/state-preservation improvements |
| Keyboard shortcuts | PR 1.3 | Check if any shortcuts exist |
| Quick actions (snooze presets, etc.) | PR 4.1 | Check for presets and quick-action affordances |
| Lightweight instrumentation | PR 1.5 | Check `handoff.instrumentation` or similar |
| Parity/regression tests | PR 5.1 | Verify default rulebook vs legacy parity tests |

---

## 3. Implementation Phases

### Phase 1 — Now Page Foundation and Smoothness

**Goal:** Make the Now page feel faster and less disruptive.

| Task | Priority | Dependencies | Deliverables |
|------|----------|--------------|--------------|
| **1.1 Verify snapshot contract** | High | None | Confirm `get_now_snapshot` returns typed contract; page uses it exclusively; tests cover contract |
| **1.2 Reduce disruptive reruns** | High | 1.1 | Apply Projects-style autosave/partial-update patterns to add/edit/snooze/check-in/reopen; preserve focus/context |
| **1.3 Keyboard shortcuts** | Medium | 1.2 | Add shortcuts for common actions; ensure discoverability (tooltip or help) |
| **1.4 Quick actions** | Medium | 1.2 | Snooze presets; low-risk interaction polish |
| **1.5 Instrumentation** | Low | 1.1 | Lightweight timing/logging for render and key actions |

**Phase exit criteria:**

- Snapshot contract is stable and tested.
- Common actions preserve context better.
- Default behavior unchanged for users.

---

### Phase 2 — Rulebook Core Engine (Verify/Extend)

**Goal:** Ensure rule evaluation is explicit, typed, and explainable.

| Task | Priority | Dependencies | Deliverables |
|------|----------|--------------|--------------|
| **2.1 Verify rulebook contracts** | High | None | Confirm typed models for rules, conditions, match results; default rules mirror current semantics |
| **2.2 Verify rule engine** | High | 2.1 | Exclusive priority-based evaluation; deterministic section matches; match explanations |
| **2.3 Verify persistence** | High | 2.1 | Load/save in settings JSON; fallback on invalid data; reset to defaults |

**Phase exit criteria:**

- Engine evaluates open handoffs in stable order.
- Default rules reproduce current behavior.
- Match explanations available for UI.

---

### Phase 3 — Rulebook Adoption on Now Page (Verify/Extend)

**Goal:** Now page uses rulebook for open sections; explanations visible.

| Task | Priority | Dependencies | Deliverables |
|------|----------|--------------|--------------|
| **3.1 Verify rulebook-backed sectioning** | High | Phase 2 | Open sections driven by rule engine; Upcoming = fallback; Concluded lifecycle-driven |
| **3.2 Surface match explanations** | Medium | 3.1 | Display "why this matched" in Risk/Action required items |

**Phase exit criteria:**

- Default install behaves like spec.
- Users can understand why items are in each section.

---

### Phase 4 — Rulebook Editor in System Settings

**Goal:** Users can review, edit, and reset rulebook.

| Task | Priority | Dependencies | Deliverables |
|------|----------|--------------|--------------|
| **4.1 Read-only preview + reset** | High | Phase 3 | Summary of rules, order, semantics; reset-to-default button |
| **4.2 Editable rulebook UI** | High | 4.1 | Edit enabled state, priority, conditions; validation; save |
| **4.3 Custom sections (optional)** | Medium | 4.2 | Add/remove/reorder custom open sections |

**Phase exit criteria:**

- Users can inspect and update rules.
- Invalid configs rejected with clear messages.
- Reset restores built-in defaults.

---

### Phase 5 — Hardening and Release Readiness

**Goal:** Lock in behavior with tests and documentation.

| Task | Priority | Dependencies | Deliverables |
|------|----------|--------------|--------------|
| **5.1 Parity and regression coverage** | High | Phase 4 | Tests comparing default rulebook to legacy semantics; settings corruption fallback |
| **5.2 Release notes and guidance** | Medium | 5.1 | RELEASE_NOTES.md; user guidance for rulebook, reset, customization |

**Phase exit criteria:**

- Default and customized rulebooks covered by tests.
- Docs explain changes and reset path.

---

## 4. Suggested Execution Order

```
1. Phase 1.1 — Verify snapshot contract
2. Phase 2.1–2.3 — Verify rulebook engine and persistence
3. Phase 3.1–3.2 — Verify rulebook adoption and explanations
4. Phase 1.2 — Reduce reruns (aligns with Projects autosave)
5. Phase 4.1–4.2 — Rulebook preview and editor
6. Phase 1.3–1.5 — Keyboard shortcuts, quick actions, instrumentation
7. Phase 4.3 — Custom sections (if in scope)
8. Phase 5.1–5.2 — Tests and release notes
```

---

## 5. Files to Touch (Reference)

| Phase | Primary files |
|-------|---------------|
| 1.1 | `services/handoff_service.py`, `pages/now.py`, `tests/test_pages_now.py`, `tests/test_todo_service.py` |
| 1.2 | `pages/now.py`, `pages/now_forms.py`, `autosave.py`, `tests/test_uat_seeded.py` |
| 1.3–1.5 | `pages/now.py`, `instrumentation` or similar, tests |
| 2.x | `core/rulebook.py`, `services/settings_service.py`, `data/queries.py`, `tests/test_rulebook.py`, `tests/test_settings_service.py` |
| 3.x | `pages/now.py`, `pages/now_forms.py`, `core/page_models.py` |
| 4.x | `pages/system_settings.py`, `services/settings_service.py`, `services/handoff_service.py` |
| 5.x | `tests/*`, `RELEASE_NOTES.md`, `README.md` |

---

## 6. Constraints and Guardrails

- **No public API changes** for external consumers.
- **No new dependencies** unless justified.
- **Backward compatibility** for default users.
- **Architecture:** Pages → services → data (no direct `handoff.data` from pages).
- **Rollback:** Each phase/PR should be independently revertible.

---

## 7. Testing Strategy

| Area | Commands |
|------|----------|
| Data/rulebook | `uv run pytest tests/test_rulebook.py tests/test_data.py tests/test_settings_service.py` |
| Pages/UI | `uv run pytest tests/test_pages_now.py tests/test_pages_system_settings.py tests/test_dashboard.py` |
| Integration | `uv run pytest tests/test_app_integration.py tests/test_uat_seeded.py` |
| Full CI | `uv run handoff-dev ci` |

---

## 8. Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Default behavior drifts | Parity tests; preserve built-in default definitions |
| Streamlit state regressions | Small PRs; integration coverage for add/conclude/reopen/snooze |
| Malformed settings | Validate on load; fallback to defaults; reset in System Settings |
| Rulebook complexity creep | Keep v1 global-only; exclusive rules; constrained editor |

---

## 9. Done Criteria (Release-Wide)

The implementation is complete when:

- [ ] Now page feels more stable during common actions
- [ ] Default users get the same sectioning as today
- [ ] Users understand why items are in rulebook-driven sections
- [ ] Users can review, edit, and reset rulebook in System Settings
- [ ] Upcoming remains fallback; Concluded remains lifecycle-driven
- [ ] Invalid settings fall back to defaults safely
- [ ] Full CI passes: `uv run handoff-dev ci`
