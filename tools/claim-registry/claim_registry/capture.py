"""Verbatim source capture and content identity (spec section 1.1).

Bytes are preserved exactly as captured: no trailing newline is added, no CRLF
conversion, no Unicode normalization, no trimming.  Raw SHA-256 and byte
length are recorded separately from the Git blob identity.

For API documents a synthetic Git blob object id is computed without writing an
object::

    SHA256(ASCII("blob ") || ASCII(decimal(byte_length)) || NUL || bytes)

labeled ``git-blob-sha256``.  ``source_ref`` is::

    src:<percent-encoded locator>:<blob_algorithm>:<blob_oid>

Percent encoding keeps ASCII unreserved ``[A-Za-z0-9._~-]`` unchanged and
emits every other byte as uppercase ``%HH``.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

UNRESERVED = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-"
)

BLOB_ALGORITHM = "git-blob-sha256"


def raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_git_blob_oid(data: bytes) -> str:
    """Git blob object id (sha256 object-format) without writing an object."""
    header = b"blob " + str(len(data)).encode("ascii") + b"\x00"
    return hashlib.sha256(header + data).hexdigest()


def percent_encode(text: str | bytes) -> str:
    """UTF-8 percent encoding with unreserved ``[A-Za-z0-9._~-]``."""
    raw = text.encode("utf-8") if isinstance(text, str) else text
    out: list[str] = []
    for b in raw:
        if b in UNRESERVED:
            out.append(chr(b))
        else:
            out.append(f"%{b:02X}")
    return "".join(out)


def make_source_ref(locator: str, blob_oid: str,
                    blob_algorithm: str = BLOB_ALGORITHM) -> str:
    return f"src:{percent_encode(locator)}:{blob_algorithm}:{blob_oid}"


@dataclass(frozen=True)
class SourceCapture:
    """One immutable captured document."""

    locator: str
    source_class: str
    data: bytes
    pointer_ref: str | None = None
    interpretation_ref: str | None = None
    blob_algorithm: str = BLOB_ALGORITHM

    # derived at construction
    sha256: str = field(init=False)
    byte_length: int = field(init=False)
    blob_oid: str = field(init=False)
    source_ref: str = field(init=False)
    empty: bool = field(init=False)
    bom: bool = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "sha256", raw_sha256(self.data))
        object.__setattr__(self, "byte_length", len(self.data))
        object.__setattr__(self, "blob_oid", synthetic_git_blob_oid(self.data))
        object.__setattr__(
            self, "source_ref", make_source_ref(self.locator, self.blob_oid, self.blob_algorithm)
        )
        object.__setattr__(self, "empty", len(self.data) == 0)
        object.__setattr__(self, "bom", self.data.startswith(b"\xef\xbb\xbf"))

    def record(self) -> dict:
        """Registry ``sources`` entry."""
        return {
            "source_ref": self.source_ref,
            "locator": self.locator,
            "class": self.source_class,
            "pointer_ref": self.pointer_ref,
            "interpretation_ref": self.interpretation_ref,
            "blob_algorithm": self.blob_algorithm,
            "blob_oid": self.blob_oid,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "empty": self.empty,
            "bom": self.bom,
        }


def capture_bytes(
    data: bytes,
    locator: str,
    *,
    source_class: str = "api-document",
    pointer_ref: str | None = None,
    interpretation_ref: str | None = None,
) -> SourceCapture:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("capture_bytes requires bytes; decode text exactly once upstream")
    return SourceCapture(
        locator=locator,
        source_class=source_class,
        data=bytes(data),
        pointer_ref=pointer_ref,
        interpretation_ref=interpretation_ref,
    )


def capture_file(
    path: str,
    locator: str,
    *,
    source_class: str = "in-diff-file",
    pointer_ref: str | None = None,
    interpretation_ref: str | None = None,
) -> SourceCapture:
    with open(path, "rb") as fh:
        data = fh.read()
    return SourceCapture(
        locator=locator,
        source_class=source_class,
        data=data,
        pointer_ref=pointer_ref,
        interpretation_ref=interpretation_ref,
    )


def verify_capture(record: dict, data: bytes) -> list[str]:
    """Recompute capture identity checks; returns list of failures."""
    failures: list[str] = []
    if record.get("byte_length") != len(data):
        failures.append(
            f"byte_length mismatch: recorded {record.get('byte_length')} actual {len(data)}"
        )
    actual_sha = raw_sha256(data)
    if record.get("sha256") != actual_sha:
        failures.append(
            f"sha256 mismatch: recorded {record.get('sha256')} actual {actual_sha}"
        )
    algorithm = record.get("blob_algorithm")
    if algorithm != BLOB_ALGORITHM:
        failures.append(f"unsupported blob_algorithm {algorithm!r}")
    else:
        actual_oid = synthetic_git_blob_oid(data)
        if record.get("blob_oid") != actual_oid:
            failures.append(
                f"blob_oid mismatch: recorded {record.get('blob_oid')} actual {actual_oid}"
            )
    locator = record.get("locator")
    if not isinstance(locator, str) or not locator:
        failures.append("locator missing")
    return failures


__all__ = [
    "BLOB_ALGORITHM",
    "SourceCapture",
    "capture_bytes",
    "capture_file",
    "make_source_ref",
    "percent_encode",
    "raw_sha256",
    "synthetic_git_blob_oid",
    "verify_capture",
]
