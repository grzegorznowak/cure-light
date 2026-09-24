"""Built-artifact contract: deterministic .pyz, TOOL.json, check-pin, E2E run/check."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from toolkit import canonical_json

from gitrepo import commit, init_repo, write

UNIT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def built():
    proc = subprocess.run(
        [sys.executable, str(UNIT / "build.py")], cwd=UNIT, capture_output=True
    )
    assert proc.returncode == 0, proc.stderr.decode()
    tool = canonical_json.canonical_loads((UNIT / "TOOL.json").read_bytes())
    return tool, UNIT / tool["artifact"]["file"]


def test_tool_json_matches_describe(built):
    tool, artifact = built
    described = canonical_json.canonical_loads(
        subprocess.run(
            [sys.executable, str(artifact), "--describe"],
            capture_output=True,
            check=True,
        ).stdout
    )
    assert described == {**tool, "artifact": None}
    assert tool["artifact"]["file"] == "dist/census-0.1.0.pyz"
    assert tool["artifact"]["sha256"] == sha256(artifact)
    assert tool["artifact"]["size"] == artifact.stat().st_size
    sidecar = (UNIT / "dist" / "census-0.1.0.pyz.sha256").read_text().split()[0]
    assert sidecar == tool["artifact"]["sha256"]


def test_build_is_deterministic():
    shas = []
    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, str(UNIT / "build.py")], cwd=UNIT, capture_output=True
        )
        assert proc.returncode == 0, proc.stderr.decode()
        shas.append(sha256(UNIT / "dist" / "census-0.1.0.pyz"))
    assert shas[0] == shas[1]
    tool = canonical_json.canonical_loads((UNIT / "TOOL.json").read_bytes())
    assert tool["artifact"]["sha256"] == shas[-1]


def test_pyz_layout_and_shebang(built):
    _tool, artifact = built
    assert artifact.read_bytes()[:23] == b"#!/usr/bin/env python3\n"
    with zipfile.ZipFile(artifact) as zf:
        names = set(zf.namelist())
    assert {"__main__.py", "census/cli.py", "census/model.py", "toolkit/tool_unit.py"} <= names
    assert not any(name.startswith("tests/") or name.endswith(".pyc") for name in names)


def test_check_pin(built):
    tool, artifact = built
    pinned = tool["artifact"]["sha256"]
    ok = subprocess.run(
        [sys.executable, str(artifact), "--check-pin", pinned],
        capture_output=True,
    )
    assert ok.returncode == 0
    bad = subprocess.run(
        [sys.executable, str(artifact), "--check-pin", "0" * 64],
        capture_output=True,
    )
    assert bad.returncode == 1


def test_built_artifact_run_and_check(tmp_path, built):
    _tool, artifact = built
    repo = init_repo(tmp_path / "r")
    write(repo, "f.txt", "a\nb\n")
    base = commit(repo, "base")
    write(repo, "f.txt", "a\nB\n")
    subject = commit(repo, "subject")
    out = tmp_path / "c.json"

    run = subprocess.run(
        [
            sys.executable,
            str(artifact),
            "run",
            "--repo",
            str(repo),
            "--base",
            base,
            "--subject",
            subject,
            "--out",
            str(out),
            "--scratch",
            str(tmp_path / "scratch"),
        ],
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr.decode()
    payload = canonical_json.canonical_loads(out.read_bytes())
    assert payload["partition"]["ok"] is True
    assert payload["counts"]["parents"] == 1

    check = subprocess.run(
        [
            sys.executable,
            str(artifact),
            "check",
            "--census",
            str(out),
            "--repo",
            str(repo),
            "--scratch",
            str(tmp_path / "check"),
        ],
        capture_output=True,
    )
    assert check.returncode == 0, check.stderr.decode()
    report = canonical_json.canonical_loads(check.stdout)
    assert report["ok"] is True
    assert report["recomputed_census_hash"] == payload["census_hash"]
