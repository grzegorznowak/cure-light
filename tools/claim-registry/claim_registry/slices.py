"""``frame-slices``: bounded byte-exact worker payloads from verified captures.

One command produces one ``frame-slices/1`` manifest directory:

    <out-dir>/manifest.json                       canonical frame-slices/1
    <out-dir>/payload/<s>-<n>.json                canonical frame-slice-input/1

Every captured source is framed exactly once with the pinned walker; slices
are bounded views over that single unit table (see
``claim_label_contract.slicing``).  Payload file names are deterministic
(source index in sorted ``source_ref`` order, slice ordinal within the
source); the manifest never records a machine path.  The out-dir is created
fresh and is never overwritten; payloads are written before the manifest so
an interrupted run cannot leave a consumable manifest behind.
"""

from __future__ import annotations

import hashlib
import os
from typing import Sequence

from toolkit import canonical_json as cj
from toolkit import tool_unit

from claim_label_contract import schemas, slicing

from .capture import SourceCapture, raw_sha256
from .frame import frame_source

MANIFEST_NAME = "manifest.json"
PAYLOAD_DIR = "payload"


def captures_sha256(captures: Sequence[SourceCapture]) -> str:
    """Content digest of the source identity set, independent of CLI order.

    The identity record is the capture-manifest source record without its
    ``file`` key; records are sorted by ``source_ref`` UTF-8 bytes.
    """
    records = sorted(
        (cap.record() for cap in captures),
        key=lambda record: record["source_ref"].encode("utf-8"),
    )
    return hashlib.sha256(cj.canonical_dumps(records)).hexdigest()


def frame_slices(captures_dir: str, out_dir: str, *, recipe: dict) -> dict:
    """Frame every captured source once, slice it, and write the manifest dir."""
    from .cli import read_capture_dir  # local import avoids a module cycle

    captures = read_capture_dir(captures_dir)
    refs = [cap.source_ref for cap in captures]
    if len(set(refs)) != len(refs):
        raise slicing.SlicePlanError("capture directory contains duplicate source_refs")
    if os.path.exists(out_dir):
        raise tool_unit.UsageError(
            f"frame-slices: {out_dir!r} already exists; refusing to overwrite "
            "(use a fresh --out-dir)"
        )

    ordered = sorted(captures, key=lambda cap: cap.source_ref.encode("utf-8"))
    frames = {}
    for cap in ordered:
        frames[cap.source_ref] = frame_source(cap.data)
    recipes = {cj.canonical_dumps(frame.recipe) for frame in frames.values()}
    if len(recipes) > 1:
        raise slicing.SlicePlanError("captures were framed with different recipes")
    frame_recipe = frames[ordered[0].source_ref].recipe
    frame_recipe_hash = cj.canonical_hash(frame_recipe)
    recipe_hash = cj.canonical_hash(recipe)

    plans_by_source: dict[str, list] = {}
    total = 0
    for cap in ordered:
        plans = slicing.plan_slices(
            cap.source_ref,
            frame_recipe_hash,
            recipe,
            [u.record(cap.source_ref) for u in frames[cap.source_ref].units],
            cap.data,
        )
        plans_by_source[cap.source_ref] = plans
        total += len(plans)

    sources = []
    for cap in ordered:
        sources.append({
            "source_ref": cap.source_ref,
            "sha256": cap.sha256,
            "byte_length": cap.byte_length,
            "units": [u.record(cap.source_ref) for u in frames[cap.source_ref].units],
        })

    payload_dir = os.path.join(out_dir, PAYLOAD_DIR)
    os.makedirs(payload_dir, exist_ok=False)
    slices = []
    for s_index, cap in enumerate(ordered):
        for n, plan in enumerate(plans_by_source[cap.source_ref]):
            name = f"{s_index:04d}-{n:04d}.json"
            rel = f"{PAYLOAD_DIR}/{name}"
            raw = plan.payload_bytes
            if raw != cj.canonical_dumps(plan.payload):  # pragma: no cover - guard
                raise slicing.SlicePlanError("payload bytes are not canonical")
            with open(os.path.join(payload_dir, name), "wb") as fh:
                fh.write(raw)
            slices.append({
                "slice_id": plan.slice_id,
                "source_ref": plan.source_ref,
                "core_ids": list(plan.core_ids),
                "overlap_ids": list(plan.overlap_ids),
                "context_only_ids": list(plan.context_only_ids),
                "input": {
                    "path": rel,
                    "sha256": raw_sha256(raw),
                    "byte_length": len(raw),
                },
            })

    manifest = {
        "schema_version": schemas.FRAME_SLICES_VERSION,
        "captures_sha256": captures_sha256(captures),
        "frame_recipe": frame_recipe,
        "frame_recipe_hash": frame_recipe_hash,
        "slice_recipe": recipe,
        "slice_recipe_hash": recipe_hash,
        "sources": sources,
        "slices": slices,
    }
    errors = schemas.validate(schemas.FRAME_SLICES_1, manifest)
    if errors:  # pragma: no cover - contract bug guard
        raise slicing.SlicePlanError(f"internal frame-slices/1 schema violation: {errors[:3]}")
    with open(os.path.join(out_dir, MANIFEST_NAME), "wb") as fh:
        fh.write(cj.canonical_dumps(manifest))

    return {
        "out_dir": out_dir,
        "manifest": os.path.join(out_dir, MANIFEST_NAME),
        "sources": len(ordered),
        "slices": total,
        "captures_sha256": manifest["captures_sha256"],
        "slice_recipe_hash": recipe_hash,
    }


__all__ = ["captures_sha256", "frame_slices"]
