# gate-check

Mechanical permission gate for a completed claim-registry run. Stdlib-only
single-artifact tool unit (`gate-check-0.1.0.pyz` + `TOOL.json`).

`gate-check check` re-derives bytes, hashes, witness counts and permission
flags from the run manifest and every recorded artifact. Exit 0 means the
mechanical `finalized_unclaimed` permission is granted; exit 1 means at least
one check failed and `report.errors` names it. The gate never consults git, a
worktree, the network, or an agent.

## Usage

```
python3 gate-check-0.1.0.pyz --describe
python3 gate-check-0.1.0.pyz --check-pin <sha256-from-TOOL.json>
python3 gate-check-0.1.0.pyz check --manifest M.json \
    [--registry R.json] [--report V.json] [--captures DIR] \
    [--proposals P.json] [--windows W.json] \
    [--tool-manifest TOOL.json] [--artifact PATH] \
    [--base-dir DIR] [--report-out OUT.json]
```

Manifest-relative paths resolve against `--base-dir` (default: the manifest
file's directory); absolute paths are unchanged; explicitly given CLI paths
override manifest paths (a missing/unreadable explicit path is a usage error,
exit 2).

Exit codes: `0` all checks passed; `1` one or more checks failed (read
`report.errors`); `2` usage/environment — missing or malformed manifest,
unreadable explicit override, unwritable `--report-out`.

## `claim-run-manifest/1` (canonical JSON, no trailing newline)

Produced by `claim-registry manifest` from files on disk; never hand-written.
Root keys are exact (unknown or missing root keys are rejected by
`gate-check`):

```json
{
  "schema_version": "claim-run-manifest/1",
  "tool": {
    "name": "claim-registry",
    "version": "0.2.0",
    "describe_sha256": "<64hex>",
    "artifact": null | {"file": "dist/claim-registry-0.2.0.pyz", "sha256": "<64hex>"}
  },
  "captures": {"path": "captures", "manifest_sha256": "<64hex>"},
  "proposals": [{"path": "proposals.json", "sha256": "<64hex>"}],
  "registry": {"path": "registry.json", "sha256": "<64hex>",
               "registry_hash": "sha256:<64hex>"},
  "report": {"path": "report.json", "sha256": "<64hex>", "valid": true,
             "finalized_unclaimed": true, "complete_registry_claims": true,
             "registry_hash": "sha256:<64hex>"},
  "windows": null
}
```

* All seven root keys are required; unknown root keys are rejected.
* `tool.artifact` and `windows` may be `null`; `tool.artifact` may be
  absent-as-null. `proposals` may be an empty list.
* File `sha256` fields are plain lowercase hex (an optional `sha256:` prefix is
  tolerated on file hashes); `registry_hash` values are compared as exact
  strings, including the producer's `sha256:` prefix.
* `tool.describe_sha256` = sha256 of the canonical TOOL.json with `artifact`
  normalized to `null` (the producer's describe recipe).

## Checks (each emitted as `{"id", "ok", "detail"}`)

* `manifest.canonical`, `manifest.shape` — canonical bytes + strict schema.
* `file[<label>].exists`, `file[<label>].sha256` — registry, report,
  captures manifest, windows.
* `registry.parse`, `registry.canonical_bytes`, `registry.envelope`,
  `registry.registry_hash`, `registry.recipe_hash`, `registry.manifest_binding`,
  `registry.witness_complete`, `registry.witness_errors`,
  `registry.witness_uncaptured`, `registry.witness_per_source`,
  `registry.witness_counts_zero` — zero pending/conflict/error counts globally
  and per source. The gate is worktree-independent.
* `report.parse`, `report.shape`, `report.valid`,
  `report.permission.finalized_unclaimed`,
  `report.permission.complete_registry_claims`, `report.checks_all_ok`,
  `report.registry_binding` (report → registry), `manifest.report_valid`,
  `manifest.report_permission`, `manifest.report_registry_hash`
  (manifest-recorded report fields ↔ the report file).
* `captures.manifest_sha256`, `captures.manifest_shape`,
  `captures.raw[<source_ref>]` (file sha256/byte_length/blob_oid/source_ref
  recompute with the producer's percent-encoding + git-blob recipe),
  `captures.registry_sources_match` (source_ref/sha256/byte_length/blob_oid).
* `tool.manifest_parse`, `tool.manifest_shape`, `tool.name_version`,
  `tool.describe_sha256` (canonical TOOL.json with `artifact` normalized to
  `null`), `tool.artifact_sha256` (artifact file vs `TOOL.json.artifact.sha256`
  and `manifest.tool.artifact.sha256`) — only when
  `--tool-manifest`/`--artifact` is given.
* `proposals.sha256[<path>]` — audit binding only.

## `gate-check-report/1` (canonical JSON on stdout; `--report-out` same bytes)

```json
{
  "schema_version": "gate-check-report/1",
  "valid": true,
  "checks": [{"id": "...", "ok": true, "detail": ""}],
  "errors": [],
  "permission": {"finalized_unclaimed": true, "complete_registry_claims": true},
  "inputs": {"<file>": "<sha256>"}
}
```

`permission` is false unless `valid` is true.

## Build & test

```
python3 build.py            # dist/gate-check-0.1.0.pyz (+ .sha256), TOOL.json
python3 -m pytest tests/ -q # real baseline-produced fixture + tamper matrix
```

The producer and its golden fixture are read from the sibling
`../claim-registry` unit; `tests/fixtures/pr17-body-v2.md` is sha256-pinned, so
absence or drift fails loudly. Tests skip only when the producer unit itself is
absent. Nothing is ever written into the producer or any git repo.
