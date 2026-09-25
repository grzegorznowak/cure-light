"""Contract-schema fixture and validator tests.

The frozen JSON Schema documents are mirrored under
``claim_label_contract/schemas/*.schema.json``; this file proves the mirror
matches the in-code documents and that the stdlib validator enforces the
strict subset the contract relies on (closed objects, bool-as-integer
rejection, exactly-one oneOf, $ref resolution).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from claim_label_contract import reconciliation, schemas, slicing
from toolkit import canonical_json as cj

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "claim_label_contract" / "schemas"

MIRRORS = {
    "frame-slices-1.schema.json": schemas.FRAME_SLICES_1,
    "frame-slice-input-1.schema.json": schemas.FRAME_SLICE_INPUT_1,
    "slice-proposals-1.schema.json": schemas.SLICE_PROPOSALS_1,
    "proposal-reconciliation-1.schema.json": schemas.PROPOSAL_RECONCILIATION_1,
}


def test_schema_mirrors_match_in_code_documents():
    for name, document in MIRRORS.items():
        loaded = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
        assert loaded == document, name


def test_closed_object_rejects_unknown_key():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "integer"}},
    }
    assert schemas.validate(schema, {"a": 1}) == []
    errors = schemas.validate(schema, {"a": 1, "b": 2})
    assert len(errors) == 1 and "unknown key 'b'" in errors[0]
    errors = schemas.validate(schema, {"b": 2})
    assert any("missing required key 'a'" in e for e in errors)


def test_integer_rejects_bool_and_float():
    schema = {"type": "integer"}
    assert schemas.validate(schema, True) == ["$: expected integer, got bool"]
    assert schemas.validate(schema, False)
    assert schemas.validate(schema, 1.0)
    assert schemas.validate(schema, -1) == []


def test_pattern_enum_min_items_and_min_length():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["h", "mode", "items", "text"],
        "properties": {
            "h": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "mode": {"enum": ["same", "separate"]},
            "items": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            "text": {"type": "string", "minLength": 1},
        },
    }
    assert schemas.validate(schema, {"h": "0" * 64, "mode": "same",
                                      "items": ["x"], "text": "t"}) == []
    assert schemas.validate(schema, {"h": "0" * 63, "mode": "same",
                                     "items": ["x"], "text": "t"})
    assert schemas.validate(schema, {"h": "0" * 64, "mode": "other",
                                     "items": ["x"], "text": "t"})
    assert schemas.validate(schema, {"h": "0" * 64, "mode": "same",
                                     "items": [], "text": "t"})
    assert schemas.validate(schema, {"h": "0" * 64, "mode": "same",
                                     "items": ["x"], "text": ""})


def test_one_of_requires_exactly_one_branch():
    claim = {
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "rationale"],
        "properties": {"state": {"const": "claim"}, "rationale": {"type": "string"}},
    }
    nonclaim = {
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "label"],
        "properties": {"state": {"const": "nonclaim"}, "label": {"enum": ["context"]}},
    }
    schema = {"type": "array", "items": {"oneOf": [claim, nonclaim]}}
    assert schemas.validate(schema, [{"state": "claim", "rationale": ""}]) == []
    assert schemas.validate(schema, [{"state": "nonclaim", "label": "context"}]) == []
    both = schemas.validate(schema, [{"state": "claim", "rationale": "", "label": "context"}])
    assert any("oneOf" in e for e in both)
    assert schemas.validate(schema, [{"state": "other"}])


def test_ref_resolution_and_unknown_ref():
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["h"],
        "properties": {"h": {"$ref": "#/$defs/hash"}},
        "$defs": {"hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
    }
    assert schemas.validate(schema, {"h": "a" * 64}) == []
    assert schemas.validate(schema, {"h": "A" * 64})
    broken = {"$ref": "#/$defs/missing", "$defs": {}}
    assert any("unresolved" in e for e in schemas.validate(broken, "x"))


def test_real_schemas_reject_empty_and_unknown_roots():
    for version, document in schemas.SCHEMAS.items():
        assert schemas.validate(document, {}) != []
        assert schemas.validate_by_name(version, {}) != []
    assert schemas.validate_by_name("nope/0", {})


# ---------------------------------------------------------------------------
# slicing on synthetic records (no tree-sitter, no producer imports)
# ---------------------------------------------------------------------------

SRC = "src:fixture"
FRAME_HASH = "sha256:" + "f" * 64


def make_records(sizes_kinds: list[tuple[int, str]], data: bytes | None = None):
    records = []
    texts = []
    pos = 0
    chunks = []
    for i, (size, kind) in enumerate(sizes_kinds):
        chunk = b"x" * size if kind != "separator" else b" " * size
        # exact text is supplied by the caller through ``data`` when needed
        records.append({
            "unit_id": f"{SRC}:{pos}-{pos + size}:{'0' * 64}",
            "source_ref": SRC,
            "ordinal": i,
            "kind": kind,
            "start": pos,
            "end": pos + size,
            "sha256": "0" * 64,
            "ancestor_refs": [],
        })
        chunks.append(chunk)
        pos += size
    blob = b"".join(chunks) if data is None else data
    return records, blob


def test_recipe_validation_rejects_bad_values():
    assert slicing.slice_recipe()["max_bytes"] == slicing.DEFAULT_MAX_BYTES
    for kwargs in (
        {"max_bytes": 0},
        {"max_bytes": True},
        {"max_units": 0},
        {"max_input_bytes": -1},
        {"overlap_units": -1},
        {"overlap_units": 80},
        {"max_slices": 0},
    ):
        with pytest.raises(slicing.SliceRecipeError):
            slicing.slice_recipe(**kwargs)


def test_plan_shrinks_overlap_until_new_core_fits():
    records, blob = make_records([(5, "paragraph")] * 4 + [(18, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=24, max_units=64, overlap_units=3,
                                  max_input_bytes=65536, max_slices=8)
    plans = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    assert [len(p.core_ids) for p in plans] == [4, 1]
    assert [len(p.overlap_ids) for p in plans] == [0, 1]
    # slice id is a pure function of source + recipe hashes + ordered ids
    expected = slicing.compute_slice_id(
        SRC, FRAME_HASH, cj.canonical_hash(recipe),
        plans[1].core_ids, plans[1].overlap_ids, (),
    )
    assert plans[1].slice_id == expected


def test_plan_zero_overlap_between_nonseparators_stops():
    records, blob = make_records([(5, "paragraph")] * 4 + [(18, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=22, max_units=64, overlap_units=3,
                                  max_input_bytes=65536, max_slices=8)
    with pytest.raises(slicing.UnverifiedSeamError) as excinfo:
        slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    assert records[3]["unit_id"] in str(excinfo.value)
    assert records[4]["unit_id"] in str(excinfo.value)


def test_plan_zero_overlap_allowed_after_separator():
    records, blob = make_records([
        (5, "paragraph"), (5, "separator"), (5, "paragraph"),
        (5, "separator"), (18, "paragraph"),
    ])
    recipe = slicing.slice_recipe(max_bytes=22, max_units=64, overlap_units=3,
                                  max_input_bytes=65536, max_slices=8)
    plans = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    cores: list[str] = []
    for plan in plans:
        cores.extend(plan.core_ids)
        assert len(plan.core_ids) >= 1
        assert not set(plan.core_ids) & set(plan.overlap_ids)
    assert cores == [r["unit_id"] for r in records]


def test_plan_exact_and_plus_one_caps():
    records, blob = make_records([(30, "paragraph")])
    ok = slicing.slice_recipe(max_bytes=30, max_units=8, max_input_bytes=65536,
                              overlap_units=1, max_slices=4)
    plans = slicing.plan_slices(SRC, FRAME_HASH, ok, records, blob)
    assert len(plans) == 1
    payload_len = len(plans[0].payload_bytes)
    at = slicing.slice_recipe(max_bytes=30, max_units=8, max_input_bytes=payload_len,
                              overlap_units=1, max_slices=4)
    assert len(slicing.plan_slices(SRC, FRAME_HASH, at, records, blob)) == 1
    over = slicing.slice_recipe(max_bytes=30, max_units=8, max_input_bytes=payload_len - 1,
                                overlap_units=1, max_slices=4)
    with pytest.raises(slicing.SliceBudgetError):
        slicing.plan_slices(SRC, FRAME_HASH, over, records, blob)
    short = slicing.slice_recipe(max_bytes=29, max_units=8, max_input_bytes=65536,
                                 overlap_units=1, max_slices=4)
    with pytest.raises(slicing.OversizedUnitError) as excinfo:
        slicing.plan_slices(SRC, FRAME_HASH, short, records, blob)
    assert records[0]["unit_id"] in str(excinfo.value)


def test_plan_max_slices_budget_and_payload_contract():
    records, blob = make_records([
        (10, "paragraph"), (2, "separator"), (10, "paragraph"),
        (2, "separator"), (10, "paragraph"),
    ])
    recipe = slicing.slice_recipe(max_bytes=10, max_units=4, max_input_bytes=65536,
                                  overlap_units=1, max_slices=2)
    with pytest.raises(slicing.SliceBudgetError):
        slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    raised = slicing.slice_recipe(max_bytes=10, max_units=4, max_input_bytes=65536,
                                  overlap_units=1, max_slices=5)
    plans = slicing.plan_slices(SRC, FRAME_HASH, raised, records, blob)
    assert len(plans) == 5
    for plan in plans:
        assert schemas.validate_by_name("frame-slice-input/1", plan.payload) == []
        assert plan.payload_bytes == cj.canonical_dumps(plan.payload)
        assert plan.payload["slice_id"] == plan.slice_id
        for unit in plan.payload["units"]:
            assert unit["text"].encode("utf-8") == blob[unit["start"]:unit["end"]]


def test_plan_deterministic_and_rejects_invalid_text():
    records, blob = make_records([(10, "paragraph"), (10, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=20, max_units=4, max_input_bytes=65536,
                                  overlap_units=1, max_slices=4)
    first = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    second = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    assert [p.payload_bytes for p in first] == [p.payload_bytes for p in second]

    bad = bytearray(b"x" * 20)
    bad[10] = 0xFF
    with pytest.raises(slicing.InvalidTextError):
        slicing.plan_slices(SRC, FRAME_HASH, recipe, records, bytes(bad))


def test_expected_visible_pairs_skips_separators():
    records, _ = make_records([
        (5, "paragraph"), (5, "separator"), (5, "paragraph"), (5, "paragraph"),
    ])
    index = {r["unit_id"]: r for r in records}
    pairs = slicing.expected_visible_pairs(
        index, [r["unit_id"] for r in records]
    )
    assert pairs == [(records[2]["unit_id"], records[3]["unit_id"])]


def test_validate_recipe_document_rejects_unknown_and_drift():
    recipe = slicing.slice_recipe()
    assert slicing.validate_recipe_document(recipe) is None
    broken = dict(recipe)
    broken["max_bytes"] = 0
    with pytest.raises(slicing.SliceRecipeError):
        slicing.validate_recipe_document(broken)
    extra = dict(recipe, extra=True)
    with pytest.raises(slicing.SliceRecipeError):
        slicing.validate_recipe_document(extra)
    drifted = dict(recipe, instructions_sha256="0" * 64)
    with pytest.raises(slicing.SliceRecipeError):
        slicing.validate_recipe_document(drifted)


# ---------------------------------------------------------------------------
# reconciliation on synthetic expected slices (no producer imports)
# ---------------------------------------------------------------------------

def _expected_from_plans(plans):
    return [
        {
            "slice_id": plan.slice_id,
            "source_ref": plan.source_ref,
            "core_ids": list(plan.core_ids),
            "overlap_ids": list(plan.overlap_ids),
            "context_only_ids": list(plan.context_only_ids),
            "payload": plan.payload,
            "payload_sha256": hashlib.sha256(plan.payload_bytes).hexdigest(),
            "payload_byte_length": len(plan.payload_bytes),
        }
        for plan in plans
    ]


def _docs_from_expected(expected):
    docs = []
    for entry in expected:
        kinds = {u["unit_id"]: u["kind"] for u in entry["payload"]["units"]}
        assignments = [
            {"source_ref": entry["source_ref"], "unit_ids": [uid],
             "state": "claim", "rationale": "test"}
            for uid in entry["core_ids"] if kinds[uid] != "separator"
        ]
        overlap_votes = [
            {"unit_id": uid, "state": "claim", "label": None,
             "role_ref": None, "rationale": "audit"}
            for uid in entry["overlap_ids"] if kinds[uid] != "separator"
        ]
        visible = list(entry["overlap_ids"]) + list(entry["core_ids"])
        grouping_votes = [
            {"left_unit_id": left, "right_unit_id": right,
             "grouping": "separate", "rationale": "pair"}
            for left, right in zip(visible, visible[1:])
            if kinds[left] != "separator" and kinds[right] != "separator"
        ]
        docs.append({
            "schema_version": "slice-proposals/1",
            "slice_id": entry["slice_id"],
            "input_sha256": entry["payload_sha256"],
            "assignments": assignments,
            "overlap_votes": overlap_votes,
            "grouping_votes": grouping_votes,
            "boundary": {"left": "clear", "right": "clear"},
        })
    return docs


def _proposal_inputs(docs):
    return [
        {"label": f"proposal[{i}]", "sha256": f"{i:064x}", "document": doc,
         "error": None}
        for i, doc in enumerate(docs)
    ]


def test_reconcile_common_roundtrip_and_unverified_seam():
    import copy

    records, blob = make_records([(5, "paragraph")] * 4 + [(18, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=24, max_units=64, overlap_units=3,
                                  max_input_bytes=65536, max_slices=4)
    plans = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    sources = {SRC: {r["unit_id"]: {"kind": r["kind"], "ordinal": r["ordinal"]}
                     for r in records}}
    expected = _expected_from_plans(plans)
    docs = _docs_from_expected(expected)
    merged, report = reconciliation.reconcile(
        sources=sources, expected_slices=expected,
        proposals=_proposal_inputs(docs), slices_sha256="0" * 64,
    )
    assert merged is not None
    assert report["complete"] is True
    assert report["merged_sha256"] == hashlib.sha256(merged).hexdigest()
    merged_doc = cj.canonical_loads(merged)
    assert {u for a in merged_doc["assignments"] for u in a["unit_ids"]} == {
        r["unit_id"] for r in records
    }

    broken = copy.deepcopy(expected)
    broken[1]["overlap_ids"] = []
    broken_docs = _docs_from_expected(broken)
    merged2, report2 = reconciliation.reconcile(
        sources=sources, expected_slices=broken,
        proposals=_proposal_inputs(broken_docs), slices_sha256="0" * 64,
    )
    assert merged2 is None
    assert report2["complete"] is False
    assert "unverified_seam" in {c["code"] for c in report2["conflicts"]}


def test_reconcile_common_report_is_order_independent():
    records, blob = make_records([(5, "paragraph")] * 4 + [(18, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=24, max_units=64, overlap_units=3,
                                  max_input_bytes=65536, max_slices=4)
    plans = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    expected = _expected_from_plans(plans)
    docs = _docs_from_expected(expected)
    # corrupt both proposals; the failure report must be byte-identical
    for doc in docs:
        doc["boundary"] = {"left": "spanning", "right": "clear"}
    first = _proposal_inputs(docs)
    second = list(reversed(_proposal_inputs(docs)))
    _, report_a = reconciliation.reconcile(
        sources={SRC: {r["unit_id"]: {"kind": r["kind"], "ordinal": r["ordinal"]}
                       for r in records}},
        expected_slices=expected, proposals=first, slices_sha256="1" * 64)
    _, report_b = reconciliation.reconcile(
        sources={SRC: {r["unit_id"]: {"kind": r["kind"], "ordinal": r["ordinal"]}
                       for r in records}},
        expected_slices=expected, proposals=second, slices_sha256="1" * 64)
    assert cj.canonical_dumps(report_a) == cj.canonical_dumps(report_b)
    assert report_a["conflicts"]


def test_plan_metadata_alone_can_overflow_payload_cap():
    record = {
        "unit_id": "src:fixture:" + "longlocator" * 40 + ":0-3:" + "0" * 64,
        "source_ref": SRC, "ordinal": 0, "kind": "paragraph",
        "start": 0, "end": 3, "sha256": "0" * 64, "ancestor_refs": [],
    }
    recipe = slicing.slice_recipe(max_bytes=64, max_units=4, max_input_bytes=600,
                                  overlap_units=0, max_slices=2)
    with pytest.raises(slicing.SliceBudgetError):
        slicing.plan_slices(SRC, FRAME_HASH, recipe, [record], b"abc")


def test_reconcile_common_foreign_source_uid_is_named():
    records, blob = make_records([(10, "paragraph")])
    recipe = slicing.slice_recipe(max_bytes=64, max_units=4, max_input_bytes=65536,
                                  overlap_units=0, max_slices=2)
    plans = slicing.plan_slices(SRC, FRAME_HASH, recipe, records, blob)
    expected = _expected_from_plans(plans)
    sources = {SRC: {r["unit_id"]: {"kind": r["kind"], "ordinal": r["ordinal"]}
                     for r in records}}
    other = "src:other:0-9:" + "0" * 64
    sources["src:other"] = {other: {"kind": "paragraph", "ordinal": 0}}
    docs = _docs_from_expected(expected)
    docs[0]["assignments"][0]["unit_ids"] = [other]
    merged, report = reconciliation.reconcile(
        sources=sources, expected_slices=expected,
        proposals=_proposal_inputs(docs), slices_sha256="0" * 64,
    )
    assert merged is None
    codes = {c["code"] for c in report["conflicts"]}
    assert "foreign_source" in codes
