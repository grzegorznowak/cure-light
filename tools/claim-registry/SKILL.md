# SKILL: claim-registry tool unit

**What it is.** One fetchable Python artifact (`.pyz`) + `TOOL.json` that turns
a designated Markdown source (PR body, plan doc, …) into a canonical
cure-light claim registry: `capture` → `frame` → `assemble` → `validate` →
`manifest`.  File/JSON in, file/JSON out; deterministic; no hidden state.

**When to run.** The coordinator agent uses this unit whenever a V1 claim
registry must be produced or re-validated.  Labeling children never run it;
they only author `claim-proposals/1` files from `frame`/`windows` output.

**Trust boundary.** Agents orchestrate and author proposals only.  The unit
computes every ID, span, and hash.  Never hand-edit registry JSON; never
compute unit IDs or sha256s yourself; never "fix" a validation report.

## 1. Fetch, verify, pin (pin placeholder = the commit sha)

```bash
PIN=<pinned-commit-sha>
BASE="https://raw.githubusercontent.com/<owner>/<repo>/$PIN/tools/claim-registry"
curl -fsSL "$BASE/TOOL.json"             -o TOOL.json
curl -fsSL "$BASE/dist/claim-registry-0.2.0.pyz" -o claim-registry-0.2.0.pyz

# sha256 verify against the pin recorded in TOOL.json
python3 - <<'PY'
import hashlib, json, sys
expected = json.load(open("TOOL.json"))["artifact"]["sha256"]
actual = hashlib.sha256(open("claim-registry-0.2.0.pyz", "rb").read()).hexdigest()
print("sha256 ok" if actual == expected else f"MISMATCH {actual} != {expected}")
sys.exit(0 if actual == expected else 1)
PY

# verify the running artifact hashes to the pin
python3 claim-registry-0.2.0.pyz --check-pin \
  "$(python3 -c 'import json;print(json.load(open("TOOL.json"))["artifact"]["sha256"])')"
```

`--check-pin` exits 0 ok / 1 mismatch / 2 not running from a `.pyz`.

## 2. Read capabilities, install dependencies

```bash
python3 claim-registry-0.2.0.pyz --describe        # canonical tool-unit/1 JSON
python3 -m pip install 'tree-sitter==0.26.0' 'tree-sitter-markdown==0.5.1'
```

Dependencies are exact-pinned.  Every command except `--describe`,
`--check-pin`, `--help` exits **2** with the missing/wrong package names and
this install line; `--describe` always works without them.

## 3. Command sequence

```bash
# 1. capture each designated source verbatim (one capture dir per source is fine;
#    a single dir may hold several sources when captured together)
python3 claim-registry-0.2.0.pyz capture --in body.md --locator 'repo#17:body' --out captures/

# 2. frame (context for labeling children), optionally windows
python3 claim-registry-0.2.0.pyz frame --in body.md --locator 'repo#17:body' --out frame.json
# labeling children return claim-proposals/1 assignments only

# 3. assemble (repeat --proposals for multi-source / multi-child runs; merged in CLI order)
python3 claim-registry-0.2.0.pyz assemble --captures captures/ \
  --proposals proposals-a.json --proposals proposals-b.json --out registry.json

# 4. validate independently
python3 claim-registry-0.2.0.pyz validate --registry registry.json --captures captures/ \
  --report-out report.json

# 5. seal the run
python3 claim-registry-0.2.0.pyz manifest --captures captures/ \
  --proposals proposals-a.json --proposals proposals-b.json \
  --registry registry.json --report report.json --out run-manifest.json
```

## 4. How to read output

* `capture` / `assemble` / `windows` / `manifest`: stdout JSON summary; primary
  artifact is the `--out` file.
* `frame`: stdout (or `--out`) JSON with `unit_count`, `block_count`,
  `separator_count`, `recipe`, `units[]`.
* `validate`: stdout report (also `--report-out`).  Read
  `valid`, `permission.finalized_unclaimed`,
  `permission.complete_registry_claims`, and `errors[]`.
* `manifest`: canonical `claim-run-manifest/1`, no trailing newline; records
  tool pin + per-input sha256s for the gate-check unit.

## 5. Failure handling

| Exit | Meaning | Action |
|------|---------|--------|
| 0 | ok | continue (for `validate`: permission flags true) |
| 1 | semantic/validation failure; every message names the exact `unit_id`/field/check | read `report.errors` / stderr, fix the proposal files, rerun `assemble` + `validate` |
| 2 | usage/environment (bad args, missing/unreadable file, missing/wrong pinned dependency, bad window recipe) | fix the invocation/paths or install the pinned deps |

* `validate` exit 1 → fix **proposals**, never the registry JSON: the registry
  is a computed artifact and hand-edits break the canonical bytes/hash checks.
* `assemble` exit 1 (`double-owned`, unknown `unit_id`, non-consecutive claim,
  unowned decomposition remainder) → fix the proposals; the message names the
  offending `unit_id`.
* Missing/hash-mismatched captures → recapture from the same source bytes; do
  not edit capture manifests.
