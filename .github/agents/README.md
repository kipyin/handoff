# Custom Copilot agents for Handoff

This directory contains project-specific custom agents for GitHub Copilot.

## Included agents

- `handoff-ci-triage.agent.md`  
  Use when CI fails or a regression appears and you need root-cause diagnosis plus minimal fixes.

- `handoff-feature-implementer.agent.md`  
  Use for product work across Streamlit pages/services with architecture-safe implementation and test updates.

- `handoff-release-build.agent.md`  
  Use when preparing a release (version bump, release notes, CI/build validation).

- `handoff-pr-reviewer-detection.agent.md`  
  Use to classify whether a PR requires a human reviewer or can rely on AI reviewers (Copilot + optional second AI). Designed for Haiku-4.5-thinking with limited reasoning; rule-augmented, not fully heuristic.

## PR Reviewer Detection (automation)

**Primary**: Cursor Cloud automation at cursor.com/automations — trigger on PR opened/pushed, use "Comment on Pull Request" tool, Haiku-4.5-thinking. No API key. See `.github/cursor-automation-pr-reviewer.md`.

**Optional GitHub Action**: `.github/workflows/pr-reviewer-detection.yml` applies `reviewer:human` / `reviewer:ai` labels via path-based rules. No API key. Use as fallback or to sync labels before the Cursor automation runs.

## Notes

- Keep agent prompts focused (what changed, expected outcome, constraints).
- Prefer running targeted checks first, then broader CI commands as confidence grows.
