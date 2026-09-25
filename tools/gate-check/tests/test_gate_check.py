"""End-to-end gate-check tests against a real baseline-produced run.

The happy-path fixture is produced once per session by
``tests/fixture_builder.py`` (baseline ``claim-registry`` capture/assemble/
validate on the committed in-tree fixture
``../claim-registry/tests/fixtures/pr17-body-v2.md``).  Each tamper test copies
the fixture into ``tmp_path`` first; the baseline and all repos stay read-only.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import fixture_builder
from toolkit import canonical_json

UNIT = Path(__file__).resolve().parents[1]
ARTIFACT_NAME = "gate-check-0.1.0.pyz"


def _run_gate(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(UNIT), env.get("PYTHONPATH", "")) if p
    )
    return subprocess.run(
        [sys.executable, "-m", "gate_check.cli", *(str(a) for a in args)],
        capture_output=True, text=True, cwd=str(cwd or UNIT), env=env,
    )


@pytest.fixture(scope="session")
def fixture(tmp_path_factory):
    if fixture_builder.find_baseline() is None:
        pytest.skip("baseline producer not available")
    dest = tmp_path_factory.mktemp("gate-fixture")
    try:
        return fixture_builder.build_fixture(dest)
    except fixture_builder.FixtureSourceError:
        raise  # committed fixture missing/drifted: hard failure, never skip
    except Exception as exc:  # environment/deps issue -> skip, never fail blind
        pytest.skip(f"cannot build producer fixture: {exc}")


def _copy_run(fixture, dest: Path) -> Path:
    shutil.copytree(fixture["dest"], dest, dirs_exist_ok=True)
    return dest


def _report(proc) -> dict:
    return json.loads(proc.stdout)


def _failing_ids(report: dict) -> list[str]:
    return [c["id"] for c in report["checks"] if not c["ok"]]


def test_happy_path(fixture):
    proc = _run_gate("check", "--manifest", fixture["manifest"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _report(proc)
    assert report["schema_version"] == "gate-check-report/1"
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["permission"] == {
        "complete_registry_claims": True,
        "finalized_unclaimed": True,
    }
    assert all(c["ok"] for c in report["checks"])
    ids = {c["id"] for c in report["checks"]}
    required = {
        "manifest.canonical",
        "manifest.shape",
        "file[registry].exists",
        "file[registry].sha256",
        "registry.parse",
        "registry.canonical_bytes",
        "registry.envelope",
        "registry.registry_hash",
        "registry.recipe_hash",
        "registry.manifest_binding",
        "registry.witness_complete",
        "registry.witness_errors",
        "registry.witness_uncaptured",
        "registry.witness_counts_zero",
        "file[report].exists",
        "file[report].sha256",
        "report.valid",
        "report.permission.finalized_unclaimed",
        "report.permission.complete_registry_claims",
        "report.checks_all_ok",
        "report.registry_binding",
        "manifest.report_valid",
        "manifest.report_permission",
        "manifest.report_registry_hash",
        "file[captures.manifest].sha256",
        "captures.manifest_sha256",
        "captures.manifest_shape",
        "captures.registry_sources_match",
        "proposals.sha256[proposals.json]",
    }
    assert required <= ids, sorted(required - ids)
    assert any(pid.endswith("registry.json") for pid in report["inputs"])


def test_report_out_matches_stdout(fixture, tmp_path):
    out = tmp_path / "gate-report.json"
    proc = _run_gate(
        "check", "--manifest", fixture["manifest"], "--report-out", out
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert out.read_bytes() + b"\n" == proc.stdout.encode("utf-8")
    assert not out.read_bytes().endswith(b"\n")


def test_base_dir_resolution(fixture, tmp_path):
    meta = tmp_path / "meta"
    meta.mkdir()
    shutil.copy2(fixture["manifest"], meta / "manifest.json")
    # Without --base-dir the relative paths resolve against meta/ -> exit 1.
    alone = _run_gate("check", "--manifest", meta / "manifest.json")
    assert alone.returncode == 1
    assert "file[registry].exists" in _failing_ids(_report(alone))
    # With --base-dir the recorded paths resolve against the fixture root.
    fixed = _run_gate(
        "check", "--manifest", meta / "manifest.json", "--base-dir", fixture["dest"]
    )
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr


def test_tool_pin_happy_path(fixture):
    proc = _run_gate(
        "check", "--manifest", fixture["manifest"],
        "--tool-manifest", fixture["tool_manifest"],
        "--artifact", fixture["artifact"],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    ids = {c["id"] for c in _report(proc)["checks"]}
    assert {"tool.manifest_parse", "tool.name_version", "tool.describe_sha256",
            "tool.artifact_sha256"} <= ids


# ---------------------------------------------------------------------------
# tamper matrix: each exits 1 and names the failing check id
# ---------------------------------------------------------------------------

def test_tamper_registry_byte(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    registry = dest / "registry.json"
    raw = registry.read_bytes()
    match = re.search(rb'"registry_hash":"sha256:([0-9a-f])', raw)
    assert match, "registry_hash value not found"
    pos = match.start(1)
    replacement = b"0" if raw[pos:pos + 1] != b"0" else b"1"
    registry.write_bytes(raw[:pos] + replacement + raw[pos + 1:])
    proc = _run_gate("check", "--manifest", dest / "manifest.json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _report(proc)
    assert "registry.registry_hash" in _failing_ids(report)
    assert any("registry.registry_hash" in e for e in report["errors"])


def test_tamper_manifest_sha(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["registry"]["sha256"] = "0" * 64
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "file[registry].sha256" in _failing_ids(_report(proc))


def test_manifest_shape_rejects_unknown_and_missing_keys(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"

    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["bogus"] = 1
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _report(proc)
    assert "manifest.shape" in _failing_ids(report)
    assert any("unknown key" in c["detail"] for c in report["checks"]
               if c["id"] == "manifest.shape")

    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    del manifest["bogus"]
    del manifest["windows"]
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    report = _report(proc)
    assert "manifest.shape" in _failing_ids(report)
    assert any("missing key" in c["detail"] for c in report["checks"]
               if c["id"] == "manifest.shape")


def test_tamper_manifest_registry_hash_prefix(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    recorded = manifest["registry"]["registry_hash"]
    assert recorded.startswith("sha256:")
    manifest["registry"]["registry_hash"] = recorded[len("sha256:"):]
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "registry.manifest_binding" in _failing_ids(_report(proc))


def test_tamper_manifest_report_permission(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["report"]["finalized_unclaimed"] = False
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "manifest.report_permission" in _failing_ids(_report(proc))


def test_tamper_manifest_report_registry_hash(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["report"]["registry_hash"] = "sha256:" + "0" * 64
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "manifest.report_registry_hash" in _failing_ids(_report(proc))


def test_empty_proposals_list_is_valid(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["proposals"] = []
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate("check", "--manifest", manifest_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    failing = _failing_ids(_report(proc))
    assert not [cid for cid in failing if cid.startswith("proposals.")]


def test_null_tool_artifact_accepted_with_pin(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    manifest_path = dest / "manifest.json"
    manifest = canonical_json.canonical_loads(manifest_path.read_bytes())
    manifest["tool"]["artifact"] = None
    manifest_path.write_bytes(canonical_json.canonical_dumps(manifest))
    proc = _run_gate(
        "check", "--manifest", manifest_path,
        "--tool-manifest", dest / "TOOL.json",
        "--artifact", dest / "fake-claim-registry-artifact.bin",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_tamper_report_valid_false(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    report_path = dest / "report.json"
    report = json.loads(report_path.read_text())
    report["valid"] = False
    report_path.write_text(json.dumps(report))
    proc = _run_gate("check", "--manifest", dest / "manifest.json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "report.valid" in _failing_ids(_report(proc))


def test_tamper_finalized_unclaimed_false(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    report_path = dest / "report.json"
    report = json.loads(report_path.read_text())
    report["permission"]["finalized_unclaimed"] = False
    report_path.write_text(json.dumps(report))
    proc = _run_gate("check", "--manifest", dest / "manifest.json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "report.permission.finalized_unclaimed" in _failing_ids(_report(proc))


def test_tamper_raw_capture_byte(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    raw_path = dest / "captures" / "raw" / "0000.bin"
    data = bytearray(raw_path.read_bytes())
    data[0] ^= 0xFF
    raw_path.write_bytes(bytes(data))
    proc = _run_gate("check", "--manifest", dest / "manifest.json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    failing = _failing_ids(_report(proc))
    assert any(entry.startswith("captures.raw[") for entry in failing), failing


def test_tamper_tool_version(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    tool = canonical_json.canonical_loads((dest / "TOOL.json").read_bytes())
    tool["version"] = "9.9.9"
    bad_tool = dest / "TOOL-bad.json"
    bad_tool.write_bytes(canonical_json.canonical_dumps(tool))
    proc = _run_gate(
        "check", "--manifest", dest / "manifest.json",
        "--tool-manifest", bad_tool, "--artifact", dest / "fake-claim-registry-artifact.bin",
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "tool.name_version" in _failing_ids(_report(proc))


# ---------------------------------------------------------------------------
# exit-code 2 cases and missing recorded files
# ---------------------------------------------------------------------------

def test_missing_manifest_exit_2(tmp_path):
    proc = _run_gate("check", "--manifest", tmp_path / "nope.json")
    assert proc.returncode == 2
    assert "manifest not found" in proc.stderr


def test_malformed_manifest_exit_2(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    proc = _run_gate("check", "--manifest", bad)
    assert proc.returncode == 2
    assert "malformed manifest" in proc.stderr


def test_missing_override_exit_2(fixture, tmp_path):
    proc = _run_gate(
        "check", "--manifest", fixture["manifest"], "--registry", tmp_path / "nope.json"
    )
    assert proc.returncode == 2
    assert "registry not found" in proc.stderr


def test_missing_recorded_file_exit_1(fixture, tmp_path):
    dest = _copy_run(fixture, tmp_path / "run")
    (dest / "registry.json").unlink()
    proc = _run_gate("check", "--manifest", dest / "manifest.json")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "file[registry].exists" in _failing_ids(_report(proc))


# ---------------------------------------------------------------------------
# built artifact
# ---------------------------------------------------------------------------

def test_built_pyz_happy_path(fixture, tmp_path):
    build = subprocess.run(
        [sys.executable, str(UNIT / "build.py"),
         "--out-dir", str(tmp_path / "dist"), "--tool-json", str(tmp_path / "TOOL.json")],
        capture_output=True, text=True,
    )
    assert build.returncode == 0, build.stderr
    artifact = tmp_path / "dist" / ARTIFACT_NAME
    run = subprocess.run(
        [sys.executable, str(artifact), "check", "--manifest", str(fixture["manifest"])],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert json.loads(run.stdout)["valid"] is True
