"""RED-first contract tests for ``claim-run-manifest/2`` (sliced sealing).

The producer currently seals only ``claim-run-manifest/1``; every test here
invokes the real CLI (never an import) and asserts the intended
``--slices/--slice-proposal/--reconciliation/--proposals`` behavior, so the
RED run fails on the command contract, not on a Python import.

The helper builds a complete, small sliced run through the CLI: batch capture
of two sources -> frame-slices with small caps (forcing overlaps) -> one
mechanical child proposal per slice -> proposal-reconcile -> assemble ->
validate -> seal.  The child oracle mirrors ``test_proposal_reconcile``:
single-unit claims for core non-separators, mirroring votes for overlap
non-separators, mechanically enumerated adjacent grouping votes, clear
boundaries.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from toolkit import canonical_json as cj

UNIT_ROOT = Path(__file__).resolve().parents[1]
COMMON = UNIT_ROOT.parent / "common"

SRC_A = (
    b"# Alpha\n\nIntro paragraph one with a few words.\n\n"
    b"- item a\n- item b\n\nMore text here in another paragraph.\n\n"
    b"```\ncode block line\n```\n\nFinal alpha paragraph wraps up.\n"
)
SRC_B = (
    b"## Beta\n\nBeta intro paragraph.\n\n"
    b"| a | b |\n|---|---|\n| 1 | 2 |\n\n"
    b"Beta closing statement here.\n"
)

MANIFEST_V1_KEYS = {
    "schema_version", "tool", "captures", "proposals", "registry", "report",
    "windows",
}


def _env() -> dict:
    env = dict(os.environ)
    paths = [str(COMMON)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def cli(*args, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", *args],
        cwd=str(cwd or UNIT_ROOT), capture_output=True, text=True,
        env=_env(), timeout=300,
    )


def sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def auto_child(slices_dir: Path, entry: dict) -> dict:
    payload = json.loads((slices_dir / entry["input"]["path"]).read_bytes())
    kinds = {u["unit_id"]: u["kind"] for u in payload["units"]}
    assignments = [
        {"source_ref": entry["source_ref"], "unit_ids": [uid],
         "state": "claim", "rationale": "mechanical test claim"}
        for uid in entry["core_ids"] if kinds[uid] != "separator"
    ]
    overlap_votes = [
        {"unit_id": uid, "state": "claim", "label": None, "role_ref": None,
         "rationale": "audit claim"}
        for uid in entry["overlap_ids"] if kinds[uid] != "separator"
    ]
    visible = entry["overlap_ids"] + entry["core_ids"]
    grouping_votes = [
        {"left_unit_id": left, "right_unit_id": right,
         "grouping": "separate", "rationale": "test pair"}
        for left, right in zip(visible, visible[1:])
        if kinds[left] != "separator" and kinds[right] != "separator"
    ]
    return {
        "schema_version": "slice-proposals/1",
        "slice_id": entry["slice_id"],
        "input_sha256": entry["input"]["sha256"],
        "assignments": assignments,
        "overlap_votes": overlap_votes,
        "grouping_votes": grouping_votes,
        "boundary": {"left": "clear", "right": "clear"},
    }


def build_sliced_run(tmp_path: Path, *, seal_children=None) -> dict:
    """Run capture->...->validate, then attempt the v2 seal (rc returned)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    src_a = tmp_path / "a.md"
    src_a.write_bytes(SRC_A)
    src_b = tmp_path / "b.md"
    src_b.write_bytes(SRC_B)
    capdir = tmp_path / "captures"
    capture = cli(
        "capture", "--in", str(src_a), "--locator", "repo#17:a",
        "--in", str(src_b), "--locator", "repo#17:b", "--out", str(capdir),
    )
    slices_dir = tmp_path / "slices"
    frame_slices = cli(
        "frame-slices", "--captures", str(capdir), "--out-dir", str(slices_dir),
        "--max-bytes", "300", "--max-units", "8", "--overlap-units", "2",
    )
    slices_doc = json.loads((slices_dir / "manifest.json").read_bytes())
    children_dir = tmp_path / "children"
    children_dir.mkdir(exist_ok=True)
    children = []
    for i, entry in enumerate(slices_doc["slices"]):
        path = children_dir / f"child-{i:04d}.json"
        path.write_bytes(cj.canonical_dumps(auto_child(slices_dir, entry)))
        children.append(path)

    merged = tmp_path / "merged.json"
    reconciliation = tmp_path / "reconciliation.json"
    reconcile_args = [
        "proposal-reconcile", "--captures", str(capdir),
        "--slices", str(slices_dir / "manifest.json"),
    ]
    for path in children:
        reconcile_args += ["--proposal", str(path)]
    reconcile_args += ["--out", str(merged), "--report-out", str(reconciliation)]
    reconcile = cli(*reconcile_args)

    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    assemble = cli("assemble", "--captures", str(capdir),
                   "--proposals", str(merged), "--out", str(registry))
    validate = cli("validate", "--registry", str(registry),
                   "--captures", str(capdir), "--report-out", str(report))

    manifest_path = tmp_path / "run-manifest.json"
    seal_children = list(children if seal_children is None else seal_children)
    seal_args = [
        "manifest", "--captures", str(capdir),
        "--slices", str(slices_dir / "manifest.json"),
    ]
    for path in seal_children:
        seal_args += ["--slice-proposal", str(path)]
    seal_args += [
        "--reconciliation", str(reconciliation), "--proposals", str(merged),
        "--registry", str(registry), "--report", str(report),
        "--out", str(manifest_path),
    ]
    seal = cli(*seal_args)
    return {
        "captures": capdir,
        "slices_dir": slices_dir,
        "slices_manifest": slices_dir / "manifest.json",
        "slices_doc": slices_doc,
        "children_dir": children_dir,
        "children": children,
        "merged": merged,
        "reconciliation": reconciliation,
        "registry": registry,
        "report": report,
        "manifest_path": manifest_path,
        "capture": capture,
        "frame_slices": frame_slices,
        "reconcile": reconcile,
        "assemble": assemble,
        "validate": validate,
        "seal": seal,
        "seal_args": seal_args,
    }


def sealed(tmp_path: Path) -> dict:
    run = build_sliced_run(tmp_path)
    assert run["seal"].returncode == 0, run["seal"].stderr
    run["manifest"] = json.loads(run["manifest_path"].read_bytes())
    return run


# ---------------------------------------------------------------------------
# happy path + labeling block
# ---------------------------------------------------------------------------

def test_manifest_v2_happy_path_and_labeling_shape(tmp_path):
    run = sealed(tmp_path)
    manifest = run["manifest"]
    assert manifest["schema_version"] == "claim-run-manifest/2"
    assert set(manifest) == (MANIFEST_V1_KEYS | {"labeling"})
    labeling = manifest["labeling"]
    assert set(labeling) == {"mode", "slices", "inputs", "merged", "reconciliation"}
    assert labeling["mode"] == "sliced"

    # Relocatable, in-run relative refs (never absolute paths).
    for spec in (labeling["slices"], labeling["merged"], labeling["reconciliation"]):
        assert not os.path.isabs(spec["path"]), spec
        assert ".." not in Path(spec["path"]).parts, spec
    assert labeling["slices"] == {
        "path": "slices/manifest.json", "sha256": sha(run["slices_manifest"])}
    assert labeling["merged"] == {"path": "merged.json", "sha256": sha(run["merged"])}
    assert labeling["reconciliation"] == {
        "path": "reconciliation.json", "sha256": sha(run["reconciliation"])}

    # exactly one child per slice, sorted by slice_id, hash-bound to the file.
    slice_ids = [entry["slice_id"] for entry in run["slices_doc"]["slices"]]
    assert len(labeling["inputs"]) == len(slice_ids)
    recorded_ids = [item["slice_id"] for item in labeling["inputs"]]
    assert recorded_ids == sorted(recorded_ids, key=lambda s: s.encode("utf-8"))
    assert set(recorded_ids) == set(slice_ids)
    for item in labeling["inputs"]:
        path = tmp_path / item["path"]
        assert path.is_file()
        assert item["sha256"] == sha(path)
        entry = next(e for e in run["slices_doc"]["slices"]
                     if e["slice_id"] == item["slice_id"])
        assert item["path"] == f"children/{path.name}"
        payload = json.loads((run["slices_dir"] / entry["input"]["path"]).read_bytes())
        assert payload["slice_id"] == item["slice_id"]

    # top-level proposals must equal [labeling.merged]
    assert manifest["proposals"] == [{
        "path": labeling["merged"]["path"], "sha256": labeling["merged"]["sha256"]}]

    assert manifest["tool"]["name"] == "claim-registry"
    assert manifest["tool"]["version"] == "0.3.0"
    raw = run["manifest_path"].read_bytes()
    assert not raw.endswith(b"\n")
    assert cj.canonical_dumps(manifest) == raw

    # require at least one overlap audit in this fixture (proves the slice caps
    # forced overlaps; a silent cap drift would make the audit vacuous).
    assert any(e["overlap_ids"] for e in run["slices_doc"]["slices"])


def test_manifest_v1_unchanged_without_new_flags(tmp_path):
    run = build_sliced_run(tmp_path)
    assert run["reconcile"].returncode == 0, run["reconcile"].stderr
    out = tmp_path / "legacy-manifest.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 0, res.stderr
    legacy = json.loads(out.read_bytes())
    assert legacy["schema_version"] == "claim-run-manifest/1"
    assert set(legacy) == MANIFEST_V1_KEYS
    assert "labeling" not in legacy
    assert legacy["proposals"] == [{
        "path": str(run["merged"]), "sha256": sha(run["merged"])}]


def test_manifest_v2_deterministic_repeat(tmp_path):
    run = build_sliced_run(tmp_path)
    assert run["seal"].returncode == 0, run["seal"].stderr
    second_out = tmp_path / "run-manifest-2.json"
    args = list(run["seal_args"])
    args[args.index("--out") + 1] = str(second_out)
    res = cli(*args)
    assert res.returncode == 0, res.stderr
    assert run["manifest_path"].read_bytes() == second_out.read_bytes()


# ---------------------------------------------------------------------------
# new-flag contract: all required together, one merged proposal
# ---------------------------------------------------------------------------

def test_manifest_v2_partial_flags_exit_2(tmp_path):
    run = build_sliced_run(tmp_path)
    slices = str(run["slices_manifest"])
    recon = str(run["reconciliation"])
    merged = str(run["merged"])
    child = str(run["children"][0])
    cases = [
        ["--slices", slices],
        ["--slice-proposal", child],
        ["--reconciliation", recon],
        ["--slices", slices, "--reconciliation", recon],
        ["--slices", slices, "--reconciliation", recon, "--proposals", merged],
    ]
    for extra in cases:
        out = tmp_path / "partial.json"
        res = cli("manifest", "--captures", str(run["captures"]), *extra,
                  "--out", str(out))
        assert res.returncode == 2, (extra, res.returncode, res.stderr)
        assert not out.exists()


def test_manifest_v2_requires_exactly_one_merged_proposal(tmp_path):
    run = build_sliced_run(tmp_path)
    out = tmp_path / "two-proposals.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--slices", str(run["slices_manifest"]),
        *sum((["--slice-proposal", str(c)] for c in run["children"]), []),
        "--reconciliation", str(run["reconciliation"]),
        "--proposals", str(run["merged"]), "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 2, res.stderr
    assert not out.exists()


# ---------------------------------------------------------------------------
# child set completeness and binding
# ---------------------------------------------------------------------------

def test_manifest_v2_child_set_must_cover_every_slice(tmp_path):
    run = build_sliced_run(tmp_path)
    out = tmp_path / "incomplete.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--slices", str(run["slices_manifest"]),
        *sum((["--slice-proposal", str(c)] for c in run["children"][:-1]), []),
        "--reconciliation", str(run["reconciliation"]),
        "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert res.stderr.strip()
    assert not out.exists()


def test_manifest_v2_rejects_duplicate_and_foreign_children(tmp_path):
    run = build_sliced_run(tmp_path)

    def reseal(children, out):
        return cli(
            "manifest", "--captures", str(run["captures"]),
            "--slices", str(run["slices_manifest"]),
            *sum((["--slice-proposal", str(c)] for c in children), []),
            "--reconciliation", str(run["reconciliation"]),
            "--proposals", str(run["merged"]),
            "--registry", str(run["registry"]), "--report", str(run["report"]),
            "--out", str(out),
        )

    dup = tmp_path / "duplicate.json"
    res = reseal(run["children"] + [run["children"][0]], dup)
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not dup.exists()

    foreign_doc = json.loads(run["children"][0].read_bytes())
    foreign_doc["slice_id"] = "sha256:" + "0" * 64
    foreign = tmp_path / "children" / "foreign.json"
    foreign.write_bytes(cj.canonical_dumps(foreign_doc))
    out = tmp_path / "foreign.json"
    res = reseal(run["children"] + [foreign], out)
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()


def test_manifest_v2_rejects_wrong_input_hash(tmp_path):
    run = build_sliced_run(tmp_path)
    bad_doc = json.loads(run["children"][0].read_bytes())
    bad_doc["input_sha256"] = "0" * 64
    bad = tmp_path / "children" / "bad-input.json"
    bad.write_bytes(cj.canonical_dumps(bad_doc))
    children = [bad] + run["children"][1:]
    out = tmp_path / "bad-input-manifest.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--slices", str(run["slices_manifest"]),
        *sum((["--slice-proposal", str(c)] for c in children), []),
        "--reconciliation", str(run["reconciliation"]),
        "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()


# ---------------------------------------------------------------------------
# hash/schema binding of slices + reconciliation + merged
# ---------------------------------------------------------------------------

def test_manifest_v2_rejects_noncanonical_inputs(tmp_path):
    run = build_sliced_run(tmp_path)
    noncanonical = tmp_path / "slices" / "manifest-pretty.json"
    doc = json.loads(run["slices_manifest"].read_bytes())
    noncanonical.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    out = tmp_path / "nc.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--slices", str(noncanonical),
        *sum((["--slice-proposal", str(c)] for c in run["children"]), []),
        "--reconciliation", str(run["reconciliation"]),
        "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()


def test_manifest_v2_binds_reconciliation_to_slices_and_merged(tmp_path):
    run = build_sliced_run(tmp_path)
    report = json.loads(run["reconciliation"].read_bytes())

    def reseal(report_doc, out):
        report_path = tmp_path / "reconciliation-variant.json"
        report_path.write_bytes(cj.canonical_dumps(report_doc))
        return cli(
            "manifest", "--captures", str(run["captures"]),
            "--slices", str(run["slices_manifest"]),
            *sum((["--slice-proposal", str(c)] for c in run["children"]), []),
            "--reconciliation", str(report_path),
            "--proposals", str(run["merged"]),
            "--registry", str(run["registry"]), "--report", str(run["report"]),
            "--out", str(out),
        )

    bad = dict(report)
    bad["slices_sha256"] = "0" * 64
    out = tmp_path / "bad-slices-hash.json"
    res = reseal(bad, out)
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()

    bad = dict(report)
    bad["merged_sha256"] = "0" * 64
    out = tmp_path / "bad-merged-hash.json"
    res = reseal(bad, out)
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()

    bad = dict(report)
    bad["complete"] = False
    bad["merged_sha256"] = None
    out = tmp_path / "incomplete.json"
    res = reseal(bad, out)
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()


def test_manifest_v2_rejects_reconciliation_schema_violation(tmp_path):
    run = build_sliced_run(tmp_path)
    report = json.loads(run["reconciliation"].read_bytes())
    del report["complete"]
    bad = tmp_path / "reconciliation-bad-schema.json"
    bad.write_bytes(cj.canonical_dumps(report))
    out = tmp_path / "bad-schema.json"
    res = cli(
        "manifest", "--captures", str(run["captures"]),
        "--slices", str(run["slices_manifest"]),
        *sum((["--slice-proposal", str(c)] for c in run["children"]), []),
        "--reconciliation", str(bad),
        "--proposals", str(run["merged"]),
        "--registry", str(run["registry"]), "--report", str(run["report"]),
        "--out", str(out),
    )
    assert res.returncode == 1, (res.returncode, res.stderr)
    assert not out.exists()
