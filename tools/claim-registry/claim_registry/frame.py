"""Deterministic atomic-unit walker over the tree-sitter-markdown BLOCK grammar.

Implements the frame of ``cure-light-claim-registry-spec.md`` (sections 1.2-1.4):
atomic Markdown blocks with exact UTF-8 byte spans ``[start, end)``, a strict
byte partition, and pinned extraction recipes.

Strictness summary (README has the long form):

* Every emitted span begins at a physical line start and ends after its final
  line terminator (LF terminates a line; a preceding CR stays in the line's
  bytes) or at EOF.
* Block-quote prefixes and list indentation are absorbed into the child unit's
  span (start extended to the physical line start of the child's line).
* For a compound list item, the first child's span starts at the item marker.
* ``separator`` units exist only for whitespace-only gaps.  Gaps whose only
  non-whitespace bytes are block-quote marker lines (``>``-only lines) are
  attributed to the sibling unit inside the same ``block_quote``; any other
  non-whitespace gap raises :class:`ExtractionError` with byte offset + snippet.
* A tree containing ERROR/MISSING nodes raises :class:`ExtractionError`.
  An unclosed fence is valid CommonMark and therefore frames normally.

Determinism: parsing and collection are pure; identical source bytes and the
same walker script always produce identical units and unit ids.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
from dataclasses import dataclass
from typing import Iterable, Sequence

import tree_sitter_markdown as _tsm
from tree_sitter import Language, Parser

# --------------------------------------------------------------------------
# Grammar surface - pinned kinds
# --------------------------------------------------------------------------

#: Smallest self-contained block kinds inventoried as units.
LEAF_KINDS: frozenset[str] = frozenset(
    {
        "atx_heading",
        "setext_heading",
        "paragraph",
        "fenced_code_block",
        "indented_code_block",
        "html_block",
        "thematic_break",
        "link_reference_definition",
        # Extension beyond the spec's example list: the block grammar parses
        # front matter as opaque metadata nodes.  They are inventoried with
        # explicit kinds so no bytes are lost (documented in README).
        "minus_metadata",
        "plus_metadata",
    }
)

#: Pipe-table piece kinds - one unit per row-ish line.
ROW_KINDS: frozenset[str] = frozenset(
    {"pipe_table_header", "pipe_table_delimiter_row", "pipe_table_row"}
)

#: List/task markers are structural bytes inside the owning item unit.
MARKER_KINDS: frozenset[str] = frozenset(
    {
        "list_marker_minus",
        "list_marker_plus",
        "list_marker_star",
        "list_marker_dot",
        "list_marker_parenthesis",
        "task_list_marker_checked",
        "task_list_marker_unchecked",
    }
)

#: Kinds that may be emitted (all grammar leaf kinds plus the gap kind).
UNIT_KINDS: frozenset[str] = LEAF_KINDS | ROW_KINDS | {"separator"}

BOM = b"\xef\xbb\xbf"

WALKER_VERSION = "1"


def _pkg_version(name: str, fallback: str) -> str:
    try:
        return importlib.metadata.version(name)
    except Exception:  # pragma: no cover - defensive
        return fallback


PARSER_NAME = "tree-sitter-markdown"
PARSER_VERSION = _pkg_version("tree-sitter-markdown", "0.5.1")
RUNTIME_NAME = "tree-sitter"
RUNTIME_VERSION = _pkg_version("tree-sitter", "0.26.0")


class ExtractionError(Exception):
    """Fail-loud extraction failure with byte offset and snippet."""

    def __init__(self, message: str, src: bytes | None = None,
                 offset: int | None = None, end: int | None = None):
        self.message = message
        self.offset = offset
        self.end = end
        self.snippet = repr(src[offset:end][:80]) if (src is not None and offset is not None) else None
        where = "" if offset is None else f" at bytes [{offset},{end})"
        snip = "" if self.snippet is None else f" bytes={self.snippet}"
        super().__init__(f"{message}{where}{snip}")


# --------------------------------------------------------------------------
# Pinned recipe
# --------------------------------------------------------------------------

def script_sha256() -> str:
    """SHA-256 of the walker script bytes (this file).

    Inside a zipapp (``.pyz``) ``__file__`` is not a real path; fall back to
    the import loader's source, which is byte-identical to the built file.
    """
    try:
        with open(__file__, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError as exc:
        loader = globals().get("__loader__")
        get_source = getattr(loader, "get_source", None)
        source = None
        if get_source is not None:
            try:
                source = get_source(__name__)
            except (ImportError, OSError):
                source = None
        if source is None:
            raise ExtractionError(f"cannot hash walker script: {exc}") from exc
        return hashlib.sha256(source.encode("utf-8")).hexdigest()


def frame_recipe() -> dict:
    """Pinned frame recipe (parser, runtime, flags, script hash, kinds)."""
    return {
        "name": "claim-registry-frame",
        "version": WALKER_VERSION,
        "parser": PARSER_NAME,
        "parser_version": PARSER_VERSION,
        "runtime": RUNTIME_NAME,
        "runtime_version": RUNTIME_VERSION,
        "flags": [],
        "script_sha256": script_sha256(),
        "kinds": sorted(UNIT_KINDS),
    }


# --------------------------------------------------------------------------
# Units and frames
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Unit:
    """One atomic unit of a frame."""

    ordinal: int
    kind: str
    start: int
    end: int
    sha256: str
    ancestor_refs: tuple[str, ...] = ()

    @property
    def byte_length(self) -> int:
        return self.end - self.start

    def unit_id(self, source_ref: str) -> str:
        return f"{source_ref}:{self.start}-{self.end}:{self.sha256}"

    def record(self, source_ref: str) -> dict:
        return {
            "unit_id": self.unit_id(source_ref),
            "source_ref": source_ref,
            "ordinal": self.ordinal,
            "kind": self.kind,
            "start": self.start,
            "end": self.end,
            "sha256": self.sha256,
            "ancestor_refs": list(self.ancestor_refs),
        }


@dataclass(frozen=True)
class Frame:
    """A complete deterministic frame over one immutable source."""

    source_length: int
    units: tuple[Unit, ...]
    recipe: dict

    @property
    def unit_count(self) -> int:
        return len(self.units)

    @property
    def block_count(self) -> int:
        return sum(1 for u in self.units if u.kind != "separator")

    @property
    def separator_count(self) -> int:
        return sum(1 for u in self.units if u.kind == "separator")

    def covered_bytes(self) -> int:
        return sum(u.byte_length for u in self.units)


# --------------------------------------------------------------------------
# Internal span helpers
# --------------------------------------------------------------------------

def _line_start(src: bytes, pos: int) -> int:
    i = src.rfind(b"\n", 0, pos)
    return 0 if i < 0 else i + 1


def _snap_end(src: bytes, e: int) -> int:
    """Snap a content end to its line boundary.

    Keeps ``e`` when it already sits after a LF (or at EOF); otherwise trims
    back to the preceding LF when everything after it is indentation of the
    next line, else extends to the next LF (inclusive) or EOF.
    """
    if e == 0:
        return 0
    if src[e - 1:e] == b"\n":
        return e
    lf = src.rfind(b"\n", 0, e)
    if lf >= 0 and not src[lf + 1:e].strip(b" \t\r"):
        return lf + 1
    i = src.find(b"\n", e)
    return len(src) if i < 0 else i + 1


def _effective_end(src: bytes, node) -> int:
    """End of the node's own content, excluding trailing continuation bytes.

    tree-sitter attaches the *next* line's indentation or quote prefix to the
    preceding block as a ``block_continuation`` child (directly or through the
    tail-child chain).  Those bytes belong to the following unit's start line,
    so they are stripped before snapping to a line boundary.
    """
    e = node.end_byte
    cur = node
    while True:
        if cur.child_count == 0:
            return e
        last = cur.children[-1]
        if last.type == "block_continuation" and last.start_byte < e:
            if not src[last.end_byte:e].strip(b" \t\r\n"):
                return last.start_byte
        if last.end_byte == cur.end_byte and last.start_byte < last.end_byte:
            cur = last
            continue
        return e


def _lines_of(src: bytes, a: int, b: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    cur = a
    while cur < b:
        i = src.find(b"\n", cur)
        e = b if i < 0 else min(i + 1, b)
        out.append((cur, e))
        cur = e
    return out


def _is_marker_line(bs: bytes) -> bool:
    s = bs.strip(b" \t\r\n")
    return s != b"" and set(s) == {0x3E}  # only '>' bytes


def _is_ws(bs: bytes) -> bool:
    return bs.strip(b" \t\r\n") == b""


def _marker_suffix(src: bytes, a: int, b: int) -> int | None:
    """Start offset of the trailing run of marker-only lines, or None."""
    lines = _lines_of(src, a, b)
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        if _is_marker_line(src[lines[i][0]:lines[i][1]]):
            idx = i
            break
    if idx is None:
        return None
    for i in range(idx, len(lines)):
        seg = src[lines[i][0]:lines[i][1]]
        if not (_is_marker_line(seg) or _is_ws(seg)):
            return None
    return lines[idx][0]


def _marker_prefix_end(src: bytes, a: int, b: int) -> int | None:
    """End offset of the leading run of marker-only lines, or None."""
    lines = _lines_of(src, a, b)
    idx = None
    for i in range(len(lines)):
        if _is_marker_line(src[lines[i][0]:lines[i][1]]):
            idx = i
            break
    if idx is None:
        return None
    for i in range(0, idx + 1):
        seg = src[lines[i][0]:lines[i][1]]
        if not (_is_marker_line(seg) or _is_ws(seg)):
            return None
    return lines[idx][1]


# --------------------------------------------------------------------------
# Raw leaves and partition
# --------------------------------------------------------------------------

@dataclass
class RawLeaf:
    """A leaf block before gap attribution (exposed for tests)."""

    kind: str
    start: int
    end: int
    ancestor_spans: tuple[tuple[str, int, int], ...] = ()


def partition_units(src: bytes, leaves: Sequence[RawLeaf]) -> list[dict]:
    """Partition ``[0, len(src))`` into units and whitespace separators.

    Raises :class:`ExtractionError` on overlap, unattributable non-whitespace
    gap, or a tail that is not whitespace/marker-only.
    """
    ordered = sorted(leaves, key=lambda u: (u.start, u.end))
    for x, y in zip(ordered, ordered[1:]):
        if x.end > y.start:
            raise ExtractionError("overlapping leaf spans", src, y.start, x.end)

    units: list[dict] = []

    def emit_sep(a: int, b: int) -> None:
        if a < b:
            units.append({"kind": "separator", "start": a, "end": b,
                          "ancestor_spans": ()})

    cur = 0
    for leaf in ordered:
        start = leaf.start
        if start > cur:
            a, b = cur, start
            gap = src[a:b]
            if _is_ws(gap) or (
                a == 0 and src.startswith(BOM) and _is_ws(src[3:b])
            ):
                emit_sep(a, b)
                cur = b
            else:
                ms = _marker_suffix(src, a, b)
                if ms is not None:
                    emit_sep(a, ms)
                    cur = ms
                    start = ms
                else:
                    mp = _marker_prefix_end(src, a, b)
                    if mp is not None and units:
                        units[-1]["end"] = mp
                        if not _is_ws(src[mp:b]):
                            raise ExtractionError(
                                "non-whitespace gap after marker prefix", src, mp, b
                            )
                        emit_sep(mp, b)
                        cur = b
                    else:
                        raise ExtractionError(
                            "non-whitespace gap not attributable to container",
                            src, a, b,
                        )
        if start < cur:
            raise ExtractionError("adjusted leaf overlaps previous unit", src, start, cur)
        if start > cur:
            raise ExtractionError("internal partition gap", src, cur, start)
        units.append({
            "kind": leaf.kind,
            "start": start,
            "end": leaf.end,
            "ancestor_spans": leaf.ancestor_spans,
        })
        cur = leaf.end

    if cur < len(src):
        a, b = cur, len(src)
        gap = src[a:b]
        if _is_ws(gap):
            emit_sep(a, b)
        else:
            mp = _marker_prefix_end(src, a, b)
            if mp is not None and units:
                units[-1]["end"] = mp
                if not _is_ws(src[mp:b]):
                    raise ExtractionError(
                        "non-whitespace tail after marker prefix", src, mp, b
                    )
                emit_sep(mp, b)
            else:
                raise ExtractionError("non-whitespace tail", src, a, b)

    pos = 0
    for u in units:
        if u["start"] != pos:
            raise ExtractionError("partition discontinuity", src, pos, u["start"])
        pos = u["end"]
    if pos != len(src):
        raise ExtractionError("partition does not cover source", src, pos, len(src))
    return units


# --------------------------------------------------------------------------
# Block walker
# --------------------------------------------------------------------------

class _Walker:
    """Collects raw leaves from the block grammar in document order."""

    def __init__(self, src: bytes):
        self.src = src
        self.leaves: list[RawLeaf] = []

    # -- emission ---------------------------------------------------------

    def leaf(self, node, ctx: tuple[tuple[str, int, int], ...], *,
             kind: str | None = None, start_anchor: int | None = None) -> None:
        start = node.start_byte if start_anchor is None else min(start_anchor, node.start_byte)
        start = _line_start(self.src, start)
        end = _snap_end(self.src, _effective_end(self.src, node))
        self.leaves.append(
            RawLeaf(kind=kind or node.type, start=start, end=end, ancestor_spans=ctx)
        )

    # -- compound list items ---------------------------------------------

    def item(self, item, ctx: tuple[tuple[str, int, int], ...]) -> None:
        content = [
            c for c in item.children
            if c.type not in MARKER_KINDS and c.type != "block_continuation"
        ]
        if not content:
            # Empty list item (e.g. a bare "-" line): the item is its own
            # smallest block.
            self.leaf(item, ctx, kind="list_item")
            return
        if len(content) == 1 and content[0].type == "paragraph":
            # Simple item: marker + wrapped content = one unit.
            self.leaf(item, ctx, kind="list_item")
            return
        ctx2 = ctx + (("list_item", item.start_byte, item.end_byte),)
        first = True
        for c in content:
            if first:
                first_leaf = self.first_leaf(c)
                if first_leaf is None:
                    raise ExtractionError(
                        "compound list item first child has no leaf block",
                        self.src, item.start_byte, item.end_byte,
                    )
                self.leaf(first_leaf, ctx2, start_anchor=item.start_byte)
                first = False
            else:
                self.collect(c, ctx2)

    def first_leaf(self, node):
        if node.type in LEAF_KINDS:
            return node
        if node.type == "pipe_table":
            for c in node.children:
                if c.type in ROW_KINDS:
                    return c
        for c in node.children:
            found = self.first_leaf(c)
            if found is not None:
                return found
        return None

    # -- recursion --------------------------------------------------------

    def collect(self, node, ctx: tuple[tuple[str, int, int], ...]) -> None:
        t = node.type
        if t in ("document", "section"):
            for c in node.children:
                self.collect(c, ctx)
        elif t == "block_quote":
            child_ctx = ctx + (("block_quote", node.start_byte, node.end_byte),)
            for c in node.children:
                if c.type in ("block_quote_marker", "block_continuation"):
                    continue
                self.collect(c, child_ctx)
        elif t == "list":
            child_ctx = ctx + (("list", node.start_byte, node.end_byte),)
            for c in node.children:
                if c.type == "list_item":
                    self.item(c, child_ctx)
        elif t == "pipe_table":
            child_ctx = ctx + (("pipe_table", node.start_byte, node.end_byte),)
            for c in node.children:
                if c.type in ROW_KINDS:
                    self.leaf(c, child_ctx)
        elif t in LEAF_KINDS:
            self.leaf(node, ctx)
        elif t == "block_continuation":
            return
        else:
            if not node.children:
                raise ExtractionError(
                    f"unsupported empty block node type {t!r}",
                    self.src, node.start_byte, node.end_byte,
                )
            for c in node.children:
                self.collect(c, ctx)


def _check_parse_errors(src: bytes, root) -> None:
    errors: list[tuple[str, int, int]] = []

    def walk(n) -> None:
        if n.type == "ERROR" or getattr(n, "is_missing", False):
            errors.append((n.type, n.start_byte, n.end_byte))
        for c in n.children:
            walk(c)

    walk(root)
    if errors:
        kind, s, e = errors[0]
        raise ExtractionError(f"parse error node {kind}", src, s, e)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def frame_source(src: bytes) -> Frame:
    """Extract the deterministic atomic-unit frame over ``src`` verbatim."""
    parser = Parser(Language(_tsm.language()))
    tree = parser.parse(src)
    _check_parse_errors(src, tree.root_node)
    walker = _Walker(src)
    walker.collect(tree.root_node, ())
    drafts = partition_units(src, walker.leaves)
    units: list[Unit] = []
    for ordinal, d in enumerate(drafts):
        span = src[d["start"]:d["end"]]
        units.append(
            Unit(
                ordinal=ordinal,
                kind=d["kind"],
                start=d["start"],
                end=d["end"],
                sha256=hashlib.sha256(span).hexdigest(),
                ancestor_refs=tuple(
                    f"{kind}:{s}-{e}" for kind, s, e in d["ancestor_spans"]
                ),
            )
        )
    return Frame(source_length=len(src), units=tuple(units), recipe=frame_recipe())


def frame_file(path: str) -> Frame:
    with open(path, "rb") as fh:
        return frame_source(fh.read())


def span_is_line_aligned(src: bytes, unit: Unit) -> bool:
    """Validator helper: start is a physical line start, end after LF or EOF."""
    if unit.start != 0 and src[unit.start - 1:unit.start] != b"\n":
        return False
    return unit.end == len(src) or src[unit.end - 1:unit.end] == b"\n"
