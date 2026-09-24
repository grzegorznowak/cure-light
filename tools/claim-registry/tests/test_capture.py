"""Capture and content identity tests (spec section 1.1)."""

from __future__ import annotations

import hashlib

from claim_registry.capture import (
    SourceCapture,
    capture_bytes,
    make_source_ref,
    percent_encode,
    raw_sha256,
    synthetic_git_blob_oid,
    verify_capture,
)


def test_bytes_are_kept_verbatim():
    data = b"# T\r\n\r\nno trailing newline"
    cap = capture_bytes(data, "repo#1:body")
    assert cap.data == data                      # no newline added, no CRLF conversion
    assert cap.byte_length == len(data)
    assert cap.sha256 == hashlib.sha256(data).hexdigest()
    assert cap.empty is False


def test_synthetic_git_blob_oid_known_constants():
    # Git SHA-256 object-format empty blob.
    assert synthetic_git_blob_oid(b"") == (
        "473a0f4c3be8a93681a267e3b1e9a7dcda1185436fe141f7749120a303721813"
    )
    assert synthetic_git_blob_oid(b"hello\n") == (
        "2cf8d83d9ee29543b34a87727421fdecb7e3f3a183d337639025de576db9ebb4"
    )
    assert raw_sha256(b"hello\n") != synthetic_git_blob_oid(b"hello\n")


def test_percent_encoding_unreserved_and_uppercase_hex():
    assert percent_encode("repo/name#17:body") == "repo%2Fname%2317%3Abody"
    assert percent_encode("AZaz09._~-") == "AZaz09._~-"
    assert percent_encode("h\u00e9llo") == "h%C3%A9llo"   # UTF-8 bytes, uppercase
    assert percent_encode(b"\x00\xff") == "%00%FF"


def test_source_ref_format():
    cap = capture_bytes(b"body\n", "repo#17:body")
    assert cap.source_ref == (
        f"src:repo%2317%3Abody:git-blob-sha256:{cap.blob_oid}"
    )
    assert make_source_ref("x", "abc") == "src:x:git-blob-sha256:abc"


def test_zero_byte_source_record():
    cap = capture_bytes(b"", "repo#17:empty-body")
    assert cap.empty is True
    assert cap.byte_length == 0
    assert cap.sha256 == hashlib.sha256(b"").hexdigest()
    assert cap.blob_oid == (
        "473a0f4c3be8a93681a267e3b1e9a7dcda1185436fe141f7749120a303721813"
    )
    record = cap.record()
    assert record["empty"] is True
    assert verify_capture(record, b"") == []


def test_distinct_locators_are_distinct_refs_even_with_equal_bytes():
    a = capture_bytes(b"same\n", "repo#1:body")
    b = capture_bytes(b"same\n", "repo#2:body")
    assert a.sha256 == b.sha256
    assert a.blob_oid == b.blob_oid
    assert a.source_ref != b.source_ref


def test_verify_capture_detects_tampering():
    cap = capture_bytes(b"body\n", "repo#1:body")
    record = cap.record()
    assert verify_capture(record, b"body\n") == []
    assert verify_capture(record, b"body")          # length + hash
    record["sha256"] = "0" * 64
    assert verify_capture(record, b"body\n")


def test_capture_rejects_text():
    try:
        capture_bytes("text", "repo#1:body")  # type: ignore[arg-type]
    except TypeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("capture_bytes accepted str input")
    # the correct path: encode exactly once upstream
    cap = capture_bytes("caf\u00e9".encode("utf-8"), "repo#1:body")
    assert cap.sha256 == hashlib.sha256(b"caf\xc3\xa9").hexdigest()
    assert isinstance(cap, SourceCapture)
