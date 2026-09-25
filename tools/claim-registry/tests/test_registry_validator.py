"""Registry assembly and independent validator acceptance tests."""

from __future__ import annotations

import copy
import hashlib
import json

import pytest

from claim_registry import canonical
from claim_registry.capture import capture_bytes
from claim_registry.frame import frame_source
from claim_registry.registry import (
    RegistryAssemblyError,
    assemble_registry,
    default_proposals,
)
from claim_registry.validator import validate_registry

SMALL = b"# Title\n\nAlpha claim.\n\nBeta claim.\n"


def build_small():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    res = assemble_registry(
        [cap], {cap.source_ref: frame}, default_proposals(cap.source_ref, frame)
    )
    return cap, frame, res


def build_pr_body(pr_body):
    cap = capture_bytes(pr_body, "repo#17:body")
    frame = frame_source(pr_body)
    res = assemble_registry(
        [cap], {cap.source_ref: frame}, default_proposals(cap.source_ref, frame)
    )
    return cap, frame, res


def reseal(envelope):
    envelope["registry_hash"] = canonical.registry_hash(envelope["payload"])
    return envelope


def rehash_claim(envelope, src_by_ref, claim):
    data = src_by_ref[claim["source_ref"]]
    old_id = claim["claim_id"]
    claim["sha256"] = hashlib.sha256(data[claim["start"]:claim["end"]]).hexdigest()
    claim["claim_id"] = (
        f'{claim["source_ref"]}:{claim["start"]}-{claim["end"]}:{claim["sha256"]}'
    )
    for label in envelope["payload"]["labels"]:
        if label["claim_id"] == old_id:
            label["claim_id"] = claim["claim_id"]
    return claim


def test_assemble_and_validate_complete_pr_body(pr_body):
    cap, frame, res = build_pr_body(pr_body)
    assert res.payload["schema_version"] == "claim-registry/1"
    assert res.payload["witness"]["complete"] is True
    assert res.canonical_bytes == canonical.canonical_dumps(res.envelope)
    assert not res.canonical_bytes.endswith(b"\n")
    assert res.envelope["registry_hash"].startswith("sha256:")
    assert res.payload["recipe_hash"].startswith("sha256:")

    report = validate_registry(
        res.envelope, {cap.source_ref: pr_body}, raw_bytes=res.canonical_bytes
    )
    assert report.valid, [c for c in report.checks if not c.ok]
    assert report.errors == []
    assert report.permission == {
        "complete_registry_claims": True,
        "finalized_unclaimed": True,
    }
    assert report.registry_hash == res.envelope["registry_hash"]
    # witness counts sum to the whole source
    ps = report.recomputed_witness["per_source"][0]
    assert ps["unit_count"] == len(res.payload["units"])
    assert ps["covered_unit_count"] == ps["unit_count"]
    assert ps["covered_byte_count"] == len(pr_body)
    assert ps["pending_count"] == 0


def test_validator_rejects_registry_file_trailing_newline(pr_body):
    cap, _, res = build_pr_body(pr_body)
    report = validate_registry(
        res.envelope,
        {cap.source_ref: pr_body},
        raw_bytes=res.canonical_bytes + b"\n",
    )
    assert not report.valid
    assert any(c.name == "canonical_bytes" for c in report.checks if not c.ok)


def test_validator_rejects_dropped_unit():
    cap, _, res = build_small()
    data = copy.deepcopy(res.envelope)
    dropped = data["payload"]["units"].pop(0)
    data["payload"]["labels"] = [
        lab for lab in data["payload"]["labels"]
        if lab["unit_id"] != dropped["unit_id"]
    ]
    reseal(data)
    report = validate_registry(data, {cap.source_ref: SMALL})
    assert not report.valid
    failed = {c.name for c in report.checks if not c.ok}
    assert failed & {"re_extract[%s]" % cap.source_ref, "unit_count_reconciles",
                     "partition[%s]" % cap.source_ref, "labels_count",
                     "labels_exhaustive"}


def test_validator_rejects_double_owned_unit():
    cap, _, res = build_small()
    data = copy.deepcopy(res.envelope)
    dup = dict(data["payload"]["labels"][0])
    data["payload"]["labels"].append(dup)
    reseal(data)
    report = validate_registry(data, {cap.source_ref: SMALL})
    assert not report.valid
    assert any(c.name == "label_unique" for c in report.checks if not c.ok)


def test_validator_rejects_mid_unit_claim_boundary():
    cap, frame, res = build_small()
    data = copy.deepcopy(res.envelope)
    src_by_ref = {cap.source_ref: SMALL}
    claim = data["payload"]["claims"][0]
    unit = next(u for u in data["payload"]["units"]
                if u["unit_id"] == claim["unit_ids"][0])
    claim["start"] = unit["start"] + 1
    rehash_claim(data, src_by_ref, claim)
    reseal(data)
    report = validate_registry(data, src_by_ref)
    assert not report.valid
    failed = {c.name for c in report.checks if not c.ok}
    assert any(name.startswith("claim_span_matches_units") for name in failed)


def test_validator_rejects_claim_jumping_over_separator():
    cap, frame, res = build_small()
    data = copy.deepcopy(res.envelope)
    src_by_ref = {cap.source_ref: SMALL}
    claims = data["payload"]["claims"]
    # claims[0] = heading unit, claims[1] = paragraph unit; separator between.
    c0, c1 = claims[0], claims[1]
    merged = {
        "claim_id": None,
        "source_ref": c0["source_ref"],
        "start": c0["start"],
        "end": c1["end"],
        "sha256": None,
        "unit_ids": c0["unit_ids"] + c1["unit_ids"],
        "parent_ref": None,
        "active": True,
    }
    rehash_claim(data, src_by_ref, merged)
    data["payload"]["claims"] = [merged] + [
        c for c in claims if c not in (c0, c1)
    ]
    for label in data["payload"]["labels"]:
        if label["unit_id"] in merged["unit_ids"]:
            label["claim_id"] = merged["claim_id"]
    reseal(data)
    report = validate_registry(data, src_by_ref)
    assert not report.valid
    failed = {c.name for c in report.checks if not c.ok}
    assert any(name.startswith("claim_contiguous") for name in failed)
    assert any(name.startswith("claim_span_units") for name in failed)


def test_validator_rejects_tampered_registry_hash():
    cap, _, res = build_small()
    data = copy.deepcopy(res.envelope)
    data["registry_hash"] = "sha256:" + "0" * 64
    report = validate_registry(data, {cap.source_ref: SMALL})
    assert not report.valid
    assert any(c.name == "registry_hash" for c in report.checks if not c.ok)


def test_validator_rejects_tampered_unit_hash():
    cap, _, res = build_small()
    data = copy.deepcopy(res.envelope)
    data["payload"]["units"][0]["sha256"] = "0" * 64
    reseal(data)
    report = validate_registry(data, {cap.source_ref: SMALL})
    assert not report.valid
    assert any(c.name == "unit_sha" for c in report.checks if not c.ok)


def test_producer_complete_flag_is_not_trusted():
    cap, frame, res = build_small()
    data = copy.deepcopy(res.envelope)
    # Drop ownership of one unit but keep a producer-supplied complete=true.
    unit = data["payload"]["units"][1]
    data["payload"]["labels"] = [
        lab for lab in data["payload"]["labels"] if lab["unit_id"] != unit["unit_id"]
    ]
    data["payload"]["witness"]["complete"] = True
    reseal(data)
    report = validate_registry(data, {cap.source_ref: SMALL})
    assert not report.valid
    assert any(c.name == "complete_recomputed" for c in report.checks if not c.ok)
    assert report.permission["finalized_unclaimed"] is False


def test_partial_registry_valid_but_not_permitted():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    first = frame.units[0]
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": [
            {
                "source_ref": cap.source_ref,
                "unit_ids": [first.unit_id(cap.source_ref)],
                "state": "claim",
                "rationale": "partial pilot",
            }
        ],
    }
    res = assemble_registry([cap], {cap.source_ref: frame}, proposals)
    assert res.payload["witness"]["complete"] is False
    states = {lab["state"] for lab in res.payload["labels"]}
    assert "pending" in states
    report = validate_registry(res.envelope, {cap.source_ref: SMALL})
    assert report.valid
    assert report.permission == {
        "complete_registry_claims": False,
        "finalized_unclaimed": False,
    }


# --------------------------------------------------------------------------
# assembly-side strictness
# --------------------------------------------------------------------------

def test_assembly_rejects_double_owned_units():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    uid = frame.units[0].unit_id(cap.source_ref)
    other = frame.units[2].unit_id(cap.source_ref)
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": [
            {"source_ref": cap.source_ref, "unit_ids": [uid], "state": "claim"},
            {"source_ref": cap.source_ref, "unit_ids": [uid, other], "state": "claim"},
        ],
    }
    with pytest.raises(RegistryAssemblyError):
        assemble_registry([cap], {cap.source_ref: frame}, proposals)


def test_assembly_rejects_non_consecutive_claim_members():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    units = [u.unit_id(cap.source_ref) for u in frame.units]
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": [
            {"source_ref": cap.source_ref, "unit_ids": [units[0], units[2]],
             "state": "claim"},
        ],
    }
    with pytest.raises(RegistryAssemblyError) as excinfo:
        assemble_registry([cap], {cap.source_ref: frame}, proposals)
    assert "consecutive" in str(excinfo.value)


def test_assembly_rejects_separator_claim_member():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    units = [u.unit_id(cap.source_ref) for u in frame.units]
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": [
            {"source_ref": cap.source_ref, "unit_ids": [units[1]], "state": "claim"},
        ],
    }
    with pytest.raises(RegistryAssemblyError):
        assemble_registry([cap], {cap.source_ref: frame}, proposals)


def test_assembly_rejects_nonclaim_without_rationale():
    cap = capture_bytes(SMALL, "repo#1:body")
    frame = frame_source(SMALL)
    units = [u.unit_id(cap.source_ref) for u in frame.units]
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": [
            {"source_ref": cap.source_ref, "unit_ids": [units[1]],
             "state": "nonclaim", "label": "context", "role_ref": "x"},
        ],
    }
    with pytest.raises(RegistryAssemblyError):
        assemble_registry([cap], {cap.source_ref: frame}, proposals)


def test_decomposition_roundtrip_and_remainder_rule():
    src = b"- one\n- two\n- three\n"
    cap = capture_bytes(src, "repo#2:body")
    frame = frame_source(src)
    units = [u.unit_id(cap.source_ref) for u in frame.units]
    base_assignments = [
        {"source_ref": cap.source_ref, "unit_ids": [units[1]], "state": "nonclaim",
         "label": "context", "rationale": "middle item", "role_ref": "test"},
    ]
    proposals = {
        "schema_version": "claim-proposals/1",
        "assignments": base_assignments,
        "decomposition": [
            {
                "parent": {"source_ref": cap.source_ref, "unit_ids": units},
                "children": [{"unit_ids": [units[0]]}, {"unit_ids": [units[2]]}],
            }
        ],
    }
    res = assemble_registry([cap], {cap.source_ref: frame}, proposals)
    claims = {c["claim_id"]: c for c in res.payload["claims"]}
    parents = [c for c in claims.values() if c["active"] is False]
    children = [c for c in claims.values() if c["parent_ref"]]
    assert len(parents) == 1 and len(children) == 2
    for child in children:
        assert child["parent_ref"] == parents[0]["claim_id"]
    report = validate_registry(res.envelope, {cap.source_ref: src},
                               raw_bytes=res.canonical_bytes)
    assert report.valid, [c for c in report.checks if not c.ok]

    # remainder without explicit nonclaim ownership must fail assembly
    bad = copy.deepcopy(proposals)
    bad["assignments"] = []
    with pytest.raises(RegistryAssemblyError) as excinfo:
        assemble_registry([cap], {cap.source_ref: frame}, bad)
    assert "remainder unit unowned" in str(excinfo.value)

    # child not contained in parent must fail
    bad2 = copy.deepcopy(proposals)
    bad2["decomposition"][0]["parent"]["unit_ids"] = units[:2]
    with pytest.raises(RegistryAssemblyError) as excinfo:
        assemble_registry([cap], {cap.source_ref: frame}, bad2)
    assert "not contained" in str(excinfo.value)


def test_registry_json_roundtrip_through_disk(pr_body, tmp_path):
    cap, _, res = build_pr_body(pr_body)
    path = tmp_path / "registry.json"
    path.write_bytes(res.canonical_bytes)
    on_disk = path.read_bytes()
    assert on_disk == res.canonical_bytes
    envelope = canonical.canonical_loads(on_disk)
    assert envelope == res.envelope
    report = validate_registry(envelope, {cap.source_ref: pr_body}, raw_bytes=on_disk)
    assert report.valid
    # json.dumps of the parsed value is not canonical but must parse identically
    assert json.loads(json.dumps(envelope)) == envelope


TABLE = b"| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"


def test_validator_rejects_dropped_table_row():
    cap = capture_bytes(TABLE, "repo#3:body")
    frame = frame_source(TABLE)
    res = assemble_registry(
        [cap], {cap.source_ref: frame}, default_proposals(cap.source_ref, frame)
    )
    kinds = [u["kind"] for u in res.payload["units"]]
    assert kinds == ["pipe_table_header", "pipe_table_delimiter_row",
                     "pipe_table_row", "pipe_table_row"]
    data = copy.deepcopy(res.envelope)
    row = data["payload"]["units"].pop(3)  # drop the last table row
    data["payload"]["labels"] = [
        lab for lab in data["payload"]["labels"] if lab["unit_id"] != row["unit_id"]
    ]
    reseal(data)
    report = validate_registry(data, {cap.source_ref: TABLE})
    assert not report.valid
    failed = {c.name for c in report.checks if not c.ok}
    assert failed & {"re_extract[%s]" % cap.source_ref,
                     "unit_count_reconciles",
                     "partition[%s]" % cap.source_ref,
                     "labels_count", "labels_exhaustive"}


def test_validator_rejects_duplicated_table_row():
    cap = capture_bytes(TABLE, "repo#3:body")
    frame = frame_source(TABLE)
    res = assemble_registry(
        [cap], {cap.source_ref: frame}, default_proposals(cap.source_ref, frame)
    )
    data = copy.deepcopy(res.envelope)
    row = copy.deepcopy(data["payload"]["units"][3])
    row["ordinal"] = 4
    data["payload"]["units"].append(row)
    reseal(data)
    report = validate_registry(data, {cap.source_ref: TABLE})
    assert not report.valid
    assert any(c.name in ("unit_unique", "re_extract[%s]" % cap.source_ref,
                          "unit_count_reconciles", "partition[%s]" % cap.source_ref)
               for c in report.checks if not c.ok)
