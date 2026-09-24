"""gate-check: mechanical permission gate for a completed claim-registry run.

The unit is stdlib-only and deliberately does not consult git, a worktree, the
network, or an agent.  It re-derives bytes, hashes and flags from the recorded
artifacts of a run and emits ``gate-check-report/1``.
"""

from __future__ import annotations

import sys
from pathlib import Path

__version__ = "0.1.0"


def _ensure_toolkit() -> None:
    """Dev checkout only: make ``common/toolkit`` importable.

    In the packaged ``.pyz`` ``toolkit`` is a top-level package and this is a
    no-op.  In a dev checkout ``gate_check/`` sits next to ``common/`` and the
    shared helpers are imported by inserting ``common`` on ``sys.path``.
    """
    try:
        import toolkit  # noqa: F401
    except ModuleNotFoundError:
        common = Path(__file__).resolve().parents[2] / "common"
        if common.is_dir() and str(common) not in sys.path:
            sys.path.insert(0, str(common))


_ensure_toolkit()
