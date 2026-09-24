"""Unit tests for the partition checker: failures must be loud and named."""

from __future__ import annotations

from census.partition import check_partition


def file_rec(path="f.txt", status="M", old_blob="aa", new_blob="bb"):
    return {
        "old_path": path if status != "A" else None,
        "new_path": path if status != "D" else None,
        "status": status,
        "old_blob": old_blob,
        "new_blob": new_blob,
        "old_mode": "100644",
        "new_mode": "100644",
    }


def parent_rec(path="f.txt", old_start=1, old_count=1, new_start=1, new_count=1):
    return {
        "parent_id": f"p:{old_start}:{old_count}:{new_start}:{new_count}",
        "old_path": path,
        "new_path": path,
        "kind": "lines",
        "old_start": old_start,
        "old_count": old_count,
        "new_start": new_start,
        "new_count": new_count,
        "patch_sha256": "a" * 64,
    }


def counts(parents=1):
    return {
        "files": 1,
        "parents": parents,
        "events": 0,
        "unique_changed_lines": {"old": 1, "new": 1},
        "by_status": {"A": 0, "D": 0, "M": 1, "T": 0},
    }


def run(**overrides):
    kwargs = dict(
        files=[file_rec()],
        parents=[parent_rec()],
        events=[],
        counts=counts(),
        inventory={"f.txt": "M"},
        numstat={"f.txt": {"added": 1, "deleted": 1}},
        extraction_errors=[],
        patch_errors=[],
        hunk_errors=[],
        blob_lines={"aa": 10, "bb": 10},
    )
    kwargs.update(overrides)
    return check_partition(**kwargs)


def status_of(partition, check_id):
    return next(c["ok"] for c in partition["checks"] if c["id"] == check_id)


def test_good_payload_ok():
    partition = run()
    assert partition["ok"] is True
    assert partition["errors"] == []
    assert all(c["ok"] for c in partition["checks"])


def test_duplicate_parent_range_fails_loud():
    partition = run(parents=[parent_rec(), parent_rec()], counts=counts(parents=2))
    assert partition["ok"] is False
    assert status_of(partition, "hunk_bounds") is False
    assert any("hunk_bounds" in e for e in partition["errors"])


def test_missing_file_record_fails_loud():
    partition = run(parents=[parent_rec(path="g.txt")])
    assert partition["ok"] is False
    assert status_of(partition, "parent_refs") is False
    assert any("g.txt" in e for e in partition["errors"])


def test_numstat_mismatch_fails_loud():
    partition = run(parents=[parent_rec(old_count=2, new_count=2)])
    assert partition["ok"] is False
    assert status_of(partition, "numstat_counts") is False
    assert any("numstat" in e for e in partition["errors"])


def test_uncovered_file_fails_loud():
    partition = run(parents=[], counts={**counts(parents=0)}, numstat={"f.txt": {"added": 0, "deleted": 0}})
    assert partition["ok"] is False
    assert status_of(partition, "file_coverage") is False


def test_counts_mismatch_fails_loud():
    partition = run(counts={**counts(parents=5)})
    assert partition["ok"] is False
    assert status_of(partition, "counts_consistent") is False


def test_extraction_error_fails_loud():
    partition = run(extraction_errors=["patch stream: malformed hunk header"])
    assert partition["ok"] is False
    assert status_of(partition, "extraction") is False


def test_hunk_header_mismatch_fails_loud():
    partition = run(hunk_errors=["f.txt: hunk body has 2 old lines"])
    assert partition["ok"] is False
    assert status_of(partition, "hunk_headers") is False
