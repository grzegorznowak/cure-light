"""Contract-schema fixture and validator tests.

The frozen JSON Schema documents are mirrored under
``claim_label_contract/schemas/*.schema.json``; this file proves the mirror
matches the in-code documents and that the stdlib validator enforces the
strict subset the contract relies on (closed objects, bool-as-integer
rejection, exactly-one oneOf, $ref resolution).
"""

from __future__ import annotations

import json
from pathlib import Path

from claim_label_contract import schemas

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
