# conformance-pass.md — Vector 1: contract vs code

**Question:** does the code deliver what the PR description + linked issue (incl. locked decisions) claim?

**Fleet group:** `flash`. **Stance:** *prove every stated behavior and compatibility claim; cite evidence; do not redesign.*

## Split

By **contract surface**, not by file. One child per surface (adjust to the PR's shape):

1. **Derivation core** — the pure computation (common/supported/effective sets): intersection/union algebra, reasoning fusion, ordering, vocabulary.
2. **Persistence / schema guard** — persisted fields, versioning, migration, opaque-key preservation, capping.
3. **Spawn / router / schema** — new tool params, fail-early gate, error semantics, reachability.
4. **Main-session + TUI** — prompt injection format, editor flow, warnings, display.
5. **Tests** — which contract-mandated behaviors are actually under test, and which claims rely on tests that don't exercise them.

Each child receives: the CONTRACT.js slice for its surface, the assigned file list, the focused diff, and this stance.

## Child return format (compact, evidence-bound)

```text
VERIFIED: <contract clause> → <file:line> — conforms
GAP: <contract clause> → <code reality> — what diverges (file:line)
NONE: <surface> — no gaps found
```

- GAPs must show a concrete divergence (missing backing, contradiction, or overstatement), not a style opinion.
- Verdict per surface; a surface with no gap says so explicitly.

## Aggregation

The coordinator deduplicates findings into a **claim × implementation/test matrix**: every contract claim listed, marked `backed` / `unbacked` / `contradicted`, with evidence. Unresolved claims become findings rather than assumptions.

## Failure to avoid

- **Paraphrased contracts.** Children must compare against the verbatim locked decisions, not a summary.
- **Over-claiming from tests.** "Tested" ≠ "true" if the test fixture doesn't match the real system (mock-reality mismatch is itself a finding).
- **No-op findings.** A GAP without a concrete user-visible divergence is dropped.

## Disposition on completion

Output goes to the notebook findings page. Operator gate: proceed to Vector 2 only when Vector 1 has a clean/accepted disposition (open contract gaps don't block, but they are carried into Vector 2 as context).