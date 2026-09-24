"""Independent mechanical validator for ``claim-registry/1``.

The validator recomputes everything it can from captured source bytes and the
pinned walker recipe.  Producer-supplied values (including ``complete: true``)
are never trusted: they are compared against the recomputation.

A failing report blocks the ``finalized_unclaimed`` permission flag (spec
section 3: "Failed validation prohibits complete-registry claims and finalized
UNCLAIMED").
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from . import canonical
from .capture import verify_capture
from .frame import ExtractionError, frame_recipe, frame_source, span_is_line_aligned
from .registry import (
    CANONICALIZATION,
    NONCLAIM_LABELS,
    SCHEMA_VERSION,
)
from .windows import WindowRecipeError, validate_windows, window_recipe

PAYLOAD_KEYS = {
    "schema_version", "recipe", "recipe_hash", "sources", "units", "claims",
    "labels", "groups", "precedence", "witness",
}
RECIPE_KEYS = {"frame", "window", "canonicalization"}
SOURCE_KEYS = {
    "source_ref", "locator", "class", "pointer_ref", "interpretation_ref",
    "blob_algorithm", "blob_oid", "sha256", "byte_length", "empty", "bom",
}
UNIT_KEYS = {
    "unit_id", "source_ref", "ordinal", "kind", "start", "end", "sha256",
    "ancestor_refs",
}
CLAIM_KEYS = {
    "claim_id", "source_ref", "start", "end", "sha256", "unit_ids",
    "parent_ref", "active",
}
LABEL_KEYS = {
    "unit_id", "state", "claim_id", "nonclaim_label", "rationale", "role_ref",
}
WITNESS_KEYS = {"per_source", "uncaptured_source_refs", "complete", "errors"}
WITNESS_PS_KEYS = {
    "source_ref", "sha256", "byte_length", "blob_algorithm", "blob_oid",
    "frame_recipe_hash", "unit_count", "covered_unit_count",
    "covered_byte_count", "pending_count", "conflict_count", "error_count",
    "empty_source", "complete",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ValidationReport:
    valid: bool
    checks: list[Check] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    recomputed_witness: dict | None = None
    permission: dict = field(default_factory=dict)
    registry_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "registry_hash": self.registry_hash,
            "checks": [
                {"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks
            ],
            "errors": list(self.errors),
            "recomputed_witness": self.recomputed_witness,
            "permission": dict(self.permission),
        }


class _Ctx:
    def __init__(self):
        self.checks: list[Check] = []
        self.errors: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(name=name, ok=bool(ok), detail="" if ok else detail))
        if not ok:
            self.errors.append(f"{name}: {detail}" if detail else name)
        return ok


def _keys_ok(ctx: _Ctx, name: str, obj, allowed: set[str], where: str) -> bool:
    if not isinstance(obj, dict):
        return ctx.check(name, False, f"{where} is not an object")
    extra = set(obj) - allowed
    missing = allowed - set(obj)
    if extra:
        return ctx.check(name, False, f"{where} has unknown keys {sorted(extra)}")
    if missing:
        return ctx.check(name, False, f"{where} is missing keys {sorted(missing)}")
    return True


def _valid_recipe(recipe) -> bool:
    if not isinstance(recipe, dict):
        return False
    try:
        window_recipe(
            recipe["window"]["max_units"],
            recipe["window"]["max_bytes"],
            recipe["window"]["overlap_units"],
        )
    except (KeyError, TypeError, WindowRecipeError):
        return False
    return recipe.get("canonicalization") == CANONICALIZATION


def validate_registry(
    envelope: dict,
    captures: Mapping[str, bytes],
    *,
    windows_manifests: Sequence[dict] | None = None,
    raw_bytes: bytes | None = None,
) -> ValidationReport:
    """Validate an envelope against captured source bytes.

    ``captures`` is the designation manifest: a mapping ``source_ref -> bytes``
    for every source the registry claims to cover.  The source sets must match.
    When ``raw_bytes`` is given (the registry file bytes), it must be the exact
    canonical serialization of the envelope; a trailing newline fails.
    """
    ctx = _Ctx()
    report = ValidationReport(valid=False, checks=ctx.checks, errors=ctx.errors)

    # -- 1. envelope and canonical bytes ---------------------------------
    if not _keys_ok(ctx, "envelope_shape", envelope, {"payload", "registry_hash"},
                    "envelope"):
        _finish(report, None)
        return report
    payload = envelope.get("payload")
    claimed_hash = envelope.get("registry_hash")
    report.registry_hash = claimed_hash if isinstance(claimed_hash, str) else None
    if not _keys_ok(ctx, "payload_shape", payload, PAYLOAD_KEYS, "payload"):
        _finish(report, payload)
        return report
    try:
        re_serialized = canonical.canonical_dumps(envelope)
        if raw_bytes is not None:
            ctx.check(
                "canonical_bytes",
                re_serialized == raw_bytes,
                "registry file bytes are not the canonical claim-json/1 serialization "
                "(trailing newline, whitespace or reordered keys)",
            )
        else:
            ctx.check(
                "canonical_bytes",
                canonical.canonical_loads(re_serialized) == envelope,
                "envelope is not canonical claim-json/1",
            )
    except canonical.CanonicalizationError as exc:
        ctx.check("canonical_bytes", False, str(exc))
    recomputed_hash = canonical.registry_hash(payload) if isinstance(payload, dict) else None
    ctx.check(
        "registry_hash",
        isinstance(claimed_hash, str) and claimed_hash == recomputed_hash,
        f"claimed {claimed_hash!r} recomputed {recomputed_hash!r}",
    )
    ctx.check(
        "schema_version",
        payload.get("schema_version") == SCHEMA_VERSION,
        f"expected {SCHEMA_VERSION!r} got {payload.get('schema_version')!r}",
    )
    ctx.check(
        "recipe_hash",
        payload.get("recipe_hash") == canonical.recipe_hash(payload.get("recipe", {})),
        "recipe_hash does not reproduce",
    )
    ctx.check(
        "recipe_shape",
        _valid_recipe(payload.get("recipe")),
        "recipe invalid (canonicalization or window bounds)",
    )
    ctx.check(
        "recipe_pins",
        payload.get("recipe", {}).get("frame") == frame_recipe(),
        "frame recipe pins do not match the current walker/parser/runtime; "
        "re-extraction under the pinned recipe is not reproducible here",
    )

    # -- 2. sources reproduce --------------------------------------------
    sources = payload.get("sources")
    units = payload.get("units")
    claims = payload.get("claims")
    labels = payload.get("labels")
    witness = payload.get("witness")
    for name, val in (("sources", sources), ("units", units), ("claims", claims),
                      ("labels", labels), ("witness", witness)):
        ctx.check(f"{name}_type", isinstance(val, list) if name != "witness"
                  else isinstance(val, dict), f"{name} has wrong type")
    if not all(isinstance(v, list) for v in (sources, units, claims, labels)) \
            or not isinstance(witness, dict):
        _finish(report, payload)
        return report
    src_records: dict[str, dict] = {}
    for i, s in enumerate(sources):
        if not isinstance(s, dict):
            ctx.check("source_shape", False, f"sources[{i}] is not an object")
            continue
        ref = s.get("source_ref")
        if isinstance(ref, str):
            if ref in src_records:
                ctx.check("source_unique", False, f"duplicate source_ref {ref}")
            src_records[ref] = s
        _keys_ok(ctx, "source_shape", s, SOURCE_KEYS, f"sources[{i}]")
    capture_refs = set(captures)
    registry_refs = set(src_records)
    ctx.check(
        "source_set_reconciles",
        capture_refs == registry_refs,
        f"captures-only {sorted(capture_refs - registry_refs)[:3]} "
        f"registry-only {sorted(registry_refs - capture_refs)[:3]}",
    )
    for ref, record in src_records.items():
        data = captures.get(ref)
        if data is None:
            continue
        failures = verify_capture(record, data)
        from .capture import make_source_ref
        try:
            expected_ref = make_source_ref(
                record.get("locator", ""), record.get("blob_oid", ""),
                record.get("blob_algorithm", ""),
            )
        except Exception:  # pragma: no cover - defensive
            expected_ref = None
        if expected_ref != ref:
            failures.append(f"source_ref does not reproduce from locator (got {expected_ref})")
        if record.get("empty") != (len(data) == 0):
            failures.append("empty flag mismatch")
        if record.get("bom") != data.startswith(b"\xef\xbb\xbf"):
            failures.append("bom flag mismatch")
        ctx.check(f"source_reproduces[{ref}]", not failures, "; ".join(failures))

    # -- 3. re-extraction -------------------------------------------------
    frames = {}
    for ref, data in sorted(captures.items()):
        try:
            frames[ref] = frame_source(data)
        except ExtractionError as exc:
            ctx.check(f"re_extract[{ref}]", False, f"extraction failed: {exc}")
    units_by_id: dict[str, dict] = {}
    units_by_source: dict[str, list[dict]] = {}
    for ref, frame in frames.items():
        expected = [u.record(ref) for u in frame.units]
        actual = [u for u in units if u.get("source_ref") == ref]
        ctx.check(
            f"re_extract[{ref}]",
            actual == expected,
            "payload units differ from re-extraction under the pinned recipe",
        )
        units_by_source[ref] = expected

    # -- 4. unit partition and ids ---------------------------------------
    expected_total = sum(len(v) for v in units_by_source.values())
    ctx.check("unit_count_reconciles", len(units) == expected_total,
              f"payload has {len(units)} units, re-extraction {expected_total}")
    ordered_ok = True
    for i, u in enumerate(units):
        if not isinstance(u, dict):
            ctx.check("unit_shape", False, f"units[{i}] is not an object")
            ordered_ok = False
            continue
        uid = u.get("unit_id")
        if isinstance(uid, str):
            if uid in units_by_id:
                ctx.check("unit_unique", False, f"duplicate unit_id {uid}")
            units_by_id[uid] = u
        if not _keys_ok(ctx, "unit_shape", u, UNIT_KEYS, f"units[{i}]"):
            ordered_ok = False
            continue
        ref = u.get("source_ref")
        data = captures.get(ref)
        if data is None:
            ctx.check("unit_source", False, f"units[{i}] unknown source_ref {ref!r}")
            ordered_ok = False
            continue
        uid = u.get("unit_id")
        expected_id = f"{ref}:{u.get('start')}-{u.get('end')}:{u.get('sha256')}"
        if uid != expected_id:
            ctx.check("unit_id_format", False, f"units[{i}] id {uid!r} != {expected_id!r}")
        start, end = u.get("start"), u.get("end")
        if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(data)):
            ctx.check("unit_bounds", False, f"units[{i}] bad bounds [{start},{end})")
            ordered_ok = False
            continue
        if hashlib.sha256(data[start:end]).hexdigest() != u.get("sha256"):
            ctx.check("unit_sha", False, f"units[{i}] sha mismatch for [{start},{end})")
        if not isinstance(u.get("ancestor_refs"), list):
            ctx.check("unit_ancestors", False, f"units[{i}].ancestor_refs not a list")
        ordered_ok = ordered_ok and isinstance(u.get("ordinal"), int)
    # partition per source: covered bytes equal source length, gapless
    for ref, expected in units_by_source.items():
        data = captures[ref]
        spans = [(u["start"], u["end"]) for u in expected]
        pos = 0
        ok = True
        detail = ""
        for a, b in spans:
            if a != pos:
                ok = False
                detail = f"gap/overlap at [{pos},{a})"
                break
            pos = b
        if pos != len(data):
            ok = False
            detail = f"partition ends at {pos}, source length {len(data)}"
        if ok:
            # line alignment check on recomputed frame units
            frame = frames[ref]
            for u in frame.units:
                if not span_is_line_aligned(data, u):
                    ok = False
                    detail = f"unit {u.ordinal} span not line-aligned"
                    break
        ctx.check(f"partition[{ref}]", ok, detail)
    # ordering
    keys = [(u.get("source_ref"), u.get("ordinal")) for u in units]
    ctx.check("unit_order", keys == sorted(keys, key=lambda k: (str(k[0]).encode(), k[1] if isinstance(k[1], int) else -1)),
              "units are not in source_ref/ordinal order")

    # -- 5. claims --------------------------------------------------------
    claims_by_id: dict[str, dict] = {}
    label_by_unit: dict[str, dict] = {}
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            ctx.check("claim_shape", False, f"claims[{i}] is not an object")
            continue
        cid = c.get("claim_id")
        if isinstance(cid, str):
            if cid in claims_by_id:
                ctx.check("claim_unique", False, f"duplicate claim_id {cid}")
            claims_by_id[cid] = c
        _keys_ok(ctx, "claim_shape", c, CLAIM_KEYS, f"claims[{i}]")
    for i, c in enumerate(claims):
        if not isinstance(c, dict) or c.get("claim_id") not in claims_by_id:
            continue
        ref = c.get("source_ref")
        data = captures.get(ref)
        start, end, sha = c.get("start"), c.get("end"), c.get("sha256")
        if data is None or not isinstance(start, int) or not isinstance(end, int):
            ctx.check("claim_bounds", False, f"claims[{i}] bad source/bounds")
            continue
        expected_id = f"{ref}:{start}-{end}:{hashlib.sha256(data[start:end]).hexdigest()}"
        ctx.check(f"claim_id[{i}]", c.get("claim_id") == expected_id,
                  f"{c.get('claim_id')!r} != {expected_id!r}")
        ctx.check(f"claim_sha[{i}]",
                  c.get("sha256") == hashlib.sha256(data[start:end]).hexdigest(),
                  f"claims[{i}] sha256 does not reproduce over [{start},{end})")
        member_ids = c.get("unit_ids")
        if not isinstance(member_ids, list) or not member_ids:
            ctx.check("claim_members", False, f"claims[{i}] unit_ids empty")
            continue
        members = [units_by_id.get(uid) for uid in member_ids]
        if any(m is None for m in members):
            ctx.check("claim_members_exist", False, f"claims[{i}] unknown unit ids")
            continue
        if any(m.get("source_ref") != ref for m in members):
            ctx.check("claim_members_source", False, f"claims[{i}] members from other sources")
        ordinals = [m["ordinal"] for m in members]
        ctx.check(
            f"claim_contiguous[{i}]",
            ordinals == list(range(ordinals[0], ordinals[0] + len(ordinals))),
            f"claim member ordinals not consecutive: {ordinals}",
        )
        ctx.check(
            f"claim_span_matches_units[{i}]",
            members[0]["start"] == start and members[-1]["end"] == end,
            "claim span != first..last member unit span",
        )
        if any(m["kind"] == "separator" for m in members):
            ctx.check(f"claim_no_separator[{i}]", False, "separator unit is a claim member")
        # every unit intersecting the claim span must be a member
        member_set = set(member_ids)
        for u in units_by_source.get(ref, []):
            intersects = u["start"] < end and start < u["end"]
            if intersects and u["unit_id"] not in member_set:
                ctx.check(
                    f"claim_span_units[{i}]",
                    False,
                    f"claim [{start},{end}) intersects unit {u['unit_id']} outside membership",
                )
                break
    # crossing overlaps and containment
    claims_by_source: dict[str, list[dict]] = {}
    for c in claims:
        if isinstance(c, dict) and isinstance(c.get("source_ref"), str):
            claims_by_source.setdefault(c["source_ref"], []).append(c)
    for ref, group in claims_by_source.items():
        for a in group:
            if not all(k in a for k in ("claim_id", "start", "end", "active", "parent_ref")):
                continue
            for b in group:
                if a is b or not all(k in b for k in ("claim_id", "start", "end")):
                    continue
                a_start, a_end = a.get("start"), a.get("end")
                b_start, b_end = b.get("start"), b.get("end")
                if not all(isinstance(x, int) for x in (a_start, a_end, b_start, b_end)):
                    continue
                if a_start < b_start < a_end < b_end:
                    ctx.check("no_crossing_overlaps", False,
                              f"claims {a.get('claim_id')} and {b.get('claim_id')} cross")
                contained = a_start <= b_start and b_end <= a_end and (a_start, a_end) != (b_start, b_end)
                if contained:
                    parent_ok = (
                        a.get("active") is False
                        and b.get("parent_ref") == a.get("claim_id")
                    )
                    ctx.check("containment_only", parent_ok,
                              f"{b.get('claim_id')} contained in {a.get('claim_id')} "
                              "without inactive parent_ref")
        # member disjointness among active claims
        seen_units: dict[str, str] = {}
        for c in group:
            if not all(k in c for k in ("claim_id", "active", "unit_ids")):
                continue
            if c.get("active") is False:
                continue
            for uid in c.get("unit_ids", []):
                if uid in seen_units and seen_units[uid] != c.get("claim_id"):
                    ctx.check("claim_member_disjoint", False,
                              f"unit {uid} in multiple active claims")
                seen_units[uid] = c.get("claim_id")
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            continue
        parent_ref = c.get("parent_ref")
        if parent_ref is None:
            continue
        parent = claims_by_id.get(parent_ref)
        if parent is None:
            ctx.check("parent_exists", False, f"claims[{i}] parent_ref {parent_ref!r} unknown")
            continue
        if parent.get("source_ref") != c.get("source_ref"):
            ctx.check("parent_source", False, f"claims[{i}] parent in another source")
        ctx.check(
            "parent_contains",
            parent.get("start", 0) <= c.get("start", -1)
            and c.get("end", -1) <= parent.get("end", 0)
            and (parent.get("start"), parent.get("end")) != (c.get("start"), c.get("end")),
            f"claims[{i}] parent {parent_ref} does not strictly contain child span",
        )
        ctx.check("parent_inactive", parent.get("active") is False,
                  f"parent {parent_ref} is active while child {c.get('claim_id')} exists")

    # -- 6. ownership -----------------------------------------------------
    ctx.check("claim_order",
              claims == sorted(claims, key=lambda c: (
                  str(c.get("source_ref")).encode(), c.get("start", -1),
                  c.get("end", -1), str(c.get("claim_id")))),
              "claims are not in source_ref/start/end/id order")
    expected_unit_ids = [u["unit_id"] for u in units]
    ctx.check(
        "labels_count",
        len(labels) == len(units),
        f"{len(labels)} labels for {len(units)} units",
    )
    for i, lab in enumerate(labels):
        if not _keys_ok(ctx, "label_shape", lab, LABEL_KEYS, f"labels[{i}]"):
            continue
        uid = lab.get("unit_id")
        if uid in label_by_unit:
            ctx.check("label_unique", False, f"duplicate label for {uid}")
        label_by_unit[uid] = lab
        state = lab.get("state")
        if state not in ("claim", "nonclaim", "pending"):
            ctx.check("label_state", False, f"labels[{i}] invalid state {state!r}")
        elif state == "claim":
            cid = lab.get("claim_id")
            claim = claims_by_id.get(cid)
            if claim is None:
                ctx.check("label_claim_exists", False, f"labels[{i}] unknown claim {cid!r}")
            elif uid not in set(claim.get("unit_ids", [])):
                ctx.check("label_claim_membership", False,
                          f"labels[{i}] unit not a member of its claim")
            ctx.check("label_claim_fields",
                      lab.get("nonclaim_label") is None,
                      f"labels[{i}] claim label carries nonclaim_label")
        elif state == "nonclaim":
            if lab.get("nonclaim_label") not in NONCLAIM_LABELS:
                ctx.check("label_nonclaim_label", False,
                          f"labels[{i}] invalid nonclaim label {lab.get('nonclaim_label')!r}")
            if not isinstance(lab.get("rationale"), str) or not lab.get("rationale", "").strip():
                ctx.check("label_rationale", False, f"labels[{i}] missing rationale")
            if not isinstance(lab.get("role_ref"), str) or not lab.get("role_ref", "").strip():
                ctx.check("label_role_ref", False, f"labels[{i}] missing role_ref")
            ctx.check("label_nonclaim_claim_field", lab.get("claim_id") is None,
                      f"labels[{i}] nonclaim carries claim_id")
        else:
            ctx.check("label_pending_fields",
                      lab.get("claim_id") is None and lab.get("nonclaim_label") is None,
                      f"labels[{i}] pending label carries owner fields")
    ctx.check(
        "labels_exhaustive",
        set(label_by_unit) == set(expected_unit_ids),
        "labels do not cover exactly the unit set",
    )
    # separators mechanically context
    for u in units:
        if u.get("kind") != "separator":
            continue
        lab = label_by_unit.get(u.get("unit_id"))
        if lab is None:
            continue
        ctx.check(
            "separator_context",
            lab.get("state") == "nonclaim" and lab.get("nonclaim_label") == "context",
            f"separator {u.get('unit_id')} is not nonclaim context",
        )

    # -- 7. recomputed witness -------------------------------------------
    recomputed = _recompute_witness(
        captures, frames, label_by_unit, units, payload, witness
    )
    report.recomputed_witness = recomputed
    if isinstance(witness, dict) and _keys_ok(ctx, "witness_shape", witness,
                                              WITNESS_KEYS, "witness"):
        serialized_ps = {s.get("source_ref"): s for s in witness.get("per_source", [])
                         if isinstance(s, dict)}
        recomputed_ps = {s["source_ref"]: s for s in recomputed["per_source"]}
        mismatch = []
        for ref, rec in sorted(recomputed_ps.items()):
            ser = serialized_ps.get(ref)
            if ser is None:
                mismatch.append(f"{ref}: missing serialized witness")
                continue
            if not _keys_ok(ctx, "witness_source_shape", ser, WITNESS_PS_KEYS, f"witness[{ref}]"):
                continue
            for key, val in rec.items():
                if ser.get(key) != val:
                    mismatch.append(f"{ref}.{key}: serialized {ser.get(key)!r} recomputed {val!r}")
        if set(serialized_ps) != set(recomputed_ps):
            mismatch.append("serialized per_source set differs from recomputed")
        ctx.check("witness_recomputes", not mismatch, "; ".join(mismatch[:4]))
        ctx.check(
            "witness_uncaptured",
            sorted(witness.get("uncaptured_source_refs", [])) == recomputed["uncaptured_source_refs"],
            "uncaptured_source_refs mismatch",
        )
        ctx.check("witness_errors_empty", witness.get("errors") in ([], None)
                  or witness.get("errors") == [],
                  f"witness.errors = {witness.get('errors')!r}")
        serialized_complete = witness.get("complete")
        recomputed_complete = recomputed["complete"]
        ctx.check(
            "complete_recomputed",
            isinstance(serialized_complete, bool) and serialized_complete == recomputed_complete,
            f"serialized complete={serialized_complete!r} recomputed={recomputed_complete!r}",
        )

    # -- 8. groups / precedence refs -------------------------------------
    group_ids = set()
    for g in payload.get("groups", []) or []:
        if not isinstance(g, dict) or not isinstance(g.get("group_id"), str):
            ctx.check("group_shape", False, "group requires string group_id")
            continue
        if g["group_id"] in group_ids:
            ctx.check("group_unique", False, f"duplicate group_id {g['group_id']}")
        group_ids.add(g["group_id"])
        for uid in g.get("unit_ids", []) or []:
            ctx.check("group_unit_exists", uid in units_by_id, f"group {g['group_id']} unit {uid}")
        for cid in g.get("claim_ids", []) or []:
            ctx.check("group_claim_exists", cid in claims_by_id, f"group {g['group_id']} claim {cid}")
    prec_ids = set()
    for p in payload.get("precedence", []) or []:
        if not isinstance(p, dict) or not isinstance(p.get("precedence_id"), str):
            ctx.check("precedence_shape", False, "precedence requires string precedence_id")
            continue
        if p["precedence_id"] in prec_ids:
            ctx.check("precedence_unique", False, f"duplicate precedence_id {p['precedence_id']}")
        prec_ids.add(p["precedence_id"])

    # -- 9. windows -------------------------------------------------------
    if windows_manifests:
        for m in windows_manifests:
            ref = m.get("source_ref") if isinstance(m, dict) else None
            if ref not in frames:
                ctx.check("windows_source", False, f"window manifest source {ref!r} unknown")
                continue
            failures = validate_windows(m, frames[ref].units, ref)
            ctx.check(f"windows[{ref}]", not failures, "; ".join(failures[:3]))

    _finish(report, payload)
    return report


def _recompute_witness(
    captures, frames, label_by_unit, units, payload, witness
) -> dict:
    per_source = []
    for ref, data in sorted(captures.items()):
        frame = frames[ref]
        owned = 0
        owned_bytes = 0
        pending = 0
        for u in frame.units:
            lab = label_by_unit.get(u.unit_id(ref))
            if lab is None:
                pending += 1
                continue
            if lab.get("state") in ("claim", "nonclaim"):
                owned += 1
                owned_bytes += u.byte_length
            elif lab.get("state") == "pending":
                pending += 1
        uncaptured = sorted(set((witness or {}).get("uncaptured_source_refs", []) or []))
        per_source.append({
            "source_ref": ref,
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_length": len(data),
            "blob_algorithm": "git-blob-sha256",
            "blob_oid": _blob_oid(data),
            "frame_recipe_hash": canonical.recipe_hash(frame.recipe),
            "unit_count": frame.unit_count,
            "covered_unit_count": owned,
            "covered_byte_count": owned_bytes,
            "pending_count": pending,
            "conflict_count": 0,
            "error_count": 0,
            "empty_source": len(data) == 0,
            "complete": pending == 0,
        })
    complete = all(s["complete"] for s in per_source) and not sorted(
        set((witness or {}).get("uncaptured_source_refs", []) or [])
    )
    return {
        "per_source": per_source,
        "uncaptured_source_refs": sorted(set((witness or {}).get("uncaptured_source_refs", []) or [])),
        "complete": complete,
        "errors": [],
    }


def _blob_oid(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\x00"
    return hashlib.sha256(header + data).hexdigest()


def _finish(report: ValidationReport, payload) -> None:
    report.valid = all(c.ok for c in report.checks)
    complete = bool(
        isinstance(payload, dict)
        and isinstance(payload.get("witness"), dict)
        and payload["witness"].get("complete") is True
        and report.valid
    )
    report.permission = {
        "complete_registry_claims": complete,
        "finalized_unclaimed": complete,
    }


__all__ = [
    "Check",
    "ValidationReport",
    "validate_registry",
]
