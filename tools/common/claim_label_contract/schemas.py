"""Frozen closed JSON Schema fixtures for the sliced-labeling contract.

The schema documents below are the contract surface.  They are mirrored as
plain ``.schema.json`` fixtures under this package's ``schemas/`` directory
(``tests/test_claim_label_contract.py`` asserts the mirror is byte-equal as
data) so downstream reviewers can read the frozen contract without importing
code.

Conventions enforced by the schemas (and by the producer/gate):

* every object is closed (``additionalProperties: false``);
* ``sha256`` file digests are 64 lowercase hex characters; object content ids
  are ``sha256:<hex>``;
* integer fields reject booleans (JSON ``true`` is not an integer);
* no floats, no nulls except where the contract explicitly allows them;
* offsets are global, zero-based, half-open UTF-8 byte offsets.

:func:`validate` implements exactly the JSON Schema subset used here:
``$ref`` (local ``#/$defs/<name>``), ``type`` (single name or list),
``const``, ``enum``, ``required``, ``properties``, ``additionalProperties:
false``, ``items``, ``minItems``/``maxItems``, ``minLength``, ``pattern``,
``minimum`` and ``oneOf``.  Anything else in a schema document is ignored as
an annotation.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------

#: Unit kinds the frame walker may emit (frame.UNIT_KINDS plus the compound
#: list-item kind; the walker can emit ``list_item``).
UNIT_KINDS = [
    "atx_heading",
    "fenced_code_block",
    "html_block",
    "indented_code_block",
    "link_reference_definition",
    "list_item",
    "minus_metadata",
    "paragraph",
    "pipe_table_delimiter_row",
    "pipe_table_header",
    "pipe_table_row",
    "plus_metadata",
    "separator",
    "setext_heading",
    "thematic_break",
]

NONCLAIM_LABELS = ["advisory", "baseline", "context", "example"]
BOUNDARY_VALUES = ["clear", "spanning", "uncertain"]
GROUPING_VALUES = ["same", "separate", "uncertain"]

FRAME_SLICES_VERSION = "frame-slices/1"
FRAME_SLICE_INPUT_VERSION = "frame-slice-input/1"
SLICE_PROPOSALS_VERSION = "slice-proposals/1"
PROPOSAL_RECONCILIATION_VERSION = "proposal-reconciliation/1"

_HEX = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
_OBJECT_HASH = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
_NONEMPTY_STRING = {"type": "string", "minLength": 1}
_STRING_LIST = {"type": "array", "items": {"type": "string"}}
_UNIT_ID_LIST = {"type": "array", "items": {"type": "string", "minLength": 1}}

_UNIT_PROPERTIES = {
    "unit_id": {"type": "string", "minLength": 1},
    "source_ref": {"type": "string", "minLength": 1},
    "ordinal": {"type": "integer", "minimum": 0},
    "kind": {"enum": UNIT_KINDS},
    "start": {"type": "integer", "minimum": 0},
    "end": {"type": "integer", "minimum": 0},
    "sha256": _HEX,
    "ancestor_refs": _STRING_LIST,
}

_UNIT_REQUIRED = [
    "unit_id",
    "source_ref",
    "ordinal",
    "kind",
    "start",
    "end",
    "sha256",
    "ancestor_refs",
]

_SLICE_RECIPE = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "version",
        "algorithm",
        "max_bytes",
        "max_units",
        "max_input_bytes",
        "overlap_units",
        "max_slices",
        "instructions_version",
        "instructions_sha256",
    ],
    "properties": {
        "version": {"const": "claim-registry-slice/1"},
        "algorithm": {"const": "greedy-largest-core/1"},
        "max_bytes": {"type": "integer", "minimum": 1},
        "max_units": {"type": "integer", "minimum": 1},
        "max_input_bytes": {"type": "integer", "minimum": 1},
        "overlap_units": {"type": "integer", "minimum": 0},
        "max_slices": {"type": "integer", "minimum": 1},
        "instructions_version": {"type": "string", "minLength": 1},
        "instructions_sha256": _HEX,
    },
}

_CLAIM_ASSIGNMENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_ref", "unit_ids", "state", "rationale"],
    "properties": {
        "source_ref": {"type": "string", "minLength": 1},
        "unit_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "state": {"const": "claim"},
        "rationale": {"type": "string"},
    },
}

_NONCLAIM_ASSIGNMENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_ref", "unit_ids", "state", "label", "rationale", "role_ref"],
    "properties": {
        "source_ref": {"type": "string", "minLength": 1},
        "unit_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
        "state": {"const": "nonclaim"},
        "label": {"enum": NONCLAIM_LABELS},
        "rationale": {"type": "string", "minLength": 1},
        "role_ref": {"type": "string", "minLength": 1},
    },
}

_CLAIM_VOTE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["unit_id", "state", "label", "role_ref", "rationale"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 1},
        "state": {"const": "claim"},
        "label": {"type": "null"},
        "role_ref": {"type": "null"},
        "rationale": {"type": "string"},
    },
}

_NONCLAIM_VOTE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["unit_id", "state", "label", "role_ref", "rationale"],
    "properties": {
        "unit_id": {"type": "string", "minLength": 1},
        "state": {"const": "nonclaim"},
        "label": {"enum": NONCLAIM_LABELS},
        "role_ref": {"type": "string", "minLength": 1},
        "rationale": {"type": "string", "minLength": 1},
    },
}

_GROUPING_VOTE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["left_unit_id", "right_unit_id", "grouping", "rationale"],
    "properties": {
        "left_unit_id": {"type": "string", "minLength": 1},
        "right_unit_id": {"type": "string", "minLength": 1},
        "grouping": {"enum": GROUPING_VALUES},
        "rationale": {"type": "string"},
    },
}

_BOUNDARY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["left", "right"],
    "properties": {
        "left": {"enum": BOUNDARY_VALUES},
        "right": {"enum": BOUNDARY_VALUES},
    },
}

_ISSUE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["code", "source_ref", "unit_ids", "slice_ids", "values"],
    "properties": {
        "code": {"type": "string", "minLength": 1},
        "source_ref": {"oneOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
        "unit_ids": _UNIT_ID_LIST,
        "slice_ids": _UNIT_ID_LIST,
        "values": {"type": "array"},
    },
}

FRAME_SLICES_1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:cure-light:frame-slices/1",
    "title": "frame-slices/1",
    "description": (
        "Sliced labeling manifest for a verified capture set: complete global "
        "unit tables plus bounded byte-exact slice payload references.  "
        "captures_sha256 = sha256(canonical claim-json/1 of the source "
        "identity records sorted by source_ref UTF-8), where each identity "
        "record is the capture-manifest source record without its file key."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "captures_sha256",
        "frame_recipe",
        "frame_recipe_hash",
        "slice_recipe",
        "slice_recipe_hash",
        "sources",
        "slices",
    ],
    "properties": {
        "schema_version": {"const": FRAME_SLICES_VERSION},
        "captures_sha256": _HEX,
        "frame_recipe": {"type": "object"},
        "frame_recipe_hash": _OBJECT_HASH,
        "slice_recipe": _SLICE_RECIPE,
        "slice_recipe_hash": _OBJECT_HASH,
        "sources": {"type": "array", "items": {"$ref": "#/$defs/source"}},
        "slices": {"type": "array", "items": {"$ref": "#/$defs/slice"}},
    },
    "$defs": {
        "unit": {
            "type": "object",
            "additionalProperties": False,
            "required": _UNIT_REQUIRED,
            "properties": _UNIT_PROPERTIES,
        },
        "source": {
            "type": "object",
            "additionalProperties": False,
            "required": ["source_ref", "sha256", "byte_length", "units"],
            "properties": {
                "source_ref": {"type": "string", "minLength": 1},
                "sha256": _HEX,
                "byte_length": {"type": "integer", "minimum": 0},
                "units": {"type": "array", "items": {"$ref": "#/$defs/unit"}},
            },
        },
        "payload_ref": {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "sha256", "byte_length"],
            "properties": {
                "path": {"type": "string", "minLength": 1},
                "sha256": _HEX,
                "byte_length": {"type": "integer", "minimum": 1},
            },
        },
        "slice": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "slice_id",
                "source_ref",
                "core_ids",
                "overlap_ids",
                "context_only_ids",
                "input",
            ],
            "properties": {
                "slice_id": _OBJECT_HASH,
                "source_ref": {"type": "string", "minLength": 1},
                "core_ids": _UNIT_ID_LIST,
                "overlap_ids": _UNIT_ID_LIST,
                "context_only_ids": _UNIT_ID_LIST,
                "input": {"$ref": "#/$defs/payload_ref"},
            },
        },
    },
}

FRAME_SLICE_INPUT_1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:cure-light:frame-slice-input/1",
    "title": "frame-slice-input/1",
    "description": (
        "Complete worker input for one slice: pinned instructions, global "
        "unit records with their exact UTF-8 text, and the core/overlap/"
        "context id partition.  Serialized as canonical claim-json/1 and "
        "bounded by the slice recipe's max_input_bytes."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "slice_id",
        "source_ref",
        "frame_recipe_hash",
        "slice_recipe_hash",
        "instructions",
        "units",
        "core_ids",
        "overlap_ids",
        "context_only_ids",
    ],
    "properties": {
        "schema_version": {"const": FRAME_SLICE_INPUT_VERSION},
        "slice_id": _OBJECT_HASH,
        "source_ref": {"type": "string", "minLength": 1},
        "frame_recipe_hash": _OBJECT_HASH,
        "slice_recipe_hash": _OBJECT_HASH,
        "instructions": {
            "type": "object",
            "additionalProperties": False,
            "required": ["version", "text"],
            "properties": {
                "version": {"type": "string", "minLength": 1},
                "text": {"type": "string", "minLength": 1},
            },
        },
        "units": {"type": "array", "items": {"$ref": "#/$defs/unit_text"}},
        "core_ids": _UNIT_ID_LIST,
        "overlap_ids": _UNIT_ID_LIST,
        "context_only_ids": _UNIT_ID_LIST,
    },
    "$defs": {
        "unit_text": {
            "type": "object",
            "additionalProperties": False,
            "required": _UNIT_REQUIRED + ["text"],
            "properties": {**_UNIT_PROPERTIES, "text": {"type": "string"}},
        },
    },
}

SLICE_PROPOSALS_1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:cure-light:slice-proposals/1",
    "title": "slice-proposals/1",
    "description": (
        "One child agent's answer for exactly one frame-slice-input/1: "
        "primary claim/nonclaim assignments owning only core nonseparator "
        "units, one overlap vote per overlap nonseparator, one grouping vote "
        "per mechanically enumerated visible nonseparator adjacency pair, "
        "and the slice's left/right boundary declarations."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "slice_id",
        "input_sha256",
        "assignments",
        "overlap_votes",
        "grouping_votes",
        "boundary",
    ],
    "properties": {
        "schema_version": {"const": SLICE_PROPOSALS_VERSION},
        "slice_id": _OBJECT_HASH,
        "input_sha256": _HEX,
        "assignments": {
            "type": "array",
            "items": {"oneOf": [_CLAIM_ASSIGNMENT, _NONCLAIM_ASSIGNMENT]},
        },
        "overlap_votes": {
            "type": "array",
            "items": {"oneOf": [_CLAIM_VOTE, _NONCLAIM_VOTE]},
        },
        "grouping_votes": {"type": "array", "items": _GROUPING_VOTE},
        "boundary": _BOUNDARY,
    },
}

PROPOSAL_RECONCILIATION_1 = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "urn:cure-light:proposal-reconciliation/1",
    "title": "proposal-reconciliation/1",
    "description": (
        "Deterministic reconciliation report for one frame-slices/1 run.  "
        "complete=true and a non-null merged_sha256 only when the merged "
        "claim-proposals/1 document was published; every failed attempt "
        "publishes this report and never a merged artifact."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "slices_sha256",
        "inputs",
        "merged_sha256",
        "complete",
        "conflicts",
        "warnings",
        "counts",
    ],
    "properties": {
        "schema_version": {"const": PROPOSAL_RECONCILIATION_VERSION},
        "slices_sha256": _HEX,
        "inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["slice_id", "sha256"],
                "properties": {"slice_id": _OBJECT_HASH, "sha256": _HEX},
            },
        },
        "merged_sha256": {
            "oneOf": [_HEX, {"type": "null"}],
        },
        "complete": {"type": "boolean"},
        "conflicts": {"type": "array", "items": _ISSUE},
        "warnings": {"type": "array", "items": _ISSUE},
        "counts": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "expected_slices",
                "received_proposals",
                "primary_assignments",
                "audited_overlap_units",
                "audited_seams",
            ],
            "properties": {
                "expected_slices": {"type": "integer", "minimum": 0},
                "received_proposals": {"type": "integer", "minimum": 0},
                "primary_assignments": {"type": "integer", "minimum": 0},
                "audited_overlap_units": {"type": "integer", "minimum": 0},
                "audited_seams": {"type": "integer", "minimum": 0},
            },
        },
    },
}

SCHEMAS = {
    FRAME_SLICES_VERSION: FRAME_SLICES_1,
    FRAME_SLICE_INPUT_VERSION: FRAME_SLICE_INPUT_1,
    SLICE_PROPOSALS_VERSION: SLICE_PROPOSALS_1,
    PROPOSAL_RECONCILIATION_VERSION: PROPOSAL_RECONCILIATION_1,
}


# ---------------------------------------------------------------------------
# strict JSON Schema subset validator
# ---------------------------------------------------------------------------

def _type_ok(type_name: str, value) -> bool:
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    raise ValueError(f"unsupported schema type {type_name!r}")


def _validate(schema: dict, value, path: str, root: dict) -> list[str]:
    errors: list[str] = []

    if "$ref" in schema:
        ref = schema["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported $ref {ref!r}"]
        target = root.get("$defs", {}).get(ref[len("#/$defs/"):])
        if not isinstance(target, dict):
            return [f"{path}: unresolved $ref {ref!r}"]
        return _validate(target, value, path, root)

    if "oneOf" in schema:
        matched = 0
        for sub in schema["oneOf"]:
            if not _validate(sub, value, path, root):
                matched += 1
        if matched != 1:
            errors.append(f"{path}: expected exactly one oneOf branch, matched {matched}")
        return errors

    declared = schema.get("type")
    if declared is not None:
        names = declared if isinstance(declared, list) else [declared]
        if not any(_type_ok(name, value) for name in names):
            errors.append(
                f"{path}: expected {'|'.join(names)}, got {type(value).__name__}"
            )
            return errors

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than maxItems {schema['maxItems']}")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(value):
                errors.extend(_validate(items, item, f"{path}[{i}]", root))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                errors.extend(
                    _validate(properties[key], item, f"{path}.{key}", root)
                )
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unknown key {key!r}")

    return errors


def validate(schema: dict, value) -> list[str]:
    """Return a sorted list of schema violations (empty means valid)."""
    return sorted(_validate(schema, value, "$", schema))


def validate_by_name(schema_version: str, value) -> list[str]:
    schema = SCHEMAS.get(schema_version)
    if schema is None:
        return [f"$: unknown schema_version {schema_version!r}"]
    return validate(schema, value)


__all__ = [
    "BOUNDARY_VALUES",
    "FRAME_SLICES_1",
    "FRAME_SLICES_VERSION",
    "FRAME_SLICE_INPUT_1",
    "FRAME_SLICE_INPUT_VERSION",
    "GROUPING_VALUES",
    "NONCLAIM_LABELS",
    "PROPOSAL_RECONCILIATION_1",
    "PROPOSAL_RECONCILIATION_VERSION",
    "SCHEMAS",
    "SLICE_PROPOSALS_1",
    "SLICE_PROPOSALS_VERSION",
    "UNIT_KINDS",
    "validate",
    "validate_by_name",
]
