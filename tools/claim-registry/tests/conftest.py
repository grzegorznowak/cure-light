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
PR_BODY_SHA = "10b5b3018d8928ce607735a6c31181be463f983bbc21ba07aa1985b9b4e1c2a7"
PLAN_DOC_SHA = "62460fba139488f273b8c494ab203b9817b625a3c6146955cf00432659624a07"

PR_BODY_PATHS = [
    "/tmp/pr17-body-v2.md",
    os.path.join(FIXTURES, "pr17-body-v2.md"),
]
PLAN_DOC_PATHS = [
    "/home/vscode/cure-light-bothends/docs/contract-adequacy-validation-plan.md",
    os.path.join(FIXTURES, "contract-adequacy-validation-plan.md"),
]


def _first_existing(paths):
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def load_golden(paths, expected_sha, expected_len):
    path = _first_existing(paths)
    if path is None:
        pytest.skip(f"golden source not found in {paths}")
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
    return load_golden(PR_BODY_PATHS, PR_BODY_SHA, 10385)


@pytest.fixture(scope="session")
def plan_doc() -> bytes:
    return load_golden(PLAN_DOC_PATHS, PLAN_DOC_SHA, 10428)
