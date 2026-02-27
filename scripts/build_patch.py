"""Legacy helper for building source-only patch zips.

This module is kept for historical reference but is no longer used in the
preferred build pipeline. For production updates, always use the obfuscated
patch flow:

    uv run todo build-zip
    uv run todo build-obfuscated-patch
"""

from __future__ import annotations
