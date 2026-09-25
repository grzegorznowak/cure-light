"""Negative cases: strict failure modes and identity boundaries."""

from __future__ import annotations

import hashlib

import pytest

from claim_registry.capture import capture_bytes
from claim_registry.frame import (
    ExtractionError,
    RawLeaf,
    frame_source,
    partition_units,
    span_is_line_aligned,
)


def test_appended_transport_newline_changes_source_identity(pr_body):
    variant = pr_body + b"\n"
    base = capture_bytes(pr_body, "repo#17:body")
    changed = capture_bytes(variant, "repo#17:body")
    assert changed.byte_length == base.byte_length + 1
    assert changed.sha256 != base.sha256
    assert changed.blob_oid != base.blob_oid
    assert changed.source_ref != base.source_ref

    frame_a = frame_source(pr_body)
    frame_b = frame_source(variant)
    assert frame_a.units != frame_b.units
    assert frame_a.units[-1].end == len(pr_body)
    assert frame_b.units[-1].end == len(variant)


def test_crlf_vs_lf_produce_different_span_bytes():
    lf = b"# Title\n\nbody\n"
    crlf = b"# Title\r\n\r\nbody\r\n"
    frame_lf = frame_source(lf)
    frame_crlf = frame_source(crlf)
    assert frame_lf.covered_bytes() == len(lf)
    assert frame_crlf.covered_bytes() == len(crlf)
    heading = frame_crlf.units[0]
    assert crlf[heading.start:heading.end] == b"# Title\r\n"
    assert heading.sha256 == hashlib.sha256(b"# Title\r\n").hexdigest()
    assert heading.sha256 != frame_lf.units[0].sha256
    assert [u.unit_id("s") for u in frame_crlf.units] != [
        u.unit_id("s") for u in frame_lf.units
    ]


def test_multibyte_offsets_are_byte_exact():
    src = "# \U0001F680 plan\n\ncaf\u00e9\n".encode("utf-8")
    frame = frame_source(src)
    heading = frame.units[0]
    assert heading.kind == "atx_heading"
    assert src[heading.start:heading.end] == "# \U0001F680 plan\n".encode("utf-8")
    # byte length, not character length
    assert heading.byte_length == len("# \U0001F680 plan\n".encode("utf-8"))
    assert heading.byte_length != len("# \U0001F680 plan\n")
    assert heading.sha256 == hashlib.sha256(
        "# \U0001F680 plan\n".encode("utf-8")
    ).hexdigest()
    assert frame.covered_bytes() == len(src)


def test_nested_lists_partition_and_marker_inclusion():
    src = (
        b"1. outer\n"
        b"   - inner a\n"
        b"   - inner b\n"
        b"\n"
        b"   continued paragraph\n"
        b"2. next\n"
        b"\n"
        b"   > quote inside list\n"
        b"   > more quote\n"
    )
    frame = frame_source(src)
    units = list(frame.units)
    pos = 0
    for u in units:
        assert u.start == pos
        pos = u.end
    assert pos == len(src)
    # The first child of the compound outer item includes the item marker.
    assert units[0].start == 0
    assert src[units[0].start:units[0].start + 3] == b"1. "
    assert all(span_is_line_aligned(src, u) for u in units)


def test_manufactured_non_whitespace_gap_raises_with_location():
    src = b"alpha\nxyz\nbravo\n"
    leaves = [
        RawLeaf(kind="paragraph", start=0, end=6),
        RawLeaf(kind="paragraph", start=10, end=len(src)),
    ]
    with pytest.raises(ExtractionError) as excinfo:
        partition_units(src, leaves)
    err = excinfo.value
    assert err.offset == 6
    assert err.end == 10
    assert "xyz" in str(err)
    assert "non-whitespace gap" in str(err)


def test_overlapping_leaves_raise():
    src = b"alpha\n\nbravo\n"
    leaves = [
        RawLeaf(kind="paragraph", start=0, end=8),
        RawLeaf(kind="paragraph", start=6, end=len(src)),
    ]
    with pytest.raises(ExtractionError) as excinfo:
        partition_units(src, leaves)
    assert "overlapping" in str(excinfo.value)


def test_parse_error_raises_with_location():
    src = b"\x00\x01\x02 text\n"
    with pytest.raises(ExtractionError) as excinfo:
        frame_source(src)
    err = excinfo.value
    assert err.offset == 0
    assert err.end == 1
    assert "ERROR" in str(err)


def test_unclosed_fence_frames_to_eof():
    src = b"Before fence.\n\n```\ndef login():\n    ...\n"
    frame = frame_source(src)
    fence = [u for u in frame.units if u.kind == "fenced_code_block"]
    assert len(fence) == 1
    assert fence[0].end == len(src)
    assert src[fence[0].start:fence[0].end].startswith(b"```\n")


def test_empty_and_whitespace_sources():
    assert frame_source(b"").units == ()
    ws_src = b"\n\n  \n"
    ws = frame_source(ws_src)
    assert len(ws.units) == 1
    assert ws.units[0].kind == "separator"
    assert ws.units[0].start == 0 and ws.units[0].end == len(ws_src)


def test_bom_stays_in_first_unit():
    src = b"\xef\xbb\xbf# Title\n\nbody\n"
    frame = frame_source(src)
    assert frame.units[0].start == 0
    assert src[frame.units[0].start:frame.units[0].end].startswith(b"\xef\xbb\xbf")
    assert frame.covered_bytes() == len(src)
