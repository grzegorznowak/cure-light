import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.dirname(HERE)
COMMON = os.path.join(os.path.dirname(UNIT), "common")

for path in (UNIT, COMMON):
    if path not in sys.path:
        sys.path.insert(0, path)
