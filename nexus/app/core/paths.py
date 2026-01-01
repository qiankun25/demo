"""Path helpers for monorepo imports.

The repo is a monorepo where some shared libraries live outside the `nexus/` folder.
In Docker (when built with repo-root context), those folders are available at runtime.
This module makes imports resilient in local dev and container environments.
"""

from __future__ import annotations

import os
import sys
from typing import List


def _candidates() -> List[str]:
    here = os.path.abspath(os.path.dirname(__file__))  # nexus/app/core
    # repo root when running from source: .../demo-feature-nexus/nexus/app/core
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    return [
        os.path.join(repo_root, "tool_services", "libs", "contracts"),
    ]


def ensure_contracts_on_path() -> None:
    """Ensure `nexus_contracts` can be imported."""
    for p in _candidates():
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)


