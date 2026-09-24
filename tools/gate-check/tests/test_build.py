"""Artifact/describe/pin tests for the gate-check unit itself."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

UNIT = Path(__file__).resolve().parents[1]
ARTIFACT_NAME = "gate-check-0.1.0.pyz"


def _build(tmp_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(UNIT / "build.py"),
         "--out-dir", str(tmp_path / "dist"), "--tool-json", str(tmp_path / "TOOL.json")],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_describe_schema():
    proc = subprocess.run(
        [sys.executable, "-m", "gate_check.cli", "--describe"],
        capture_output=True, text=True, cwd=str(UNIT),
    )
    assert proc.returncode == 0, proc.stderr
    described = json.loads(proc.stdout)
    assert described["schema_version"] == "tool-unit/1"
    assert described["name"] == "gate-check"
    assert described["version"] == "0.1.0"
    assert described["artifact"] is None
    assert described["dependencies"] == []
    assert "check" in described["commands"]
    assert described["commands"]["check"]["exit_codes"]["0"].startswith("all checks passed")
    assert not proc.stdout.endswith("\n\n")


def test_build_is_deterministic(tmp_path):
    a = _build(tmp_path / "a")
    b = _build(tmp_path / "b")
    artifact_a = Path(a["artifact"])
    artifact_b = Path(b["artifact"])
    assert a["sha256"] == b["sha256"]
    assert artifact_a.read_bytes() == artifact_b.read_bytes()
    tool_a = (tmp_path / "a" / "TOOL.json").read_bytes()
    tool_b = (tmp_path / "b" / "TOOL.json").read_bytes()
    assert tool_a == tool_b
    parsed = json.loads(tool_a)
    assert parsed["artifact"]["sha256"] == a["sha256"]
    assert parsed["artifact"]["file"] == f"dist/{ARTIFACT_NAME}"
    assert parsed["artifact"]["size"] == artifact_a.stat().st_size


def test_check_pin(tmp_path):
    summary = _build(tmp_path)
    artifact = Path(summary["artifact"])
    ok = subprocess.run(
        [sys.executable, str(artifact), "--check-pin", summary["sha256"]],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0, ok.stderr
    bad = subprocess.run(
        [sys.executable, str(artifact), "--check-pin", "0" * 64],
        capture_output=True, text=True,
    )
    assert bad.returncode == 1
    assert "mismatch" in bad.stderr


def test_describe_from_built_artifact_matches_tool_json(tmp_path):
    summary = _build(tmp_path)
    artifact = Path(summary["artifact"])
    desc = subprocess.run(
        [sys.executable, str(artifact), "--describe"], capture_output=True, text=True
    )
    assert desc.returncode == 0, desc.stderr
    described = json.loads(desc.stdout)
    tool = json.loads((tmp_path / "TOOL.json").read_bytes())
    tool.pop("artifact")
    tool["artifact"] = None
    assert described == tool
