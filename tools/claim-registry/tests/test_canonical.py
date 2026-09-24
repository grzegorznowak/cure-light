"""Canonicalization ``claim-json/1`` tests (spec section 2)."""

from __future__ import annotations

import hashlib

import pytest

from claim_registry.canonical import (
    CanonicalizationError,
    MAX_SAFE_INT,
    assert_canonical_bytes,
    canonical_dumps,
    canonical_hash,
    canonical_loads,
    recipe_hash,
    registry_hash,
    serialize_registry,
)


def test_key_sorting_and_compact_separators():
    assert canonical_dumps({"b": 1, "a": [True, None, "x"]}) == (
        b'{"a":[true,null,"x"],"b":1}'
    )
    assert canonical_dumps({"z": {"b": 1, "a": 2}}) == b'{"z":{"a":2,"b":1}}'
    assert canonical_dumps([1, 2, 3]) == b"[1,2,3]"
    assert canonical_dumps({}) == b"{}"
    assert canonical_dumps([]) == b"[]"


def test_no_trailing_newline():
    assert not canonical_dumps({"a": 1}).endswith(b"\n")


def test_string_escaping_rules():
    assert canonical_dumps({"t": 'a"b\\c'}) == b'{"t":"a\\"b\\\\c"}'
    assert canonical_dumps({"t": "a\u0001b"}) == b'{"t":"a\\u0001b"}'
    assert canonical_dumps({"t": "a\u001fb"}) == b'{"t":"a\\u001fb"}'
    # non-ASCII emitted literally as UTF-8, no normalization
    assert canonical_dumps({"t": "caf\u00e9"}) == b'{"t":"caf\xc3\xa9"}'
    # combining sequence stays as-is (no normalization)
    assert canonical_dumps({"t": "e\u0301"}) == '{"t":"e\u0301"}'.encode("utf-8")
    # slash and HTML are NOT escaped
    assert canonical_dumps({"t": "</script>"}) == b'{"t":"</script>"}'


def test_number_rules():
    assert canonical_dumps(0) == b"0"
    assert canonical_dumps(MAX_SAFE_INT) == str(MAX_SAFE_INT).encode()
    for bad in (-1, 1.0, 1.5, MAX_SAFE_INT + 1, float("nan"), float("inf")):
        with pytest.raises(CanonicalizationError):
            canonical_dumps(bad)


def test_rejects_non_ascii_keys_and_surrogates():
    with pytest.raises(CanonicalizationError):
        canonical_dumps({"\u00e9": 1})
    with pytest.raises(CanonicalizationError):
        canonical_dumps({"t": "\ud800"})


def test_hashes_reproduce_and_ignore_whitespace_input():
    payload = {"schema_version": "claim-registry/1", "n": 1}
    expected = "sha256:" + hashlib.sha256(canonical_dumps(payload)).hexdigest()
    assert registry_hash(payload) == expected
    assert recipe_hash({"a": 1}) == canonical_hash({"a": 1})


def test_serialize_registry_envelope_shape():
    payload = {"x": [1, 2], "y": "z"}
    raw = serialize_registry(payload)
    value = canonical_loads(raw)
    assert value["payload"] == payload
    assert value["registry_hash"] == registry_hash(payload)
    assert canonical_dumps(value) == raw


def test_canonical_loads_rejects_duplicates_and_bad_json():
    with pytest.raises(CanonicalizationError):
        canonical_loads(b'{"a":1,"a":2}')
    with pytest.raises(CanonicalizationError):
        canonical_loads(b"{bad json}")
    with pytest.raises(CanonicalizationError):
        canonical_loads(b'{"a":NaN}')


def test_assert_canonical_bytes_detects_trailing_newline():
    raw = canonical_dumps({"a": 1})
    assert_canonical_bytes(raw)
    with pytest.raises(CanonicalizationError):
        assert_canonical_bytes(raw + b"\n")
    with pytest.raises(CanonicalizationError):
        assert_canonical_bytes(b'{ "a" : 1 }')
