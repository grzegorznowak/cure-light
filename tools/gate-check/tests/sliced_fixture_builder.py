"""Build a real ``claim-run-manifest/2`` sliced fixture for gate tests.

Runs the sibling producer CLI (dev checkout, ``python -m claim_registry.cli``)
in a temp directory: batch capture of two small sources -> frame-slices with
small caps (forcing overlaps) -> one mechanical child proposal per slice ->
proposal-reconcile -> assemble -> validate -> seal ``claim-run-manifest/2``.
Nothing is written into the baseline or any repo.

The builder returns every completed process as data; tests assert the step
results themselves so a missing feature is a named assertion failure, never a
silent fixture error or skip.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from subprocess import CompletedProcess, run

UNIT = Path(__file__).resolve().parents[1]
COMMON = UNIT.parent / "common"
if str(COMMON) not in sys.path:  # dev checkout import for canonical dumps
    sys.path.insert(0, str(COMMON))

from toolkit import canonical_json as cj  # noqa: E402

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

STEPS = ("capture", "frame_slices", "reconcile", "assemble", "validate", "seal")


def find_producer() -> Path | None:
    candidate = UNIT.parent / "claim-registry"
    if (candidate / "claim_registry" / "cli.py").is_file():
        return candidate
    return None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _producer(producer: Path, args: list[str], cwd: Path) -> CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(producer), str(COMMON)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return run(
        [sys.executable, "-m", "claim_registry.cli", *args],
        cwd=str(cwd), capture_output=True, text=True, env=env, timeout=300,
    )


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


def build(dest: Path) -> dict:
    producer = find_producer()
    if producer is None:
        raise RuntimeError("sibling claim-registry producer not found")
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    src_a = dest / "a.md"
    src_a.write_bytes(SRC_A)
    src_b = dest / "b.md"
    src_b.write_bytes(SRC_B)

    captures = dest / "captures"
    capture = _producer(producer, [
        "capture", "--in", str(src_a), "--locator", "repo#17:a",
        "--in", str(src_b), "--locator", "repo#17:b", "--out", str(captures),
    ], dest)

    slices_dir = dest / "slices"
    frame_slices = _producer(producer, [
        "frame-slices", "--captures", str(captures), "--out-dir", str(slices_dir),
        "--max-bytes", "300", "--max-units", "8", "--overlap-units", "2",
    ], dest)
    slices_doc = None
    children: list[Path] = []
    if (slices_dir / "manifest.json").is_file():
        slices_doc = json.loads((slices_dir / "manifest.json").read_bytes())
        children_dir = dest / "children"
        children_dir.mkdir(exist_ok=True)
        for i, entry in enumerate(slices_doc["slices"]):
            path = children_dir / f"child-{i:04d}.json"
            path.write_bytes(cj.canonical_dumps(auto_child(slices_dir, entry)))
            children.append(path)

    merged = dest / "merged.json"
    reconciliation = dest / "reconciliation.json"
    reconcile_args = [
        "proposal-reconcile", "--captures", str(captures),
        "--slices", str(slices_dir / "manifest.json"),
    ]
    for path in children:
        reconcile_args += ["--proposal", str(path)]
    reconcile_args += ["--out", str(merged), "--report-out", str(reconciliation)]
    reconcile = _producer(producer, reconcile_args, dest)

    registry = dest / "registry.json"
    report = dest / "report.json"
    assemble = _producer(producer, [
        "assemble", "--captures", str(captures),
        "--proposals", str(merged), "--out", str(registry),
    ], dest)
    validate = _producer(producer, [
        "validate", "--registry", str(registry),
        "--captures", str(captures), "--report-out", str(report),
    ], dest)

    manifest_path = dest / "run-manifest.json"
    seal_args = [
        "manifest", "--captures", str(captures),
        "--slices", str(slices_dir / "manifest.json"),
    ]
    for path in children:
        seal_args += ["--slice-proposal", str(path)]
    seal_args += [
        "--reconciliation", str(reconciliation), "--proposals", str(merged),
        "--registry", str(registry), "--report", str(report),
        "--out", str(manifest_path),
    ]
    seal = _producer(producer, seal_args, dest)

    return {
        "dest": dest,
        "producer": producer,
        "captures": captures,
        "slices_dir": slices_dir,
        "slices_manifest": slices_dir / "manifest.json",
        "slices_doc": slices_doc,
        "children": children,
        "merged": merged,
        "reconciliation": reconciliation,
        "registry": registry,
        "report": report,
        "manifest": manifest_path,
        "capture": capture,
        "frame_slices": frame_slices,
        "reconcile": reconcile,
        "assemble": assemble,
        "validate": validate,
        "seal": seal,
    }
