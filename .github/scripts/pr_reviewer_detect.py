#!/usr/bin/env python3
"""
Classify whether a PR requires a human reviewer or can rely on AI reviewers.

Path-based rules only (used by GitHub Action). The Cursor Cloud automation
provides the Haiku-based override when it runs on PR events.

Reads from env: PR_FILES (newline-separated). Writes to stdout: reviewer:human
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


def main() -> None:
    files_raw = os.environ.get("PR_FILES", "")
    files = [f.strip() for f in files_raw.split("\n") if f.strip()]

    result = path_classify(files)
    if result == "human":
        print("reviewer:human", flush=True)
    else:
        print("reviewer:ai", flush=True)


if __name__ == "__main__":
    main()
    sys.exit(0)
