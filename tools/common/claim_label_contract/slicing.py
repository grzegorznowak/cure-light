"""Deterministic slicing of a verified capture's global unit table.

The frame is computed exactly once per captured source; slices are bounded
views over that single unit table.  A worker payload never reparses Markdown,
never derives local ids, and carries each unit's exact UTF-8 text.

Recipe (``claim-registry-slice/1``, algorithm ``greedy-largest-core/1``):

* every source is sliced independently, in global ordinal order;
* each slice takes the *longest* new core prefix (units not yet in a core)
  admitted by ``max_bytes`` raw text and ``max_units`` including separators;
* the target is ``overlap_units`` immediately preceding units; the overlap is
  reduced (down to zero) whenever the larger overlap would leave no room for
  a new core unit under ``max_bytes``/``max_units``;
* the core is then trimmed from the right until the complete serialized
  worker payload fits ``max_input_bytes``;
* cores partition every source exactly once; a unit is primary-owned by the
  slice whose core contains it; overlap units are audit-only;
* an empty source has zero slices and no units;
* a unit larger than ``max_bytes``, a payload that cannot fit even one new
  core unit, an unverifiable seam (zero overlap left between two adjacent
  non-separator units) or exceeding ``max_slices`` is a named failure - never
  a split unit, a partial success or a silently enlarged budget.

Slice ids are content ids over ``source_ref`` + recipe hashes + the ordered
core/overlap/context ids, so they never depend on payload bytes, file paths or
arrival order.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from toolkit import canonical_json as cj

SLICE_RECIPE_VERSION = "claim-registry-slice/1"
SLICE_ALGORITHM = "greedy-largest-core/1"
FRAME_SLICE_INPUT_VERSION = "frame-slice-input/1"

DEFAULT_MAX_BYTES = 16384
DEFAULT_MAX_UNITS = 80
DEFAULT_MAX_INPUT_BYTES = 65536
DEFAULT_OVERLAP_UNITS = 4
DEFAULT_MAX_SLICES = 32

INSTRUCTIONS_VERSION = "claim-registry-slice-instructions/1"
INSTRUCTIONS = (
    "You are labeling exactly ONE bounded slice of ONE immutable Markdown "
    "source. Every unit id is global and permanent; every unit carries its "
    "exact UTF-8 text. Units with kind \"separator\" are mechanical: they are "
    "never labeled, never primary-owned, and never part of any claim.\n"
    "\n"
    "Return ONE canonical claim-json/1 document, schema slice-proposals/1, "
    "with exactly these fields: schema_version, slice_id, input_sha256, "
    "assignments, overlap_votes, grouping_votes, boundary.\n"
    "\n"
    "assignments: primary ownership for ONLY the non-separator unit ids in "
    "core_ids, each core non-separator exactly once. A claim assignment lists "
    "one or more consecutive whole core units and must lie entirely inside "
    "this slice's core; a nonclaim assignment carries label (context, "
    "advisory, example, baseline), a non-empty rationale and a non-empty "
    "role_ref. Claims and nonclaims must not overlap.\n"
    "\n"
    "overlap_votes: exactly one vote per non-separator unit in overlap_ids, "
    "mirroring the owner's state/label/role (label and role_ref are null for "
    "claim). Differences in rationale are reported as warnings.\n"
    "\n"
    "grouping_votes: exactly one vote per mechanically visible adjacent "
    "non-separator pair in ordinal order (left_unit_id, right_unit_id, "
    "grouping in {same, separate, uncertain}, rationale). grouping=same only "
    "when both units belong to one semantic group; every claim's internal "
    "adjacencies must vote same and every claim boundary must vote separate.\n"
    "\n"
    "boundary.left / boundary.right: clear, spanning or uncertain. Use "
    "spanning when a claim or group crosses the slice core's left/right edge "
    "and uncertain when that cannot be decided; both stop reconciliation "
    "rather than being repaired. Do not invent unit ids: context is visible "
    "only through overlap_ids."
)


class SliceRecipeError(ValueError):
    """Invalid slice recipe/bounds -> usage failure (exit 2)."""


class SlicePlanError(ValueError):
    """Named slicing failure -> semantic failure (exit 1)."""


class OversizedUnitError(SlicePlanError):
    def __init__(self, unit_id: str, unit_bytes: int, max_bytes: int):
        self.unit_id = unit_id
        self.unit_bytes = unit_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"oversized unit {unit_id}: {unit_bytes} bytes > max_bytes={max_bytes}; "
            "adjust the bounded budget explicitly, never split the unit"
        )


class InvalidTextError(SlicePlanError):
    def __init__(self, unit_id: str, exc: UnicodeDecodeError):
        super().__init__(
            f"unit {unit_id} is not valid UTF-8 and cannot be transported: {exc}"
        )


class UnverifiedSeamError(SlicePlanError):
    def __init__(self, left_unit_id: str, right_unit_id: str):
        self.left_unit_id = left_unit_id
        self.right_unit_id = right_unit_id
        super().__init__(
            f"unverified seam between adjacent non-separator units "
            f"{left_unit_id} and {right_unit_id}: overlap was reduced to zero, "
            "so no slice can audit whether a claim crosses the boundary; "
            "raise the budget or stop"
        )


class SliceBudgetError(SlicePlanError):
    pass


def instructions_bytes() -> bytes:
    return INSTRUCTIONS.encode("utf-8")


def instructions_sha256() -> str:
    return hashlib.sha256(instructions_bytes()).hexdigest()


def slice_recipe(
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_units: int = DEFAULT_MAX_UNITS,
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES,
    overlap_units: int = DEFAULT_OVERLAP_UNITS,
    max_slices: int = DEFAULT_MAX_SLICES,
) -> dict:
    """Validate and freeze a slice recipe document."""
    limits = {
        "max_bytes": max_bytes,
        "max_units": max_units,
        "max_input_bytes": max_input_bytes,
        "overlap_units": overlap_units,
        "max_slices": max_slices,
    }
    for name, value in limits.items():
        if not isinstance(value, int) or isinstance(value, bool):
            raise SliceRecipeError(f"{name} must be an integer")
    for name in ("max_bytes", "max_units", "max_input_bytes", "max_slices"):
        if limits[name] < 1:
            raise SliceRecipeError(f"{name} must be >= 1")
    if overlap_units < 0:
        raise SliceRecipeError("overlap_units must be >= 0")
    if overlap_units >= max_units:
        raise SliceRecipeError("overlap_units must be < max_units")
    return {
        "version": SLICE_RECIPE_VERSION,
        "algorithm": SLICE_ALGORITHM,
        "max_bytes": max_bytes,
        "max_units": max_units,
        "max_input_bytes": max_input_bytes,
        "overlap_units": overlap_units,
        "max_slices": max_slices,
        "instructions_version": INSTRUCTIONS_VERSION,
        "instructions_sha256": instructions_sha256(),
    }


def validate_recipe_document(recipe: Mapping) -> None:
    """Re-validate a recipe document parsed from a manifest/argument."""
    if not isinstance(recipe, Mapping):
        raise SliceRecipeError("slice recipe must be an object")
    expected = slice_recipe(
        max_bytes=recipe.get("max_bytes"),
        max_units=recipe.get("max_units"),
        max_input_bytes=recipe.get("max_input_bytes"),
        overlap_units=recipe.get("overlap_units"),
        max_slices=recipe.get("max_slices"),
    )
    if (recipe.get("version") != SLICE_RECIPE_VERSION
            or recipe.get("algorithm") != SLICE_ALGORITHM):
        raise SliceRecipeError("unsupported slice recipe version/algorithm")
    if recipe.get("instructions_version") != INSTRUCTIONS_VERSION:
        raise SliceRecipeError("unsupported pinned instructions version")
    if recipe.get("instructions_sha256") != instructions_sha256():
        raise SliceRecipeError(
            "instructions_sha256 does not match the pinned instruction bytes"
        )
    extra = set(recipe) - set(expected)
    if extra:
        raise SliceRecipeError(f"unknown slice recipe keys: {sorted(extra)}")
    if cj.canonical_dumps(dict(recipe)) != cj.canonical_dumps(expected):
        raise SliceRecipeError("slice recipe does not match the pinned values")


def compute_slice_id(
    source_ref: str,
    frame_recipe_hash: str,
    slice_recipe_hash: str,
    core_ids: Sequence[str],
    overlap_ids: Sequence[str],
    context_only_ids: Sequence[str],
) -> str:
    """Object id of one slice: source + recipe hashes + ordered unit ids."""
    value = {
        "source_ref": source_ref,
        "frame_recipe_hash": frame_recipe_hash,
        "slice_recipe_hash": slice_recipe_hash,
        "core_ids": list(core_ids),
        "overlap_ids": list(overlap_ids),
        "context_only_ids": list(context_only_ids),
    }
    return "sha256:" + hashlib.sha256(cj.canonical_dumps(value)).hexdigest()


@dataclass(frozen=True)
class SlicePlan:
    slice_id: str
    source_ref: str
    core_ids: tuple[str, ...]
    overlap_ids: tuple[str, ...]
    context_only_ids: tuple[str, ...]
    payload: dict
    payload_bytes: bytes
    #: Ordinal of the first core unit (stable merged ordering key).
    first_ordinal: int


def _visible_records(records, texts, overlap_ids, core_ids, context_only_ids):
    wanted = list(overlap_ids) + list(core_ids) + list(context_only_ids)
    index = {r["unit_id"]: (r, t) for r, t in zip(records, texts)}
    units = []
    for uid in wanted:
        record, text = index[uid]
        units.append({**record, "text": text})
    return units


def plan_slices(
    source_ref: str,
    frame_recipe_hash: str,
    recipe: Mapping,
    unit_records: Sequence[Mapping],
    data: bytes,
    *,
    verify_spans: bool = False,
) -> list[SlicePlan]:
    """Plan the deterministic slice partition for one verified source."""
    validate_recipe_document(recipe)
    slice_recipe_hash = cj.canonical_hash(dict(recipe))
    records = [dict(r) for r in unit_records]
    for i, record in enumerate(records):
        if record.get("ordinal") != i:
            raise SlicePlanError(
                f"unit records must be ordinal-contiguous from 0; record {i} has "
                f"ordinal {record.get('ordinal')!r}"
            )
        if record.get("source_ref") != source_ref:
            raise SlicePlanError(
                f"unit {record.get('unit_id')!r} belongs to source "
                f"{record.get('source_ref')!r}, not {source_ref!r}"
            )

    texts: list[str] = []
    lengths: list[int] = []
    for record in records:
        start, end = record["start"], record["end"]
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start <= end <= len(data)):
            raise SlicePlanError(
                f"unit {record['unit_id']} has invalid span [{start},{end}) "
                f"for {len(data)} captured bytes"
            )
        span = data[start:end]
        if verify_spans and hashlib.sha256(span).hexdigest() != record.get("sha256"):
            raise SlicePlanError(
                f"unit {record['unit_id']} span sha256 does not match the capture"
            )
        if len(span) > recipe["max_bytes"]:
            raise OversizedUnitError(record["unit_id"], len(span), recipe["max_bytes"])
        try:
            texts.append(span.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise InvalidTextError(record["unit_id"], exc) from exc
        lengths.append(len(span))

    def build_payload(o_start: int, pos: int, end: int) -> dict:
        overlap_ids = tuple(r["unit_id"] for r in records[o_start:pos])
        core_ids = tuple(r["unit_id"] for r in records[pos:end])
        units = _visible_records(records, texts, overlap_ids, core_ids, ())
        payload = {
            "schema_version": FRAME_SLICE_INPUT_VERSION,
            "slice_id": None,  # filled after ids are known (id excludes payload)
            "source_ref": source_ref,
            "frame_recipe_hash": frame_recipe_hash,
            "slice_recipe_hash": slice_recipe_hash,
            "instructions": {"version": INSTRUCTIONS_VERSION, "text": INSTRUCTIONS},
            "units": units,
            "core_ids": list(core_ids),
            "overlap_ids": list(overlap_ids),
            "context_only_ids": [],
        }
        return payload

    n = len(records)
    plans: list[SlicePlan] = []
    pos = 0
    while pos < n:
        target = min(recipe["overlap_units"], pos)
        chosen: tuple[int, int, dict] | None = None
        for overlap in range(target, -1, -1):
            o_start = pos - overlap
            total_units = overlap
            total_bytes = sum(lengths[o_start:pos])
            end = pos
            while (
                end < n
                and total_units + 1 <= recipe["max_units"]
                and total_bytes + lengths[end] <= recipe["max_bytes"]
            ):
                total_bytes += lengths[end]
                total_units += 1
                end += 1
            # Trim the core from the right until the complete serialized
            # payload fits max_input_bytes (>=1 new core unit required).
            while end > pos:
                payload = build_payload(o_start, pos, end)
                core_ids = tuple(r["unit_id"] for r in records[pos:end])
                overlap_ids = tuple(r["unit_id"] for r in records[o_start:pos])
                slice_id = compute_slice_id(
                    source_ref, frame_recipe_hash, slice_recipe_hash,
                    core_ids, overlap_ids, (),
                )
                payload["slice_id"] = slice_id
                payload_bytes = cj.canonical_dumps(payload)
                if len(payload_bytes) <= recipe["max_input_bytes"]:
                    chosen = (o_start, end, {
                        "slice_id": slice_id,
                        "core_ids": core_ids,
                        "overlap_ids": overlap_ids,
                        "payload": payload,
                        "payload_bytes": payload_bytes,
                    })
                    break
                end -= 1
            if chosen is not None:
                break
        if chosen is None:
            record = records[pos]
            raise SliceBudgetError(
                f"unit {record['unit_id']} cannot fit max_input_bytes="
                f"{recipe['max_input_bytes']} even as a single new core unit; "
                "raise the budget explicitly or stop"
            )
        o_start, end, built = chosen
        left = records[pos - 1] if pos > 0 else None
        right = records[pos]
        if (not built["overlap_ids"] and left is not None
                and left["kind"] != "separator" and right["kind"] != "separator"):
            raise UnverifiedSeamError(left["unit_id"], right["unit_id"])
        plans.append(SlicePlan(
            slice_id=built["slice_id"],
            source_ref=source_ref,
            core_ids=built["core_ids"],
            overlap_ids=built["overlap_ids"],
            context_only_ids=(),
            payload=built["payload"],
            payload_bytes=built["payload_bytes"],
            first_ordinal=pos,
        ))
        pos = end
    if len(plans) > recipe["max_slices"]:
        first = plans[recipe["max_slices"]]
        raise SliceBudgetError(
            f"slice budget exceeded: {len(plans)} slices > max_slices="
            f"{recipe['max_slices']} (first over-budget slice {first.slice_id}); "
            "raise the budget explicitly, never label partially"
        )
    return plans


def expected_visible_pairs(records: Mapping[str, Mapping], visible_ids: Sequence[str]) -> list[tuple[str, str]]:
    """Mechanically enumerate adjacent non-separator pairs in visible order."""
    pairs = []
    for left, right in zip(visible_ids, visible_ids[1:]):
        if records[left]["kind"] == "separator" or records[right]["kind"] == "separator":
            continue
        pairs.append((left, right))
    return pairs


__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_INPUT_BYTES",
    "DEFAULT_MAX_SLICES",
    "DEFAULT_MAX_UNITS",
    "DEFAULT_OVERLAP_UNITS",
    "FRAME_SLICE_INPUT_VERSION",
    "INSTRUCTIONS",
    "INSTRUCTIONS_VERSION",
    "InvalidTextError",
    "OversizedUnitError",
    "SLICE_ALGORITHM",
    "SLICE_RECIPE_VERSION",
    "SliceBudgetError",
    "SlicePlan",
    "SlicePlanError",
    "SliceRecipeError",
    "UnverifiedSeamError",
    "compute_slice_id",
    "expected_visible_pairs",
    "instructions_bytes",
    "instructions_sha256",
    "plan_slices",
    "slice_recipe",
    "validate_recipe_document",
]
