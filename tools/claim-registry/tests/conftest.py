"""Shared test fixtures and helpers."""

from __future__ import annotations

import hashlib
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")

#: The shared toolkit lives in the sibling ``common/`` directory of the unit
#: (“import toolkit” is a dev-time import; the packaged .pyz bundles it).
UNIT_ROOT = os.path.dirname(HERE)
COMMON = os.path.join(os.path.dirname(UNIT_ROOT), "common")
if COMMON not in sys.path:
    sys.path.insert(0, COMMON)

#: Canonical acceptance pins (spec: PR #17 body raw API-string hash; plan doc hash).
#: The golden sources are ONLY the committed in-tree fixtures: a missing file is
#: a broken checkout and fails hard (never skips); altered bytes fail the pins.
PR_BODY_SHA = "10b5b3018d8928ce607735a6c31181be463f983bbc21ba07aa1985b9b4e1c2a7"
PLAN_DOC_SHA = "62460fba139488f273b8c494ab203b9817b625a3c6146955cf00432659624a07"

PR_BODY_PATH = os.path.join(FIXTURES, "pr17-body-v2.md")
PLAN_DOC_PATH = os.path.join(FIXTURES, "contract-adequacy-validation-plan.md")


def load_golden(path, expected_sha, expected_len):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"committed golden fixture missing: {path} "
            "(hermetic tests never fall back to machine-local copies)"
        )
    with open(path, "rb") as fh:
        data = fh.read()
    assert len(data) == expected_len, (
        f"{path}: length {len(data)} != pinned {expected_len}"
    )
    assert hashlib.sha256(data).hexdigest() == expected_sha, (
        f"{path}: sha256 mismatch (file may have been altered)"
    )
    return data


@pytest.fixture(scope="session")
def pr_body() -> bytes:
    return load_golden(PR_BODY_PATH, PR_BODY_SHA, 10385)


@pytest.fixture(scope="session")
def plan_doc() -> bytes:
    return load_golden(PLAN_DOC_PATH, PLAN_DOC_SHA, 10428)
