"""Mechanical consistency checks behind ``gate-check check``.

Every check is emitted as ``{"id", "ok", "detail"}`` in a
``gate-check-report/1`` document.  The gate re-derives bytes, hashes, witness
counts and permission flags from the recorded artifacts; it never trusts a
producer-supplied boolean without a recomputation.  It is deliberately
worktree-independent: no git command, repository state or network access is
consulted.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from claim_label_contract import reconciliation as contract_reconciliation
from claim_label_contract import schemas as contract_schemas
from claim_label_contract import slicing as contract_slicing
from toolkit import canonical_json
from toolkit.tool_unit import UsageError, sha256_file

RUN_MANIFEST_SCHEMA = "claim-run-manifest/1"
RUN_MANIFEST_SCHEMA_V2 = "claim-run-manifest/2"
RUN_LABELING_SCHEMA = contract_schemas.CLAIM_RUN_LABELING_VERSION
GATE_REPORT_SCHEMA = "gate-check-report/1"
CAPTURE_MANIFEST_SCHEMA = "capture-manifest/1"
BLOB_ALGORITHM = "git-blob-sha256"

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SHA256ISH = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")

# Percent encoding keeps ASCII unreserved [A-Za-z0-9._~-] and emits everything
# else as uppercase %HH (claim_registry/capture.py).
_UNRESERVED = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-"
)

MANIFEST_KEYS = {
    "schema_version", "tool", "captures", "proposals", "registry", "report",
    "windows",
}
MANIFEST_KEYS_V2 = MANIFEST_KEYS | {"labeling"}
TOOL_KEYS = {"name", "version", "describe_sha256", "artifact"}
ARTIFACT_KEYS = {"file", "sha256"}
CAPTURES_KEYS = {"path", "manifest_sha256"}
REGISTRY_KEYS = {"path", "sha256", "registry_hash"}
REPORT_KEYS = {
    "path", "sha256", "valid", "finalized_unclaimed",
    "complete_registry_claims", "registry_hash",
}
PROPOSAL_KEYS = {"path", "sha256"}
WINDOWS_KEYS = {"path", "sha256"}
CAPTURE_RECORD_KEYS = {
    "source_ref", "locator", "class", "pointer_ref", "interpretation_ref",
    "blob_algorithm", "blob_oid", "sha256", "byte_length", "empty", "bom",
    "file",
}


# --------------------------------------------------------------------------
# stdlib reimplementation of the producer's tiny capture recipe
# --------------------------------------------------------------------------

def percent_encode(text: str | bytes) -> str:
    raw = text.encode("utf-8") if isinstance(text, str) else text
    out: list[str] = []
    for b in raw:
        if b in _UNRESERVED:
            out.append(chr(b))
        else:
            out.append(f"%{b:02X}")
    return "".join(out)


def synthetic_git_blob_oid(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\x00"
    return hashlib.sha256(header + data).hexdigest()


def make_source_ref(locator: str, blob_oid: str,
                    blob_algorithm: str = BLOB_ALGORITHM) -> str:
    return f"src:{percent_encode(locator)}:{blob_algorithm}:{blob_oid}"


def _norm_sha(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("sha256:"):
        return value[len("sha256:"):]
    return value


def _is_sha256ish(value: Any) -> bool:
    return isinstance(value, str) and _SHA256ISH.fullmatch(value) is not None


def _check_exact_keys(obj: Any, allowed: set[str], where: str) -> str | None:
    if not isinstance(obj, dict):
        return f"{where} is not an object"
    extra = sorted(set(obj) - allowed)
    missing = sorted(allowed - set(obj))
    if extra:
        return f"{where} has unknown keys {extra}"
    if missing:
        return f"{where} is missing keys {missing}"
    return None


def _check_subset_keys(obj: Any, required: set[str], where: str) -> str | None:
    if not isinstance(obj, dict):
        return f"{where} is not an object"
    missing = sorted(required - set(obj))
    if missing:
        return f"{where} is missing keys {missing}"
    return None


def validate_manifest_shape(value: Any) -> tuple[bool, str]:
    """Strict ``claim-run-manifest/1`` or ``/2`` shape; first violation returned."""
    if not isinstance(value, dict):
        return False, "manifest is not an object"
    version = value.get("schema_version")
    if version == RUN_MANIFEST_SCHEMA_V2:
        err = _check_exact_keys(value, MANIFEST_KEYS_V2, "manifest")
        if err:
            return False, err
        ok, err = _validate_manifest_blocks(value)
        if not ok:
            return False, err
        errors = contract_schemas.validate(
            contract_schemas.CLAIM_RUN_LABELING_1, value["labeling"]
        )
        if errors:
            return False, "manifest.labeling: " + "; ".join(errors)
        merged = value["labeling"]["merged"]
        if value["proposals"] != [
            {"path": merged["path"], "sha256": merged["sha256"]}
        ]:
            return False, (
                "manifest.proposals must equal [manifest.labeling.merged] in "
                "claim-run-manifest/2"
            )
        return True, ""
    err = _check_exact_keys(value, MANIFEST_KEYS, "manifest")
    if err:
        return False, err
    if value["schema_version"] != RUN_MANIFEST_SCHEMA:
        return False, (
            f"schema_version {value['schema_version']!r} != {RUN_MANIFEST_SCHEMA!r} "
            f"or {RUN_MANIFEST_SCHEMA_V2!r}"
        )
    return _validate_manifest_blocks(value)


def _validate_manifest_blocks(value: dict) -> tuple[bool, str]:
    """Shared flat-block validation for /1 and /2 (root keys already checked)."""
    tool = value["tool"]
    # ``artifact`` may be absent-as-null or an object; every other key is required.
    err = _check_subset_keys(tool, {"name", "version", "describe_sha256"}, "manifest.tool")
    if err:
        return False, err
    extra = sorted(set(tool) - TOOL_KEYS)
    if extra:
        return False, f"manifest.tool has unknown keys {extra}"
    if not isinstance(tool["name"], str) or not tool["name"]:
        return False, "manifest.tool.name must be a non-empty string"
    if not isinstance(tool["version"], str) or not tool["version"]:
        return False, "manifest.tool.version must be a non-empty string"
    if not _is_sha256ish(tool["describe_sha256"]):
        return False, "manifest.tool.describe_sha256 must be a sha256 hex string"
    artifact = tool.get("artifact")
    if artifact is not None:
        err = _check_exact_keys(artifact, ARTIFACT_KEYS, "manifest.tool.artifact")
        if err:
            return False, err
        if not isinstance(artifact["file"], str) or not artifact["file"]:
            return False, "manifest.tool.artifact.file must be a non-empty string"
        if not _is_sha256ish(artifact["sha256"]):
            return False, "manifest.tool.artifact.sha256 must be a sha256 hex string"

    caps = value["captures"]
    err = _check_exact_keys(caps, CAPTURES_KEYS, "manifest.captures")
    if err:
        return False, err
    if not isinstance(caps["path"], str) or not caps["path"]:
        return False, "manifest.captures.path must be a non-empty string"
    if not _is_sha256ish(caps["manifest_sha256"]):
        return False, "manifest.captures.manifest_sha256 must be a sha256 hex string"

    proposals = value["proposals"]
    if not isinstance(proposals, list):
        return False, "manifest.proposals must be a list"
    for i, spec in enumerate(proposals):
        err = _check_exact_keys(spec, PROPOSAL_KEYS, f"manifest.proposals[{i}]")
        if err:
            return False, err
        if not isinstance(spec["path"], str) or not spec["path"]:
            return False, f"manifest.proposals[{i}].path must be a non-empty string"
        if not _is_sha256ish(spec["sha256"]):
            return False, f"manifest.proposals[{i}].sha256 must be a sha256 hex string"

    reg = value["registry"]
    err = _check_exact_keys(reg, REGISTRY_KEYS, "manifest.registry")
    if err:
        return False, err
    if not isinstance(reg["path"], str) or not reg["path"]:
        return False, "manifest.registry.path must be a non-empty string"
    if not _is_sha256ish(reg["sha256"]):
        return False, "manifest.registry.sha256 must be a sha256 hex string"
    if not _is_sha256ish(reg["registry_hash"]):
        return False, "manifest.registry.registry_hash must be a hash string"

    rep = value["report"]
    err = _check_exact_keys(rep, REPORT_KEYS, "manifest.report")
    if err:
        return False, err
    if not isinstance(rep["path"], str) or not rep["path"]:
        return False, "manifest.report.path must be a non-empty string"
    if not _is_sha256ish(rep["sha256"]):
        return False, "manifest.report.sha256 must be a sha256 hex string"
    for key in ("valid", "finalized_unclaimed", "complete_registry_claims"):
        if not isinstance(rep[key], bool):
            return False, f"manifest.report.{key} must be a boolean"
    if not _is_sha256ish(rep["registry_hash"]):
        return False, "manifest.report.registry_hash must be a hash string"

    windows = value["windows"]
    if windows is not None:
        err = _check_exact_keys(windows, WINDOWS_KEYS, "manifest.windows")
        if err:
            return False, err
        if not isinstance(windows["path"], str) or not windows["path"]:
            return False, "manifest.windows.path must be a non-empty string"
        if not _is_sha256ish(windows["sha256"]):
            return False, "manifest.windows.sha256 must be a sha256 hex string"
    return True, ""


# --------------------------------------------------------------------------
# check collector
# --------------------------------------------------------------------------

class Gate:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.checks: list[dict] = []
        self.errors: list[str] = []
        self.inputs: dict[str, str] = {}
        self.registry_payload: dict | None = None
        self.registry_hash: str | None = None
        self.report: dict | None = None

    def check(self, cid: str, ok: bool, detail: str = "") -> bool:
        ok = bool(ok)
        self.checks.append({"id": cid, "ok": ok, "detail": "" if ok else detail})
        if not ok:
            self.errors.append(f"{cid}: {detail}" if detail else cid)
        return ok

    def record_input(self, path: Path) -> str | None:
        try:
            digest = sha256_file(path)
        except OSError:
            return None
        self.inputs[str(path)] = digest
        return digest

    def finish(self) -> dict:
        valid = bool(self.checks) and all(c["ok"] for c in self.checks)
        return {
            "schema_version": GATE_REPORT_SCHEMA,
            "valid": valid,
            "checks": self.checks,
            "errors": self.errors,
            "permission": {
                "finalized_unclaimed": valid,
                "complete_registry_claims": valid,
            },
            "inputs": {key: self.inputs[key] for key in sorted(self.inputs)},
        }


# --------------------------------------------------------------------------
# argument / path helpers
# --------------------------------------------------------------------------

def _resolve(base: Path, path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (base / path)


def _require_file(path: Path | None, label: str) -> Path | None:
    if path is None:
        return None
    if not path.is_file():
        raise UsageError(f"{label} not found: {path}")
    return path


def _file_check(g: Gate, label: str, path: Path, recorded_sha: Any) -> str | None:
    """Emit file exists/sha256 checks; returns actual sha when readable."""
    if not path.is_file():
        g.check(f"file[{label}].exists", False, f"missing {path}")
        return None
    actual = g.record_input(path) or ""
    g.check(f"file[{label}].exists", True)
    if recorded_sha is not None:
        g.check(
            f"file[{label}].sha256",
            _norm_sha(actual) == _norm_sha(recorded_sha),
            f"recorded {recorded_sha} actual {actual}",
        )
    return actual


# --------------------------------------------------------------------------
# individual artifact checks
# --------------------------------------------------------------------------

def check_registry(g: Gate, path: Path, recorded_hash: Any) -> None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        g.check("registry.read", False, f"unreadable {path}: {exc}")
        return
    try:
        value = canonical_json.canonical_loads(raw)
    except canonical_json.CanonicalizationError as exc:
        g.check("registry.parse", False, f"not claim-json/1: {exc}")
        return
    g.check("registry.parse", True)
    g.check(
        "registry.canonical_bytes",
        canonical_json.canonical_dumps(value) == raw,
        "registry bytes are not the canonical claim-json/1 serialization "
        "(trailing newline, whitespace, key order or duplicate keys)",
    )
    if not isinstance(value, dict) or set(value) != {"payload", "registry_hash"}:
        g.check("registry.envelope", False, "envelope must have exactly payload+registry_hash")
        return
    payload = value.get("payload")
    if not isinstance(payload, dict):
        g.check("registry.envelope", False, "payload is not an object")
        return
    g.check("registry.envelope", True)

    recomputed = canonical_json.registry_hash(payload)
    g.registry_payload = payload
    g.registry_hash = recomputed
    g.check(
        "registry.registry_hash",
        value.get("registry_hash") == recomputed,
        f"envelope registry_hash {value.get('registry_hash')!r} != recompute {recomputed!r}",
    )
    recipe = payload.get("recipe")
    recipe_ok = isinstance(recipe, dict) and (
        payload.get("recipe_hash") == canonical_json.recipe_hash(recipe)
    )
    g.check("registry.recipe_hash", recipe_ok, "recipe_hash does not reproduce from recipe")
    if recorded_hash is not None:
        g.check(
            "registry.manifest_binding",
            recorded_hash == recomputed,
            f"manifest.registry.registry_hash {recorded_hash!r} != registry recompute "
            f"{recomputed!r}",
        )

    witness = payload.get("witness")
    if not isinstance(witness, dict):
        g.check("registry.witness", False, "payload.witness is not an object")
        return
    g.check("registry.witness", True)
    g.check(
        "registry.witness_complete",
        witness.get("complete") is True,
        f"witness.complete={witness.get('complete')!r}",
    )
    errors = witness.get("errors")
    g.check(
        "registry.witness_errors",
        errors in ([], None),
        f"witness.errors={errors!r}",
    )
    uncaptured = witness.get("uncaptured_source_refs")
    g.check(
        "registry.witness_uncaptured",
        uncaptured == [],
        f"witness.uncaptured_source_refs={uncaptured!r}",
    )
    per_source = witness.get("per_source")
    if not isinstance(per_source, list):
        g.check("registry.witness_per_source", False, "witness.per_source is not a list")
        return
    g.check("registry.witness_per_source", True)
    offenders: list[str] = []
    totals = {"pending_count": 0, "conflict_count": 0, "error_count": 0}
    for i, source in enumerate(per_source):
        if not isinstance(source, dict):
            offenders.append(f"per_source[{i}] is not an object")
            continue
        ref = source.get("source_ref") or f"per_source[{i}]"
        for key in ("pending_count", "conflict_count", "error_count"):
            value_ = source.get(key)
            if value_ != 0 or isinstance(value_, bool):
                offenders.append(f"{ref}.{key}={value_!r}")
            elif isinstance(value_, int):
                totals[key] += value_
        if source.get("complete") is not True:
            offenders.append(f"{ref}.complete={source.get('complete')!r}")
    g.check(
        "registry.witness_counts_zero",
        not offenders and all(v == 0 for v in totals.values()),
        "non-zero/absent counts: " + "; ".join(offenders[:6]),
    )


def check_report(g: Gate, path: Path, registry_hash: str | None,
                 recorded: dict) -> None:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        g.check("report.read", False, f"unreadable {path}: {exc}")
        return
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        g.check("report.parse", False, f"not valid JSON: {exc}")
        return
    g.check("report.parse", True)
    if not isinstance(report, dict):
        g.check("report.shape", False, "report is not an object")
        return
    g.check("report.shape", True)
    g.report = report
    g.check("report.valid", report.get("valid") is True, f"valid={report.get('valid')!r}")
    permission = report.get("permission")
    permission = permission if isinstance(permission, dict) else {}
    g.check(
        "report.permission.finalized_unclaimed",
        permission.get("finalized_unclaimed") is True,
        f"finalized_unclaimed={permission.get('finalized_unclaimed')!r}",
    )
    g.check(
        "report.permission.complete_registry_claims",
        permission.get("complete_registry_claims") is True,
        f"complete_registry_claims={permission.get('complete_registry_claims')!r}",
    )
    checks = report.get("checks")
    failing: list[str] = []
    if isinstance(checks, list):
        for i, entry in enumerate(checks):
            if not isinstance(entry, dict) or entry.get("ok") is not True:
                label = None
                if isinstance(entry, dict):
                    label = entry.get("name") or entry.get("id")
                failing.append(label or f"checks[{i}]")
    else:
        failing.append("checks is not a list")
    g.check("report.checks_all_ok", not failing,
            "failing validation checks: " + ", ".join(map(str, failing[:6])))
    if registry_hash is not None:
        g.check(
            "report.registry_binding",
            report.get("registry_hash") == registry_hash,
            f"report registry_hash {report.get('registry_hash')!r} != registry recompute "
            f"{registry_hash!r}",
        )
    recorded_valid = recorded.get("valid")
    g.check(
        "manifest.report_valid",
        recorded_valid is report.get("valid"),
        f"manifest.report.valid={recorded_valid!r}, report.valid={report.get('valid')!r}",
    )
    mismatches: list[str] = []
    for key in ("finalized_unclaimed", "complete_registry_claims"):
        if recorded.get(key) is not permission.get(key):
            mismatches.append(
                f"manifest.report.{key}={recorded.get(key)!r} "
                f"report.permission.{key}={permission.get(key)!r}"
            )
    g.check(
        "manifest.report_permission",
        not mismatches,
        "; ".join(mismatches),
    )
    g.check(
        "manifest.report_registry_hash",
        recorded.get("registry_hash") == report.get("registry_hash"),
        f"manifest.report.registry_hash={recorded.get('registry_hash')!r} "
        f"report.registry_hash={report.get('registry_hash')!r}",
    )


def check_captures(g: Gate, captures_dir: Path, recorded_manifest_sha: Any) -> None:
    manifest_path = captures_dir / "manifest.json"
    if not manifest_path.is_file():
        g.check("captures.manifest", False, f"missing {manifest_path}")
        return
    raw = manifest_path.read_bytes()
    actual_sha = g.record_input(manifest_path) or ""
    if recorded_manifest_sha is not None:
        g.check(
            "captures.manifest_sha256",
            _norm_sha(actual_sha) == _norm_sha(recorded_manifest_sha),
            f"recorded {recorded_manifest_sha} actual {actual_sha}",
        )
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        g.check("captures.manifest_shape", False, f"not valid JSON: {exc}")
        return
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != CAPTURE_MANIFEST_SCHEMA
        or not isinstance(manifest.get("sources"), list)
    ):
        g.check(
            "captures.manifest_shape",
            False,
            f"expected {CAPTURE_MANIFEST_SCHEMA!r} with a sources list",
        )
        return
    g.check("captures.manifest_shape", True)

    records: dict[str, dict] = {}
    for i, record in enumerate(manifest["sources"]):
        where = f"captures.sources[{i}]"
        err = _check_subset_keys(record, CAPTURE_RECORD_KEYS, where)
        if err:
            g.check(where, False, err)
            continue
        ref = record["source_ref"]
        if not isinstance(ref, str) or not ref:
            g.check(where, False, "source_ref must be a non-empty string")
            continue
        records[ref] = record
        raw_path = captures_dir / str(record["file"])
        if not raw_path.is_file():
            g.check(f"captures.raw[{ref}]", False, f"missing {raw_path}")
            continue
        data = raw_path.read_bytes()
        g.record_input(raw_path)
        problems: list[str] = []
        data_sha = hashlib.sha256(data).hexdigest()
        if data_sha != record["sha256"]:
            problems.append(f"sha256 recorded {record['sha256']} actual {data_sha}")
        if len(data) != record["byte_length"]:
            problems.append(f"byte_length recorded {record['byte_length']} actual {len(data)}")
        algorithm = record.get("blob_algorithm")
        if algorithm != BLOB_ALGORITHM:
            problems.append(f"unsupported blob_algorithm {algorithm!r}")
        else:
            oid = synthetic_git_blob_oid(data)
            if oid != record.get("blob_oid"):
                problems.append(f"blob_oid recorded {record.get('blob_oid')} actual {oid}")
            expected_ref = make_source_ref(record.get("locator", ""), oid)
            if expected_ref != ref:
                problems.append(f"source_ref recompute {expected_ref!r} != {ref!r}")
        g.check(f"captures.raw[{ref}]", not problems, "; ".join(problems[:4]))

    if g.registry_payload is None:
        return
    registry_sources = {
        s["source_ref"]: s
        for s in g.registry_payload.get("sources", [])
        if isinstance(s, dict) and isinstance(s.get("source_ref"), str)
    }
    mismatches: list[str] = []
    for ref, record in sorted(records.items()):
        reg = registry_sources.get(ref)
        if reg is None:
            mismatches.append(f"{ref}: missing from registry sources")
            continue
        for key in ("sha256", "byte_length", "blob_oid"):
            if reg.get(key) != record.get(key):
                mismatches.append(
                    f"{ref}.{key}: registry {reg.get(key)!r} capture {record.get(key)!r}"
                )
    for ref in sorted(registry_sources):
        if ref not in records:
            mismatches.append(f"{ref}: registry source has no capture record")
    g.check(
        "captures.registry_sources_match",
        not mismatches,
        "; ".join(mismatches[:6]),
    )


def check_tool(g: Gate, tool_record: dict, tool_manifest_path: Path | None,
               artifact_path: Path | None) -> None:
    tool_manifest: dict | None = None
    if tool_manifest_path is not None:
        try:
            parsed = json.loads(tool_manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            g.check("tool.manifest_parse", False, f"unreadable TOOL.json: {exc}")
            parsed = None
        if parsed is not None:
            g.check("tool.manifest_parse", True)
            if not isinstance(parsed, dict):
                g.check("tool.manifest_shape", False, "TOOL.json is not an object")
            else:
                g.check("tool.manifest_shape", True)
                tool_manifest = parsed
                g.check(
                    "tool.name_version",
                    parsed.get("name") == tool_record.get("name")
                    and parsed.get("version") == tool_record.get("version"),
                    f"TOOL.json {parsed.get('name')}@{parsed.get('version')} != manifest "
                    f"{tool_record.get('name')}@{tool_record.get('version')}",
                )
                without_artifact = dict(parsed)
                # The producer's describe recipe keeps the key and normalizes it
                # to null (``_tool_block`` in claim_registry/cli.py).
                without_artifact["artifact"] = None
                try:
                    recomputed = canonical_json.canonical_hash(without_artifact)[len("sha256:"):]
                except canonical_json.CanonicalizationError as exc:
                    recomputed = None
                    g.check("tool.describe_sha256", False,
                            f"TOOL.json cannot be canonicalized: {exc}")
                else:
                    g.check(
                        "tool.describe_sha256",
                        _norm_sha(recomputed) == _norm_sha(tool_record.get("describe_sha256")),
                        f"recomputed {recomputed} manifest {tool_record.get('describe_sha256')}",
                    )

    if artifact_path is None:
        return
    actual = g.record_input(artifact_path)
    if actual is None:
        g.check("tool.artifact_sha256", False, f"unreadable artifact {artifact_path}")
        return
    expected: list[tuple[str, Any]] = []
    if isinstance(tool_manifest, dict) and isinstance(tool_manifest.get("artifact"), dict):
        expected.append(("TOOL.json.artifact.sha256", tool_manifest["artifact"].get("sha256")))
    manifest_artifact = tool_record.get("artifact")
    if isinstance(manifest_artifact, dict):
        expected.append(("manifest.tool.artifact.sha256", manifest_artifact.get("sha256")))
    expected = [(label, value) for label, value in expected if _is_sha256ish(value)]
    if not expected:
        g.check(
            "tool.artifact_sha256",
            False,
            f"no recorded artifact sha to compare against (actual {actual})",
        )
        return
    g.check(
        "tool.artifact_sha256",
        all(_norm_sha(value) == _norm_sha(actual) for _, value in expected),
        f"actual {actual}; " + "; ".join(f"{label}={value}" for label, value in expected),
    )


def check_proposals(g: Gate, items: list[tuple[str, Path, Any]]) -> None:
    for label, path, recorded in items:
        if not path.is_file():
            g.check(f"proposals.sha256[{label}]", False, f"missing {path}")
            continue
        actual = g.record_input(path) or ""
        if recorded is None:
            g.check(f"proposals.sha256[{label}]", True)
        else:
            g.check(
                f"proposals.sha256[{label}]",
                _norm_sha(actual) == _norm_sha(recorded),
                f"recorded {recorded} actual {actual}",
            )


# --------------------------------------------------------------------------
# sliced-run replay (claim-run-manifest/2)
# --------------------------------------------------------------------------

def _read_maybe(path: Path | None) -> bytes | None:
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _resolve_run_ref(base: Path, raw: Any) -> tuple[Path | None, str | None]:
    """Resolve a /2 recorded ref under the run root; reject escapes/aliases."""
    if not isinstance(raw, str) or not raw:
        return None, "empty path"
    path = Path(raw)
    if path.is_absolute():
        return None, "absolute path"
    if ".." in path.parts:
        return None, "parent-directory traversal"
    resolved = (base / path).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        return None, "escapes the run root"
    if resolved == base:
        return None, "resolves to the run root"
    return resolved, None


def _compare_registry_to_merged(registry_payload: dict, merged: dict) -> list[str]:
    """Reconciled ownership/grouping/rationales vs the actual registry labels."""
    problems: list[str] = []
    assignments = merged.get("assignments", [])
    unit_records = {
        u["unit_id"]: u for u in registry_payload.get("units", [])
        if isinstance(u, dict) and isinstance(u.get("unit_id"), str)
    }
    labels = {
        label["unit_id"]: label for label in registry_payload.get("labels", [])
        if isinstance(label, dict) and isinstance(label.get("unit_id"), str)
    }
    expected_owner: dict[str, int] = {}
    for index, assignment in enumerate(assignments):
        for uid in assignment.get("unit_ids", []):
            if uid in expected_owner:
                problems.append(f"merged proposals assign {uid} more than once")
            expected_owner[uid] = index
    for uid in sorted(expected_owner):
        if uid not in unit_records:
            problems.append(f"merged proposals assign unknown unit {uid}")

    merged_claims = [
        tuple(a.get("unit_ids", [])) for a in assignments if a.get("state") == "claim"
    ]
    registry_claims = [
        tuple(c.get("unit_ids", [])) for c in registry_payload.get("claims", [])
    ]
    if merged_claims != registry_claims:
        problems.append(
            "registry claims (membership/order) differ from the merged claim "
            "assignments"
        )
    claim_id_by_uid: dict[str, Any] = {}
    for claim in registry_payload.get("claims", []):
        for uid in claim.get("unit_ids", []):
            claim_id_by_uid[uid] = claim.get("claim_id")

    for uid in sorted(unit_records):
        unit = unit_records[uid]
        label = labels.get(uid)
        if label is None:
            problems.append(f"{uid}: no registry label")
            continue
        index = expected_owner.get(uid)
        if index is None:
            if unit.get("kind") != "separator":
                problems.append(
                    f"{uid}: non-separator unit is not owned by the merged proposals"
                )
            elif (
                label.get("state") != "nonclaim"
                or label.get("nonclaim_label") != "context"
                or label.get("role_ref") != "spec:claim-registry/1#separator"
            ):
                problems.append(f"{uid}: separator is not mechanically nonclaim context")
            continue
        assignment = assignments[index]
        if label.get("state") != assignment.get("state"):
            problems.append(
                f"{uid}: registry state {label.get('state')!r} != merged "
                f"{assignment.get('state')!r}"
            )
            continue
        if assignment.get("state") == "claim":
            if claim_id_by_uid.get(uid) is None:
                problems.append(f"{uid}: claim label has no registry claim membership")
            elif label.get("claim_id") != claim_id_by_uid.get(uid):
                problems.append(f"{uid}: label claim_id differs from its claim membership")
            if label.get("rationale", "") != assignment.get("rationale", ""):
                problems.append(
                    f"{uid}: claim rationale {label.get('rationale')!r} != merged "
                    f"{assignment.get('rationale')!r}"
                )
        else:
            for merged_key, label_key in (
                ("label", "nonclaim_label"),
                ("role_ref", "role_ref"),
                ("rationale", "rationale"),
            ):
                if label.get(label_key) != assignment.get(merged_key):
                    problems.append(
                        f"{uid}: {label_key} differs from the merged nonclaim assignment"
                    )
                    break
    return problems


def check_sliced(
    g: Gate,
    *,
    base: Path,
    labeling: dict,
    captures_dir: Path,
    registry_payload: dict | None,
) -> None:
    """Replay a claim-run-manifest/2 labeling block from the recorded bytes.

    The gate never reparses Markdown (producer-side ``validate`` owns parser
    correctness): it re-verifies span identity against captured bytes, re-plans
    the recipe-determined partition and payloads, re-runs deterministic
    reconciliation over the recorded children, and compares the outcome with
    the recorded merged/report bytes and the actual registry labels/claims.
    """
    ref_problems: list[str] = []
    slices_path, problem = _resolve_run_ref(base, labeling["slices"]["path"])
    if problem:
        ref_problems.append(f"slices: {problem}")
    merged_path, problem = _resolve_run_ref(base, labeling["merged"]["path"])
    if problem:
        ref_problems.append(f"merged: {problem}")
    reconciliation_path, problem = _resolve_run_ref(
        base, labeling["reconciliation"]["path"]
    )
    if problem:
        ref_problems.append(f"reconciliation: {problem}")

    input_paths: list[tuple[dict, Path | None]] = []
    seen_sids: set[str] = set()
    seen_paths: set[Path] = set()
    for index, item in enumerate(labeling["inputs"]):
        path, problem = _resolve_run_ref(base, item["path"])
        if problem:
            ref_problems.append(f"inputs[{index}]: {problem}")
        if item["slice_id"] in seen_sids:
            ref_problems.append(f"inputs[{index}]: duplicate slice_id {item['slice_id']}")
        seen_sids.add(item["slice_id"])
        if path is not None:
            if path in seen_paths:
                ref_problems.append(f"inputs[{index}]: duplicate path alias {path}")
            seen_paths.add(path)
        input_paths.append((item, path))
    named_paths = {
        p for p in (slices_path, merged_path, reconciliation_path) if p is not None
    }
    for index, (item, path) in enumerate(input_paths):
        if path is not None and path in named_paths:
            ref_problems.append(f"inputs[{index}]: aliases a recorded named artifact")
    g.check("sliced.refs_safe", not ref_problems, "; ".join(ref_problems[:6]))

    if slices_path is not None:
        _file_check(g, "sliced.slices", slices_path, labeling["slices"]["sha256"])
    if merged_path is not None:
        _file_check(g, "sliced.merged", merged_path, labeling["merged"]["sha256"])
    if reconciliation_path is not None:
        _file_check(
            g, "sliced.reconciliation", reconciliation_path,
            labeling["reconciliation"]["sha256"],
        )
    for index, (item, path) in enumerate(input_paths):
        label = f"sliced.inputs[{index}]"
        if path is None:
            g.check(f"file[{label}].exists", False, "unresolved recorded path")
            continue
        _file_check(g, label, path, item["sha256"])

    # -- slices manifest: canonical + schema -------------------------------
    slices_raw = _read_maybe(slices_path)
    slices_doc: dict | None = None
    if slices_raw is None:
        g.check("sliced.slices_parse", False, "slices manifest unavailable")
        g.check("sliced.slices_schema", False, "slices manifest unavailable")
    else:
        try:
            parsed = canonical_json.canonical_loads(slices_raw)
        except canonical_json.CanonicalizationError as exc:
            g.check("sliced.slices_parse", False, f"not claim-json/1: {exc}")
            g.check("sliced.slices_schema", False, "not claim-json/1")
        else:
            g.check("sliced.slices_parse", True)
            errors = contract_schemas.validate(contract_schemas.FRAME_SLICES_1, parsed)
            g.check("sliced.slices_schema", not errors, "; ".join(errors[:6]))
            if not errors:
                slices_doc = parsed

    # -- captures: records + raw bytes -------------------------------------
    capture_records: dict[str, dict] = {}
    capture_raw: dict[str, bytes] = {}
    capture_manifest_path = captures_dir / "manifest.json"
    if capture_manifest_path.is_file():
        try:
            capture_manifest = json.loads(capture_manifest_path.read_bytes().decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            capture_manifest = None
        if isinstance(capture_manifest, dict):
            for record in capture_manifest.get("sources", []):
                if not isinstance(record, dict) or not isinstance(record.get("source_ref"), str):
                    continue
                ref = record["source_ref"]
                capture_records[ref] = record
                raw_path = captures_dir / str(record.get("file", ""))
                if raw_path.is_file():
                    capture_raw[ref] = raw_path.read_bytes()

    # -- captures_sha256 recompute -----------------------------------------
    if slices_doc is not None and capture_records:
        try:
            identity = sorted(
                ({k: v for k, v in record.items() if k != "file"}
                 for record in capture_records.values()),
                key=lambda record: record["source_ref"].encode("utf-8"),
            )
            recomputed = hashlib.sha256(
                canonical_json.canonical_dumps(identity)
            ).hexdigest()
        except (canonical_json.CanonicalizationError, KeyError, TypeError) as exc:
            g.check("sliced.captures_sha256", False, f"cannot recompute: {exc}")
        else:
            g.check(
                "sliced.captures_sha256",
                recomputed == slices_doc["captures_sha256"],
                f"recomputed {recomputed} recorded {slices_doc['captures_sha256']}",
            )
    else:
        g.check("sliced.captures_sha256", False, "capture records or slices manifest unavailable")

    # -- sources binding + unit identity/span replay -----------------------
    source_problems: list[str] = []
    unit_problems: list[str] = []
    units_by_ref: dict[str, dict[str, dict]] = {}
    if slices_doc is None:
        source_problems.append("slices manifest unavailable")
        unit_problems.append("slices manifest unavailable")
    else:
        manifest_refs = [s["source_ref"] for s in slices_doc["sources"]]
        if set(manifest_refs) != set(capture_records):
            source_problems.append(
                f"source set {sorted(manifest_refs)} != captures {sorted(capture_records)}"
            )
        for source in slices_doc["sources"]:
            ref = source["source_ref"]
            record = capture_records.get(ref)
            if record is None:
                source_problems.append(f"{ref}: no capture record")
                continue
            if (source["sha256"] != record.get("sha256")
                    or source["byte_length"] != record.get("byte_length")):
                source_problems.append(f"{ref}: sha256/byte_length differ from the capture")
            raw = capture_raw.get(ref)
            if raw is None:
                source_problems.append(f"{ref}: captured raw bytes unavailable")
                continue
            units = source["units"]
            units_by_ref[ref] = {u["unit_id"]: u for u in units}
            if [u["ordinal"] for u in units] != list(range(len(units))):
                unit_problems.append(f"{ref}: ordinals are not contiguous from 0")
            if len({u["unit_id"] for u in units}) != len(units):
                unit_problems.append(f"{ref}: duplicate unit_id")
            for unit in units:
                uid = unit["unit_id"]
                if unit["source_ref"] != ref:
                    unit_problems.append(f"{uid}: source_ref mismatch")
                    continue
                start, end = unit["start"], unit["end"]
                if not (0 <= start <= end <= len(raw)):
                    unit_problems.append(f"{uid}: span outside the captured bytes")
                    continue
                expected_id = f"{ref}:{start}-{end}:{unit['sha256']}"
                if uid != expected_id:
                    unit_problems.append(f"{uid}: unit_id does not recompute as {expected_id}")
                actual = hashlib.sha256(raw[start:end]).hexdigest()
                if actual != unit["sha256"]:
                    unit_problems.append(
                        f"{uid}: span sha256 {actual} != recorded {unit['sha256']}"
                    )
    g.check("sliced.sources_binding", not source_problems, "; ".join(source_problems[:6]))
    g.check("sliced.units_replay", not unit_problems, "; ".join(unit_problems[:6]))

    # -- global unit table equality with the registry ----------------------
    if registry_payload is None:
        g.check("sliced.registry_units_match", False, "registry payload unavailable")
    elif slices_doc is None:
        g.check("sliced.registry_units_match", False, "slices manifest unavailable")
    else:
        expected_units = [u for s in slices_doc["sources"] for u in s["units"]]
        g.check(
            "sliced.registry_units_match",
            registry_payload.get("units") == expected_units,
            "registry units differ from the frame-slices global unit table",
        )

    # -- recipe replay: partition + payload bytes --------------------------
    plans: list = []
    partition_problems: list[str] = []
    if slices_doc is None:
        partition_problems.append("slices manifest unavailable")
    else:
        for source in slices_doc["sources"]:
            ref = source["source_ref"]
            raw = capture_raw.get(ref, b"")
            try:
                plans.extend(contract_slicing.plan_slices(
                    ref,
                    slices_doc["frame_recipe_hash"],
                    slices_doc["slice_recipe"],
                    source["units"],
                    raw,
                    verify_spans=True,
                ))
            except Exception as exc:  # noqa: BLE001 - reported as a check failure
                partition_problems.append(f"{ref}: {exc}")
    recorded = slices_doc["slices"] if slices_doc is not None else []
    if not partition_problems:
        if len(plans) != len(recorded):
            partition_problems.append(
                f"recipe yields {len(plans)} slices, manifest records {len(recorded)}"
            )
        else:
            for index, (plan, entry) in enumerate(zip(plans, recorded)):
                if (
                    plan.slice_id != entry["slice_id"]
                    or plan.source_ref != entry["source_ref"]
                    or list(plan.core_ids) != entry["core_ids"]
                    or list(plan.overlap_ids) != entry["overlap_ids"]
                    or list(plan.context_only_ids) != entry["context_only_ids"]
                ):
                    partition_problems.append(
                        f"slice[{index}] {entry.get('slice_id')!r} differs from the recipe replay"
                    )
    g.check("sliced.partition_replay", not partition_problems, "; ".join(partition_problems[:6]))

    payload_problems: list[str] = []
    expected_slices: list[dict] = []
    replay_ready = not partition_problems and len(plans) == len(recorded)
    if not replay_ready:
        payload_problems.append("partition replay failed; payloads not replayed")
    else:
        slices_dir = slices_path.parent if slices_path is not None else None
        for index, (plan, entry) in enumerate(zip(plans, recorded)):
            spec = entry["input"]
            target, problem = (
                _resolve_run_ref(slices_dir, spec["path"])
                if slices_dir is not None else (None, "slices dir unavailable")
            )
            if problem:
                payload_problems.append(f"slice[{index}]: payload path: {problem}")
                continue
            data = _read_maybe(target)
            if data is None:
                payload_problems.append(f"slice[{index}]: payload unreadable")
                continue
            if data != plan.payload_bytes:
                payload_problems.append(
                    f"slice[{index}] {plan.slice_id}: payload bytes differ from the replay"
                )
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest != spec["sha256"]:
                payload_problems.append(f"slice[{index}]: input.sha256 mismatch")
            if len(data) != spec["byte_length"]:
                payload_problems.append(f"slice[{index}]: input.byte_length mismatch")
            expected_slices.append({
                "slice_id": plan.slice_id,
                "source_ref": plan.source_ref,
                "core_ids": list(plan.core_ids),
                "overlap_ids": list(plan.overlap_ids),
                "context_only_ids": list(plan.context_only_ids),
                "payload_sha256": digest,
                "payload_byte_length": len(data),
            })
    g.check("sliced.payload_replay", not payload_problems, "; ".join(payload_problems[:6]))

    # -- child inputs: hash + schema + slice binding -----------------------
    proposal_inputs: list[dict] = []
    child_problems: list[str] = []
    recorded_by_id = {entry["slice_id"]: entry for entry in recorded}
    for index, (item, path) in enumerate(input_paths):
        label = f"input[{index}]"
        if path is None:
            child_problems.append(f"{label}: unresolved recorded path")
            proposal_inputs.append({"label": label, "sha256": item["sha256"],
                                    "document": None, "error": "unresolved path"})
            continue
        data = _read_maybe(path)
        if data is None:
            child_problems.append(f"{label}: unreadable {path}")
            proposal_inputs.append({"label": label, "sha256": item["sha256"],
                                    "document": None, "error": "unreadable"})
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"]:
            child_problems.append(f"{label}: file sha256 differs from the recorded digest")
        try:
            doc = canonical_json.canonical_loads(data)
        except canonical_json.CanonicalizationError as exc:
            child_problems.append(f"{label}: not claim-json/1: {exc}")
            proposal_inputs.append({"label": label, "sha256": digest,
                                    "document": None, "error": str(exc)})
            continue
        errors = contract_schemas.validate(contract_schemas.SLICE_PROPOSALS_1, doc)
        if errors:
            child_problems.append(f"{label}: not slice-proposals/1: {errors[0]}")
        entry = recorded_by_id.get(doc.get("slice_id")) if isinstance(doc, dict) else None
        if entry is None:
            child_problems.append(
                f"{label}: slice_id {doc.get('slice_id') if isinstance(doc, dict) else None!r} "
                "is not in the frame-slices manifest"
            )
        elif doc.get("input_sha256") != entry["input"]["sha256"]:
            child_problems.append(f"{label}: input_sha256 does not bind its slice payload")
        proposal_inputs.append({"label": label, "sha256": digest,
                                "document": doc, "error": None})
    g.check("sliced.inputs_binding", not child_problems, "; ".join(child_problems[:6]))

    # -- deterministic reconciliation replay -------------------------------
    merged_replay: bytes | None = None
    report_replay_bytes: bytes | None = None
    replay_problems: list[str] = []
    if not replay_ready or slices_doc is None:
        replay_problems.append("partition replay unavailable")
    else:
        sources_index = {
            ref: {uid: dict(record) for uid, record in units.items()}
            for ref, units in units_by_ref.items()
        }
        try:
            merged_replay, report_replay = contract_reconciliation.reconcile(
                sources=sources_index,
                expected_slices=expected_slices,
                proposals=proposal_inputs,
                slices_sha256=hashlib.sha256(slices_raw).hexdigest(),
            )
            report_replay_bytes = canonical_json.canonical_dumps(report_replay)
        except Exception as exc:  # noqa: BLE001 - reported as a check failure
            replay_problems.append(f"reconciliation replay error: {exc}")
    merged_recorded = _read_maybe(merged_path)
    reconciliation_recorded = _read_maybe(reconciliation_path)
    if replay_problems:
        g.check("sliced.reconcile_replay.merged", False, "; ".join(replay_problems))
        g.check("sliced.reconcile_replay.report", False, "; ".join(replay_problems))
    else:
        g.check(
            "sliced.reconcile_replay.merged",
            merged_recorded is not None and merged_replay is not None
            and merged_recorded == merged_replay,
            "recorded merged proposals differ from the deterministic replay",
        )
        g.check(
            "sliced.reconcile_replay.report",
            reconciliation_recorded is not None and report_replay_bytes is not None
            and reconciliation_recorded == report_replay_bytes,
            "recorded reconciliation report differs from the deterministic replay",
        )

    # -- recorded merged / report shape ------------------------------------
    merged_doc: dict | None = None
    if merged_recorded is None:
        g.check("sliced.merged_parse", False, "merged file unavailable")
    else:
        try:
            parsed = canonical_json.canonical_loads(merged_recorded)
        except canonical_json.CanonicalizationError as exc:
            g.check("sliced.merged_parse", False, f"not claim-json/1: {exc}")
        else:
            ok = (
                isinstance(parsed, dict)
                and parsed.get("schema_version") == "claim-proposals/1"
                and isinstance(parsed.get("assignments"), list)
            )
            g.check("sliced.merged_parse", ok,
                    "recorded merged file is not a claim-proposals/1 document")
            if ok:
                merged_doc = parsed
    if reconciliation_recorded is None:
        g.check("sliced.reconciliation_parse", False, "reconciliation file unavailable")
    else:
        try:
            parsed = canonical_json.canonical_loads(reconciliation_recorded)
        except canonical_json.CanonicalizationError as exc:
            g.check("sliced.reconciliation_parse", False, f"not claim-json/1: {exc}")
        else:
            errors = contract_schemas.validate(
                contract_schemas.PROPOSAL_RECONCILIATION_1, parsed
            )
            g.check("sliced.reconciliation_parse", not errors, "; ".join(errors[:4]))

    # -- reconciled ownership/grouping/rationales vs the registry ----------
    reference: dict | None = None
    if merged_replay is not None:
        try:
            reference = canonical_json.canonical_loads(merged_replay)
        except canonical_json.CanonicalizationError:
            reference = None
    if reference is None:
        reference = merged_doc
    if registry_payload is None or reference is None:
        g.check(
            "sliced.registry_match", False,
            "registry payload or replayed merged proposals unavailable",
        )
    else:
        problems = _compare_registry_to_merged(registry_payload, reference)
        g.check("sliced.registry_match", not problems, "; ".join(problems[:8]))


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------

def run_check(
    *,
    manifest_path: Path,
    base_dir: Path | None = None,
    registry_override: Path | None = None,
    report_override: Path | None = None,
    captures_override: Path | None = None,
    proposals_override: Path | None = None,
    windows_override: Path | None = None,
    tool_manifest_override: Path | None = None,
    artifact_override: Path | None = None,
    require_sliced: bool = False,
) -> dict:
    """Run every check and return the ``gate-check-report/1`` document.

    Raises ``tool_unit.UsageError`` (exit 2) for a missing/malformed manifest or
    an explicitly named but unreadable override path.
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        raise UsageError(f"manifest not found: {manifest_path}")
    try:
        raw = manifest_path.read_bytes()
    except OSError as exc:
        raise UsageError(f"manifest unreadable: {manifest_path}: {exc}") from exc
    try:
        value = canonical_json.canonical_loads(raw)
    except canonical_json.CanonicalizationError as exc:
        raise UsageError(f"malformed manifest {manifest_path}: {exc}") from exc

    base = Path(base_dir).resolve() if base_dir is not None else manifest_path.resolve().parent
    g = Gate(base)
    g.record_input(manifest_path)
    g.check(
        "manifest.canonical",
        canonical_json.canonical_dumps(value) == raw,
        "manifest bytes are not canonical claim-json/1 "
        "(trailing newline, whitespace, key order or duplicate keys)",
    )
    shape_ok, shape_detail = validate_manifest_shape(value)
    g.check("manifest.shape", shape_ok, shape_detail)
    if not shape_ok:
        return g.finish()

    sliced = value["schema_version"] == RUN_MANIFEST_SCHEMA_V2
    if require_sliced and not sliced:
        g.check(
            "manifest.sliced_required",
            False,
            "manifest is claim-run-manifest/1 but --require-sliced was given; "
            "a sliced run cannot be verified from a legacy manifest",
        )
    elif require_sliced:
        g.check("manifest.sliced_required", True)
    if sliced and proposals_override is not None:
        raise UsageError(
            "gate-check: --proposals override is not allowed for "
            "claim-run-manifest/2 (the recorded labeling.inputs are authoritative "
            "child inputs; --require-sliced and /2 replay are the audit path)"
        )

    tool = value["tool"]

    registry_override = _require_file(registry_override, "registry")
    report_override = _require_file(report_override, "report")
    proposals_override = _require_file(proposals_override, "proposals")
    windows_override = _require_file(windows_override, "windows")
    tool_manifest_override = _require_file(tool_manifest_override, "tool manifest")
    artifact_override = _require_file(artifact_override, "artifact")
    if captures_override is not None:
        if not (Path(captures_override) / "manifest.json").is_file():
            raise UsageError(f"captures dir has no manifest.json: {captures_override}")

    registry_path = registry_override or _resolve(base, value["registry"]["path"])
    report_path = report_override or _resolve(base, value["report"]["path"])
    captures_dir = (
        Path(captures_override).resolve() if captures_override is not None
        else _resolve(base, value["captures"]["path"])
    )
    windows_spec = value["windows"]
    windows_path = windows_override or (
        _resolve(base, windows_spec["path"]) if windows_spec is not None else None
    )

    # -- recorded files: existence + sha256 --------------------------------
    _file_check(g, "registry", registry_path, value["registry"]["sha256"])
    _file_check(g, "report", report_path, value["report"]["sha256"])
    _file_check(
        g, "captures.manifest", captures_dir / "manifest.json",
        value["captures"]["manifest_sha256"],
    )
    if windows_path is not None:
        _file_check(g, "windows", windows_path, windows_spec.get("sha256"))

    # -- registry ----------------------------------------------------------
    if registry_path.is_file():
        check_registry(g, registry_path, value["registry"]["registry_hash"])

    # -- validation report -------------------------------------------------
    if report_path.is_file():
        check_report(g, report_path, g.registry_hash, value["report"])
        if g.report is not None:
            recorded_permission = g.report.get("permission")
            recorded_permission = (
                recorded_permission if isinstance(recorded_permission, dict) else {}
            )
            g.check(
                "report.permission_shape",
                set(recorded_permission) >= {
                    "finalized_unclaimed", "complete_registry_claims",
                },
                f"permission keys {sorted(recorded_permission)}",
            )

    # -- captures ----------------------------------------------------------
    if (captures_dir / "manifest.json").is_file():
        check_captures(g, captures_dir, value["captures"]["manifest_sha256"])

    # -- sliced labeling replay (claim-run-manifest/2) ---------------------
    if sliced:
        check_sliced(
            g,
            base=base,
            labeling=value["labeling"],
            captures_dir=captures_dir,
            registry_payload=g.registry_payload,
        )

    # -- proposals (audit binding only) ------------------------------------
    if proposals_override is not None:
        recorded = None
        for spec in value["proposals"]:
            candidate = _resolve(base, spec["path"])
            if candidate == Path(proposals_override).resolve() or spec["path"] == str(proposals_override):
                recorded = spec["sha256"]
                break
        proposal_items = [(str(proposals_override), Path(proposals_override), recorded)]
    else:
        proposal_items = [
            (spec["path"], _resolve(base, spec["path"]), spec["sha256"])
            for spec in value["proposals"]
        ]
    check_proposals(g, proposal_items)

    # -- tool pin (only when the operator pins it) -------------------------
    if tool_manifest_override is not None or artifact_override is not None:
        check_tool(g, tool, tool_manifest_override, artifact_override)

    return g.finish()
