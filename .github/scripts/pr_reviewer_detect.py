#!/usr/bin/env python3
"""
Classify whether a PR requires a human reviewer or can rely on AI reviewers.

Uses path-based rules first (Haiku-limited: rule-augmented). If all paths are
agent-safe and ANTHROPIC_API_KEY is set, calls Haiku-4.5-thinking for optional
override (e.g. security keywords, breaking changes).

Reads from env: PR_TITLE, PR_BODY, PR_FILES (newline-separated), PR_ADDITIONS,
PR_DELETIONS, ANTHROPIC_API_KEY (optional). Writes to stdout: reviewer:human
or reviewer:ai.
"""

from __future__ import annotations

import os
import sys

HIGH_RISK_PATTERNS = [
    "src/handoff/models.py",
    "src/handoff/migrations/",
    "src/handoff/updater.py",
    "pyproject.toml",
    ".github/CODEOWNERS",
    ".github/workflows/",
]


def matches_high_risk(filename: str) -> bool:
    for pattern in HIGH_RISK_PATTERNS:
        if pattern.endswith("/"):
            if filename.startswith(pattern):
                return True
        elif filename == pattern:
            return True
    return False


def path_classify(filenames: list[str]) -> str:
    """Return 'human' if any high-risk path touched, else 'ai'."""
    for f in filenames:
        if matches_high_risk(f):
            return "human"
    return "ai"


def haiku_override(
    title: str, body: str, files: list[str], additions: int, deletions: int
) -> str | None:
    """Call Haiku for optional override. Return 'human' or 'ai' or None if unavailable."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    body_preview = (body or "")[:500]
    file_list = "\n".join(f"- {f}" for f in files[:30])
    if len(files) > 30:
        file_list += f"\n- ... and {len(files) - 30} more"

    prompt = f"""Classify this PR. Reply with ONLY one line: HUMAN or AI.

CRITERIA:
- HUMAN: Security words (security, auth, vulnerability, CVE), breaking change, or very large
  (500+ lines, 20+ files).
- AI: Otherwise.

TITLE: {title}

BODY (preview): {body_preview}

FILES ({len(files)} total):
{file_list}

CHANGES: +{additions} -{deletions}

Reply with exactly: HUMAN or AI"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=16,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip().upper() if msg.content else ""
        if "HUMAN" in text:
            return "human"
        return "ai"
    except Exception:
        return None


def main() -> None:
    title = os.environ.get("PR_TITLE", "")
    body = os.environ.get("PR_BODY", "")
    files_raw = os.environ.get("PR_FILES", "")
    files = [f.strip() for f in files_raw.split("\n") if f.strip()]
    additions = int(os.environ.get("PR_ADDITIONS", "0"))
    deletions = int(os.environ.get("PR_DELETIONS", "0"))

    result = path_classify(files)
    if result == "human":
        print("reviewer:human", flush=True)
        return

    override = haiku_override(title, body, files, additions, deletions)
    if override == "human":
        print("reviewer:human", flush=True)
    else:
        print("reviewer:ai", flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
