"""Gate-check ``claim-run-manifest/2`` replay + ``--require-sliced`` contract.

Uses ``sliced_fixture_builder`` (real sibling producer CLI: capture ->
frame-slices -> children -> reconcile -> assemble -> validate -> seal /2).
Every fixture step is asserted by ``_ready`` so a missing feature is a named
failure, never a skip.  Tamper tests mutate one artifact and then recompute
the outer recorded hashes (and the manifest bytes) so only semantic replay can
catch the tampering.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import fixture_builder
import sliced_fixture_builder as sfb
from toolkit import canonical_json as cj

UNIT = Path(__file__).resolve().parents[1]

EXPECTED_SLICED_IDS = {
    "sliced.refs_safe",
    "file[sliced.slices].exists",
    "file[sliced.slices].sha256",
    "file[sliced.merged].sha256",
    "file[sliced.reconciliation].sha256",
    "sliced.slices_parse",
    "sliced.slices_schema",
    "sliced.captures_sha256",
    "sliced.sources_binding",
    "sliced.units_replay",
    "sliced.registry_units_match",
    "sliced.partition_replay",
    "sliced.payload_replay",
    "sliced.inputs_binding",
    "sliced.merged_parse",
    "sliced.reconciliation_parse",
    "sliced.reconcile_replay.merged",
    "sliced.reconcile_replay.report",
    "sliced.registry_match",
}


def _run_gate(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(UNIT), env.get("PYTHONPATH", "")) if p
    )
    return subprocess.run(
        [sys.executable, "-m", "gate_check.cli", *(str(a) for a in args)],
        capture_output=True, text=True, cwd=str(cwd or UNIT), env=env,
    )


def _report(proc) -> dict:
    return json.loads(proc.stdout)


def _failing(report: dict) -> list[str]:
    return [c["id"] for c in report["checks"] if not c["ok"]]


@pytest.fixture(scope="session")
def sliced_run(tmp_path_factory):
    if sfb.find_producer() is None:
        pytest.skip("baseline producer not available")
    dest = tmp_path_factory.mktemp("sliced-fixture")
    return sfb.build(dest)


@pytest.fixture(scope="session")
def legacy_run(tmp_path_factory):
    if fixture_builder.find_baseline() is None:
        pytest.skip("baseline producer not available")
    dest = tmp_path_factory.mktemp("legacy-fixture")
    try:
        return fixture_builder.build_fixture(dest)
    except fixture_builder.FixtureSourceError:
        raise
    except Exception as exc:
        pytest.skip(f"cannot build producer fixture: {exc}")


def _ready(run):
    for step in sfb.STEPS:
        proc = run[step]
        assert proc.returncode == 0, (
            f"fixture step {step!r} failed rc={proc.returncode}: {proc.stderr[-800:]}"
        )
    return run


def _copy(run, dest: Path) -> Path:
    shutil.copytree(run["dest"], dest, dirs_exist_ok=True)
    # Rebase the legacy absolute path blocks onto the copy so tamper tests
    # mutate what the gate actually reads (the /2 labeling refs are relative).
    manifest_path = _manifest_path(dest)
    manifest = json.loads(manifest_path.read_bytes())
    manifest["captures"]["path"] = str(dest / "captures")
    if manifest.get("registry") is not None:
        manifest["registry"]["path"] = str(dest / "registry.json")
    if manifest.get("report") is not None:
        manifest["report"]["path"] = str(dest / "report.json")
    windows = manifest.get("windows")
    if isinstance(windows, dict):
        windows["path"] = str(dest / Path(windows["path"]).name)
    manifest_path.write_bytes(cj.canonical_dumps(manifest))
    return dest


def _manifest_path(dest: Path) -> Path:
    for name in ("run-manifest.json", "manifest.json"):
        candidate = dest / name
        if candidate.is_file():
            return candidate
    raise AssertionError(f"no run manifest in {dest}")


def _load_manifest(dest: Path) -> dict:
    return json.loads(_manifest_path(dest).read_bytes())


def _write_manifest(dest: Path, manifest: dict) -> None:
    _manifest_path(dest).write_bytes(cj.canonical_dumps(manifest))


# ---------------------------------------------------------------------------
# happy path / legacy back-compat / require-sliced
# ---------------------------------------------------------------------------

def test_sliced_happy_path_and_required_sliced(sliced_run):
    run = _ready(sliced_run)
    proc = _run_gate("check", "--manifest", run["manifest"], "--require-sliced")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    report = _report(proc)
    assert report["valid"] is True
    assert report["permission"] == {
        "complete_registry_claims": True, "finalized_unclaimed": True}
    ids = {c["id"] for c in report["checks"]}
    assert EXPECTED_SLICED_IDS <= ids, sorted(EXPECTED_SLICED_IDS - ids)
    assert not _failing(report)

    # Also valid without the flag: /2 is verified whenever it is present.
    plain = _run_gate("check", "--manifest", run["manifest"])
    assert plain.returncode == 0, plain.stdout + plain.stderr


def test_require_sliced_rejects_legacy_v1(legacy_run):
    plain = _run_gate("check", "--manifest", legacy_run["manifest"])
    assert plain.returncode == 0, plain.stdout + plain.stderr
    forced = _run_gate("check", "--manifest", legacy_run["manifest"],
                       "--require-sliced")
    assert forced.returncode == 1, forced.stdout + forced.stderr
    assert "manifest.sliced_required" in _failing(_report(forced))


def test_v1_root_keys_reject_labeling_regression(legacy_run, tmp_path):
    dest = _copy(legacy_run, tmp_path / "legacy")
    manifest = _load_manifest(dest)
    manifest["labeling"] = {"mode": "sliced"}
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "manifest.shape" in _failing(_report(proc))


def test_v2_shape_unknown_missing_and_proposals_mismatch(sliced_run, tmp_path):
    run = _ready(sliced_run)

    dest = _copy(run, tmp_path / "unknown")
    manifest = _load_manifest(dest)
    manifest["bogus"] = 1
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "manifest.shape" in _failing(_report(proc))

    dest = _copy(run, tmp_path / "missing")
    manifest = _load_manifest(dest)
    del manifest["labeling"]
    manifest["schema_version"] = "claim-run-manifest/1"
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "manifest.sliced_required" not in _failing(_report(proc))
    assert "manifest.shape" not in _failing(_report(proc))  # a valid legacy /1
    forced = _run_gate("check", "--manifest", _manifest_path(dest),
                       "--require-sliced")
    assert forced.returncode == 1
    assert "manifest.sliced_required" in _failing(_report(forced))

    dest = _copy(run, tmp_path / "proposals")
    manifest = _load_manifest(dest)
    manifest["proposals"] = [{"path": "other.json", "sha256": "0" * 64}]
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "manifest.shape" in _failing(_report(proc))


def test_v2_proposals_override_rejected_exit_2(sliced_run, tmp_path):
    run = _ready(sliced_run)
    proc = _run_gate("check", "--manifest", run["manifest"],
                     "--proposals", run["merged"])
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "override" in proc.stderr


# ---------------------------------------------------------------------------
# tamper matrix: outer hashes recomputed, semantic replay must still fail
# ---------------------------------------------------------------------------

def test_v2_slices_hash_tamper(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    manifest = _load_manifest(dest)
    manifest["labeling"]["slices"]["sha256"] = "0" * 64
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "file[sliced.slices].sha256" in _failing(_report(proc))


def test_v2_ref_path_escape_rejected(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    manifest = _load_manifest(dest)
    manifest["labeling"]["inputs"][0]["path"] = "../outside.json"
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.refs_safe" in _failing(_report(proc))


def test_v2_captures_sha256_tamper(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    slices_path = dest / "slices" / "manifest.json"
    slices_doc = json.loads(slices_path.read_bytes())
    slices_doc["captures_sha256"] = "0" * 64
    slices_path.write_bytes(cj.canonical_dumps(slices_doc))
    manifest = _load_manifest(dest)
    manifest["labeling"]["slices"]["sha256"] = sfb.sha256_file(slices_path)
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.captures_sha256" in _failing(_report(proc))


def test_v2_child_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    child = dest / "children" / Path(run["children"][0]).name
    doc = json.loads(child.read_bytes())
    doc["assignments"][0]["rationale"] = "tampered rationale"
    child.write_bytes(cj.canonical_dumps(doc))
    manifest = _load_manifest(dest)
    manifest["labeling"]["inputs"][0]["sha256"] = sfb.sha256_file(child)
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    failing = set(_failing(_report(proc)))
    assert {"sliced.reconcile_replay.merged", "sliced.reconcile_replay.report"} <= failing


def test_v2_report_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    report_path = dest / "reconciliation.json"
    report = json.loads(report_path.read_bytes())
    report["counts"]["audited_seams"] += 1
    report_path.write_bytes(cj.canonical_dumps(report))
    manifest = _load_manifest(dest)
    manifest["labeling"]["reconciliation"]["sha256"] = sfb.sha256_file(report_path)
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    failing = set(_failing(_report(proc)))
    assert "sliced.reconcile_replay.report" in failing
    assert "sliced.reconcile_replay.merged" not in failing


def test_v2_payload_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    slices_path = dest / "slices" / "manifest.json"
    slices_doc = json.loads(slices_path.read_bytes())
    entry = slices_doc["slices"][0]
    payload_path = dest / "slices" / entry["input"]["path"]
    data = bytearray(payload_path.read_bytes())
    marker = b'"text":"'
    pos = bytes(data).index(marker) + len(marker)
    data[pos] = ord("X") if data[pos] != ord("X") else ord("Y")
    payload_path.write_bytes(bytes(data))
    entry["input"]["sha256"] = sfb.sha256_file(payload_path)
    slices_path.write_bytes(cj.canonical_dumps(slices_doc))
    manifest = _load_manifest(dest)
    manifest["labeling"]["slices"]["sha256"] = sfb.sha256_file(slices_path)
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.payload_replay" in _failing(_report(proc))


def test_v2_unit_sha_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    slices_path = dest / "slices" / "manifest.json"
    slices_doc = json.loads(slices_path.read_bytes())
    slices_doc["sources"][0]["units"][0]["sha256"] = "0" * 64
    slices_path.write_bytes(cj.canonical_dumps(slices_doc))
    manifest = _load_manifest(dest)
    manifest["labeling"]["slices"]["sha256"] = sfb.sha256_file(slices_path)
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.units_replay" in _failing(_report(proc))


def test_v2_merged_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    merged_path = dest / "merged.json"
    merged = json.loads(merged_path.read_bytes())
    merged["assignments"][0]["rationale"] = "tampered merged"
    merged_path.write_bytes(cj.canonical_dumps(merged))
    manifest = _load_manifest(dest)
    sha = sfb.sha256_file(merged_path)
    manifest["labeling"]["merged"]["sha256"] = sha
    manifest["proposals"][0]["sha256"] = sha
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.reconcile_replay.merged" in _failing(_report(proc))


def test_v2_missing_child_entry_fails_complete_set(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    manifest = _load_manifest(dest)
    manifest["labeling"]["inputs"] = manifest["labeling"]["inputs"][:-1]
    _write_manifest(dest, manifest)
    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "sliced.reconcile_replay.report" in _failing(_report(proc))


def test_v2_registry_rationale_tamper_outer_hashes_recomputed(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    registry_path = dest / "registry.json"
    envelope = json.loads(registry_path.read_bytes())
    payload = envelope["payload"]
    for label in payload["labels"]:
        if label["state"] == "claim":
            label["rationale"] = "tampered rationale"
            break
    envelope["registry_hash"] = cj.registry_hash(payload)
    registry_path.write_bytes(cj.canonical_dumps(envelope))

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(run["producer"]), str(UNIT.parent / "common")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    revalidate = subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", "validate",
         "--registry", str(registry_path), "--captures", str(dest / "captures"),
         "--report-out", str(dest / "report.json")],
        cwd=str(dest), env=env, capture_output=True, text=True,
    )
    assert revalidate.returncode == 0, revalidate.stderr

    report = json.loads((dest / "report.json").read_bytes())
    manifest = _load_manifest(dest)
    manifest["registry"]["sha256"] = sfb.sha256_file(registry_path)
    manifest["registry"]["registry_hash"] = envelope["registry_hash"]
    manifest["report"]["sha256"] = sfb.sha256_file(dest / "report.json")
    manifest["report"]["valid"] = report["valid"]
    manifest["report"]["finalized_unclaimed"] = report["permission"]["finalized_unclaimed"]
    manifest["report"]["complete_registry_claims"] = report["permission"]["complete_registry_claims"]
    manifest["report"]["registry_hash"] = report["registry_hash"]
    _write_manifest(dest, manifest)

    proc = _run_gate("check", "--manifest", _manifest_path(dest))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    failing = set(_failing(_report(proc)))
    assert "sliced.registry_match" in failing
    assert "sliced.reconcile_replay.merged" not in failing
    assert not [cid for cid in failing if cid.startswith("report.")], sorted(failing)


def test_v2_downgrade_to_v1(sliced_run, tmp_path):
    run = _ready(sliced_run)
    dest = _copy(run, tmp_path / "run")
    manifest = _load_manifest(dest)
    del manifest["labeling"]
    manifest["schema_version"] = "claim-run-manifest/1"
    _write_manifest(dest, manifest)
    plain = _run_gate("check", "--manifest", _manifest_path(dest))
    assert plain.returncode == 0, plain.stdout + plain.stderr
    forced = _run_gate("check", "--manifest", _manifest_path(dest),
                       "--require-sliced")
    assert forced.returncode == 1, forced.stdout + forced.stderr
    assert "manifest.sliced_required" in _failing(_report(forced))
