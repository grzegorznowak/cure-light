"""proposal-reconcile CLI contract tests (RED-first: command not implemented).

Built on real ``frame-slices`` manifests produced by the CLI, so every RED
failure is "the reconciliation command is missing", never an import error.
The helper below is an independent proposal oracle: it reads the frozen
payloads and emits one claim per core non-separator, overlap votes mirroring
the owner, mechanically enumerated grouping votes, and clear boundaries.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from claim_label_contract import schemas
from toolkit import canonical_json as cj

UNIT_ROOT = Path(__file__).resolve().parents[1]
COMMON = UNIT_ROOT.parent / "common"
PYZ = UNIT_ROOT / "dist" / "claim-registry-0.2.0.pyz"

SCHEMA_PROPOSALS = "slice-proposals/1"
SCHEMA_REPORT = "proposal-reconciliation/1"


def _env() -> dict:
    env = dict(os.environ)
    paths = [str(COMMON)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def cli(*args: str, cwd: Path | None = None, env: dict | None = None):
    return subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", *args],
        cwd=str(cwd or UNIT_ROOT), capture_output=True, text=True,
        env=env or _env(), timeout=300,
    )


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def read_json(path: Path) -> dict:
    return json.loads(read_bytes(path).decode("utf-8"))


def capture(tmp_path: Path, sources: list[tuple[str, bytes]]) -> Path:
    capdir = tmp_path / "captures"
    args = ["capture"]
    for name, data in sources:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        args += ["--in", str(path), "--locator", f"repo#17:{name}"]
    args += ["--out", str(capdir)]
    proc = cli(*args)
    assert proc.returncode == 0, proc.stderr
    return capdir


def slice_fixture(tmp_path: Path, sources: list[tuple[str, bytes]], *caps: str):
    capdir = capture(tmp_path, sources)
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out), *caps)
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    return capdir, out, manifest


PANEL = (
    b"# T\n\n"
    b"| a | b |\n|---|---|\n| 1 | 2 |\n\n"
    b"Alpha.\n\nBeta.\n"
)


def auto_proposals(manifest: dict, slices_dir: Path) -> dict[str, dict]:
    """One single-unit claim per core non-separator; all pairs 'separate'."""
    docs: dict[str, dict] = {}
    for entry in manifest["slices"]:
        payload = read_json(slices_dir / entry["input"]["path"])
        kinds = {u["unit_id"]: u["kind"] for u in payload["units"]}
        assignments = [
            {"source_ref": entry["source_ref"], "unit_ids": [uid],
             "state": "claim", "rationale": "test claim"}
            for uid in entry["core_ids"] if kinds[uid] != "separator"
        ]
        overlap_votes = [
            {"unit_id": uid, "state": "claim", "label": None,
             "role_ref": None, "rationale": "audit claim"}
            for uid in entry["overlap_ids"] if kinds[uid] != "separator"
        ]
        visible = entry["overlap_ids"] + entry["core_ids"]
        grouping_votes = [
            {"left_unit_id": left, "right_unit_id": right,
             "grouping": "separate", "rationale": "test pair"}
            for left, right in zip(visible, visible[1:])
            if kinds[left] != "separator" and kinds[right] != "separator"
        ]
        docs[entry["slice_id"]] = {
            "schema_version": SCHEMA_PROPOSALS,
            "slice_id": entry["slice_id"],
            "input_sha256": entry["input"]["sha256"],
            "assignments": assignments,
            "overlap_votes": overlap_votes,
            "grouping_votes": grouping_votes,
            "boundary": {"left": "clear", "right": "clear"},
        }
    return docs


def write_proposals(tmp_path: Path, docs: dict[str, dict], order=None) -> list[Path]:
    order = order or list(docs)
    outdir = tmp_path / "proposals"
    outdir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, slice_id in enumerate(order):
        path = outdir / f"{i:04d}.json"
        path.write_bytes(cj.canonical_dumps(docs[slice_id]))
        paths.append(path)
    return paths


def reconcile(tmp_path: Path, capdir: Path, slices_dir: Path, proposals: list[Path],
              *, out: Path | None = None, report: Path | None = None):
    out = out or tmp_path / "merged.json"
    report = report or tmp_path / "report.json"
    args = ["proposal-reconcile", "--captures", str(capdir),
            "--slices", str(slices_dir / "manifest.json")]
    for path in proposals:
        args += ["--proposal", str(path)]
    args += ["--out", str(out), "--report-out", str(report)]
    proc = cli(*args)
    return proc, out, report


def long_source() -> bytes:
    parts = []
    for i in range(8):
        parts.append(f"## H{i}\n\nParagraph {i} " + ("z" * 220) + "\n\n")
        parts.append(f"| k{i} | v{i} |\n|---|---|\n| {i} | {i + 1} |\n\n")
    return "".join(parts).encode("utf-8")


def multi_slice_fixture(tmp_path: Path):
    return slice_fixture(
        tmp_path, [("long.md", long_source())],
        "--max-bytes", "500", "--max-units", "10", "--overlap-units", "2",
    )


# ---------------------------------------------------------------------------
# CLI / success contract
# ---------------------------------------------------------------------------

def test_describe_lists_proposal_reconcile():
    proc = cli("--describe")
    assert proc.returncode == 0, proc.stderr
    commands = json.loads(proc.stdout)["commands"]
    assert "proposal-reconcile" in commands
    spec = commands["proposal-reconcile"]
    assert set(spec["exit_codes"]) == {"0", "1", "2"}
    names = {param["name"] for param in spec["params"]}
    assert {"--captures", "--slices", "--proposal", "--out", "--report-out"} <= names


def test_reconcile_success_and_registry_pipeline(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    docs = auto_proposals(manifest, slices_dir)
    for doc in docs.values():
        assert schemas.validate_by_name(SCHEMA_PROPOSALS, doc) == []
    paths = write_proposals(tmp_path, docs)
    proc, out, report_path = reconcile(tmp_path, capdir, slices_dir, paths)
    assert proc.returncode == 0, proc.stderr
    assert out.is_file() and report_path.is_file()

    merged_raw = read_bytes(out)
    merged = json.loads(merged_raw.decode("utf-8"))
    assert cj.canonical_dumps(merged) == merged_raw
    assert merged["schema_version"] == "claim-proposals/1"
    assert merged["decomposition"] == [] and merged["groups"] == []
    assert merged["precedence"] == [] and merged["uncaptured_source_refs"] == []
    owned = [uid for a in merged["assignments"] for uid in a["unit_ids"]]
    assert len(owned) == len(set(owned))
    source = manifest["sources"][0]
    core_nonseparators = {
        u["unit_id"] for u in source["units"] if u["kind"] != "separator"
    }
    assert set(owned) == core_nonseparators

    report = read_json(report_path)
    assert schemas.validate_by_name(SCHEMA_REPORT, report) == []
    assert report["complete"] is True
    assert report["merged_sha256"] == hashlib.sha256(merged_raw).hexdigest()
    assert report["slices_sha256"] == hashlib.sha256(
        read_bytes(slices_dir / "manifest.json")).hexdigest()
    assert report["inputs"] == sorted(
        [{"slice_id": sid, "sha256": hashlib.sha256(read_bytes(p)).hexdigest()}
         for sid, p in zip(docs, paths)],
        key=lambda r: r["slice_id"],
    )
    counts = report["counts"]
    assert counts["expected_slices"] == len(manifest["slices"])
    assert counts["received_proposals"] == len(paths)

    # the merged document is accepted by the existing registry pipeline
    registry = tmp_path / "registry.json"
    assert cli("assemble", "--captures", str(capdir), "--proposals", str(out),
               "--out", str(registry)).returncode == 0
    probe = cli("validate", "--registry", str(registry), "--captures", str(capdir))
    assert probe.returncode == 0, probe.stdout
    validation = json.loads(probe.stdout)
    assert validation["permission"] == {
        "complete_registry_claims": True, "finalized_unclaimed": True,
    }


def test_reconcile_d1_two_sources_merged(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(
        tmp_path, [("panel.md", PANEL), ("long.md", long_source())],
        "--max-bytes", "800", "--max-units", "12", "--overlap-units", "2",
    )
    docs = auto_proposals(manifest, slices_dir)
    paths = write_proposals(tmp_path, docs)
    proc, out, report_path = reconcile(tmp_path, capdir, slices_dir, paths)
    assert proc.returncode == 0, proc.stderr
    merged = read_json(out)
    refs = {a["source_ref"] for a in merged["assignments"]}
    assert refs == {s["source_ref"] for s in manifest["sources"]}
    report = read_json(report_path)
    assert report["counts"]["expected_slices"] == len(manifest["slices"])


# ---------------------------------------------------------------------------
# failure report / stale output
# ---------------------------------------------------------------------------

def test_reconcile_failure_publishes_report_and_removes_stale_merged(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    docs = auto_proposals(manifest, slices_dir)
    sid = next(iter(docs))
    docs[sid]["boundary"] = {"left": "spanning", "right": "clear"}
    paths = write_proposals(tmp_path, docs)
    stale = tmp_path / "merged.json"
    stale.write_bytes(b"stale successful output")
    proc, out, report_path = reconcile(tmp_path, capdir, slices_dir, paths, out=stale)
    assert proc.returncode == 1, proc.stdout
    assert not stale.exists(), "stale merged artifact survived a failed retry"
    report = read_json(report_path)
    assert schemas.validate_by_name(SCHEMA_REPORT, report) == []
    assert report["complete"] is False
    assert report["merged_sha256"] is None
    assert any(c["code"] == "boundary_spanning" for c in report["conflicts"])


def test_reconcile_missing_duplicate_foreign_hash_mismatch(tmp_path):
    capdir, slices_dir, manifest = multi_slice_fixture(tmp_path)
    docs = auto_proposals(manifest, slices_dir)
    sids = list(docs)
    assert len(sids) >= 2
    sid = sids[0]

    # missing proposals for every unlisted slice
    only = docs[sid]
    good = write_proposals(tmp_path / "only", docs, order=[sid])[0]
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [good])
    assert proc.returncode == 1
    report = read_json(report_path)
    missing = [c for c in report["conflicts"] if c["code"] == "missing_proposal"]
    assert missing and {c["slice_ids"][0] for c in missing} == set(sids[1:])

    # duplicate proposal
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [good, good],
                                     out=tmp_path / "m-dup.json",
                                     report=tmp_path / "r-dup.json")
    assert proc.returncode == 1
    assert any(c["code"] == "duplicate_proposal"
               for c in read_json(report_path)["conflicts"])

    # foreign slice id
    foreign = json.loads(json.dumps(only))
    foreign["slice_id"] = "sha256:" + "a" * 64
    fp = tmp_path / "foreign.json"
    fp.write_bytes(cj.canonical_dumps(foreign))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [fp],
                                     out=tmp_path / "m-f.json",
                                     report=tmp_path / "r-f.json")
    assert proc.returncode == 1
    assert any(c["code"] == "foreign_slice"
               for c in read_json(report_path)["conflicts"])

    # payload hash mismatch
    tampered = json.loads(json.dumps(only))
    tampered["input_sha256"] = "b" * 64
    tp = tmp_path / "hash.json"
    tp.write_bytes(cj.canonical_dumps(tampered))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [tp],
                                     out=tmp_path / "m-h.json",
                                     report=tmp_path / "r-h.json")
    assert proc.returncode == 1
    codes = {c["code"] for c in read_json(report_path)["conflicts"]}
    assert codes & {"input_hash_mismatch", "slice_replay_mismatch"}


def test_reconcile_closed_schema_rejects_unknown_and_bool(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    docs = auto_proposals(manifest, slices_dir)
    sid = next(iter(docs))

    unknown = json.loads(json.dumps(docs[sid]))
    unknown["decomposition"] = [{"parent": {}}]
    p1 = tmp_path / "unknown.json"
    p1.write_bytes(cj.canonical_dumps(unknown))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p1],
                                     out=tmp_path / "m-u.json",
                                     report=tmp_path / "r-u.json")
    assert proc.returncode == 1
    assert any(c["code"] == "proposal_invalid"
               for c in read_json(report_path)["conflicts"])

    parent_ref = json.loads(json.dumps(docs[sid]))
    parent_ref["assignments"][0]["parent_ref"] = None
    p2 = tmp_path / "parent.json"
    p2.write_bytes(cj.canonical_dumps(parent_ref))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p2],
                                     out=tmp_path / "m-p.json",
                                     report=tmp_path / "r-p.json")
    assert proc.returncode == 1
    assert any(c["code"] == "proposal_invalid"
               for c in read_json(report_path)["conflicts"])

    # duplicate JSON keys are not canonical JSON
    p3 = tmp_path / "dupe.json"
    p3.write_bytes(b'{"schema_version":"slice-proposals/1","schema_version":"x"}')
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p3],
                                     out=tmp_path / "m-d.json",
                                     report=tmp_path / "r-d.json")
    assert proc.returncode == 1
    assert any(c["code"] == "proposal_invalid"
               for c in read_json(report_path)["conflicts"])


def test_reconcile_missing_and_unreadable_proposal_is_usage_error(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    missing = tmp_path / "nope.json"
    proc, out, report = reconcile(tmp_path, capdir, slices_dir, [missing])
    assert proc.returncode == 2, proc.stdout
    assert not report.exists()
    assert not out.exists()


# ---------------------------------------------------------------------------
# assignment / vote / grouping / boundary policy
# ---------------------------------------------------------------------------

def test_reconcile_assignment_ownership_errors(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    docs = auto_proposals(manifest, slices_dir)
    sid = next(iter(docs))
    doc = docs[sid]

    # double ownership within the slice
    dup = json.loads(json.dumps(doc))
    if len(dup["assignments"]) >= 2:
        dup["assignments"][1]["unit_ids"] = list(dup["assignments"][0]["unit_ids"])
    p = tmp_path / "dup.json"
    p.write_bytes(cj.canonical_dumps(dup))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p],
                                     out=tmp_path / "m-a.json",
                                     report=tmp_path / "r-a.json")
    assert proc.returncode == 1
    codes = {c["code"] for c in read_json(report_path)["conflicts"]}
    assert codes & {"unit_owned_twice", "claim_not_contiguous", "assignment_missing"}

    # missing core coverage
    short = json.loads(json.dumps(doc))
    short["assignments"] = short["assignments"][:-1]
    p = tmp_path / "short.json"
    p.write_bytes(cj.canonical_dumps(short))
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p],
                                     out=tmp_path / "m-s.json",
                                     report=tmp_path / "r-s.json")
    assert proc.returncode == 1
    assert any(c["code"] == "assignment_missing"
               for c in read_json(report_path)["conflicts"])


def test_reconcile_overlap_vote_conflict_and_rationale_warning(tmp_path):
    capdir, slices_dir, manifest = multi_slice_fixture(tmp_path)
    docs = auto_proposals(manifest, slices_dir)
    audited = [sid for sid, d in docs.items() if d["overlap_votes"]]
    assert audited, "fixture produced no overlap audit"
    sid = audited[0]

    conflict = json.loads(json.dumps(docs[sid]))
    conflict["overlap_votes"][0]["state"] = "nonclaim"
    conflict["overlap_votes"][0]["label"] = "context"
    conflict["overlap_votes"][0]["role_ref"] = "spec:test"
    conflict["overlap_votes"][0]["rationale"] = "different"
    p = tmp_path / "conflict.json"
    p.write_bytes(cj.canonical_dumps(conflict))
    others = write_proposals(tmp_path, {k: v for k, v in docs.items() if k != sid},
                             order=[k for k in docs if k != sid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-c.json",
                                     report=tmp_path / "r-c.json")
    assert proc.returncode == 1
    report = read_json(report_path)
    codes = {c["code"] for c in report["conflicts"]}
    assert "state_disagreement" in codes or "label_disagreement" in codes

    warning = json.loads(json.dumps(docs[sid]))
    warning["overlap_votes"][0]["rationale"] = "independently derived rationale"
    p = tmp_path / "warning.json"
    p.write_bytes(cj.canonical_dumps(warning))
    others = write_proposals(tmp_path / "warned", {k: v for k, v in docs.items() if k != sid},
                             order=[k for k in docs if k != sid])
    proc, out, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                       out=tmp_path / "m-w.json",
                                       report=tmp_path / "r-w.json")
    assert proc.returncode == 0, proc.stderr
    report = read_json(report_path)
    assert report["complete"] is True
    assert any(w["code"] == "audit_rationale_differs" for w in report["warnings"])
    # primary rationale is never replaced by the audit rationale
    merged = read_json(out)
    assert all("independently derived" not in a.get("rationale", "")
               for a in merged["assignments"])


def test_reconcile_grouping_disagreement_and_uncertain(tmp_path):
    capdir, slices_dir, manifest = multi_slice_fixture(tmp_path)
    docs = auto_proposals(manifest, slices_dir)
    with_pairs = [sid for sid, d in docs.items() if d["grouping_votes"]]
    assert len(with_pairs) >= 2, "fixture produced fewer than two audited pairs"
    sid = with_pairs[1]

    disagree = json.loads(json.dumps(docs[sid]))
    disagree["grouping_votes"][0]["grouping"] = "same"
    p = tmp_path / "disagree.json"
    p.write_bytes(cj.canonical_dumps(disagree))
    others = write_proposals(tmp_path / "d2", {k: v for k, v in docs.items() if k != sid},
                             order=[k for k in docs if k != sid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-g.json",
                                     report=tmp_path / "r-g.json")
    assert proc.returncode == 1
    codes = {c["code"] for c in read_json(report_path)["conflicts"]}
    assert codes & {"grouping_disagreement", "grouping_assignment_mismatch"}

    uncertain = json.loads(json.dumps(docs[sid]))
    uncertain["grouping_votes"][0]["grouping"] = "uncertain"
    p = tmp_path / "uncertain.json"
    p.write_bytes(cj.canonical_dumps(uncertain))
    others = write_proposals(tmp_path / "d3", {k: v for k, v in docs.items() if k != sid},
                             order=[k for k in docs if k != sid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-gu.json",
                                     report=tmp_path / "r-gu.json")
    assert proc.returncode == 1
    assert any(c["code"] == "grouping_uncertain"
               for c in read_json(report_path)["conflicts"])


def test_reconcile_boundary_uncertain_and_missing_votes(tmp_path):
    capdir, slices_dir, manifest = multi_slice_fixture(tmp_path)
    docs = auto_proposals(manifest, slices_dir)
    sid = next(iter(docs))

    boundary = json.loads(json.dumps(docs[sid]))
    boundary["boundary"] = {"left": "uncertain", "right": "clear"}
    p = tmp_path / "b.json"
    p.write_bytes(cj.canonical_dumps(boundary))
    others = write_proposals(tmp_path / "b2", {k: v for k, v in docs.items() if k != sid},
                             order=[k for k in docs if k != sid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-b.json",
                                     report=tmp_path / "r-b.json")
    assert proc.returncode == 1
    assert any(c["code"] == "boundary_uncertain"
               for c in read_json(report_path)["conflicts"])

    audited = [s for s, d in docs.items() if d["overlap_votes"]]
    assert audited, "fixture produced no overlap audit"
    vsid = audited[0]
    missing_vote = json.loads(json.dumps(docs[vsid]))
    missing_vote["overlap_votes"] = missing_vote["overlap_votes"][1:]
    p = tmp_path / "v.json"
    p.write_bytes(cj.canonical_dumps(missing_vote))
    others = write_proposals(tmp_path / "v2", {k: v for k, v in docs.items() if k != vsid},
                             order=[k for k in docs if k != vsid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-v.json",
                                     report=tmp_path / "r-v.json")
    assert proc.returncode == 1
    assert any(c["code"] == "vote_missing"
               for c in read_json(report_path)["conflicts"])

    # excess vote: a core non-separator voted as if it were overlap
    excess = json.loads(json.dumps(docs[vsid]))
    entry = next(e for e in manifest["slices"] if e["slice_id"] == vsid)
    payload_doc = read_json(slices_dir / entry["input"]["path"])
    kinds = {u["unit_id"]: u["kind"] for u in payload_doc["units"]}
    core_uid = next(uid for uid in entry["core_ids"] if kinds[uid] != "separator")
    excess["overlap_votes"] = excess["overlap_votes"] + [{
        "unit_id": core_uid, "state": "claim", "label": None,
        "role_ref": None, "rationale": "excess",
    }]
    p = tmp_path / "excess.json"
    p.write_bytes(cj.canonical_dumps(excess))
    others = write_proposals(tmp_path / "e2", {k: v for k, v in docs.items() if k != vsid},
                             order=[k for k in docs if k != vsid])
    proc, _, report_path = reconcile(tmp_path, capdir, slices_dir, [p] + others,
                                     out=tmp_path / "m-e.json",
                                     report=tmp_path / "r-e.json")
    assert proc.returncode == 1
    assert any(c["code"] == "vote_excess"
               for c in read_json(report_path)["conflicts"])


def test_reconcile_empty_and_separator_only_sources(tmp_path):
    # empty source -> zero slices -> zero proposals required, empty merge
    capdir = capture(tmp_path / "e", [("empty.md", b"")])
    slices = tmp_path / "e-slices"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(slices)).returncode == 0
    manifest = read_json(slices / "manifest.json")
    assert manifest["slices"] == []
    proc, out, report_path = reconcile(tmp_path / "e-run", capdir, slices, [])
    assert proc.returncode == 0, proc.stderr
    assert read_json(out)["assignments"] == []
    report = read_json(report_path)
    assert report["complete"] is True
    assert report["counts"]["expected_slices"] == 0

    # whitespace-only source -> one mechanical separator-only core with no
    # labelable units; the child still audits nothing and merges cleanly
    capdir2 = capture(tmp_path / "w", [("ws.md", b"\n\n")])
    slices2 = tmp_path / "w-slices"
    assert cli("frame-slices", "--captures", str(capdir2), "--out-dir", str(slices2)).returncode == 0
    manifest2 = read_json(slices2 / "manifest.json")
    docs = auto_proposals(manifest2, slices2)
    assert docs and all(not d["assignments"] for d in docs.values())
    paths = write_proposals(tmp_path / "w-prop", docs)
    proc, out2, report2 = reconcile(tmp_path / "w-run", capdir2, slices2, paths)
    assert proc.returncode == 0, proc.stderr
    assert read_json(out2)["assignments"] == []
    assert read_json(report2)["complete"] is True
    registry = tmp_path / "w-registry.json"
    assert cli("assemble", "--captures", str(capdir2), "--proposals", str(out2),
               "--out", str(registry)).returncode == 0
    probe = cli("validate", "--registry", str(registry), "--captures", str(capdir2))
    assert probe.returncode == 0, probe.stdout


# ---------------------------------------------------------------------------
# determinism / tampering / packaging
# ---------------------------------------------------------------------------

def test_reconcile_determinism_reordered_inputs(tmp_path):
    capdir, slices_dir, manifest = multi_slice_fixture(tmp_path)
    docs = auto_proposals(manifest, slices_dir)
    forward = write_proposals(tmp_path / "fwd", docs, order=list(docs))
    proc, out_a, report_a = reconcile(tmp_path, capdir, slices_dir, forward,
                                      out=tmp_path / "m-a.json",
                                      report=tmp_path / "r-a.json")
    assert proc.returncode == 0, proc.stderr

    # same child bytes, different CLI arrival order -> byte-identical outputs
    proc, out_b, report_b = reconcile(tmp_path, capdir, slices_dir,
                                      list(reversed(forward)),
                                      out=tmp_path / "m-b.json",
                                      report=tmp_path / "r-b.json")
    assert proc.returncode == 0, proc.stderr
    assert read_bytes(out_a) == read_bytes(out_b)
    assert read_bytes(report_a) == read_bytes(report_b)

    # semantically equivalent child files with reordered assignments still
    # yield byte-identical merged proposals (registry order is canonical)
    reversed_docs = {k: json.loads(json.dumps(v)) for k, v in docs.items()}
    for doc in reversed_docs.values():
        doc["assignments"] = list(reversed(doc["assignments"]))
        doc["grouping_votes"] = list(reversed(doc["grouping_votes"]))
    backward = write_proposals(tmp_path / "bwd", reversed_docs,
                               order=list(reversed_docs))
    proc, out_c, _ = reconcile(tmp_path, capdir, slices_dir, backward,
                               out=tmp_path / "m-c.json",
                               report=tmp_path / "r-c.json")
    assert proc.returncode == 0, proc.stderr
    assert read_bytes(out_a) == read_bytes(out_c)


def test_reconcile_rejects_tampered_slices_manifest(tmp_path):
    capdir, slices_dir, manifest = slice_fixture(tmp_path, [("panel.md", PANEL)])
    docs = auto_proposals(manifest, slices_dir)
    paths = write_proposals(tmp_path, docs)
    raw = read_bytes(slices_dir / "manifest.json")
    tampered = json.loads(raw.decode("utf-8"))
    tampered["sources"][0]["units"][0]["end"] += 1
    bad = tmp_path / "bad-manifest.json"
    bad.write_bytes(cj.canonical_dumps(tampered))
    report_path = tmp_path / "r-t.json"
    proc = cli("proposal-reconcile", "--captures", str(capdir), "--slices", str(bad),
               "--proposal", str(paths[0]), "--out", str(tmp_path / "m-t.json"),
               "--report-out", str(report_path))
    assert proc.returncode == 1
    codes = {c["code"] for c in read_json(report_path)["conflicts"]}
    assert codes & {"frame_mismatch", "slice_replay_mismatch", "payload_mismatch"}


def test_reconcile_built_pyz_pipeline_outside_repo(tmp_path):
    assert PYZ.is_file(), "committed artifact missing; run build.py"
    work = tmp_path / "work"
    work.mkdir()
    (work / "body.md").write_bytes(PANEL)
    env = _env()
    env["PYTHONPATH"] = ""
    steps = [
        ["capture", "--in", str(work / "body.md"), "--locator", "repo#17:body",
         "--out", str(work / "caps")],
        ["frame-slices", "--captures", str(work / "caps"), "--out-dir", str(work / "slices")],
    ]
    for step in steps:
        proc = subprocess.run([sys.executable, str(PYZ), *step], cwd=str(work),
                              capture_output=True, text=True, env=env, timeout=120)
        assert proc.returncode == 0, proc.stderr

    manifest = read_json(work / "slices" / "manifest.json")
    docs = auto_proposals(manifest, work / "slices")
    proposal_paths = write_proposals(work, docs)
    args = [sys.executable, str(PYZ), "proposal-reconcile",
            "--captures", str(work / "caps"),
            "--slices", str(work / "slices" / "manifest.json")]
    for path in proposal_paths:
        args += ["--proposal", str(path)]
    args += ["--out", str(work / "merged.json"), "--report-out", str(work / "report.json")]
    proc = subprocess.run(args, cwd=str(work), capture_output=True, text=True,
                          env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr

    registry = subprocess.run(
        [sys.executable, str(PYZ), "assemble", "--captures", str(work / "caps"),
         "--proposals", str(work / "merged.json"), "--out", str(work / "registry.json")],
        cwd=str(work), capture_output=True, text=True, env=env, timeout=120,
    )
    assert registry.returncode == 0, registry.stderr
    validate = subprocess.run(
        [sys.executable, str(PYZ), "validate", "--registry", str(work / "registry.json"),
         "--captures", str(work / "caps")],
        cwd=str(work), capture_output=True, text=True, env=env, timeout=120,
    )
    assert validate.returncode == 0, validate.stdout + validate.stderr
    permissions = json.loads(validate.stdout)["permission"]
    assert permissions == {"complete_registry_claims": True, "finalized_unclaimed": True}
