"""Deterministic reconciliation of per-slice child proposals.

Policy (frozen from the D3 review; do not water down):

* every expected slice needs exactly one child document whose ``input_sha256``
  matches the payload digest; missing/duplicate/foreign children are named
  conflicts;
* primary assignments own only non-separator *core* units, each exactly once,
  claims are consecutive whole core units wholly inside one core; overlap and
  context units can never be primary-owned; separators are never labeled;
* every overlap non-separator carries exactly one audit vote which must agree
  with the owner's state/label/role.  A differing audit rationale is retained
  as a *warning*; the primary rationale is never replaced;
* one grouping vote per mechanically enumerated visible non-separator
  adjacency pair; votes for a pair visible in two slices must agree, only
  ``same``/``separate`` are accepted (``uncertain`` stops), and the vote must
  match the claim-group adjacency implied by the primary assignments;
* ``boundary.left``/``right`` must be ``clear``; ``spanning`` and
  ``uncertain`` are named conflicts, never silently repaired;
* a seam whose immediate predecessor is a non-separator is evidence-backed
  only when the later slice lists that predecessor in ``overlap_ids``;
  otherwise it is an ``unverified_seam`` conflict;
* the merged output is one ``claim-proposals/1`` document with canonically
  ordered primary assignments and empty decomposition/groups/precedence/
  uncaptured_source_refs; slice ids never leak into registry ids.

The function is pure: it returns canonical merged bytes (or ``None``) plus the
``proposal-reconciliation/1`` report.  All machine paths and timestamps are
excluded from both.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import hashlib

from toolkit import canonical_json as cj

from . import schemas

PROPOSALS_SCHEMA_VERSION = "claim-proposals/1"


class ReconciliationReportError(ValueError):
    """Internal report-shape bug (never expected for validated inputs)."""


def _issue(code: str, source_ref, unit_ids=(), slice_ids=(), values=()) -> dict:
    return {
        "code": code,
        "source_ref": source_ref,
        "unit_ids": sorted(set(unit_ids), key=lambda uid: uid.encode("utf-8")),
        "slice_ids": sorted(set(slice_ids), key=lambda sid: sid.encode("utf-8")),
        "values": list(values),
    }


def _sorted_issues(issues: list[dict]) -> list[dict]:
    return sorted(issues, key=cj.canonical_dumps)


def _visible_pairs(kinds: Mapping[str, str], visible_ids: Sequence[str]):
    for left, right in zip(visible_ids, visible_ids[1:]):
        if kinds[left] != "separator" and kinds[right] != "separator":
            yield left, right


def reconcile(
    *,
    sources: Mapping[str, Mapping[str, Mapping]],
    expected_slices: Sequence[Mapping],
    proposals: Sequence[Mapping],
    slices_sha256: str,
) -> tuple[bytes | None, dict]:
    """Merge validated child proposals; returns (merged_bytes|None, report)."""
    conflicts: list[dict] = []
    warnings: list[dict] = []

    def C(code, source_ref=None, unit_ids=(), slice_ids=(), values=()):
        conflicts.append(_issue(code, source_ref, unit_ids, slice_ids, values))

    def W(code, source_ref=None, unit_ids=(), slice_ids=(), values=()):
        warnings.append(_issue(code, source_ref, unit_ids, slice_ids, values))

    kinds_by_source = {
        ref: {uid: rec["kind"] for uid, rec in units.items()}
        for ref, units in sources.items()
    }
    ordinals_by_source = {
        ref: {uid: rec["ordinal"] for uid, rec in units.items()}
        for ref, units in sources.items()
    }
    unit_source = {
        uid: ref for ref, units in sources.items() for uid in units
    }

    by_slice = {s["slice_id"]: s for s in expected_slices}
    slice_order = list(by_slice)

    # -- child intake -------------------------------------------------------
    inputs: list[dict] = []
    docs: dict[str, tuple[dict, Mapping]] = {}
    seen_sids: set[str] = set()
    for proposal in proposals:
        doc = proposal.get("document")
        if doc is None:
            C("proposal_invalid", None, (), (), [proposal.get("error") or "unparseable"])
            continue
        sid = doc.get("slice_id") if isinstance(doc, dict) else None
        if isinstance(sid, str):
            inputs.append({"slice_id": sid, "sha256": proposal["sha256"]})
        errors = schemas.validate(schemas.SLICE_PROPOSALS_1, doc)
        if errors:
            C("proposal_invalid", None, (), [sid] if isinstance(sid, str) else [],
              errors[:8])
            if isinstance(sid, str):
                seen_sids.add(sid)
            continue
        if not isinstance(sid, str) or sid not in by_slice:
            C("foreign_slice", None, (), [sid] if isinstance(sid, str) else [],
              [proposal.get("label") or "proposal"])
            continue
        if sid in docs:
            C("duplicate_proposal", by_slice[sid]["source_ref"], (), [sid],
              [proposal.get("label") or "proposal"])
            continue
        seen_sids.add(sid)
        expected = by_slice[sid]
        if doc["input_sha256"] != expected["payload_sha256"]:
            C("input_hash_mismatch", expected["source_ref"], (), [sid],
              [doc["input_sha256"], expected["payload_sha256"]])
            continue
        docs[sid] = (doc, proposal)
    for sid in slice_order:
        if sid not in seen_sids:
            C("missing_proposal", by_slice[sid]["source_ref"], (), [sid], ())

    # -- pass A: primary assignments ---------------------------------------
    owners: dict[str, dict] = {}
    covered_by_slice: dict[str, set[str]] = {}
    for sid in slice_order:
        expected = by_slice[sid]
        ref = expected["source_ref"]
        kinds = kinds_by_source.get(ref, {})
        ordinals = ordinals_by_source.get(ref, {})
        core_set = set(expected["core_ids"])
        overlap_set = set(expected["overlap_ids"])
        context_set = set(expected["context_only_ids"])
        core_nonseps = [uid for uid in expected["core_ids"] if kinds.get(uid) != "separator"]
        covered: set[str] = set()
        covered_by_slice[sid] = covered
        if sid not in docs:
            continue
        doc = docs[sid][0]
        local_seen: dict[str, int] = {}
        for ai, assignment in enumerate(doc["assignments"]):
            aref = assignment["source_ref"]
            members = list(assignment["unit_ids"])
            if aref != ref:
                C("foreign_source", ref, members, [sid], [aref])
                continue
            bad = False
            for uid in members:
                if uid not in kinds:
                    other = unit_source.get(uid)
                    if other is None:
                        C("unknown_unit", ref, [uid], [sid], ())
                    else:
                        C("foreign_source", ref, [uid], [sid], [other])
                    bad = True
                elif uid not in core_set:
                    if uid in overlap_set:
                        C("overlap_as_owner", ref, [uid], [sid], ())
                    elif uid in context_set:
                        C("context_as_owner", ref, [uid], [sid], ())
                    else:
                        C("unit_outside_slice", ref, [uid], [sid], ())
                    bad = True
                elif kinds[uid] == "separator":
                    C("separator_labeled", ref, [uid], [sid], ())
                    bad = True
                if uid in local_seen:
                    C("unit_owned_twice", ref, [uid], [sid],
                      [local_seen[uid], ai])
                    bad = True
                local_seen[uid] = ai
            if bad:
                continue
            if assignment["state"] == "claim":
                member_ordinals = sorted(ordinals[uid] for uid in members)
                if member_ordinals != list(range(member_ordinals[0],
                                                 member_ordinals[0] + len(members))):
                    C("claim_not_contiguous", ref, members, [sid],
                      member_ordinals)
                    continue
                group_key = (sid, ai)
                for uid in members:
                    owners[uid] = {
                        "state": "claim", "label": None, "role_ref": None,
                        "rationale": assignment["rationale"],
                        "group_key": group_key, "slice_id": sid,
                    }
                    covered.add(uid)
            else:
                for uid in members:
                    owners[uid] = {
                        "state": "nonclaim", "label": assignment["label"],
                        "role_ref": assignment["role_ref"],
                        "rationale": assignment["rationale"],
                        "group_key": None, "slice_id": sid,
                    }
                    covered.add(uid)
        for uid in core_nonseps:
            if uid not in covered:
                C("assignment_missing", ref, [uid], [sid], ())

    # -- pass B: overlap votes ---------------------------------------------
    audited_overlap_units = 0
    for sid in slice_order:
        expected = by_slice[sid]
        if sid not in docs:
            continue
        ref = expected["source_ref"]
        kinds = kinds_by_source.get(ref, {})
        doc = docs[sid][0]
        overlap_nonseps = [
            uid for uid in expected["overlap_ids"] if kinds.get(uid) != "separator"
        ]
        audited_overlap_units += len(overlap_nonseps)
        overlap_set = set(expected["overlap_ids"])
        seen_votes: dict[str, int] = {}
        for vi, vote in enumerate(doc["overlap_votes"]):
            uid = vote["unit_id"]
            if uid not in kinds:
                other = unit_source.get(uid)
                C("unknown_unit" if other is None else "foreign_source", ref,
                  [uid], [sid], () if other is None else [other])
                continue
            if uid not in overlap_set or kinds[uid] == "separator":
                C("vote_excess", ref, [uid], [sid], ())
                continue
            if uid in seen_votes:
                C("vote_duplicate", ref, [uid], [sid], [seen_votes[uid], vi])
                continue
            seen_votes[uid] = vi
            owner = owners.get(uid)
            if owner is None:
                C("vote_for_unowned", ref, [uid], [sid], ())
                continue
            pair_slices = [sid, owner["slice_id"]]
            if vote["state"] != owner["state"]:
                C("state_disagreement", ref, [uid], pair_slices,
                  [vote["state"], owner["state"]])
                continue
            if vote["state"] == "nonclaim":
                if vote["label"] != owner["label"]:
                    C("label_disagreement", ref, [uid], pair_slices,
                      [vote["label"], owner["label"]])
                    continue
                if vote["role_ref"] != owner["role_ref"]:
                    C("role_disagreement", ref, [uid], pair_slices,
                      [vote["role_ref"], owner["role_ref"]])
                    continue
            if vote["rationale"] != owner["rationale"]:
                W("audit_rationale_differs", ref, [uid], pair_slices,
                  [owner["rationale"], vote["rationale"]])
        for uid in overlap_nonseps:
            if uid not in seen_votes:
                C("vote_missing", ref, [uid], [sid], ())

    # -- pass C: grouping votes --------------------------------------------
    pair_votes: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for sid in slice_order:
        expected = by_slice[sid]
        ref = expected["source_ref"]
        kinds = kinds_by_source.get(ref, {})
        wanted = list(_visible_pairs(
            kinds, list(expected["overlap_ids"]) + list(expected["core_ids"])
        ))
        if sid not in docs:
            continue
        doc = docs[sid][0]
        wanted_set = set(wanted)
        seen_pairs: set[tuple[str, str]] = set()
        for vote in doc["grouping_votes"]:
            pair = (vote["left_unit_id"], vote["right_unit_id"])
            if pair in seen_pairs:
                C("grouping_duplicate", ref, pair, [sid], ())
                continue
            seen_pairs.add(pair)
            if pair not in wanted_set:
                C("grouping_excess", ref, pair, [sid], ())
                continue
            pair_votes.setdefault(pair, []).append((sid, vote["grouping"]))
        for pair in wanted:
            if pair not in seen_pairs:
                C("grouping_missing", ref, pair, [sid], ())
    for pair, votes in pair_votes.items():
        values = {grouping for _, grouping in votes}
        slices_involved = [sid for sid, _ in votes]
        if len(values) > 1:
            C("grouping_disagreement", None, pair, slices_involved,
              sorted(values))
            continue
        grouping = votes[0][1]
        if grouping == "uncertain":
            C("grouping_uncertain", None, pair, slices_involved, ())
            continue
        left_owner = owners.get(pair[0])
        right_owner = owners.get(pair[1])
        if left_owner is None or right_owner is None:
            continue
        same_group = (
            left_owner["state"] == right_owner["state"] == "claim"
            and left_owner["group_key"] == right_owner["group_key"]
        )
        expected_grouping = "same" if same_group else "separate"
        if grouping != expected_grouping:
            C("grouping_assignment_mismatch", left_owner["slice_id"], pair,
              slices_involved, [grouping, expected_grouping])

    # -- pass D: boundaries and seam evidence ------------------------------
    for sid in slice_order:
        expected = by_slice[sid]
        ref = expected["source_ref"]
        if sid not in docs:
            continue
        boundary = docs[sid][0]["boundary"]
        core = list(expected["core_ids"])
        overlap = list(expected["overlap_ids"])
        if boundary["left"] != "clear":
            units = ([overlap[-1], core[0]] if overlap else [core[0]])
            C(f"boundary_{boundary['left']}", ref, units, [sid], ())
        if boundary["right"] != "clear":
            C(f"boundary_{boundary['right']}", ref, [core[-1]], [sid], ())

    audited_seams = 0
    by_source: dict[str, list] = {}
    for sid in slice_order:
        expected = by_slice[sid]
        by_source.setdefault(expected["source_ref"], []).append(expected)
    for ref, entries in by_source.items():
        kinds = kinds_by_source.get(ref, {})
        for prev_slice, next_slice in zip(entries, entries[1:]):
            prev_uid = prev_slice["core_ids"][-1]
            next_uid = next_slice["core_ids"][0]
            if kinds.get(prev_uid) != "separator" and prev_uid not in next_slice["overlap_ids"]:
                C("unverified_seam", ref, [prev_uid, next_uid],
                  [next_slice["slice_id"]], ())
            else:
                audited_seams += 1

    counts = {
        "expected_slices": len(expected_slices),
        "received_proposals": len(proposals),
        "primary_assignments": len(owners),
        "audited_overlap_units": audited_overlap_units,
        "audited_seams": audited_seams,
    }

    merged_bytes: bytes | None = None
    if not conflicts:
        merged_bytes = _build_merged(by_slice, slice_order, docs, ordinals_by_source)
    report = {
        "schema_version": schemas.PROPOSAL_RECONCILIATION_VERSION,
        "slices_sha256": slices_sha256,
        "inputs": sorted(inputs, key=lambda record: record["slice_id"].encode("utf-8")),
        "merged_sha256": (
            None if merged_bytes is None
            else hashlib.sha256(merged_bytes).hexdigest()
        ),
        "complete": merged_bytes is not None,
        "conflicts": _sorted_issues(conflicts),
        "warnings": _sorted_issues(warnings),
        "counts": counts,
    }
    shape_errors = schemas.validate(schemas.PROPOSAL_RECONCILIATION_1, report)
    if shape_errors:
        raise ReconciliationReportError(
            f"internal proposal-reconciliation/1 shape bug: {shape_errors[:3]}"
        )
    return merged_bytes, report


def _build_merged(by_slice, slice_order, docs, ordinals_by_source) -> bytes:
    entries = []
    for sid in slice_order:
        expected = by_slice[sid]
        ref = expected["source_ref"]
        ordinals = ordinals_by_source.get(ref, {})
        doc = docs[sid][0]
        for assignment in doc["assignments"]:
            entry = {"source_ref": ref, "unit_ids": list(assignment["unit_ids"]),
                     "state": assignment["state"]}
            entry["rationale"] = assignment["rationale"]
            if assignment["state"] == "nonclaim":
                entry["label"] = assignment["label"]
                entry["role_ref"] = assignment["role_ref"]
            entry["_first"] = min(ordinals[uid] for uid in assignment["unit_ids"])
            entries.append(entry)
    entries.sort(key=lambda e: (e["source_ref"].encode("utf-8"), e["_first"]))
    assignments = [
        {k: v for k, v in entry.items() if k != "_first"} for entry in entries
    ]
    merged = {
        "schema_version": PROPOSALS_SCHEMA_VERSION,
        "assignments": assignments,
        "decomposition": [],
        "groups": [],
        "precedence": [],
        "uncaptured_source_refs": [],
    }
    return cj.canonical_dumps(merged)


__all__ = ["PROPOSALS_SCHEMA_VERSION", "ReconciliationReportError", "reconcile"]
