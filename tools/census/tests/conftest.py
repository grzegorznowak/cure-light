"""Dev-time import paths: ``census`` package + shared ``toolkit``."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNIT = HERE.parent
COMMON = UNIT.parent / "common"

for path in (str(COMMON), str(UNIT)):
    if path not in sys.path:
        sys.path.insert(0, path)
