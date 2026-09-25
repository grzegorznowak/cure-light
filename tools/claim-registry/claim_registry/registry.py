"""Registry assembly: captures + frames + label proposals -> canonical JSON.

Proposals input format (``claim-proposals/1``) is documented in README and
summarized here::

    {
      "schema_version": "claim-proposals/1",
      "assignments": [
        {"source_ref": "...", "unit_ids": ["..."], "state": "claim",
         "rationale": "...", "parent_ref": null},
        {"source_ref": "...", "unit_ids": ["..."], "state": "nonclaim",
         "label": "context", "rationale": "...", "role_ref": "..."}
      ],
      "groups": [],            # optional, non-owning semantic groups
      "precedence": [],        # optional, authority-cited precedence records
      "uncaptured_source_refs": []   # optional witness limitations
    }

Ownership rules (spec section 1.3): every unit has exactly one owner; claims
are contiguous runs of whole units (consecutive ordinals); separators are
mechanically nonclaim ``context``; unowned units are recorded ``pending``;
double ownership is an error.  Claim ids are
``<source_ref>:<start>-<end>:<sha256(span bytes)>``.
"""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

from . import canonical
from .capture import SourceCapture
from .frame import Frame, Unit

SCHEMA_VERSION = "claim-registry/1"
PROPOSALS_SCHEMA_VERSION = "claim-proposals/1"
CANONICALIZATION = "claim-json/1"
NONCLAIM_LABELS = ("context", "advisory", "example", "baseline")
DEFAULT_WINDOW_RECIPE = {
    "version": "1",
    "max_units": 64,
    "max_bytes": 65536,
    "overlap_units": 8,
}


class RegistryAssemblyError(ValueError):
    """Fail-loud assembly failure (unknown ids, double ownership, ...)."""


@dataclass
class AssemblyResult:
    payload: dict
    envelope: dict
    canonical_bytes: bytes
    notes: list[str]


def _claim_sha(data: bytes, start: int, end: int) -> str:
    return hashlib.sha256(data[start:end]).hexdigest()


def _claim_id(source_ref: str, start: int, end: int, sha: str) -> str:
    return f"{source_ref}:{start}-{end}:{sha}"


def default_proposals(source_ref: str, frame: Frame) -> dict:
    """One claim per non-separator block; separators explicit nonclaim context."""
    assignments = []
    for u in frame.units:
        if u.kind == "separator":
            assignments.append(
                {
                    "source_ref": source_ref,
                    "unit_ids": [u.unit_id(source_ref)],
                    "state": "nonclaim",
                    "label": "context",
                    "rationale": "mechanical separator",
                    "role_ref": "spec:claim-registry/1#separator",
                }
            )
        else:
            assignments.append(
                {
                    "source_ref": source_ref,
                    "unit_ids": [u.unit_id(source_ref)],
                    "state": "claim",
                    "rationale": "",
                }
            )
    return {
        "schema_version": PROPOSALS_SCHEMA_VERSION,
        "assignments": assignments,
    }


def _load_unit_index(
    captures: Sequence[SourceCapture], frames: Mapping[str, Frame]
) -> tuple[
    dict[str, SourceCapture],
    dict[str, Unit],
    dict[str, dict[str, Unit]],
]:
    capture_map: dict[str, SourceCapture] = {}
    for cap in captures:
        if cap.source_ref in capture_map:
            raise RegistryAssemblyError(f"duplicate source_ref {cap.source_ref}")
        capture_map[cap.source_ref] = cap
    for ref in frames:
        if ref not in capture_map:
            raise RegistryAssemblyError(f"frame for uncaptured source {ref}")
    units_by_id: dict[str, Unit] = {}
    units_by_source: dict[str, dict[str, Unit]] = {}
    for ref, frame in frames.items():
        per_source: dict[str, Unit] = {}
        for unit in frame.units:
            uid = unit.unit_id(ref)
            if uid in units_by_id:
                raise RegistryAssemblyError(f"duplicate unit_id {uid}")
            units_by_id[uid] = unit
            per_source[uid] = unit
        units_by_source[ref] = per_source
    for ref in capture_map:
        if ref not in frames:
            raise RegistryAssemblyError(f"captured source without frame: {ref}")
    return capture_map, units_by_id, units_by_source


def _validate_assignments(
    proposals: dict,
    capture_map: Mapping[str, SourceCapture],
    units_by_id: Mapping[str, Unit],
    units_by_source: Mapping[str, Mapping[str, Unit]],
) -> tuple[list[dict], list[dict]]:
    assignments = proposals.get("assignments")
    if not isinstance(assignments, list):
        raise RegistryAssemblyError("proposals.assignments must be a list")
    claimed_units: set[str] = set()
    claim_drafts: list[dict] = []
    nonclaim_drafts: list[dict] = []
    for i, a in enumerate(assignments):
        where = f"assignments[{i}]"
        if not isinstance(a, dict):
            raise RegistryAssemblyError(f"{where} must be an object")
        source_ref = a.get("source_ref")
        if source_ref not in capture_map:
            raise RegistryAssemblyError(f"{where}: unknown source_ref {source_ref!r}")
        unit_ids = a.get("unit_ids")
        if not isinstance(unit_ids, list) or not unit_ids:
            raise RegistryAssemblyError(f"{where}: unit_ids must be a non-empty list")
        state = a.get("state")
        if state not in ("claim", "nonclaim"):
            raise RegistryAssemblyError(f"{where}: state must be claim or nonclaim")
        members: list[Unit] = []
        for uid in unit_ids:
            unit = units_by_id.get(uid)
            if unit is None:
                raise RegistryAssemblyError(f"{where}: unknown unit_id {uid!r}")
            if uid in claimed_units:
                raise RegistryAssemblyError(f"{where}: unit double-owned: {uid}")
            claimed_units.add(uid)
            members.append(unit)
        members.sort(key=lambda u: u.ordinal)
        if state == "claim":
            ordinals = [u.ordinal for u in members]
            if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
                raise RegistryAssemblyError(
                    f"{where}: claim members must be consecutive whole units, got {ordinals}"
                )
            if any(u.kind == "separator" for u in members):
                raise RegistryAssemblyError(
                    f"{where}: separator units cannot be claim members"
                )
            claim_drafts.append(
                {
                    "source_ref": source_ref,
                    "members": members,
                    "rationale": a.get("rationale", ""),
                    "parent_ref": a.get("parent_ref"),
                }
            )
        else:
            label = a.get("label")
            if label not in NONCLAIM_LABELS:
                raise RegistryAssemblyError(
                    f"{where}: nonclaim label must be one of {NONCLAIM_LABELS}, got {label!r}"
                )
            rationale = a.get("rationale")
            role_ref = a.get("role_ref")
            if not isinstance(rationale, str) or not rationale.strip():
                raise RegistryAssemblyError(f"{where}: nonclaim rationale required")
            if not isinstance(role_ref, str) or not role_ref.strip():
                raise RegistryAssemblyError(f"{where}: nonclaim role_ref required")
            if any(u.kind == "separator" for u in members) and label != "context":
                raise RegistryAssemblyError(
                    f"{where}: separator units are mechanically nonclaim context"
                )
            nonclaim_drafts.append(
                {
                    "source_ref": source_ref,
                    "members": members,
                    "label": label,
                    "rationale": rationale,
                    "role_ref": role_ref,
                }
            )
    return claim_drafts, nonclaim_drafts


def _build_claims(
    src_by_ref: Mapping[str, bytes],
    claim_drafts: list[dict],
    notes: list[str],
) -> tuple[list[dict], dict[str, dict]]:
    claims: list[dict] = []
    by_id: dict[str, dict] = {}
    for draft in claim_drafts:
        ref = draft["source_ref"]
        members = draft["members"]
        start, end = members[0].start, members[-1].end
        sha = _claim_sha(src_by_ref[ref], start, end)
        cid = _claim_id(ref, start, end, sha)
        claim = {
            "claim_id": cid,
            "source_ref": ref,
            "start": start,
            "end": end,
            "sha256": sha,
            "unit_ids": [u.unit_id(ref) for u in members],
            "parent_ref": None,
            "active": True,
            "_draft": draft,
        }
        if cid in by_id:
            raise RegistryAssemblyError(f"duplicate claim_id {cid}")
        by_id[cid] = claim
        claims.append(claim)

    return claims, by_id


def _validate_decomposition(
    proposals: dict,
    capture_map: Mapping[str, SourceCapture],
    units_by_id: Mapping[str, Unit],
) -> list[dict]:
    """Parse and validate the optional ``decomposition`` section.

    Shape::

        "decomposition": [
          {"parent": {"source_ref": "...", "unit_ids": [...]},
           "children": [{"unit_ids": [...], "rationale": "..."}, ...]}
        ]

    Parents become inactive non-owning containers; children are active claims
    with ``parent_ref`` pointing at the parent claim id.  Containment-only and
    strict-containment rules are enforced here.
    """
    entries = proposals.get("decomposition", []) or []
    if not isinstance(entries, list):
        raise RegistryAssemblyError("proposals.decomposition must be a list")
    drafts: list[dict] = []
    for i, entry in enumerate(entries):
        where = f"decomposition[{i}]"
        if not isinstance(entry, dict):
            raise RegistryAssemblyError(f"{where} must be an object")
        parent_spec = entry.get("parent")
        children_spec = entry.get("children")
        if not isinstance(parent_spec, dict):
            raise RegistryAssemblyError(f"{where}.parent must be an object")
        if not isinstance(children_spec, list) or not children_spec:
            raise RegistryAssemblyError(f"{where}.children must be a non-empty list")

        def unit_list(spec, label):
            if not isinstance(spec, dict):
                raise RegistryAssemblyError(f"{where}.{label} must be an object")
            ref = spec.get("source_ref")
            if ref not in capture_map:
                raise RegistryAssemblyError(f"{where}.{label}: unknown source_ref {ref!r}")
            uids = spec.get("unit_ids")
            if not isinstance(uids, list) or not uids:
                raise RegistryAssemblyError(f"{where}.{label}: unit_ids must be non-empty")
            units: list[Unit] = []
            for uid in uids:
                u = units_by_id.get(uid)
                if u is None:
                    raise RegistryAssemblyError(f"{where}.{label}: unknown unit_id {uid!r}")
                units.append(u)
            units.sort(key=lambda u: u.ordinal)
            ordinals = [u.ordinal for u in units]
            if ordinals != list(range(ordinals[0], ordinals[0] + len(ordinals))):
                raise RegistryAssemblyError(
                    f"{where}.{label}: units must be consecutive whole units"
                )
            if any(u.kind == "separator" for u in units):
                raise RegistryAssemblyError(
                    f"{where}.{label}: separators cannot belong to decomposition spans"
                )
            return ref, units

        ref, parent_units = unit_list(parent_spec, "parent")
        parent_span = (parent_units[0].start, parent_units[-1].end)
        child_drafts = []
        seen_child_units: set[str] = set()
        for j, child_spec in enumerate(children_spec):
            if isinstance(child_spec, dict):
                child_spec = dict(child_spec)
                child_spec.setdefault("source_ref", ref)
            cref, child_units = unit_list(child_spec, f"children[{j}]")
            if cref != ref:
                raise RegistryAssemblyError(
                    f"{where}.children[{j}]: parent and child from different sources"
                )
            child_span = (child_units[0].start, child_units[-1].end)
            if not (parent_span[0] <= child_span[0] and child_span[1] <= parent_span[1]):
                raise RegistryAssemblyError(
                    f"{where}.children[{j}]: child span not contained in parent span"
                )
            if child_span == parent_span:
                raise RegistryAssemblyError(
                    f"{where}.children[{j}]: child equals full parent span"
                )
            ids = {u.unit_id(ref) for u in child_units}
            if ids & seen_child_units:
                raise RegistryAssemblyError(
                    f"{where}.children[{j}]: children overlap each other"
                )
            seen_child_units |= ids
            child_drafts.append({
                "units": child_units,
                "rationale": child_spec.get("rationale", "") if isinstance(child_spec, dict) else "",
            })
        drafts.append({"source_ref": ref, "parent_units": parent_units,
                       "children": child_drafts})
    return drafts


def _apply_decomposition(
    src_by_ref: Mapping[str, bytes],
    claims: list[dict],
    by_id: dict[str, dict],
    owner: dict[str, dict],
    drafts: list[dict],
    notes: list[str],
) -> None:
    """Materialize decomposition claims after regular ownership is known."""
    children_total = 0
    for draft in drafts:
        ref = draft["source_ref"]
        parent_units = draft["parent_units"]
        p_start, p_end = parent_units[0].start, parent_units[-1].end
        p_sha = _claim_sha(src_by_ref[ref], p_start, p_end)
        parent_id = _claim_id(ref, p_start, p_end, p_sha)
        if parent_id in by_id:
            raise RegistryAssemblyError(f"duplicate decomposition parent {parent_id}")
        child_claims: list[dict] = []
        for child in draft["children"]:
            c_units = child["units"]
            c_start, c_end = c_units[0].start, c_units[-1].end
            c_sha = _claim_sha(src_by_ref[ref], c_start, c_end)
            c_id = _claim_id(ref, c_start, c_end, c_sha)
            if c_id in by_id:
                raise RegistryAssemblyError(f"duplicate decomposition child {c_id}")
            for u in c_units:
                uid = u.unit_id(ref)
                if uid in owner:
                    raise RegistryAssemblyError(
                        f"decomposition child unit already owned: {uid}"
                    )
            claim = {
                "claim_id": c_id,
                "source_ref": ref,
                "start": c_start,
                "end": c_end,
                "sha256": c_sha,
                "unit_ids": [u.unit_id(ref) for u in c_units],
                "parent_ref": parent_id,
                "active": True,
            }
            claims.append(claim)
            by_id[c_id] = claim
            for u in c_units:
                owner[u.unit_id(ref)] = {
                    "claim_id": c_id,
                    "rationale": child.get("rationale", "") or "",
                }
            child_claims.append(claim)
            children_total += 1
        parent = {
            "claim_id": parent_id,
            "source_ref": ref,
            "start": p_start,
            "end": p_end,
            "sha256": p_sha,
            "unit_ids": [u.unit_id(ref) for u in parent_units],
            "parent_ref": None,
            "active": False,
        }
        claims.append(parent)
        by_id[parent_id] = parent
        child_units = {uid for c in child_claims for uid in c["unit_ids"]}
        for u in parent_units:
            uid = u.unit_id(ref)
            if uid in child_units:
                continue
            own = owner.get(uid)
            if own is None:
                raise RegistryAssemblyError(
                    f"decomposition remainder unit unowned in parent {parent_id}: {uid}"
                )
            if "claim_id" in own:
                raise RegistryAssemblyError(
                    f"decomposition remainder unit double-owned in parent {parent_id}: {uid}"
                )
    if drafts:
        notes.append(
            f"decomposition validated: {len(drafts)} parent container(s), "
            f"{children_total} contained child claim(s); parents recorded inactive"
        )
    else:
        notes.append("decomposition validation deferred: no decomposition declared in proposals")


def _build_witness(
    captures: Sequence[SourceCapture],
    frames: Mapping[str, Frame],
    labels_by_unit: Mapping[str, dict],
    recipe: dict,
    uncaptured_source_refs: list[str],
) -> dict:
    per_source = []
    ordered = sorted(captures, key=lambda c: c.source_ref.encode("utf-8"))
    for cap in ordered:
        frame = frames[cap.source_ref]
        owned = 0
        owned_bytes = 0
        pending = 0
        conflicts = 0
        for unit in frame.units:
            label = labels_by_unit.get(unit.unit_id(cap.source_ref))
            if label is None:
                continue
            if label["state"] in ("claim", "nonclaim"):
                owned += 1
                owned_bytes += unit.byte_length
            elif label["state"] == "pending":
                pending += 1
            if label.get("_conflict"):
                conflicts += 1
        complete = pending == 0 and conflicts == 0
        per_source.append(
            {
                "source_ref": cap.source_ref,
                "sha256": cap.sha256,
                "byte_length": cap.byte_length,
                "blob_algorithm": cap.blob_algorithm,
                "blob_oid": cap.blob_oid,
                "frame_recipe_hash": canonical.recipe_hash(frame.recipe),
                "unit_count": frame.unit_count,
                "covered_unit_count": owned,
                "covered_byte_count": owned_bytes,
                "pending_count": pending,
                "conflict_count": conflicts,
                "error_count": 0,
                "empty_source": cap.empty,
                "complete": complete,
            }
        )
    complete = (
        all(s["complete"] for s in per_source)
        and not uncaptured_source_refs
    )
    return {
        "per_source": per_source,
        "uncaptured_source_refs": sorted(set(uncaptured_source_refs)),
        "complete": complete,
        "errors": [],
    }


def assemble_registry(
    captures: Sequence[SourceCapture],
    frames: Mapping[str, Frame],
    proposals: dict,
    *,
    window_recipe: dict | None = None,
) -> AssemblyResult:
    """Assemble the canonical registry envelope."""
    if proposals.get("schema_version") != PROPOSALS_SCHEMA_VERSION:
        raise RegistryAssemblyError(
            f"proposals schema_version must be {PROPOSALS_SCHEMA_VERSION!r}"
        )
    capture_map, units_by_id, units_by_source = _load_unit_index(captures, frames)
    claim_drafts, nonclaim_drafts = _validate_assignments(
        proposals, capture_map, units_by_id, units_by_source
    )
    decomposition_drafts = _validate_decomposition(proposals, capture_map, units_by_id)
    notes: list[str] = []
    src_by_ref = {c.source_ref: c.data for c in captures}
    claims, claims_by_id = _build_claims(src_by_ref, claim_drafts, notes)

    # unit_id -> ownership
    owner: dict[str, dict] = {}
    for claim in claims:
        for uid in claim["unit_ids"]:
            owner[uid] = {
                "claim_id": claim["claim_id"],
                "rationale": claim["_draft"].get("rationale", "") or "",
            }
    for draft in nonclaim_drafts:
        for unit in draft["members"]:
            uid = unit.unit_id(draft["source_ref"])
            if uid in owner:
                raise RegistryAssemblyError(f"unit double-owned: {uid}")
            owner[uid] = {
                "nonclaim_label": draft["label"],
                "rationale": draft["rationale"],
                "role_ref": draft["role_ref"],
            }

    # decomposition containers are materialized after regular ownership so
    # remainder units must already carry explicit nonclaim ownership.
    _apply_decomposition(src_by_ref, claims, claims_by_id, owner,
                         decomposition_drafts, notes)

    # auto-assign unowned separators to mechanical nonclaim context
    for ref, frame in frames.items():
        for unit in frame.units:
            uid = unit.unit_id(ref)
            if uid in owner:
                continue
            if unit.kind == "separator":
                owner[uid] = {
                    "nonclaim_label": "context",
                    "rationale": "blank/structural separator (mechanical)",
                    "role_ref": "spec:claim-registry/1#separator",
                }

    # labels in unit order
    labels = []
    labels_by_unit: dict[str, dict] = {}
    ordered_sources = sorted(capture_map.values(), key=lambda c: c.source_ref.encode("utf-8"))
    for cap in ordered_sources:
        for unit in frames[cap.source_ref].units:
            uid = unit.unit_id(cap.source_ref)
            own = owner.get(uid)
            if own is None:
                entry = {
                    "unit_id": uid,
                    "state": "pending",
                    "claim_id": None,
                    "nonclaim_label": None,
                    "rationale": "no proposal covered this unit",
                    "role_ref": None,
                }
            elif "claim_id" in own:
                entry = {
                    "unit_id": uid,
                    "state": "claim",
                    "claim_id": own["claim_id"],
                    "nonclaim_label": None,
                    "rationale": own.get("rationale", ""),
                    "role_ref": None,
                }
            else:
                entry = {
                    "unit_id": uid,
                    "state": "nonclaim",
                    "claim_id": None,
                    "nonclaim_label": own["nonclaim_label"],
                    "rationale": own["rationale"],
                    "role_ref": own["role_ref"],
                }
            labels.append(entry)
            labels_by_unit[uid] = entry

    # groups / precedence
    groups = copy.deepcopy(proposals.get("groups", []) or [])
    for g in groups:
        if not isinstance(g, dict) or not isinstance(g.get("group_id"), str):
            raise RegistryAssemblyError("each group requires a string group_id")
        for key in ("unit_ids", "claim_ids"):
            if key in g and isinstance(g[key], list):
                g[key] = sorted(g[key], key=lambda x: str(x).encode("utf-8"))
    groups.sort(key=lambda g: g["group_id"].encode("utf-8"))
    precedence = copy.deepcopy(proposals.get("precedence", []) or [])
    for p in precedence:
        if not isinstance(p, dict) or not isinstance(p.get("precedence_id"), str):
            raise RegistryAssemblyError("each precedence record requires a string precedence_id")
    precedence.sort(key=lambda p: p["precedence_id"].encode("utf-8"))

    recipes = {canonical.canonical_dumps(frame.recipe) for frame in frames.values()}
    if len(recipes) > 1:
        raise RegistryAssemblyError("frames were produced with different recipes")
    frame_recipe = next(iter(frames.values())).recipe

    recipe = {
        "frame": frame_recipe,
        "window": dict(window_recipe or DEFAULT_WINDOW_RECIPE),
        "canonicalization": CANONICALIZATION,
    }

    unit_records = []
    for cap in ordered_sources:
        for unit in frames[cap.source_ref].units:
            unit_records.append(unit.record(cap.source_ref))

    claims_out = sorted(claims, key=lambda c: (
        c["source_ref"].encode("utf-8"), c["start"], c["end"], c["claim_id"]))
    claims_out = [
        {k: v for k, v in c.items() if not k.startswith("_")} for c in claims_out
    ]

    uncaptured = proposals.get("uncaptured_source_refs", []) or []
    if not isinstance(uncaptured, list) or not all(isinstance(x, str) for x in uncaptured):
        raise RegistryAssemblyError("uncaptured_source_refs must be a list of strings")

    witness = _build_witness(
        captures, frames, labels_by_unit, frame_recipe, uncaptured
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "recipe": recipe,
        "recipe_hash": canonical.recipe_hash(recipe),
        "sources": sorted(
            (cap.record() for cap in captures),
            key=lambda s: s["source_ref"].encode("utf-8"),
        ),
        "units": unit_records,
        "claims": claims_out,
        "labels": labels,
        "groups": groups,
        "precedence": precedence,
        "witness": witness,
    }
    envelope = {"registry_hash": canonical.registry_hash(payload), "payload": payload}
    return AssemblyResult(
        payload=payload,
        envelope=envelope,
        canonical_bytes=canonical.canonical_dumps(envelope),
        notes=notes,
    )


__all__ = [
    "AssemblyResult",
    "CANONICALIZATION",
    "DEFAULT_WINDOW_RECIPE",
    "NONCLAIM_LABELS",
    "PROPOSALS_SCHEMA_VERSION",
    "RegistryAssemblyError",
    "SCHEMA_VERSION",
    "assemble_registry",
    "default_proposals",
]
