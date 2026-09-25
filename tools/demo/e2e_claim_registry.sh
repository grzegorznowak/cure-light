#!/usr/bin/env bash
# Deterministic end-to-end demo: built claim-registry + gate-check (+ census)
# artifacts, exercised exactly as the coordinator agent would run them.
#
# Usage: demo/e2e_claim_registry.sh [pr-body.md]
# Default fixture: claim-registry/tests/fixtures/pr17-body-v2.md (no external fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PR_BODY="${1:-}"
if [ -z "$PR_BODY" ]; then
  PR_BODY="$ROOT/claim-registry/tests/fixtures/pr17-body-v2.md"
fi

PU="$ROOT/claim-registry"
GU="$ROOT/gate-check"
CU="$ROOT/census"
PRZ="$PU/dist/claim-registry-0.3.0.pyz"
GCZ="$GU/dist/gate-check-0.2.0.pyz"
CZ="$CU/dist/census-0.1.0.pyz"

if [ ! -f "$PR_BODY" ]; then
  echo "E2E: missing fixture $PR_BODY" >&2
  exit 2
fi

[ -f "$PRZ" ] || (cd "$PU" && python3 build.py >/dev/null)
[ -f "$GCZ" ] || (cd "$GU" && python3 build.py >/dev/null)

verify_unit() {  # $1=dir $2=pyz
  local dir="$1" pyz="$2"
  local expected actual
  expected="$(python3 -c "import json,sys;print(json.load(open('$dir/TOOL.json'))['artifact']['sha256'])")"
  actual="$(sha256sum "$pyz" | cut -d' ' -f1)"
  if [ "$expected" != "$actual" ]; then
    echo "E2E: artifact pin mismatch for $pyz" >&2
    exit 1
  fi
  python3 "$pyz" --check-pin "$expected" >/dev/null 2>&1
}

verify_unit "$PU" "$PRZ"
verify_unit "$GU" "$GCZ"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

# --- claim registry flow ---------------------------------------------------
python3 "$PRZ" capture --in "$PR_BODY" --locator 'repo#17:body' --out captures >/dev/null

# (deterministic demo proposals: one claim per non-separator block)
PYTHONPATH="$PU" python3 - "$PR_BODY" <<'PY'
import json
import sys
from claim_registry.capture import SourceCapture
from claim_registry.frame import frame_source
from claim_registry.registry import default_proposals

data = open(sys.argv[1], "rb").read()
cap = SourceCapture(locator="repo#17:body", source_class="in-diff-file", data=data)
json.dump(default_proposals(cap.source_ref, frame_source(data)), open("proposals.json", "w"))
PY

python3 "$PRZ" assemble --captures captures --proposals proposals.json --out registry.json >/dev/null
python3 "$PRZ" validate --registry registry.json --captures captures --report-out report.json >/dev/null
python3 "$PRZ" manifest --captures captures --proposals proposals.json \
  --registry registry.json --report report.json --out run-manifest.json >/dev/null
python3 "$GCZ" check --manifest run-manifest.json --base-dir . > gate-report.json

python3 - <<'PY'
import json

registry = json.load(open("registry.json"))
report = json.load(open("report.json"))
gate = json.load(open("gate-report.json"))
units = len(registry["payload"]["units"])
claims = len(registry["payload"]["claims"])
assert units == 51, f"expected 51 units, got {units}"
assert report["valid"] is True, report["errors"][:3]
assert report["permission"]["finalized_unclaimed"] is True
assert report["permission"]["complete_registry_claims"] is True
assert gate["valid"] is True, gate["errors"][:3]
assert gate["permission"]["finalized_unclaimed"] is True
assert len(gate["checks"]) >= 20, len(gate["checks"])
print(f"claim-registry PASS: {units} units / {claims} claims; "
      f"validate permission granted; gate-check {len(gate['checks'])} checks ok")
PY

# --- sliced labeling flow (claim-run-manifest/2 + --require-sliced) -------
cat > "$WORK/sliced-companion.md" <<'MD'
# Sliced companion

Companion paragraph one with enough words to form a standalone block.

- companion item a
- companion item b

```
companion fence line
```

Final companion paragraph.
MD

python3 "$PRZ" capture --in "$PR_BODY" --locator 'repo#17:body' \
  --in "$WORK/sliced-companion.md" --locator 'repo#17:companion' \
  --out sliced-captures >/dev/null
python3 "$PRZ" frame-slices --captures sliced-captures --out-dir slices \
  --max-bytes 2048 --max-units 10 --overlap-units 3 --max-slices 32 >/dev/null

# deterministic mechanical children (one per slice; mirrors the fixture-builder style)
python3 - <<'PY'
import json
import os

manifest = json.load(open("slices/manifest.json"))
os.makedirs("children", exist_ok=True)
for index, entry in enumerate(manifest["slices"]):
    with open(os.path.join("slices", entry["input"]["path"])) as fh:
        payload = json.load(fh)
    kinds = {u["unit_id"]: u["kind"] for u in payload["units"]}
    assignments = [
        {"source_ref": entry["source_ref"], "unit_ids": [uid], "state": "claim",
         "rationale": "demo mechanical claim"}
        for uid in entry["core_ids"] if kinds[uid] != "separator"]
    overlap_votes = [
        {"unit_id": uid, "state": "claim", "label": None, "role_ref": None,
         "rationale": "demo mechanical claim"}
        for uid in entry["overlap_ids"] if kinds[uid] != "separator"]
    visible = entry["overlap_ids"] + entry["core_ids"]
    grouping = [
        {"left_unit_id": left, "right_unit_id": right, "grouping": "separate",
         "rationale": "demo mechanical pair"}
        for left, right in zip(visible, visible[1:])
        if kinds[left] != "separator" and kinds[right] != "separator"]
    child = {
        "schema_version": "slice-proposals/1", "slice_id": entry["slice_id"],
        "input_sha256": entry["input"]["sha256"], "assignments": assignments,
        "overlap_votes": overlap_votes, "grouping_votes": grouping,
        "boundary": {"left": "clear", "right": "clear"},
    }
    with open(f"children/{index:04d}.json", "wb") as fh:
        fh.write(json.dumps(child, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=False).encode("utf-8"))
PY

CHILD_ARGS=()
for f in children/*.json; do CHILD_ARGS+=(--proposal "$f"); done
python3 "$PRZ" proposal-reconcile --captures sliced-captures \
  --slices slices/manifest.json "${CHILD_ARGS[@]}" \
  --out merged-sliced.json --report-out reconciliation.json >/dev/null

SEAL_ARGS=()
for f in children/*.json; do SEAL_ARGS+=(--slice-proposal "$f"); done
python3 "$PRZ" assemble --captures sliced-captures --proposals merged-sliced.json \
  --out sliced-registry.json >/dev/null
python3 "$PRZ" validate --registry sliced-registry.json --captures sliced-captures \
  --report-out sliced-report.json >/dev/null
python3 "$PRZ" manifest --captures sliced-captures --slices slices/manifest.json \
  "${SEAL_ARGS[@]}" --reconciliation reconciliation.json \
  --proposals merged-sliced.json --registry sliced-registry.json \
  --report sliced-report.json --out sliced-manifest.json >/dev/null
python3 "$GCZ" check --manifest sliced-manifest.json --base-dir . \
  --require-sliced > sliced-gate-report.json

python3 - <<'PY'
import json

sealed = json.load(open("sliced-manifest.json"))
slices = json.load(open("slices/manifest.json"))
gate = json.load(open("sliced-gate-report.json"))
assert sealed["schema_version"] == "claim-run-manifest/2"
assert sealed["labeling"]["mode"] == "sliced"
assert sealed["proposals"] == [{
    "path": sealed["labeling"]["merged"]["path"],
    "sha256": sealed["labeling"]["merged"]["sha256"],
}]
assert len(slices["slices"]) > 1, len(slices["slices"])
assert any(s["overlap_ids"] for s in slices["slices"])
assert gate["valid"] is True, gate["errors"][:3]
assert gate["permission"]["complete_registry_claims"] is True
ids = {c["id"] for c in gate["checks"]}
for cid in ("manifest.sliced_required", "sliced.reconcile_replay.merged",
            "sliced.reconcile_replay.report", "sliced.registry_match",
            "sliced.payload_replay", "sliced.units_replay"):
    assert cid in ids, cid
print(f"sliced PASS: {len(slices['slices'])} slices / "
      f"{len(sealed['labeling']['inputs'])} children; /2 replay verified")
PY

# --require-sliced must reject the legacy /1 manifest from the section above
if python3 "$GCZ" check --manifest run-manifest.json --base-dir . \
    --require-sliced >/dev/null 2>&1; then
  echo "E2E: --require-sliced accepted a legacy /1 manifest" >&2
  exit 1
fi
echo "gate-check PASS: --require-sliced rejects the legacy /1 manifest"

# --- census smoke (optional artifact) --------------------------------------
if [ -f "$CZ" ] && command -v git >/dev/null 2>&1; then
  mkdir -p cenrepo && cd cenrepo
  git init -q
  git config user.email demo@example.com
  git config user.name demo
  printf 'one\ntwo\n' > f.txt
  git add f.txt && git commit -qm one
  BASE="$(git rev-parse HEAD)"
  printf 'one\nTWO\nthree\n' > f.txt
  git commit -qam two
  SUB="$(git rev-parse HEAD)"
  python3 "$CZ" run --repo . --base "$BASE" --subject "$SUB" --out "$WORK/census.json" >/dev/null
  python3 "$CZ" check --census "$WORK/census.json" --repo . >/dev/null
  echo "census PASS: run + check reproducible on a temp repo"
  cd "$WORK"
fi

echo "E2E PASS"
