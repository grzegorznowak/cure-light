import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.dirname(HERE)
if COMMON not in sys.path:
    sys.path.insert(0, COMMON)
