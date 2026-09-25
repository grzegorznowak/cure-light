"""``proposal-reconcile`` CLI adapter: replay the slice manifest, then merge.

Replay is producer-side and independent: the capture set is re-verified, every
source is framed again with the pinned walker, the slice partition and every
payload byte are recomputed from the recorded recipe, and only then are child
proposals admitted into :func:`claim_label_contract.reconciliation.reconcile`.

A failed attempt always writes the ``proposal-reconciliation/1`` report and
never a merged artifact; the caller removes any stale merged output before the
attempt begins.
"""

from __future__ import annotations

import hashlib
import os
from typing import Sequence

from toolkit import canonical_json as cj
from toolkit import tool_unit

from claim_label_contract import reconciliation, schemas, slicing

from .capture import raw_sha256
from .slices import captures_sha256


def _read(path: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError as exc:
        raise tool_unit.UsageError(f"cannot read {path!r}: {exc}") from exc


def _issue(code: str, source_ref, unit_ids=(), slice_ids=(), values=()) -> dict:
    return {
        "code": code,
        "source_ref": source_ref,
        "unit_ids": [uid for uid in unit_ids],
        "slice_ids": [sid for sid in slice_ids],
        "values": list(values),
    }


def _report(slices_sha256, inputs, counts, conflicts, warnings) -> dict:
    return {
        "schema_version": schemas.PROPOSAL_RECONCILIATION_VERSION,
        "slices_sha256": slices_sha256,
        "inputs": sorted(inputs, key=lambda record: record["slice_id"].encode("utf-8")),
        "merged_sha256": None,
        "complete": False,
        "conflicts": sorted(conflicts, key=cj.canonical_dumps),
        "warnings": sorted(warnings, key=cj.canonical_dumps),
        "counts": counts,
    }


def _empty_counts(received: int) -> dict:
    return {
        "expected_slices": 0,
        "received_proposals": received,
        "primary_assignments": 0,
        "audited_overlap_units": 0,
        "audited_seams": 0,
    }


def reconcile_run(
    captures_dir: str,
    slices_path: str,
    proposal_paths: Sequence[str],
) -> tuple[bytes | None, dict]:
    """Return (merged canonical bytes | None, proposal-reconciliation/1)."""
    from .cli import read_capture_dir  # local: avoids a module import cycle

    conflicts: list[dict] = []
    warnings: list[dict] = []

    def C(code, source_ref=None, unit_ids=(), slice_ids=(), values=()):
        conflicts.append(_issue(code, source_ref, unit_ids, slice_ids, values))

    slices_raw = _read(slices_path)
    slices_sha256 = hashlib.sha256(slices_raw).hexdigest()
    counts = _empty_counts(len(proposal_paths))
    manifest_dir = os.path.dirname(os.path.abspath(slices_path))

    try:
        manifest = cj.canonical_loads(slices_raw)
    except cj.CanonicalizationError as exc:
        C("slices_not_canonical", None, (), (), [str(exc)])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)
    if not isinstance(manifest, dict):
        C("manifest_invalid", None, (), (), ["root is not an object"])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)
    errors = schemas.validate(schemas.FRAME_SLICES_1, manifest)
    if errors:
        C("manifest_invalid", None, (), (), errors[:8])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)
    counts["expected_slices"] = len(manifest["slices"])

    try:
        captures = read_capture_dir(captures_dir)
    except tool_unit.UsageError:
        raise
    except Exception as exc:  # SemanticError: capture verification failed
        C("capture_invalid", None, (), (), [str(exc)])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)

    from .frame import frame_source

    ordered = sorted(captures, key=lambda cap: cap.source_ref.encode("utf-8"))
    frames = {cap.source_ref: frame_source(cap.data) for cap in ordered}
    recipes = {cj.canonical_dumps(frame.recipe) for frame in frames.values()}
    if len(recipes) > 1:
        C("frame_recipe_mismatch", None, (), (), ["captured sources framed differently"])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)
    frame_recipe = frames[ordered[0].source_ref].recipe if ordered else manifest["frame_recipe"]
    recomputed_recipe_hash = cj.canonical_hash(frame_recipe)
    if (frame_recipe != manifest["frame_recipe"]
            or recomputed_recipe_hash != manifest["frame_recipe_hash"]):
        C("frame_recipe_mismatch", None, (), (),
          [manifest["frame_recipe_hash"], recomputed_recipe_hash])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)

    sources_index: dict[str, dict] = {}
    expected_sources = []
    for cap in ordered:
        units = [u.record(cap.source_ref) for u in frames[cap.source_ref].units]
        expected_sources.append({
            "source_ref": cap.source_ref,
            "sha256": cap.sha256,
            "byte_length": cap.byte_length,
            "units": units,
        })
        sources_index[cap.source_ref] = {unit["unit_id"]: unit for unit in units}
    if expected_sources != manifest["sources"]:
        C("frame_mismatch", None, (), (),
          ["recomputed global unit tables differ from the manifest"])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)
    if captures_sha256(captures) != manifest["captures_sha256"]:
        C("captures_sha256_mismatch", None, (), (),
          [captures_sha256(captures), manifest["captures_sha256"]])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)

    try:
        slicing.validate_recipe_document(manifest["slice_recipe"])
    except slicing.SliceRecipeError as exc:
        C("slice_recipe_invalid", None, (), (), [str(exc)])
        return None, _report(slices_sha256, [], counts, conflicts, warnings)

    expected_slices: list[dict] = []
    plans = []
    for cap in ordered:
        plans.extend(slicing.plan_slices(
            cap.source_ref,
            manifest["frame_recipe_hash"],
            manifest["slice_recipe"],
            [u.record(cap.source_ref) for u in frames[cap.source_ref].units],
            cap.data,
            verify_spans=True,
        ))
    manifest_slices = manifest["slices"]
    payload_problems = 0
    for i, plan in enumerate(plans):
        record = manifest_slices[i] if i < len(manifest_slices) else None
        if record is None:
            payload_problems += 1
            C("slice_replay_mismatch", plan.source_ref, (), (),
              [f"manifest has fewer slices than the recipe yields at index {i}"])
            continue
        if (record.get("slice_id") != plan.slice_id
                or record.get("source_ref") != plan.source_ref
                or record.get("core_ids") != list(plan.core_ids)
                or record.get("overlap_ids") != list(plan.overlap_ids)
                or record.get("context_only_ids") != list(plan.context_only_ids)):
            payload_problems += 1
            C("slice_replay_mismatch", plan.source_ref, [], [record.get("slice_id")],
              ["slice partition differs from the recorded recipe"])
            continue
        rel = record["input"]["path"]
        if os.path.isabs(rel) or ".." in rel.split("/"):
            payload_problems += 1
            C("unsafe_payload_path", plan.source_ref, (), [plan.slice_id], [rel])
            continue
        try:
            raw = _read(os.path.join(manifest_dir, rel))
        except tool_unit.UsageError as exc:
            payload_problems += 1
            C("payload_missing", plan.source_ref, (), [plan.slice_id], [str(exc)])
            continue
        if (raw_sha256(raw) != record["input"]["sha256"]
                or len(raw) != record["input"]["byte_length"]
                or raw != plan.payload_bytes):
            payload_problems += 1
            C("payload_mismatch", plan.source_ref, (), [plan.slice_id],
              ["payload file bytes differ from the recorded and replayed bytes"])
            continue
        expected_slices.append({
            "slice_id": plan.slice_id,
            "source_ref": plan.source_ref,
            "core_ids": list(plan.core_ids),
            "overlap_ids": list(plan.overlap_ids),
            "context_only_ids": list(plan.context_only_ids),
            "payload": plan.payload,
            "payload_sha256": raw_sha256(raw),
            "payload_byte_length": len(raw),
        })
    if len(manifest_slices) != len(plans):
        payload_problems += 1
        C("slice_count_mismatch", None, (), (),
          [len(manifest_slices), len(plans)])
    if payload_problems or len(expected_slices) != len(manifest_slices):
        return None, _report(slices_sha256, [], counts, conflicts, warnings)

    proposal_inputs: list[dict] = []
    for i, path in enumerate(proposal_paths):
        raw = _read(path)
        entry: dict = {
            "label": f"proposal[{i}]",
            "sha256": raw_sha256(raw),
            "document": None,
            "error": None,
        }
        try:
            entry["document"] = cj.canonical_loads(raw)
        except cj.CanonicalizationError as exc:
            entry["error"] = str(exc)
        proposal_inputs.append(entry)

    merged, report = reconciliation.reconcile(
        sources=sources_index,
        expected_slices=expected_slices,
        proposals=proposal_inputs,
        slices_sha256=slices_sha256,
    )
    return merged, report


__all__ = ["reconcile_run"]
