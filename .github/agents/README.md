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

The workflow `.github/workflows/pr-reviewer-detection.yml` runs on every PR and applies `reviewer:human` or `reviewer:ai` labels. It uses path-based rules first; if `ANTHROPIC_API_KEY` is set as a repository secret and paths are agent-safe, Haiku-4.5-thinking may elevate to `reviewer:human` when it detects security keywords, breaking-change signals, or very large diffs.

- **Without** `ANTHROPIC_API_KEY`: path rules only (fast, deterministic).
- **With** `ANTHROPIC_API_KEY`: path rules + optional Haiku override for edge cases.

## Notes

- Keep agent prompts focused (what changed, expected outcome, constraints).
- Prefer running targeted checks first, then broader CI commands as confidence grows.
