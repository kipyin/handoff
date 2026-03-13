# Cursor Automation: PR Reviewer Detection

Set up at [cursor.com/automations](https://cursor.com/automations). Uses Haiku-4.5-thinking (limited reasoning) — rule-augmented, no API key required.

## Setup

1. Create a new automation at cursor.com/automations
2. **Trigger**: Pull request opened, Pull request pushed (synchronize)
3. **Tools**: Comment on Pull Request (required)
4. **Model**: Haiku-4.5-thinking (or equivalent fast model)
5. **Prompt**: Use the prompt below

## Prompt (paste into automation)

```
You classify whether this PR requires a human reviewer or can rely on AI reviewers (GitHub Copilot + optional second AI like GPT-5.4-high).

You have limited reasoning — use simple, rule-augmented logic.

**Always reviewer:human** (path-based):
- Touches src/handoff/models.py
- Touches src/handoff/migrations/
- Touches src/handoff/updater.py
- Touches pyproject.toml
- Touches .github/workflows/ or .github/CODEOWNERS

**Usually reviewer:ai** (agent-safe paths): data.py, db.py, services, pages, tests, docs, etc.

**Elevate to reviewer:human** if you detect (even with agent-safe paths):
- Security keywords: security, auth, vulnerability, CVE
- Breaking change: BREAKING, breaking change, migration required
- Very large: 500+ lines changed, or 20+ files across many layers

Output exactly one of: reviewer:human or reviewer:ai.

Then use the "Comment on Pull Request" tool to post a single comment:

If reviewer:human:
## reviewer:human — Manual review required

This PR requires a human reviewer before merge.

If reviewer:ai:
## reviewer:ai — AI reviewers OK

This PR can rely on GitHub Copilot and optional second AI reviewer. Merge when CI is green.

Keep the comment concise. Do not repeat analysis.
```

## GitHub Action (optional integration)

The workflow `.github/workflows/pr-reviewer-detection.yml` runs path-based classification and applies `reviewer:human` / `reviewer:ai` labels. No API key. Use it to:

- Apply labels immediately (path rules) before Cursor automation runs
- Provide a deterministic fallback when Cursor automation doesn't trigger
- Keep labels in sync when the Cursor automation adds its comment

Cursor automation (Haiku) and GitHub Action (path rules) can run in parallel — labels from the Action, richer comment from Cursor when it runs.
