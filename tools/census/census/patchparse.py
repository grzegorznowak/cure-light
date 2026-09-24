"""Path-safe parser for the pinned ``-U0`` diff patch stream.

The stream is parsed as raw bytes; paths are decoded as UTF-8 (non-UTF-8 paths
fail loud rather than being silently mangled).  A *record* is one
``diff --git`` block; an *edit block* is one ``@@`` hunk.  ``PatchRecord.sha256``
covers the record from its ``diff --git`` header through its last hunk line
(whole record when it carries no hunk) — the parent-content witness.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

HEADER = b"diff --git "

_HUNK_RE = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchParseError(ValueError):
    """Malformed patch stream (surfaced as a partition/extraction failure)."""


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    old_lines: int  # '-' body lines actually observed
    new_lines: int  # '+' body lines actually observed


@dataclass
class PatchRecord:
    header_line: bytes
    header_candidates: tuple[str, ...]
    old_token: str | None
    new_token: str | None
    missing_old: bool
    missing_new: bool
    kind: str  # "add" | "delete" | "modify"
    is_binary: bool
    old_mode: str | None
    new_mode: str | None
    hunks: list[Hunk] = field(default_factory=list)
    sha256: str = ""


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PatchParseError(f"path is not valid UTF-8: {raw[:80]!r}") from exc


def _ascii(raw: bytes) -> str:
    return raw.strip().decode("ascii", "strict")


def _clean_path_token(raw: bytes) -> bytes:
    tok = raw.rstrip(b"\r\n")
    if tok.endswith(b"\t"):
        tok = tok[:-1]
    if tok.startswith(b'"'):
        value, _rest = _read_cquoted(tok)
        return value
    return tok


def _read_cquoted(data: bytes) -> tuple[bytes, bytes]:
    """Decode a leading C-quoted byte string; return (unquoted, rest)."""
    if not data.startswith(b'"'):
        raise PatchParseError(f"expected quoted path token: {data[:80]!r}")
    out = bytearray()
    i = 1
    while i < len(data):
        ch = data[i : i + 1]
        if ch == b'"':
            return bytes(out), data[i + 1 :]
        if ch == b"\\":
            i += 1
            if i >= len(data):
                break
            esc = data[i : i + 1]
            simple = {
                b"a": 0x07,
                b"b": 0x08,
                b"f": 0x0C,
                b"n": 0x0A,
                b"r": 0x0D,
                b"t": 0x09,
                b"v": 0x0B,
                b"\\": 0x5C,
                b'"': 0x22,
            }
            if esc in simple:
                out.append(simple[esc])
            elif esc.isdigit():
                digits = data[i : i + 3]
                value = 0
                n = 0
                for d in digits:
                    if not (48 <= d <= 55):
                        break
                    value = value * 8 + (d - 48)
                    n += 1
                if n == 0:
                    raise PatchParseError(f"bad octal escape in path: {data[:80]!r}")
                out.append(value & 0xFF)
                i += n - 1
            else:
                raise PatchParseError(f"bad escape in quoted path: {data[:80]!r}")
        else:
            out.extend(ch)
        i += 1
    raise PatchParseError(f"unterminated quoted path: {data[:80]!r}")


def _strip_a_b(raw: bytes) -> bytes:
    if raw.startswith(b"a/") or raw.startswith(b"b/"):
        return raw[2:]
    return raw


def _header_candidates(line: bytes) -> list[str]:
    payload = line[len(HEADER) :]
    out: list[str] = []
    if payload.startswith(b'"'):
        try:
            first, rest = _read_cquoted(payload)
            rest = rest.lstrip()
            if not rest.startswith(b'"'):
                return []
            second, _ = _read_cquoted(rest)
        except PatchParseError:
            return []
        if first == second:
            out.append(_decode(_strip_a_b(first)))
        return out
    for i in range(len(payload) - 2):
        if payload[i : i + 3] != b" b/":
            continue
        left, right = payload[:i], payload[i + 1 :]
        if left.startswith(b"a/") and right.startswith(b"b/") and left[2:] == right[2:]:
            out.append(_decode(left[2:]))
    return out


def _split_lines(data: bytes, start: int, end: int) -> list[tuple[int, int, bytes]]:
    lines: list[tuple[int, int, bytes]] = []
    i = start
    while i < end:
        j = data.find(b"\n", i, end)
        if j == -1:
            lines.append((i, end, data[i:end]))
            break
        lines.append((i, j + 1, data[i:j]))
        i = j + 1
    return lines


def _parse_record(data: bytes, start: int, end: int) -> PatchRecord:
    lines = _split_lines(data, start, end)
    header_line = lines[0][2]
    if not header_line.startswith(HEADER):
        raise PatchParseError(f"record does not start with a diff header: {header_line[:80]!r}")

    old_token: str | None = None
    new_token: str | None = None
    missing_old = missing_new = False
    kind: str | None = None
    old_mode: str | None = None
    new_mode: str | None = None
    is_binary = False
    hunks: list[Hunk] = []
    last_hunk_end = lines[0][1]

    i = 1
    while i < len(lines):
        _ls, le, line = lines[i]
        if line.startswith(b"old mode "):
            old_mode = _ascii(line[len(b"old mode ") :])
        elif line.startswith(b"new mode "):
            new_mode = _ascii(line[len(b"new mode ") :])
        elif line.startswith(b"new file mode "):
            kind = "add"
            new_mode = _ascii(line[len(b"new file mode ") :])
        elif line.startswith(b"deleted file mode "):
            kind = "delete"
            old_mode = _ascii(line[len(b"deleted file mode ") :])
        elif line.startswith(b"index "):
            fields = line[len(b"index ") :].split(b" ")
            if b".." not in fields[0]:
                raise PatchParseError(f"malformed index line: {line[:80]!r}")
            if len(fields) > 1:
                mode = _ascii(fields[1])
                if kind is None:
                    old_mode = old_mode or mode
                    new_mode = new_mode or mode
        elif line.startswith(b"Binary files "):
            is_binary = True
        elif line.startswith(b"--- "):
            tok = _clean_path_token(line[len(b"--- ") :])
            if tok == b"/dev/null":
                missing_old = True
            else:
                old_token = _decode(_strip_a_b(tok))
        elif line.startswith(b"+++ "):
            tok = _clean_path_token(line[len(b"+++ ") :])
            if tok == b"/dev/null":
                missing_new = True
            else:
                new_token = _decode(_strip_a_b(tok))
        elif line.startswith(b"@@"):
            match = _HUNK_RE.match(line)
            if match is None:
                raise PatchParseError(f"malformed hunk header: {line[:120]!r}")
            old_start = int(match.group(1))
            old_count = int(match.group(2) or b"1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or b"1")
            old_lines = new_lines = 0
            j = i + 1
            hunk_end = le
            while j < len(lines):
                body = lines[j][2]
                if body.startswith(b"-"):
                    old_lines += 1
                elif body.startswith(b"+"):
                    new_lines += 1
                elif body.startswith(b"\\"):
                    pass
                else:
                    break
                hunk_end = lines[j][1]
                j += 1
            hunks.append(
                Hunk(old_start, old_count, new_start, new_count, old_lines, new_lines)
            )
            last_hunk_end = hunk_end
            i = j
            continue
        i += 1

    if kind is None:
        kind = "modify"
    span_end = last_hunk_end if hunks else lines[-1][1]
    return PatchRecord(
        header_line=header_line,
        header_candidates=tuple(_header_candidates(header_line)),
        old_token=old_token,
        new_token=new_token,
        missing_old=missing_old,
        missing_new=missing_new,
        kind=kind,
        is_binary=is_binary,
        old_mode=old_mode,
        new_mode=new_mode,
        hunks=hunks,
        sha256=hashlib.sha256(data[start:span_end]).hexdigest(),
    )


def parse_patch(data: bytes) -> list[PatchRecord]:
    """Split a ``-U0`` patch stream into records (order preserved)."""
    starts = [m.start() for m in re.finditer(rb"(?m)^diff --git ", data)]
    if data and not starts:
        raise PatchParseError(
            "patch stream is non-empty but contains no 'diff --git' record"
        )
    records: list[PatchRecord] = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(data)
        records.append(_parse_record(data, start, end))
    return records
