"""Bounded window tests (spec section 1.4)."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys

import pytest

from claim_registry.canonical import canonical_hash
from claim_registry.frame import Unit
from claim_registry.windows import (
    OversizedUnitError,
    WindowRecipeError,
    build_windows,
    validate_windows,
    window_recipe,
)

SRC = "repo#1:body"


def units(n: int, size: int = 10) -> list[Unit]:
    return [
        Unit(ordinal=i, kind="paragraph", start=i * size, end=(i + 1) * size,
             sha256=f"{i:064x}")
        for i in range(n)
    ]


def test_recipe_validation():
    assert window_recipe(4, 100, 1) == {
        "version": "1", "max_units": 4, "max_bytes": 100, "overlap_units": 1
    }
    for bad in [(0, 100, 0), (4, 0, 0), (4, 100, -1), (4, 100, 4), (4, 100, 5)]:
        with pytest.raises(WindowRecipeError):
            window_recipe(*bad)


def test_longest_prefix_and_tail_overlap():
    u = units(10, 10)
    manifest = build_windows(SRC, u, max_units=3, max_bytes=25, overlap_units=1)
    bounds = [(w["ordinal_start"], w["ordinal_end"]) for w in manifest["windows"]]
    assert bounds == [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
                      (6, 7), (7, 8), (8, 9)]
    assert manifest["windows"][0]["overlap_units"] == 0
    assert all(w["overlap_units"] == 1 for w in manifest["windows"][1:])
    assert manifest["recipe_hash"] == canonical_hash(manifest["recipe"])
    assert validate_windows(manifest, u, SRC) == []


def test_overlap_reduced_for_forward_progress_and_no_terminal_overlap():
    u = units(10, 10)
    manifest = build_windows(SRC, u, max_units=2, max_bytes=10, overlap_units=1)
    bounds = [(w["ordinal_start"], w["ordinal_end"]) for w in manifest["windows"]]
    # requested overlap 1 cannot make progress on single-unit windows
    assert bounds == [(i, i) for i in range(10)]
    assert manifest["windows"][0]["overlap_units"] == 0
    assert all(w["overlap_units"] == 0 for w in manifest["windows"][1:])
    assert validate_windows(manifest, u, SRC) == []


def _variable_units(sizes: list[int], kind: str = "paragraph") -> list[Unit]:
    out = []
    pos = 0
    for i, size in enumerate(sizes):
        out.append(Unit(ordinal=i, kind=kind, start=pos, end=pos + size,
                        sha256=f"{i:064x}"))
        pos += size
    return out


def test_overlap_reduction_admits_new_core_unit_5_5_5_5_18():
    """Requested tail overlap must never crowd out every new core unit.

    Regression: with sizes 5,5,5,5,18 and max_bytes=20/overlap=3 the old
    reduction only checked ordinal progress, so it emitted overlap-only
    windows (1..3, 2..3, 3..3) before finally reaching unit 4.
    """
    u = _variable_units([5, 5, 5, 5, 18])
    manifest = build_windows(SRC, u, max_units=64, max_bytes=20, overlap_units=3)
    bounds = [
        (w["ordinal_start"], w["ordinal_end"], w["overlap_units"])
        for w in manifest["windows"]
    ]
    assert bounds == [(0, 3, 0), (4, 4, 0)]
    for i, w in enumerate(manifest["windows"]):
        assert len(w["unit_ids"]) > w["overlap_units"], (
            f"window[{i}] is overlap-only: {w}"
        )
    assert validate_windows(manifest, u, SRC) == []


def test_overlap_reduction_terminates_within_bound(tmp_path):
    """Timed guard: the 5,5,5,5,18 case must terminate and stay progressing."""
    unit_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    common = os.path.join(os.path.dirname(unit_root), "common")
    script = (
        "import json, sys\n"
        "from claim_registry.frame import Unit\n"
        "from claim_registry.windows import build_windows\n"
        "sizes = [5, 5, 5, 5, 18]\n"
        "pos = 0\n"
        "units = []\n"
        "for i, size in enumerate(sizes):\n"
        "    units.append(Unit(ordinal=i, kind='paragraph', start=pos, end=pos+size, sha256=f'{i:064x}'))\n"
        "    pos += size\n"
        "manifest = build_windows('repo#1:body', units, 64, 20, 3)\n"
        "json.dump(manifest['windows'], sys.stdout)\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = common + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", script], cwd=unit_root, capture_output=True,
        text=True, env=env, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    windows = json.loads(proc.stdout)
    assert all(len(w["unit_ids"]) > w["overlap_units"] for w in windows), windows


def test_oversized_unit_is_named_error_not_split():
    u = units(3, 10)
    u[1] = Unit(ordinal=1, kind="fenced_code_block", start=10, end=60,
                sha256="1" * 64)
    with pytest.raises(OversizedUnitError) as excinfo:
        build_windows(SRC, u, max_units=8, max_bytes=45, overlap_units=1)
    assert "oversized unit" in str(excinfo.value)
    assert "adjust the bounded budget" in str(excinfo.value)


def test_empty_source_has_no_windows():
    manifest = build_windows(SRC, [], max_units=4, max_bytes=100, overlap_units=1)
    assert manifest["windows"] == []
    assert validate_windows(manifest, [], SRC) == []


def test_determinism():
    u = units(7, 10)
    assert build_windows(SRC, u, 3, 25, 1) == build_windows(SRC, u, 3, 25, 1)


def test_validate_windows_detects_tampering():
    u = units(6, 10)
    manifest = build_windows(SRC, u, max_units=3, max_bytes=25, overlap_units=1)
    bad = copy.deepcopy(manifest)
    bad["windows"][0]["unit_ids"] = bad["windows"][0]["unit_ids"] + ["made-up"]
    failures = validate_windows(bad, u, SRC)
    assert any("unknown unit ids" in f for f in failures)
    bad2 = copy.deepcopy(manifest)
    bad2["recipe_hash"] = "sha256:" + "0" * 64
    assert any("recipe_hash" in f for f in validate_windows(bad2, u, SRC))
    bad3 = copy.deepcopy(manifest)
    bad3["windows"][0]["overlap_units"] = 5
    assert validate_windows(bad3, u, SRC)
