"""Canonical JSON serialization ``claim-json/1`` (spec section 2).

Rules implemented here:

* UTF-8 output, no BOM, no Unicode normalization.
* Object member names are ASCII schema keys; keys sorted lexicographically by
  ASCII bytes at every depth; duplicate keys rejected.
* ``","`` and ``":"`` separators without whitespace; lowercase ``true``/
  ``false``/``null``.
* Numbers are nonnegative integers <= ``2**53 - 1``, decimal digits only.
  Floats, negatives, leading zeros and negative zero are rejected.
* Strings escape ``"`` and ``\\``; U+0000-U+001F are emitted as lowercase
  ``\\u00xx``; all other Unicode is emitted literally.  Lone surrogates are
  rejected.  No slash-escaping, no HTML escaping.
* Serialization has no trailing newline.
"""

from __future__ import annotations

import hashlib
import json

MAX_SAFE_INT = 2 ** 53 - 1

# U+0000..U+001F
_ESCAPES = {
    i: f"\\u{i:04x}" for i in range(0x20)
}
_ESCAPES[0x22] = '\\"'
_ESCAPES[0x5C] = "\\\\"


class CanonicalizationError(ValueError):
    """Input cannot be represented as canonical ``claim-json/1``."""


def _encode_string(value: str) -> str:
    out: list[str] = ['"']
    for ch in value:
        esc = _ESCAPES.get(ord(ch))
        if esc is not None:
            out.append(esc)
        else:
            code = ord(ch)
            if 0xD800 <= code <= 0xDFFF:
                raise CanonicalizationError(
                    f"lone surrogate U+{code:04X} is not canonical JSON"
                )
            out.append(ch)
    out.append('"')
    text = "".join(out)
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as exc:  # pragma: no cover - guarded above
        raise CanonicalizationError(str(exc)) from exc
    return text


def _encode_int(value: int) -> str:
    if isinstance(value, bool):
        raise AssertionError("bool handled before int")
    if value < 0:
        raise CanonicalizationError("negative numbers are not canonical")
    if value > MAX_SAFE_INT:
        raise CanonicalizationError(
            f"integer {value} exceeds 2**53-1 canonical bound"
        )
    if value == 0:
        return "0"
    return str(value)


def _encode(value, out: list[str]) -> None:
    if value is None:
        out.append("null")
    elif value is True:
        out.append("true")
    elif value is False:
        out.append("false")
    elif isinstance(value, int):
        out.append(_encode_int(value))
    elif isinstance(value, float):
        raise CanonicalizationError("floats are not canonical JSON")
    elif isinstance(value, str):
        out.append(_encode_string(value))
    elif isinstance(value, (list, tuple)):
        out.append("[")
        for i, item in enumerate(value):
            if i:
                out.append(",")
            _encode(item, out)
        out.append("]")
    elif isinstance(value, dict):
        keys = list(value.keys())
        for key in keys:
            if not isinstance(key, str):
                raise CanonicalizationError(f"object key {key!r} is not a string")
            try:
                key.encode("ascii")
            except UnicodeEncodeError:
                raise CanonicalizationError(
                    f"object key {key!r} is not an ASCII schema key"
                ) from None
        out.append("{")
        for i, key in enumerate(sorted(keys)):
            if i:
                out.append(",")
            out.append(_encode_string(key))
            out.append(":")
            _encode(value[key], out)
        out.append("}")
    else:
        raise CanonicalizationError(
            f"unsupported type {type(value).__name__} is not canonical JSON"
        )


def canonical_dumps(value) -> bytes:
    """Serialize ``value`` to canonical ``claim-json/1`` bytes (no newline)."""
    out: list[str] = []
    _encode(value, out)
    return "".join(out).encode("utf-8")


def _no_duplicates(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise CanonicalizationError(f"duplicate object key {key!r}")
        seen.add(key)
    return dict(pairs)


def canonical_loads(data: bytes):
    """Strict JSON parse used by validation (duplicate keys rejected)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CanonicalizationError(f"invalid UTF-8: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates,
                          parse_constant=lambda c: (_ for _ in ()).throw(
                              CanonicalizationError(f"invalid constant {c}")))
    except json.JSONDecodeError as exc:
        raise CanonicalizationError(f"invalid JSON: {exc}") from exc


def assert_canonical_bytes(data: bytes) -> None:
    """Raise unless ``data`` is exactly the canonical serialization of its value."""
    value = canonical_loads(data)
    if canonical_dumps(value) != data:
        raise CanonicalizationError("bytes are not canonical claim-json/1")


def hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_hash(value) -> str:
    return hash_bytes(canonical_dumps(value))


def recipe_hash(recipe: dict) -> str:
    return canonical_hash(recipe)


def registry_hash(payload: dict) -> str:
    return canonical_hash(payload)


def serialize_registry(payload: dict) -> bytes:
    """Canonical bytes of the envelope ``{"payload":..., "registry_hash":...}``."""
    envelope = {"payload": payload, "registry_hash": registry_hash(payload)}
    return canonical_dumps(envelope)


__all__ = [
    "CanonicalizationError",
    "MAX_SAFE_INT",
    "assert_canonical_bytes",
    "canonical_dumps",
    "canonical_hash",
    "canonical_loads",
    "hash_bytes",
    "recipe_hash",
    "registry_hash",
    "serialize_registry",
]
