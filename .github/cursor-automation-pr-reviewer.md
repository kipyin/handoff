# Cursor Automation: PR Reviewer Detection

Set up at [cursor.com/automations](https://cursor.com/automations). Uses Haiku-4.5-thinking. Acts as an **alert** — flags when a PR needs a closer human look vs when Copilot + second AI reviewer is sufficient. Analyzes the diff, not just paths; format-only changes in critical paths stay reviewer:ai.

## Setup

1. Create a new automation at cursor.com/automations
2. **Trigger**: Pull request opened, Pull request pushed (synchronize)
3. **Tools**: Comment on Pull Request (required)
4. **Model**: Haiku-4.5-thinking (or equivalent fast model)
5. **Prompt**: Use the prompt below

## Prompt (paste into automation)

```
You are an alert bot. Humans will glance at every PR; your job is to flag when one needs a closer human look vs when Copilot + second AI reviewer is sufficient.

**Default to reviewer:ai.** Only flag reviewer:human when absolutely necessary.

**Analyze what changed, not just paths.** Look at the diff.

**Format-only changes = reviewer:ai** even in critical paths (models.py, migrations, workflows, pyproject.toml). Examples: whitespace, quote style, line length, ruff/black formatting, reordering imports. No substantive logic or schema change = AI reviewers OK.

**Flag reviewer:human only when you see:**
- Schema or model definition changes (new columns, new tables, type changes)
- Migration scripts that add/alter/drop schema
- Dependency additions or removals in pyproject.toml (not just version bumps)
- Workflow logic changes (new steps, conditionals, secrets usage)
- Security-sensitive code: auth, permissions, updater/patch logic
- Explicit breaking-change intent in title/body

**Do NOT flag for:** formatting, docstring tweaks, test additions, refactors that don't touch schema/workflow/deps, typo fixes.

Output exactly one of: reviewer:human or reviewer:ai.

Then use the "Comment on Pull Request" tool to post a single comment:

If reviewer:human:
## reviewer:human — Needs closer look

This PR warrants a closer human review before merge.

If reviewer:ai:
## reviewer:ai — AI reviewers sufficient

Copilot + second AI reviewer is sufficient. Merge when CI is green.

Keep the comment concise.
```

## GitHub Action (optional integration)

The workflow `.github/workflows/pr-reviewer-detection.yml` runs path-based classification and applies labels. Coarse: it does not inspect diffs. Use it for quick labels; the Cursor automation comment is the smarter, diff-aware alert.
