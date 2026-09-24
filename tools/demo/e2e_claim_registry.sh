#!/usr/bin/env bash
# Deterministic end-to-end demo: built claim-registry + gate-check (+ census)
# artifacts, exercised exactly as the coordinator agent would run them.
#
# Usage: demo/e2e_claim_registry.sh [pr-body.md]
# Default fixture: claim-registry/tests/fixtures/pr17-body-v2.md (fallback /tmp).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PR_BODY="${1:-}"
if [ -z "$PR_BODY" ]; then
  for candidate in "$ROOT/claim-registry/tests/fixtures/pr17-body-v2.md" /tmp/pr17-body-v2.md; do
    if [ -f "$candidate" ]; then PR_BODY="$candidate"; break; fi
  done
fi

PU="$ROOT/claim-registry"
GU="$ROOT/gate-check"
CU="$ROOT/census"
PRZ="$PU/dist/claim-registry-0.2.0.pyz"
GCZ="$GU/dist/gate-check-0.1.0.pyz"
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
