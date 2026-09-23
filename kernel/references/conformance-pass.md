# conformance-pass.md — Vector 1: contract vs changed units (both ends)

**Question:** does the code deliver what the PR description + linked issue (incl. locked decisions) claim — and is every changed unit accounted for against that contract?

**Fleet group:** `flash`. **Stance:** *prove every stated behavior and compatibility claim; account for every changed unit; cite evidence; do not redesign.*

Vector 1 owes two independent obligations:

1. **Claim adjudication** — every claim in the captured contract gets a verdict.
2. **Changed-unit accounting** — every changed range/event from the mechanical census (Phase 0.3a, intake-and-scope.md §0.3) gets exactly one final accounting state.

Neither obligation promises full semantic review: enumerated ≠ inspected ≠ explained ≠ correct ≠ adequately engineered. Enumeration and accounting are mechanically complete; semantic attribution is bounded judgment and is reported honestly when budget runs out.

## Census (Phase 0.3a)

Before the split, the coordinator runs the mechanical changed-range census over `base..subject` (exact recipe, placement and gate: intake-and-scope.md §0.3). Parent units are `git diff -U0` edit blocks; deletions, renames, mode/binary/submodule changes are explicit metadata events. The full inventory — total parents/events and unique changed lines by side — is the coverage denominator and is persisted to the state's coordinator-owned coverage pages (notebook-plan-contract.md, Coverage pages); scripts perform the O(D) enumeration and joins, and no agent ingests the whole diff.

## Split

By **contract surface first**, not by file — same pattern as before (adjust to the PR's shape: derivation core / persistence-schema / spawn-router / main-session+TUI / tests), then **capacity-bounded** within the approved budget:

- **Claim/range shards** carry one surface's claims plus the changed ranges with candidate claim links. A claim has one *verdict owner* (other shards contribute evidence); every changed leaf has one *accounting owner*.
- **Residual attribution shards** carry units with no candidate claim, packaged by path/functionality only — work packaging, never an invented contract or a new invariant.

Test claims may draw evidence from other surfaces' shards without duplicating accountability. All V1 children stay `flash`.

Each child receives: subject/base identity, its contract source slices and a queryable complete claim directory (paged — not injected wholesale), its assigned claim IDs and unit/range IDs plus input digest, exact diff slices, optional enclosing context, the scope of alternate claims it must check, budgets, and the coverage-return shape. Negative attribution requires enough claim access; otherwise the child returns the unit `UNRESOLVED`.

## Child return — two orthogonal blocks

Claim block, per assigned claim:

```text
CLAIM <claim_id> — VERIFIED: <implementation/test anchors file:line or range>
CLAIM <claim_id> — GAP: <concrete divergence: missing backing, contradiction, overstatement> (file:line / unit IDs)
CLAIM <claim_id> — INCONCLUSIVE: <what could not be decided and why>
```

Unit block, per assigned unit / leaf range:

```text
ATTRIBUTED <unit_id> → <claim_id[,…]> — role: implements | tests | necessary-support | removes/changes — why: <why this change serves this clause> — anchors: <file:line / range>
UNCLAIMED_CANDIDATE <unit_id> — <delivered behavior> — checked: <claim-directory scope searched>
EXCLUSION_REQUEST <unit_id> — class: <generated | vendor | lockfile | fixture | format | …> — proof: <evidence/tool output>
UNRESOLVED <unit_id> — reason: <unread | truncated | disputed | failed | insufficient claim access>
CLOSE <assignment digest> — processed: <n>/<n> — returned: <n> — remaining: <n>
```

Always explicit: `NONE` never substitutes for accounting, and the CLOSE line closes the assigned set. The claim block feeds the matrix; the unit block feeds the coverage ledger — a unit state is a coverage record, not a finding.

Supporting infrastructure need not be named verbatim by the author, but the dependency must be demonstrated. Same filename, lexical resemblance, a broad feature slogan, mere test existence, or a claim's VERIFIED status alone cannot explain a whole hunk. A change can be *attributable yet contradict* its claim — attribution and claim satisfaction are separate axes.

## Accounting states (exactly one per changed leaf)

| State | Meaning |
|---|---|
| `EXPLAINED` | at least one validated attribution edge to a captured claim (many edges allowed) |
| `UNCLAIMED` | inspected delivered change with no defensible clause in the *captured contract*, after the documented claim-directory check: the child returns `UNCLAIMED_CANDIDATE`, the coordinator finalizes after an alternate-surface check |
| `EXCLUDED` | explicit approved waiver of attribution (generated/vendor/whitespace bulk, …), recorded with class, exact units, evidence, producer/source linkage, rationale and policy — a path suffix alone is never sufficient |
| `UNRESOLVED` | initial / unread / truncated / disputed / failed — never quietly relabeled |

Unclaimed is **not** "no lexical match", "no owner assigned", or child silence: if contract-search breadth is inadequate, the unit stays `UNRESOLVED`. Exclusions are waivers of attribution, never assertions of correctness — lock/dependency/security changes and hand-authored behavioral fixtures stay reviewable. Unknown formats and parser errors stay `UNRESOLVED`.

## Coordinator reconciliation

1. Initialize all census units `UNRESOLVED`; load claims, assignments, approved exclusions.
2. Validate each return: output OID, assignment digest, claim/unit references, range containment, a partition with no overlap/hole in the returned set, required rationale/evidence, budget/completion. Conflicts become `UNRESOLVED`; an unrelated claim ID cannot clear a unit.
3. Merge interval edges and claim verdicts separately; route cross-surface contributions to the verdict owner; finalize `UNCLAIMED` only after the alternate attribution check; keep contradictory claim evidence visible.
4. Compute `D = EXPLAINED ⊎ UNCLAIMED ⊎ EXCLUDED ⊎ UNRESOLVED`; report counts and changed lines/events per state, exclusion classes, claim totals, noncompliant children. Enumeration, accounting, attribution and claim conformance are four distinct flags.
5. Retry/reslice bounded failures within budget; otherwise the gate offers the operator: extend budget, accept explicitly partial review, request richer contract / smaller PR, or stop.
6. Ledger detail is validated and materialized by coordinator scripts into the coverage pages; the gate shows the compact claim matrix plus coverage summary and exception groups — not full hunk returns.

## Artifacts

- **Claim × implementation/test matrix** — the semantic product: every claim marked `backed` / `unbacked` / `contradicted` with evidence, claim IDs and small coverage refs/counts.
- **Coverage ledger** — per-unit states, attribution edges, ranges, exclusions, recipe: coordinator-owned notebook coverage pages (notebook-plan-contract.md) — never scratch files, never rendered whole at the gate.
- **V2 projection** — Vector 2 consumes a paged, bounded **matrix projection**: adjudicated claims/invariants with anchors and the relevant coverage refs and uncertainty — not the ledger bulk.

A thin or empty contract stops deeper planning at the gate: request author scope, or run an explicitly limited V1-only review; never fabricate a claim or silently launch an open-ended file sweep. Unclaimed units are disclosed as accounting, not automatically bug-reviewed or declared wrong.

## Aggregation

Claims deduplicate into the matrix. Confirmed unclaimed delivery is **V1 in-scope conformance** and **blocking** — grouped into one bounded finding per coherent missing scope declaration (representative subject/base anchors, exact group counts, unit selector/hash) with `conformance_kind: unclaimed-delivery`. Remedy: the owner declares/justifies the delivered behavior in the PR description or removes it — a declaration changes the captured contract, so it lands as a closed/new state (closure-verification.md), never silent rewriting. An operator-approved waiver stays `UNCLAIMED` with its resolution recorded, never fake claim coverage.

Severity: `LOW` default; `MED` only for material undeclared behavior/API/operational commitment with an articulated review or compatibility consequence — never merely many lines, never `HIGH` from absent declaration alone. Independent current harm routes to Vector 2. Groups beyond the output cap are disclosed with counts, never silently dropped.

Claim gaps keep their concrete divergence; the old "GAP without a user-visible divergence is dropped" rule is retired. For `unclaimed-delivery` the concrete failure is *delivered behavior absent from the captured declared scope*, evidenced by unit/contract IDs plus the attribution audit — no runtime failure is invented, and unclaimed ≠ wrong/over-engineered. Deletion and metadata findings carry explicit anchors `{side, oid, path, range_or_event}` plus the checked subject absence or surviving anchor.

## Failure to avoid

- **Paraphrased contracts** — compare against verbatim locked decisions, never a summary.
- **Unaccounted units** — an absent unit or digest mismatch stays `UNRESOLVED`; retries within cap; never inferred from a sibling.
- **False coverage from a broad slogan** — exact range edges, role + rationale, separate satisfaction, split mixed parents.
- **Over-claiming from tests** — "tested" ≠ "true"; mock-reality mismatch is itself a finding.
- **Mechanical completeness sold as semantic proof** — counts prove accounting, not correctness.
- **Whole-diff ingestion** — no agent reads the full diff; ledger access is page/range-scoped.

## Disposition on completion

The claim matrix and coverage summary go to `pr-<n>-review` / the state's coverage pages. Operator gate: proceed to Vector 2 when Vector 1 has a clean or explicitly accepted disposition — open gaps and unresolved units don't block Vector 2 mechanically, but they are carried into it and disclosed. Mechanical completeness is always required for a complete coverage claim; valid `UNRESOLVED` units require explicit operator acceptance (extend / partial-review / stop).
