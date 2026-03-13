# Custom Copilot agents for Handoff

This directory contains project-specific custom agents for GitHub Copilot.

## Included agents

- `handoff-ci-triage.agent.md`  
  Use when CI fails or a regression appears and you need root-cause diagnosis plus minimal fixes.

- `handoff-feature-implementer.agent.md`  
  Use for product work across Streamlit pages/services with architecture-safe implementation and test updates.

- `handoff-release-build.agent.md`  
  Use when preparing a release (version bump, release notes, CI/build validation).

## Notes

- Keep agent prompts focused (what changed, expected outcome, constraints).
- Prefer running targeted checks first, then broader CI commands as confidence grows.
