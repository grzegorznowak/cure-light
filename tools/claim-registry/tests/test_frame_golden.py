"""Golden frame acceptance gates (spec/reuse research).

PR #17 body (committed fixture ``tests/fixtures/pr17-body-v2.md``, 10,385 B):
29 block units + 22 separators.
Plan doc (contract-adequacy-validation-plan.md, 10,428 B): the lenient
prototype reported 56 blocks + 17 separators; the strict walker reports 56
blocks + 11 separators.  The difference is not fudged - it is the strict span
rule: a span ends after its final line terminator, so the six table rows
(header, delimiter row, five data rows) absorb the single LF that the prototype
left as a pseudo-separator, and the block-quote `> ` prefix is absorbed into
the first paragraph's span (the prototype counted a non-whitespace "separator"
at bytes [99,102)).  11 whitespace separators remain.
"""

from __future__ import annotations

import hashlib

from claim_registry.frame import frame_source


def test_pr17_body_golden(pr_body):
    frame = frame_source(pr_body)
    assert len(pr_body) == 10385
    assert hashlib.sha256(pr_body).hexdigest() == (
        "10b5b3018d8928ce607735a6c31181be463f983bbc21ba07aa1985b9b4e1c2a7"
    )
    assert frame.block_count == 29, [u.kind for u in frame.units]
    assert frame.separator_count == 22
    assert frame.covered_bytes() == len(pr_body)

    kinds = {}
    for u in frame.units:
        kinds[u.kind] = kinds.get(u.kind, 0) + 1
    assert kinds == {
        "atx_heading": 4,
        "paragraph": 19,
        "list_item": 6,
        "separator": 22,
    }

    # deterministic over three runs: units, kinds, spans, sha and unit ids
    runs = [frame_source(pr_body) for _ in range(3)]
    assert runs[0].units == runs[1].units == runs[2].units
    ids = [[u.unit_id("src:test") for u in r.units] for r in runs]
    assert ids[0] == ids[1] == ids[2]

    # every separator is whitespace-only; every span is line-aligned
    for u in frame.units:
        if u.kind == "separator":
            assert not pr_body[u.start:u.end].strip(b" \t\r\n")
        assert u.start == 0 or pr_body[u.start - 1:u.start] == b"\n"
        assert u.end == len(pr_body) or pr_body[u.end - 1:u.end] == b"\n"


def test_plan_doc_golden(plan_doc):
    frame = frame_source(plan_doc)
    assert len(plan_doc) == 10428
    assert hashlib.sha256(plan_doc).hexdigest() == (
        "62460fba139488f273b8c494ab203b9817b625a3c6146955cf00432659624a07"
    )
    assert frame.block_count == 56
    # Strict walker: 11, not the prototype's 17 (explanation in module docstring).
    assert frame.separator_count == 11
    assert frame.covered_bytes() == len(plan_doc)

    kinds = {}
    for u in frame.units:
        kinds[u.kind] = kinds.get(u.kind, 0) + 1
    assert kinds == {
        "atx_heading": 11,
        "paragraph": 5,
        "list_item": 33,
        "pipe_table_header": 1,
        "pipe_table_delimiter_row": 1,
        "pipe_table_row": 5,
        "separator": 11,
    }

    # The six prototype "separator" LFs are now inside the table row spans.
    table_units = [u for u in frame.units if u.kind.startswith("pipe_table")]
    assert len(table_units) == 7
    for u in table_units:
        assert plan_doc[u.end - 1:u.end] == b"\n", (u.kind, u.start, u.end)

    # The block-quote paragraph absorbs its `> ` prefix: prototype span was
    # [102,734); strict span starts at the physical line start 100.
    bq_para = [u for u in frame.units if u.kind == "paragraph" and u.start == 100]
    assert len(bq_para) == 1
    assert plan_doc[100:102] == b"> "
    assert bq_para[0].end == 734

    # deterministic over three runs
    runs = [frame_source(plan_doc) for _ in range(3)]
    assert runs[0].units == runs[1].units == runs[2].units


def test_pr_body_is_not_fixture_corrupted(pr_body):
    """Guard against the historical accidental transport newline."""
    assert pr_body.endswith(b"\n")
    assert not pr_body.endswith(b"\n\n")
    assert pr_body.count(b"\r") == 0
