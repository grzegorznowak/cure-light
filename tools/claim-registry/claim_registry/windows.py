"""Bounded ingestion windows (spec section 1.4).

Windows are LLM-ingestion views over the complete global frame - never
identity boundaries.  Recipe: positive ``max_units``, ``max_bytes`` and
``overlap_units < max_units``.  Starting at ordinal zero, take the longest
consecutive prefix satisfying both bounds; repeat from the tail overlap.  If
the requested overlap would prevent forward progress, reduce the actual
overlap until at least one new unit is admitted and record the actual value.
Stop once the last unit has been included; never emit an overlap-only terminal
window.  An atomic unit larger than ``max_bytes`` is never split: a named
:class:`OversizedUnitError` is raised instead.

Manifests list ``source_ref``, ordinal bounds, unit ids, the recipe hash and
context-only ids (empty for the pilot).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .canonical import canonical_hash
from .frame import Unit

WINDOW_VERSION = "1"


class WindowRecipeError(ValueError):
    """Invalid window recipe."""


class OversizedUnitError(WindowRecipeError):
    """An atomic unit exceeds ``max_bytes`` and must not be split."""

    def __init__(self, unit_id: str, unit_bytes: int, max_bytes: int):
        self.unit_id = unit_id
        self.unit_bytes = unit_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"oversized unit {unit_id}: {unit_bytes} bytes > max_bytes={max_bytes}; "
            "adjust the bounded budget explicitly, never split the unit"
        )


@dataclass(frozen=True)
class Window:
    window_id: str
    ordinal_start: int
    ordinal_end: int
    overlap_units: int
    unit_ids: tuple[str, ...]
    context_only_ids: tuple[str, ...] = ()

    def record(self) -> dict:
        return {
            "window_id": self.window_id,
            "ordinal_start": self.ordinal_start,
            "ordinal_end": self.ordinal_end,
            "overlap_units": self.overlap_units,
            "unit_ids": list(self.unit_ids),
            "context_only_ids": list(self.context_only_ids),
        }


def window_recipe(max_units: int, max_bytes: int, overlap_units: int) -> dict:
    if not isinstance(max_units, int) or isinstance(max_units, bool) or max_units < 1:
        raise WindowRecipeError("max_units must be a positive integer")
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 1:
        raise WindowRecipeError("max_bytes must be a positive integer")
    if not isinstance(overlap_units, int) or isinstance(overlap_units, bool):
        raise WindowRecipeError("overlap_units must be an integer")
    if overlap_units < 0:
        raise WindowRecipeError("overlap_units must be >= 0")
    if overlap_units >= max_units:
        raise WindowRecipeError("overlap_units must be < max_units")
    return {
        "version": WINDOW_VERSION,
        "max_units": max_units,
        "max_bytes": max_bytes,
        "overlap_units": overlap_units,
    }


def build_windows(
    source_ref: str,
    units: Sequence[Unit],
    max_units: int,
    max_bytes: int,
    overlap_units: int,
) -> dict:
    """Build the deterministic window manifest for one source."""
    recipe = window_recipe(max_units, max_bytes, overlap_units)
    unit_list = list(units)
    n = len(unit_list)
    for u in unit_list:
        if u.byte_length > max_bytes:
            raise OversizedUnitError(u.unit_id(source_ref), u.byte_length, max_bytes)

    windows: list[Window] = []
    start = 0
    prev_last: int | None = None
    while start < n:
        end = start
        count = 0
        size = 0
        while end < n and count < max_units and size + unit_list[end].byte_length <= max_bytes:
            size += unit_list[end].byte_length
            count += 1
            end += 1
        if count == 0:  # pragma: no cover - guarded by the oversized check
            raise OversizedUnitError(
                unit_list[start].unit_id(source_ref),
                unit_list[start].byte_length,
                max_bytes,
            )
        last = end - 1
        actual_overlap = 0 if prev_last is None else prev_last - start + 1
        windows.append(Window(
            window_id=f"{source_ref}:w{len(windows)}",
            ordinal_start=start,
            ordinal_end=last,
            overlap_units=actual_overlap,
            unit_ids=tuple(u.unit_id(source_ref) for u in unit_list[start:end]),
        ))
        if last == n - 1:
            break
        # choose the next window start from the tail overlap: prefer the
        # requested overlap, but reduce it until at least one NEW unit
        # (ordinal > last) is admitted under both caps.  Ordinal progress
        # alone is not enough - the overlap itself can consume the byte
        # budget and produce overlap-only windows.
        requested = min(overlap_units, last + 1)
        start = last + 1  # zero overlap always admits the next unit
        for candidate_overlap in range(requested, 0, -1):
            candidate = last - candidate_overlap + 1
            count = 0
            size = 0
            end_i = candidate
            while (
                end_i <= last + 1
                and count < max_units
                and size + unit_list[end_i].byte_length <= max_bytes
            ):
                size += unit_list[end_i].byte_length
                count += 1
                end_i += 1
            if end_i > last + 1:  # the candidate admits the new core unit
                start = candidate
                break
        prev_last = last

    manifest = {
        "schema_version": "window-manifest/1",
        "source_ref": source_ref,
        "recipe": recipe,
        "recipe_hash": canonical_hash(recipe),
        "windows": [w.record() for w in windows],
    }
    return manifest


def validate_windows(manifest: dict, units: Sequence[Unit], source_ref: str) -> list[str]:
    """Reconcile a window manifest against the frame; returns failures."""
    failures: list[str] = []
    if manifest.get("source_ref") != source_ref:
        failures.append(
            f"manifest source_ref {manifest.get('source_ref')!r} != {source_ref!r}"
        )
    recipe = manifest.get("recipe", {})
    try:
        expected_recipe = window_recipe(
            recipe.get("max_units"), recipe.get("max_bytes"), recipe.get("overlap_units")
        )
    except WindowRecipeError as exc:
        failures.append(f"invalid window recipe: {exc}")
        return failures
    if manifest.get("recipe_hash") != canonical_hash(expected_recipe):
        failures.append("window recipe_hash mismatch")
    by_id = {u.unit_id(source_ref): u for u in units}
    windows = manifest.get("windows", [])
    seen: set[str] = set()
    prev_end = None
    for i, w in enumerate(windows):
        ids = w.get("unit_ids", [])
        missing = [uid for uid in ids if uid not in by_id]
        if missing:
            failures.append(f"window[{i}] references unknown unit ids: {missing[:3]}")
            continue
        ordinals = [by_id[uid].ordinal for uid in ids]
        if ordinals != list(range(w.get("ordinal_start", -1),
                                   w.get("ordinal_start", -1) + len(ordinals))):
            failures.append(f"window[{i}] ordinal bounds do not match unit ids")
        if w.get("ordinal_end") != ordinals[-1]:
            failures.append(f"window[{i}] ordinal_end mismatch")
        if prev_end is not None and ordinals[0] > prev_end + 1:
            failures.append(f"window[{i}] leaves a coverage gap")
        if prev_end is None:
            if w.get("overlap_units") != 0:
                failures.append("first window must record zero overlap")
        if prev_end is not None:
            overlap = prev_end - ordinals[0] + 1
            if overlap != w.get("overlap_units"):
                failures.append(
                    f"window[{i}] recorded overlap {w.get('overlap_units')} but actual {overlap}"
                )
            if overlap >= len(ids):
                failures.append(f"window[{i}] is overlap-only (no new units)")
        prev_end = ordinals[-1]
        seen.update(ids)
    expected_all = {u.unit_id(source_ref) for u in units}
    if units and seen != expected_all:
        failures.append("window union does not reconcile with full frame")
    if units:
        if not windows or windows[0].get("ordinal_start") != 0:
            failures.append("first window does not start at ordinal 0")
        if windows and windows[-1].get("ordinal_end") != units[-1].ordinal:
            failures.append("last window does not include the final unit")
    return failures


__all__ = [
    "OversizedUnitError",
    "WINDOW_VERSION",
    "Window",
    "WindowRecipeError",
    "build_windows",
    "validate_windows",
    "window_recipe",
]
