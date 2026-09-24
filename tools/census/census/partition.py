"""Independent partition checker for a census payload.

All checks are pure functions over already-parsed records: patch stream vs the
``--name-status -z`` inventory, ``--numstat -z`` line totals, parent/event file
references, hunk bounds/disjointness, coverage, and count consistency.  Each
check is emitted as ``{"id", "ok", "detail"}``; ``partition.ok`` is all-true.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

METADATA_MODES = ("120000", "160000")

STATUSES = ("A", "D", "M", "T")


def unique_changed_lines(parents: Sequence[Mapping[str, Any]]) -> dict:
    """Distinct touched line numbers per side (union across parents, summed per file)."""
    old_sets: dict[tuple, set] = defaultdict(set)
    new_sets: dict[tuple, set] = defaultdict(set)
    for parent in parents:
        key = (parent["old_path"], parent["new_path"])
        if parent["old_count"]:
            old_sets[key].update(
                range(parent["old_start"], parent["old_start"] + parent["old_count"])
            )
        if parent["new_count"]:
            new_sets[key].update(
                range(parent["new_start"], parent["new_start"] + parent["new_count"])
            )
    return {
        "old": sum(len(lines) for lines in old_sets.values()),
        "new": sum(len(lines) for lines in new_sets.values()),
    }


def _is_metadata(file: Mapping[str, Any]) -> bool:
    return file["old_mode"] in METADATA_MODES or file["new_mode"] in METADATA_MODES


def _file_key(file: Mapping[str, Any]) -> tuple:
    return (file["old_path"], file["new_path"])


def check_partition(
    *,
    files: Sequence[Mapping[str, Any]],
    parents: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    counts: Mapping[str, Any],
    inventory: Mapping[str, str],
    numstat: Mapping[str, Mapping[str, Any]],
    extraction_errors: Sequence[str],
    patch_errors: Sequence[str],
    hunk_errors: Sequence[str],
    blob_lines: Mapping[str, int],
) -> dict:
    checks: list[dict] = []

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "detail": detail})

    add(
        "extraction",
        not extraction_errors,
        "; ".join(extraction_errors) if extraction_errors else "no extraction errors",
    )
    add(
        "patch_inventory",
        not patch_errors,
        "; ".join(patch_errors)
        if patch_errors
        else "patch records reconcile with --name-status -z (order-independent)",
    )

    inv_paths = set(inventory)
    ns_paths = set(numstat)
    missing_ns = sorted(inv_paths - ns_paths)
    extra_ns = sorted(ns_paths - inv_paths)
    add(
        "numstat_inventory",
        not (missing_ns or extra_ns),
        (
            f"numstat missing {missing_ns}; numstat extra {extra_ns}"
            if (missing_ns or extra_ns)
            else "numstat paths match the name-status inventory exactly once each"
        ),
    )

    file_by_key = {_file_key(f): f for f in files}
    parents_by_key: dict[tuple, list] = defaultdict(list)
    for parent in parents:
        parents_by_key[(parent["old_path"], parent["new_path"])].append(parent)
    events_by_key: dict[tuple, list] = defaultdict(list)
    for event in events:
        events_by_key[(event["old_path"], event["new_path"])].append(event)

    # 1. numstat line totals per file and global.
    problems: list[str] = []
    exempt: list[str] = []
    text_old = text_new = ns_old = ns_new = 0
    for file in files:
        key = _file_key(file)
        path = file["new_path"] or file["old_path"]
        entry = numstat.get(path)
        if entry is None:
            continue
        parent_sum_old = sum(p["old_count"] for p in parents_by_key.get(key, []))
        parent_sum_new = sum(p["new_count"] for p in parents_by_key.get(key, []))
        file_events = {e["kind"] for e in events_by_key.get(key, [])}
        binary = entry.get("added") is None or entry.get("deleted") is None
        if binary or _is_metadata(file):
            if parent_sum_old or parent_sum_new:
                problems.append(
                    f"{path}: event-accounted file has line parents "
                    f"(old={parent_sum_old}, new={parent_sum_new})"
                )
            if not (file_events & {"binary", "submodule", "symlink"}):
                problems.append(
                    f"{path}: numeric/exempt numstat is not claimed by a "
                    f"binary/submodule/symlink event (events={sorted(file_events)})"
                )
            exempt.append(path)
            continue
        if parent_sum_old != entry["deleted"] or parent_sum_new != entry["added"]:
            problems.append(
                f"{path}: parents sum old={parent_sum_old} new={parent_sum_new} "
                f"!= numstat deleted={entry['deleted']} added={entry['added']}"
            )
        text_old += parent_sum_old
        text_new += parent_sum_new
        ns_old += entry["deleted"]
        ns_new += entry["added"]
    if text_old != ns_old or text_new != ns_new:
        problems.append(
            f"global line-accounted totals parents old={text_old} new={text_new} "
            f"!= numstat deleted={ns_old} added={ns_new}"
        )
    add(
        "numstat_counts",
        not problems,
        "; ".join(problems)
        if problems
        else (
            f"{len(files) - len(exempt)} line-accounted files match numstat "
            f"(global old={text_old}, new={text_new}); event-accounted "
            f"exemptions={sorted(exempt)}"
        ),
    )

    # 2. every parent/event maps to a known file pair; every file is covered.
    orphan_parents = sorted(
        {repr(key) for key in parents_by_key if key not in file_by_key}
    )
    add(
        "parent_refs",
        not orphan_parents,
        f"orphan parents: {orphan_parents}" if orphan_parents else "all parents map to file records",
    )
    orphan_events = sorted(
        {repr(key) for key in events_by_key if key not in file_by_key}
    )
    add(
        "event_refs",
        not orphan_events,
        f"orphan events: {orphan_events}" if orphan_events else "all events map to file records",
    )
    uncovered = sorted(
        repr(key)
        for key in file_by_key
        if key not in parents_by_key and key not in events_by_key
    )
    add(
        "file_coverage",
        not uncovered,
        f"files with neither parent nor event: {uncovered}"
        if uncovered
        else "every file has at least one parent or event",
    )

    # 3. hunk headers vs observed body line counts.
    add(
        "hunk_headers",
        not hunk_errors,
        "; ".join(hunk_errors) if hunk_errors else "hunk headers match observed body lines",
    )

    # 4. per file+side hunk ranges disjoint and within blob line counts.
    bounds: list[str] = []
    ranges: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
    for parent in parents:
        key = (parent["old_path"], parent["new_path"])
        file = file_by_key.get(key)
        for side, start_key, count_key, blob_key in (
            ("old", "old_start", "old_count", "old_blob"),
            ("new", "new_start", "new_count", "new_blob"),
        ):
            count = parent[count_key]
            if not count:
                continue
            oid = file.get(blob_key) if file else None
            line_count = blob_lines.get(oid) if oid else None
            if line_count is None:
                bounds.append(f"{key} {side}: no blob line count for {oid!r}")
            else:
                start = parent[start_key]
                if start < 1 or start + count - 1 > line_count:
                    bounds.append(
                        f"{key} {side}: range {start},{count} outside blob "
                        f"line count {line_count}"
                    )
            ranges[(key, side)].append((parent[start_key], count))
    overlaps: list[str] = []
    for (key, side), items in ranges.items():
        items.sort()
        prev_end = None
        for start, count in items:
            if prev_end is not None and start <= prev_end:
                overlaps.append(f"{key} {side}: overlapping ranges at line {start}")
            prev_end = start + count - 1
    add(
        "hunk_bounds",
        not (bounds or overlaps),
        "; ".join(bounds + overlaps)
        if (bounds or overlaps)
        else "per file+side hunk ranges are disjoint and within blob line counts",
    )

    # 5. counts recomputation.
    recomputed = {
        "files": len(files),
        "parents": len(parents),
        "events": len(events),
        "unique_changed_lines": unique_changed_lines(parents),
        "by_status": {
            status: sum(1 for f in files if f["status"] == status)
            for status in STATUSES
        },
    }
    add(
        "counts_consistent",
        recomputed == dict(counts),
        (
            "counts match records"
            if recomputed == dict(counts)
            else f"counts mismatch: recomputed {recomputed} vs declared {dict(counts)}"
        ),
    )

    errors = [f"{c['id']}: {c['detail']}" for c in checks if not c["ok"]]
    return {
        "ok": not errors,
        "checks": checks,
        "errors": errors,
    }
