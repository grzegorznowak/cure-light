"""frame-slices CLI contract tests (RED-first: the command is not implemented).

Covers the frozen ``frame-slices/1`` / ``frame-slice-input/1`` contract:
closed schema, byte identity and caps, core partition + overlap audit,
source identity/determinism, empty/oversized/invalid-UTF-8 failures, the
zero-overlap seam guard, the 32-slice budget and built-artifact packaging.

All assertions go through the CLI as a subprocess so a missing command is a
genuine intended-behavior failure, never an import error.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from claim_label_contract import schemas
from toolkit import canonical_json as cj

UNIT_ROOT = Path(__file__).resolve().parents[1]
COMMON = UNIT_ROOT.parent / "common"
from claim_registry.tool_manifest import MANIFEST as _MANIFEST
PYZ = UNIT_ROOT / "dist" / f"{_MANIFEST['name']}-{_MANIFEST['version']}.pyz"

SCHEMA_FRAME_SLICES = "frame-slices/1"
SCHEMA_SLICE_INPUT = "frame-slice-input/1"


def _env(extra: Path | None = None) -> dict:
    env = dict(os.environ)
    paths = [str(COMMON)]
    if extra is not None:
        paths.insert(0, str(extra))
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    return env


def cli(*args: str, cwd: Path | None = None, env: dict | None = None, timeout: int = 300):
    return subprocess.run(
        [sys.executable, "-m", "claim_registry.cli", *args],
        cwd=str(cwd or UNIT_ROOT),
        capture_output=True,
        text=True,
        env=env or _env(),
        timeout=timeout,
    )


def capture(tmp_path: Path, sources: list[tuple[str, bytes]], *, order: list[int] | None = None) -> Path:
    """Capture ``sources`` (name, bytes) in the given order; returns capture dir."""
    order = order if order is not None else list(range(len(sources)))
    capdir = tmp_path / "captures"
    args = ["capture"]
    for i in order:
        name, data = sources[i]
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        args += ["--in", str(path), "--locator", f"repo#17:{name}"]
    args += ["--out", str(capdir)]
    proc = cli(*args)
    assert proc.returncode == 0, proc.stderr
    return capdir


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def expected_captures_sha256(capdir: Path) -> str:
    manifest = read_json(capdir / "manifest.json")
    identities = sorted(
        ({k: v for k, v in record.items() if k != "file"} for record in manifest["sources"]),
        key=lambda record: record["source_ref"].encode("utf-8"),
    )
    return hashlib.sha256(cj.canonical_dumps(identities)).hexdigest()


def assert_slice_payloads(manifest: dict, out_dir: Path):
    """Structural + byte-identity checks for every payload of a manifest."""
    for entry in manifest["slices"]:
        ref = entry["input"]
        raw = (out_dir / ref["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == ref["sha256"], entry["slice_id"]
        assert len(raw) == ref["byte_length"], entry["slice_id"]
        doc = json.loads(raw.decode("utf-8"))
        assert cj.canonical_dumps(doc) == raw
        assert schemas.validate_by_name(SCHEMA_SLICE_INPUT, doc) == [], entry["slice_id"]
        assert doc["slice_id"] == entry["slice_id"]
        assert doc["core_ids"] == entry["core_ids"]
        assert doc["overlap_ids"] == entry["overlap_ids"]
        assert doc["context_only_ids"] == entry["context_only_ids"] == []
        assert doc["units"], entry["slice_id"]
        assert [u["unit_id"] for u in doc["units"]] == entry["overlap_ids"] + entry["core_ids"]
        assert doc["slice_recipe_hash"] == manifest["slice_recipe_hash"]
        assert doc["frame_recipe_hash"] == manifest["frame_recipe_hash"]
        recipe = manifest["slice_recipe"]
        text = doc["instructions"]["text"]
        assert doc["instructions"]["version"] == recipe["instructions_version"]
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == recipe["instructions_sha256"]
        assert len(raw) <= recipe["max_input_bytes"]
        text_bytes = sum(len(u["text"].encode("utf-8")) for u in doc["units"])
        assert text_bytes <= recipe["max_bytes"]
        assert len(doc["units"]) <= recipe["max_units"]


def unit_kind_index(manifest: dict) -> dict:
    return {
        u["unit_id"]: u["kind"]
        for source in manifest["sources"]
        for u in source["units"]
    }


# ---------------------------------------------------------------------------
# CLI / schema / back-compat
# ---------------------------------------------------------------------------

def test_describe_lists_frame_slices():
    proc = cli("--describe")
    assert proc.returncode == 0, proc.stderr
    commands = json.loads(proc.stdout)["commands"]
    assert "frame-slices" in commands
    spec = commands["frame-slices"]
    assert spec["usage"]
    assert set(spec["exit_codes"]) == {"0", "1", "2"}
    names = {param["name"] for param in spec["params"]}
    assert {"--captures", "--out-dir", "--max-bytes", "--max-units",
            "--max-input-bytes", "--overlap-units", "--max-slices"} <= names


def test_frame_slices_closed_schema_and_success(tmp_path):
    src = (
        b"# Title\n\nAlpha paragraph with Unicode \xe2\x9c\x93 and CRLF.\r\n\r\n"
        b"- item one\n- item two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```py\nprint('x')\n```\n"
    )
    capdir = capture(tmp_path, [("body.md", src)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    assert manifest["schema_version"] == SCHEMA_FRAME_SLICES
    assert schemas.validate_by_name(SCHEMA_FRAME_SLICES, manifest) == []
    assert manifest["captures_sha256"] == expected_captures_sha256(capdir)

    capture_record = read_json(capdir / "manifest.json")["sources"][0]
    source_ref = capture_record["source_ref"]
    assert [s["source_ref"] for s in manifest["sources"]] == [source_ref]
    assert manifest["sources"][0]["sha256"] == capture_record["sha256"]
    assert manifest["sources"][0]["byte_length"] == len(src)

    sys.path.insert(0, str(UNIT_ROOT))
    from claim_registry.frame import frame_source

    frame = frame_source(src)
    assert manifest["sources"][0]["units"] == [
        u.record(source_ref) for u in frame.units
    ]
    all_ids = [u.unit_id(source_ref) for u in frame.units]
    core_ids = [uid for entry in manifest["slices"] for uid in entry["core_ids"]]
    assert core_ids == all_ids  # cores partition the full frame once
    assert manifest["slices"][0]["overlap_ids"] == []
    assert_slice_payloads(manifest, out)

    # exact byte identity: every payload text recovers the capture span
    for entry in manifest["slices"]:
        doc = read_json(out / entry["input"]["path"])
        for unit in doc["units"]:
            span = src[unit["start"]:unit["end"]]
            assert unit["text"].encode("utf-8") == span
            assert hashlib.sha256(span).hexdigest() == unit["sha256"]


def test_frame_slices_rejects_bad_caps_and_existing_out_dir(tmp_path):
    capdir = capture(tmp_path, [("b.md", b"# T\n\nText\n")])
    checks = [
        ["--max-bytes", "0"],
        ["--max-bytes", "-1"],
        ["--max-units", "0"],
        ["--max-input-bytes", "0"],
        ["--overlap-units", "-1"],
        ["--max-slices", "0"],
        ["--overlap-units", "80"],  # >= max_units
    ]
    for i, extra in enumerate(checks):
        out = tmp_path / f"slices{i}"
        proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out), *extra)
        assert proc.returncode == 2, (extra, proc.stdout, proc.stderr)
        assert not out.exists()
    out = tmp_path / "slices-existing"
    out.mkdir()
    (out / "keep.txt").write_text("do not clobber", encoding="utf-8")
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 2
    assert (out / "keep.txt").read_text(encoding="utf-8") == "do not clobber"


def test_frame_slices_verifies_capture_bytes(tmp_path):
    capdir = capture(tmp_path, [("b.md", b"# T\n\nText\n")])
    raw = next((capdir / "raw").iterdir())
    raw.write_bytes(raw.read_bytes() + b"x")
    out = tmp_path / "slices-tamper"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 1, proc.stdout
    assert "verification" in proc.stderr.lower() or "sha256" in proc.stderr.lower()
    assert not out.exists()


# ---------------------------------------------------------------------------
# byte identity / caps
# ---------------------------------------------------------------------------

def test_frame_slices_exact_cap_and_cap_plus_one(tmp_path):
    body = ("x" * 400 + "\n").encode("utf-8")  # a single atomic unit
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "base"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out)).returncode == 0
    manifest = read_json(out / "manifest.json")
    assert len(manifest["slices"]) == 1
    payload_len = manifest["slices"][0]["input"]["byte_length"]

    at = tmp_path / "at"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(at),
               "--max-input-bytes", str(payload_len))
    assert proc.returncode == 0, proc.stderr

    over = tmp_path / "over"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(over),
               "--max-input-bytes", str(payload_len - 1))
    assert proc.returncode == 1, proc.stdout
    assert not (over / "manifest.json").exists()

    # max-bytes: one unit whose byte length is exactly the cap; cap-1 fails.
    unit = manifest["sources"][0]["units"][0]
    unit_bytes = unit["end"] - unit["start"]
    ok = tmp_path / "bytes-ok"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(ok),
               "--max-bytes", str(unit_bytes)).returncode == 0
    bad = tmp_path / "bytes-bad"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(bad),
               "--max-bytes", str(unit_bytes - 1))
    assert proc.returncode == 1
    assert unit["unit_id"] in proc.stderr


def test_frame_slices_oversized_unit_named(tmp_path):
    body = b"# T\n\n" + b"y" * 5000 + b"\n"
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out),
               "--max-bytes", "1000")
    assert proc.returncode == 1
    assert "oversized" in proc.stderr.lower()
    assert not out.exists()


def test_frame_slices_invalid_utf8_rejected(tmp_path):
    body = b"# T\n\n" + b"\xff\xfe broken" + b"\n"
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 1, proc.stdout
    assert "utf-8" in proc.stderr.lower()
    assert not out.exists()


def test_frame_slices_bom_crlf_unicode_roundtrip(tmp_path):
    body = "\ufeff# Tîtle\r\n\r\nnaïve — ✓ \x01 control\r\n".encode("utf-8")
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    assert_slice_payloads(manifest, out)
    for entry in manifest["slices"]:
        doc = read_json(out / entry["input"]["path"])
        for unit in doc["units"]:
            assert unit["text"].encode("utf-8") == body[unit["start"]:unit["end"]]


# ---------------------------------------------------------------------------
# partition / overlap / seam
# ---------------------------------------------------------------------------

def test_frame_slices_partition_overlap_and_no_overlap_only(tmp_path):
    parts = []
    for i in range(12):
        parts.append(f"## Section {i}\n\n")
        parts.append(("s%d " % i) * 120 + "\n\n")
    body = "".join(parts).encode("utf-8")
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out),
               "--max-bytes", "2048", "--max-units", "12", "--overlap-units", "2")
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    assert len(manifest["slices"]) >= 3
    assert_slice_payloads(manifest, out)
    kinds = unit_kind_index(manifest)
    by_source: dict[str, list] = {}
    for entry in manifest["slices"]:
        by_source.setdefault(entry["source_ref"], []).append(entry)
    for source_ref, entries in by_source.items():
        covered: list[str] = []
        for i, entry in enumerate(entries):
            assert entry["core_ids"], "slice without core"
            assert len(entry["core_ids"]) >= 1
            assert len(entry["overlap_ids"]) <= 2
            assert [uid for uid in entry["core_ids"]] == sorted(
                entry["core_ids"], key=lambda uid: _ordinal(manifest, uid)
            )
            if i:
                prev_core = entries[i - 1]["core_ids"]
                prev_last = prev_core[-1]
                if kinds[prev_last] != "separator":
                    assert prev_last in entry["overlap_ids"], (
                        "missing seam evidence", entry["slice_id"]
                    )
                assert all(uid not in entry["core_ids"] for uid in entry["overlap_ids"])
            covered.extend(entry["core_ids"])
        source_units = [
            u["unit_id"] for s in manifest["sources"]
            if s["source_ref"] == source_ref for u in s["units"]
        ]
        assert covered == source_units


def _ordinal(manifest: dict, unit_id: str) -> int:
    for source in manifest["sources"]:
        for unit in source["units"]:
            if unit["unit_id"] == unit_id:
                return unit["ordinal"]
    raise KeyError(unit_id)


def test_frame_slices_zero_overlap_seam_is_named_failure(tmp_path):
    # two adjacent headings (no separator between them); the first is cap-sized
    head = b"# " + b"h" * 300 + b"\n"
    body = head + b"## b\n"
    capdir = capture(tmp_path, [("b.md", body)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out),
               "--max-bytes", str(len(head) + 1), "--overlap-units", "4")
    assert proc.returncode == 1, proc.stdout
    assert "seam" in proc.stderr.lower()
    assert not out.exists()


# ---------------------------------------------------------------------------
# identity / determinism / budget / multi-source
# ---------------------------------------------------------------------------

def test_frame_slices_empty_source_and_separator_only_source(tmp_path):
    capdir = capture(tmp_path, [("empty.md", b""), ("ws.md", b"\n\n")])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    assert len(manifest["sources"]) == 2
    records = {r["locator"]: r for r in read_json(capdir / "manifest.json")["sources"]}
    empty_ref = records["repo#17:empty.md"]["source_ref"]
    ws_ref = records["repo#17:ws.md"]["source_ref"]
    by_ref = {s["source_ref"]: s for s in manifest["sources"]}
    assert by_ref[empty_ref]["units"] == []
    # an empty source has zero slices; a whitespace-only source still partitions
    # its separator units into one (mechanical, never-labeled) core
    assert [s["source_ref"] for s in manifest["slices"]] == [ws_ref]
    ws_slices = [s for s in manifest["slices"] if s["source_ref"] == ws_ref]
    assert len(ws_slices) == 1
    assert ws_slices[0]["core_ids"] == [by_ref[ws_ref]["units"][0]["unit_id"]]
    assert by_ref[ws_ref]["units"][0]["kind"] == "separator"


def test_frame_slices_source_order_permutation_is_byte_identical(tmp_path):
    sources = [("a.md", b"# A\n\nAlpha\n"), ("b.md", b"# B\n\nBeta\n")]
    cap_ab = capture(tmp_path / "ab", sources)
    cap_ba = capture(tmp_path / "ba", sources, order=[1, 0])
    out_ab, out_ba = tmp_path / "out-ab", tmp_path / "out-ba"
    assert cli("frame-slices", "--captures", str(cap_ab), "--out-dir", str(out_ab)).returncode == 0
    assert cli("frame-slices", "--captures", str(cap_ba), "--out-dir", str(out_ba)).returncode == 0
    assert (out_ab / "manifest.json").read_bytes() == (out_ba / "manifest.json").read_bytes()
    for entry in read_json(out_ab / "manifest.json")["slices"]:
        assert (out_ab / entry["input"]["path"]).read_bytes() == (
            out_ba / entry["input"]["path"]).read_bytes()


def test_frame_slices_repeat_run_is_byte_identical(tmp_path):
    capdir = capture(tmp_path, [("b.md", b"# T\n\nSome text here.\n\nMore text.\n")])
    first, second = tmp_path / "one", tmp_path / "two"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(first)).returncode == 0
    env_a = _env(); env_a["PYTHONHASHSEED"] = "1"
    env_b = _env(); env_b["PYTHONHASHSEED"] = "424242"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(second),
               env=env_a).returncode == 0
    third = tmp_path / "three"
    assert cli("frame-slices", "--captures", str(capdir), "--out-dir", str(third),
               env=env_b).returncode == 0
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    assert (first / "manifest.json").read_bytes() == (third / "manifest.json").read_bytes()


def test_frame_slices_budget_rejection_and_raised_budget(tmp_path):
    capdir = capture(tmp_path, [("big.md", _corpus(512))])
    default_out = tmp_path / "default"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(default_out))
    assert proc.returncode == 1, proc.stdout
    assert "max_slices" in proc.stderr or "budget" in proc.stderr.lower()
    raised = tmp_path / "raised"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(raised),
               "--max-slices", "96")
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(raised / "manifest.json")
    assert len(manifest["slices"]) > 32
    assert_slice_payloads(manifest, raised)


def _corpus(kib: int) -> bytes:
    out = []
    i = 0
    while sum(len(part) for part in out) < kib * 1024:
        out.append(f"## Section {i}\n\n")
        out.append(("word%d " % i) * 200 + "\n\n")
        i += 1
    return "".join(out).encode("utf-8")


def test_frame_slices_medium_scales_fit_default_budget(tmp_path):
    for kib in (128, 300):
        capdir = capture(tmp_path / f"c{kib}", [(f"{kib}.md", _corpus(kib))])
        out = tmp_path / f"s{kib}"
        proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
        assert proc.returncode == 0, (kib, proc.stderr)
        manifest = read_json(out / "manifest.json")
        assert 1 <= len(manifest["slices"]) <= 32
        assert_slice_payloads(manifest, out)


def test_frame_slices_two_committed_sources(pr_body, plan_doc, tmp_path):
    capdir = capture(tmp_path, [("pr17-body-v2.md", pr_body),
                                ("contract-adequacy-validation-plan.md", plan_doc)])
    out = tmp_path / "slices"
    proc = cli("frame-slices", "--captures", str(capdir), "--out-dir", str(out))
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(out / "manifest.json")
    assert len(manifest["sources"]) == 2
    assert 1 <= len(manifest["slices"]) <= 4
    assert_slice_payloads(manifest, out)
    # D1 x slice interplay: every unit of both fixtures is covered exactly once
    kinds = unit_kind_index(manifest)
    assert all(kind in schemas.UNIT_KINDS for kind in kinds.values())


def test_frame_slices_relocated_checkout_is_byte_identical(tmp_path):
    capdir = capture(tmp_path, [("panel.md", b"# T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nAlpha.\n")])
    env = _env()
    env["PYTHONPATH"] = str(UNIT_ROOT) + os.pathsep + env["PYTHONPATH"]
    out_a, out_b = tmp_path / "out-a", tmp_path / "out-b"

    def run(cwd):
        return subprocess.run(
            [sys.executable, "-m", "claim_registry.cli", "frame-slices",
             "--captures", str(capdir), "--out-dir", str(out_a if cwd == UNIT_ROOT else out_b)],
            cwd=str(cwd), capture_output=True, text=True, env=env, timeout=120,
        )

    first = run(UNIT_ROOT)
    assert first.returncode == 0, first.stderr
    second = run(tmp_path)
    assert second.returncode == 0, second.stderr
    assert (out_a / "manifest.json").read_bytes() == (out_b / "manifest.json").read_bytes()
    for entry in read_json(out_a / "manifest.json")["slices"]:
        assert (out_a / entry["input"]["path"]).read_bytes() == (
            out_b / entry["input"]["path"]).read_bytes()


# ---------------------------------------------------------------------------
# packaging / D4
# ---------------------------------------------------------------------------

def test_built_pyz_frame_slices_outside_repo(tmp_path):
    assert PYZ.is_file(), "committed artifact missing; step build.py"
    work = tmp_path / "work"
    work.mkdir()
    (work / "body.md").write_bytes(b"# T\n\nOutside cwd payload.\n")
    env = _env()
    env["PYTHONPATH"] = ""  # artifact must not need the repo
    cap = subprocess.run(
        [sys.executable, str(PYZ), "capture", "--in", str(work / "body.md"),
         "--locator", "repo#17:body", "--out", str(work / "caps")],
        cwd=str(work), capture_output=True, text=True, env=env, timeout=120,
    )
    assert cap.returncode == 0, cap.stderr
    proc = subprocess.run(
        [sys.executable, str(PYZ), "frame-slices", "--captures", str(work / "caps"),
         "--out-dir", str(work / "slices")],
        cwd=str(work), capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    manifest = read_json(work / "slices" / "manifest.json")
    assert manifest["schema_version"] == SCHEMA_FRAME_SLICES


def test_subject_tree_executable_is_never_invoked(tmp_path):
    """D4: the engine runs its pinned artifact; subject-tree tools stay dead."""
    subject = tmp_path / "subject"
    (subject / "tools" / "claim-registry" / "claim_registry").mkdir(parents=True)
    sentinel = tmp_path / "sentinel"
    malicious = subject / "tools" / "claim-registry" / "claim_registry" / "cli.py"
    malicious.write_text(
        "open(%r, 'w').write('called')\n" % str(sentinel), encoding="utf-8",
    )
    cli_shim = subject / "claim_registry"
    cli_shim.mkdir()
    (cli_shim / "__init__.py").write_text(
        "open(%r, 'w').write('called')\n" % str(sentinel), encoding="utf-8",
    )
    (cli_shim / "__main__.py").write_text(
        "open(%r, 'w').write('called')\n" % str(sentinel), encoding="utf-8",
    )
    work = tmp_path / "work"
    work.mkdir()
    (work / "b.md").write_bytes(b"# T\n\nPinned engine only.\n")
    env = _env()
    env["PYTHONPATH"] = str(subject)
    caps = subprocess.run(
        [sys.executable, str(PYZ), "capture", "--in", str(work / "b.md"),
         "--locator", "repo#17:body", "--out", str(work / "caps")],
        cwd=str(subject), capture_output=True, text=True, env=env, timeout=120,
    )
    assert caps.returncode == 0, caps.stderr
    proc = subprocess.run(
        [sys.executable, str(PYZ), "frame-slices", "--captures", str(work / "caps"),
         "--out-dir", str(work / "slices")],
        cwd=str(subject), capture_output=True, text=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    assert not sentinel.exists(), "subject-tree executable was invoked"


def test_windows_manifest_unchanged_by_slices_work(tmp_path):
    """Back-compat: the existing windows command output stays as before."""
    body = b"# T\n\nOne.\n\nTwo.\n"
    capdir = capture(tmp_path, [("b.md", body)])
    sys.path.insert(0, str(UNIT_ROOT))
    from claim_registry.capture import SourceCapture
    from claim_registry.frame import frame_source
    from claim_registry.registry import default_proposals

    record = read_json(capdir / "manifest.json")["sources"][0]
    cap = SourceCapture(locator=record["locator"], source_class=record["class"], data=body)
    proposal = tmp_path / "p.json"
    proposal.write_bytes(cj.canonical_dumps(
        {"schema_version": "claim-proposals/1",
         "assignments": default_proposals(cap.source_ref, frame_source(body))["assignments"]}
    ))
    registry = tmp_path / "r.json"
    assert cli("assemble", "--captures", str(capdir), "--proposals", str(proposal),
               "--out", str(registry)).returncode == 0
    proc = cli("windows", "--registry", str(registry))
    assert proc.returncode == 0, proc.stderr
    windows = json.loads(proc.stdout)
    assert windows["schema_version"] == "window-manifests/1"
