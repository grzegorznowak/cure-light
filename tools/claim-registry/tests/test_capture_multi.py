"""Multi-source batch capture (D1): one manifest, CLI order, no overwrite.

Contract under test:

* ``capture`` takes repeatable ``--in``/``--locator`` pairs (one pair per
  source, aligned by index) and writes exactly one ``capture-manifest/1`` for
  the whole batch, with records in CLI order.
* per-source metadata (``--class``/``--pointer-ref``/``--interpretation-ref``)
  may be given once (applies to every source) or once per source.
* duplicate locators are rejected before anything is written.
* a capture run never overwrites an existing manifest: recapturing into the
  same ``--out`` fails and leaves the earlier sources intact.
* single-source output is byte-compatible with the legacy
  ``write_capture_dir([cap], out)`` writer.
* core ``read_capture_dir``/``assemble`` consume the multi-record manifest
  unchanged.
"""

from __future__ import annotations

import json

from claim_registry.capture import SourceCapture
from claim_registry.cli import main, read_capture_dir, write_capture_dir
from claim_registry.frame import frame_source
from claim_registry.registry import default_proposals

A_BYTES = b"# Alpha\n\nAlpha body.\n"
B_BYTES = b"# Beta\n\nBeta body.\n- item one\n"


def _capture_manifest(capdir):
    raw = (capdir / "manifest.json").read_bytes()
    assert not raw.endswith(b"\n")  # canonical, no trailing newline
    return json.loads(raw)


def _write_sources(tmp_path):
    a = tmp_path / "alpha.md"
    b = tmp_path / "beta.md"
    a.write_bytes(A_BYTES)
    b.write_bytes(B_BYTES)
    return a, b


def test_batch_capture_one_manifest_in_cli_order(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture", "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:plan", "--out", str(out)])
    assert code == 0, capsys.readouterr().err
    summary = json.loads(capsys.readouterr().out)
    assert set(summary) == {"manifest", "sources"}

    manifest = _capture_manifest(out)
    assert manifest["schema_version"] == "capture-manifest/1"
    assert [s["locator"] for s in manifest["sources"]] == ["repo#17:body", "repo#17:plan"]
    assert [s["file"] for s in manifest["sources"]] == ["raw/0000.bin", "raw/0001.bin"]
    assert [s["source_ref"] for s in manifest["sources"]] == [
        s["source_ref"] for s in summary["sources"]
    ]
    assert (out / "raw" / "0000.bin").read_bytes() == A_BYTES
    assert (out / "raw" / "0001.bin").read_bytes() == B_BYTES

    captures = read_capture_dir(str(out))
    assert [c.locator for c in captures] == ["repo#17:body", "repo#17:plan"]
    assert [c.data for c in captures] == [A_BYTES, B_BYTES]


def test_batch_per_source_metadata_aligned_by_index(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture",
                 "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:plan",
                 "--class", "api-document", "--class", "in-diff-file",
                 "--pointer-ref", "p-alpha", "--pointer-ref", "p-beta",
                 "--interpretation-ref", "i-alpha", "--interpretation-ref", "i-beta",
                 "--out", str(out)])
    assert code == 0, capsys.readouterr().err
    capsys.readouterr()
    sources = _capture_manifest(out)["sources"]
    assert [s["class"] for s in sources] == ["api-document", "in-diff-file"]
    assert [s["pointer_ref"] for s in sources] == ["p-alpha", "p-beta"]
    assert [s["interpretation_ref"] for s in sources] == ["i-alpha", "i-beta"]


def test_batch_single_metadata_applies_to_all_sources(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture",
                 "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:plan",
                 "--class", "in-diff-file", "--pointer-ref", "shared",
                 "--out", str(out)])
    assert code == 0, capsys.readouterr().err
    capsys.readouterr()
    sources = _capture_manifest(out)["sources"]
    assert [s["class"] for s in sources] == ["in-diff-file", "in-diff-file"]
    assert [s["pointer_ref"] for s in sources] == ["shared", "shared"]
    assert [s["interpretation_ref"] for s in sources] == [None, None]


def test_batch_locator_count_mismatch_is_usage_error(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture", "--in", str(a), "--in", str(b),
                 "--locator", "only-one", "--out", str(out)])
    assert code == 2
    assert "--locator" in capsys.readouterr().err
    assert not (out / "manifest.json").exists()


def test_batch_metadata_count_mismatch_is_usage_error(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture",
                 "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:plan",
                 "--class", "x", "--class", "y", "--class", "z",
                 "--out", str(out)])
    assert code == 2
    assert "--class" in capsys.readouterr().err
    assert not (out / "manifest.json").exists()


def test_batch_duplicate_locator_rejected_before_any_write(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture",
                 "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:body",
                 "--out", str(out)])
    assert code == 2
    assert "duplicate locator" in capsys.readouterr().err
    assert not out.exists()


def test_recapture_never_overwrites_existing_sources(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    assert main(["capture", "--in", str(a), "--locator", "l-a",
                 "--out", str(out)]) == 0
    capsys.readouterr()
    before_manifest = (out / "manifest.json").read_bytes()
    before_raw = (out / "raw" / "0000.bin").read_bytes()

    code = main(["capture", "--in", str(b), "--locator", "l-b", "--out", str(out)])
    assert code == 2
    err = capsys.readouterr().err
    assert "manifest" in err and ("overwrite" in err or "refus" in err)

    assert (out / "manifest.json").read_bytes() == before_manifest
    assert (out / "raw" / "0000.bin").read_bytes() == before_raw
    assert not (out / "raw" / "0001.bin").exists()
    captures = read_capture_dir(str(out))
    assert [c.locator for c in captures] == ["l-a"]


def test_single_source_capture_byte_compatible_with_legacy_writer(tmp_path, capsys):
    a, _ = _write_sources(tmp_path)
    cli_out = tmp_path / "cli"
    lib_out = tmp_path / "lib"
    code = main(["capture", "--in", str(a), "--locator", "repo#17:body",
                 "--out", str(cli_out)])
    assert code == 0, capsys.readouterr().err
    stdout = json.loads(capsys.readouterr().out)
    assert set(stdout) == {"manifest", "source"}
    assert "file" not in stdout["source"]

    cap = SourceCapture(locator="repo#17:body", source_class="api-document",
                        data=A_BYTES)
    write_capture_dir([cap], str(lib_out))
    assert (cli_out / "manifest.json").read_bytes() == (lib_out / "manifest.json").read_bytes()
    assert (cli_out / "raw" / "0000.bin").read_bytes() == (lib_out / "raw" / "0000.bin").read_bytes()
    assert stdout["source"] == cap.record()


def test_multi_source_manifest_feeds_assemble_unchanged(tmp_path, capsys):
    a, b = _write_sources(tmp_path)
    out = tmp_path / "captures"
    code = main(["capture", "--in", str(a), "--locator", "repo#17:body",
                 "--in", str(b), "--locator", "repo#17:plan", "--out", str(out)])
    assert code == 0, capsys.readouterr().err
    capsys.readouterr()

    captures = read_capture_dir(str(out))
    assert [c.locator for c in captures] == ["repo#17:body", "repo#17:plan"]
    assert len(captures) == 2
    assignments = []
    for cap in captures:
        assignments.extend(
            default_proposals(cap.source_ref, frame_source(cap.data))["assignments"]
        )
    prop = tmp_path / "proposals.json"
    prop.write_text(json.dumps({"schema_version": "claim-proposals/1",
                                "assignments": assignments}), encoding="utf-8")

    registry = tmp_path / "registry.json"
    report = tmp_path / "report.json"
    assert main(["assemble", "--captures", str(out), "--proposals", str(prop),
                 "--out", str(registry)]) == 0
    capsys.readouterr()
    assert main(["validate", "--registry", str(registry), "--captures", str(out),
                 "--report-out", str(report)]) == 0
    report_value = json.loads(capsys.readouterr().out)
    assert report_value["valid"] is True

    envelope = json.loads(registry.read_bytes())
    source_refs = {unit["source_ref"] for unit in envelope["payload"]["units"]}
    assert source_refs == {cap.source_ref for cap in captures}
