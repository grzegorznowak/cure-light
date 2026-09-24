# Skill: gate-check (mechanical `finalized_unclaimed` permission)

**This gate is mechanical and not agent-optional.** The permission to treat a
claim registry as complete (`finalized_unclaimed`) is granted only by
`gate-check` exiting 0. An agent's word, a green producer summary, or a
hand-inspected report is not a substitute.

## When to run

Only after the claim-registry run is complete:

1. `capture` → `frame`/`windows` → labeling children → `assemble` (all proposal
   files) → `validate`, and
2. `validate` has produced its report (and `manifest` has produced
   `claim-run-manifest/1`).

Never run it mid-assembly; never run it against a hand-edited registry/report.

## Fetch and verify

```bash
curl -sSfL -o gate-check-0.1.0.pyz \
  <pinned-raw-url>/tools/gate-check/dist/gate-check-0.1.0.pyz
curl -sSfL -o TOOL-gate-check.json \
  <pinned-raw-url>/tools/gate-check/TOOL.json
sha256sum gate-check-0.1.0.pyz        # must equal TOOL-gate-check.json.artifact.sha256
python3 gate-check-0.1.0.pyz --check-pin "$(python3 -c \
  'import json;print(json.load(open("TOOL-gate-check.json"))["artifact"]["sha256"])')"
python3 gate-check-0.1.0.pyz --describe    # commands/params/exit codes (no deps needed)
```

`--check-pin` prints `pin ok` on stderr and exits 0; a mismatch exits 1. The
artifact is stdlib-only — do not install tree-sitter for this unit.

## Run

```bash
python3 gate-check-0.1.0.pyz check --manifest M.json \
    [--registry R.json] [--report V.json] [--captures DIR] \
    [--proposals P.json] [--windows W.json] \
    [--tool-manifest claim-registry-TOOL.json] [--artifact claim-registry-0.2.0.pyz] \
    [--base-dir RUN_DIR] [--report-out GATE-REPORT.json]
```

Manifest paths are relative to the manifest's directory unless `--base-dir`
says otherwise. Add `--tool-manifest`/`--artifact` to pin the producer that
produced the run.

## Manifest shape (canonical, no trailing newline)

Flat `claim-run-manifest/1` root keys: `schema_version`, `tool` (`name`,
`version`, `describe_sha256`, `artifact`: null or `{file, sha256}`), `captures`
(`path`, `manifest_sha256`), `proposals` (list; may be empty), `registry`
(`path`, `sha256`, `registry_hash`), `report` (`path`, `sha256`, `valid`,
`finalized_unclaimed`, `complete_registry_claims`, `registry_hash`), `windows`
(null or `{path, sha256}`). Unknown root keys are rejected; `registry_hash`
values are compared as exact `sha256:<hex>` strings.

## Read the report

`gate-check-report/1` (canonical JSON on stdout, and `--report-out` if given):

* exit **0** → `valid: true`, `permission.finalized_unclaimed: true`; the
  registry is mechanically complete. Proceed downstream.
* exit **1** → no permission. Read `errors` (every entry is
  `<check id>: <detail>`); `checks[].ok == false` lists all failures.
* exit **2** → usage/environment (missing/malformed manifest, unreadable path);
  fix the invocation, nothing was adjudicated.

## Failure handling

* Exit 1 with registry/report failures: **never hand-edit `registry.json`,
  `report.json` or the run manifest**. Go back to the agent-authored proposals
  (`claim-proposals/1`), fix them (a validator error names the exact
  `unit_id`/field), then rerun `assemble` → `validate` → `manifest` →
  `gate-check` from scratch.
* Captures failure (`captures.raw[...]`): the captured bytes or the capture
  manifest moved. Recapture the source from the pristine input; do not patch
  the manifest.
* Tool-pin failure: the fetched artifact/TOOL.json is not the pinned producer;
  re-fetch by hash. Do not relax the pin.
* Manifest shape/canonical failure: the manifest was not produced by
  `claim-registry manifest` (or was hand-written/edited); regenerate it.
