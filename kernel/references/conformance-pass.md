# conformance-pass.md — Vector 1: contract vs changed units (both ends)

**Question:** does the delivered change match what the captured contract — PR description + linked issue (incl. locked decisions) + explicitly designated in-diff sources — claims, and is every changed unit accounted for against that contract?

**Fleet group:** `flash`. **Stance:** *prove every stated behavior and compatibility claim; account for every changed unit; cite evidence; do not redesign.*

Vector 1 owes two independent obligations:

1. **Claim adjudication** — every claim in the captured contract gets a verdict.
2. **Changed-unit accounting** — every changed range/event from the mechanical census (Phase 0.3a, intake-and-scope.md §0.3) gets exactly one final accounting state.

Neither obligation promises full semantic review: enumerated ≠ inspected ≠ explained ≠ correct ≠ adequately engineered. Enumeration and accounting are mechanically complete; semantic attribution is bounded judgment and is reported honestly when budget runs out. Both obligations run on **canonical identities**: claim IDs, counts and the registry hash are the pinned producer's values, published only when `gate-check` exits 0 with both permission flags (`finalized_unclaimed`, `complete_registry_claims`), and the claims pages are hash-checked projections of that canonical registry (intake-and-scope.md §0.2; notebook-plan-contract.md). Window/slice IDs never become claim IDs, and no coordinator or child authors, renumbers or "fixes" an ID. Without the gate permission the claim universe is incomplete: negative attribution cannot finalize, affected claims stay `UNRESOLVED`, and the state records the explicit incomplete fallback rather than a registry of record.

## Census (Phase 0.3a)

Before the split, the coordinator runs the pinned `census` unit (`run` then `check`, exact placement and gate: intake-and-scope.md §0.3a) over the two-dot `base..subject` pair. Parent units are `git diff -U0` edit blocks; deletions, renames, mode/binary/submodule changes are explicit metadata events. The artifact's canonical `census_hash`, parent/event IDs and unique-changed-line counts by side are the coverage denominator and are projected onto the state's coordinator-owned coverage pages (notebook-plan-contract.md, Coverage pages) with identical IDs/counts; the tool performs the O(D) enumeration and joins, and no agent ingests the whole diff. A `census check` mismatch or `partition.ok:false` leaves the denominator unvalidated — affected coverage cannot claim completeness.

## Split

By **contract surface first**, not by file — same pattern as before (adjust to the PR's shape: derivation core / persistence-schema / spawn-router / main-session+TUI / tests), then **capacity-bounded** within the approved budget:

- **Claim/range shards** carry one surface's claims plus the changed ranges with candidate claim links. A claim has one *verdict owner* (other shards contribute evidence); every changed leaf has one *accounting owner*.
- **Residual attribution shards** carry units with no candidate claim, packaged by path/functionality only — work packaging, never an invented contract or a new invariant.

Test claims may draw evidence from other surfaces' shards without duplicating accountability. All V1 children stay `flash`.

Each child receives: subject/base identity, its contract source slices (captured sources + designated in-diff sources with their provenance) and a queryable complete claim directory (paged — not injected wholesale), its assigned claim IDs and unit/range IDs plus input digest, exact diff slices, optional enclosing context, the scope of alternate claims it must check, budgets, and the coverage-return shape. The claim directory is usable only with the state's `gate-check` permission — the child prompt carries the pinned report ref, both permission flags and the projected `registry_hash` (child-pass-prompt-template.md) — and its claim IDs are canonical producer IDs, never local ordinals. Negative attribution requires enough claim access; otherwise the child returns the unit `UNRESOLVED`.

## Child return — two orthogonal blocks

Claim block, per assigned claim:

```text
CLAIM <claim_id> — VERIFIED: <implementation/test anchors file:line or range>
CLAIM <claim_id> — GAP: <concrete divergence: missing backing, contradiction, overstatement> (file:line / unit IDs)
CLAIM <claim_id> — INCONCLUSIVE: <what could not be decided and why>
```

Unit block, per assigned unit / leaf range:

```text
ATTRIBUTED <unit_id> → <claim_id[,…]> — role: implements | tests | necessary-support | removes/changes | documents/specifies — why: <why this change serves this clause> — anchors: <file:line / range>
UNCLAIMED_CANDIDATE <unit_id> — <delivered behavior> — checked: <claim-directory scope searched>
EXCLUSION_REQUEST <unit_id> — class: <generated | vendor | lockfile | fixture | format | …> — proof: <evidence/tool output>
UNRESOLVED <unit_id> — reason: <unread | truncated | disputed | failed | insufficient claim access>
CLOSE <assignment digest> — processed: <n>/<n> — returned: <n> — remaining: <n>
```

Always explicit: `NONE` never substitutes for accounting, and the CLOSE line closes the assigned set. The claim block feeds the matrix; the unit block feeds the coverage ledger — a unit state is a coverage record, not a finding.

Supporting infrastructure need not be named verbatim by the author, but the dependency must be demonstrated. Same filename, lexical resemblance, a broad feature slogan, mere test existence, or a claim's VERIFIED status alone cannot explain a whole hunk. A change can be *attributable yet contradict* its claim — attribution and claim satisfaction are separate axes.

### Sources declare; delivery explains (no self-proof)

A source clause defines an expected behavior for changed targets — its own bytes never verify that the behavior is implemented, nor excuse the source unit's own attribution. `declares` is a **source/provenance role** (which captured block asserts the clause), **not** an EXPLAINED edge. A changed doc/spec unit is explained only through `documents/specifies` against an **independent purpose/target anchor** — e.g. the body/issue asking to revise X to require Y, or a distinct objective in an explicitly designated package whose repo-native change-process interprets its spec deltas as the package deliverable; necessary-support needs a demonstrated dependency, never "same package". Same-unit and mutual self-ratification are prohibited: a spec cannot clear itself by existing, and two documents cannot ratify each other. A missing or disputed anchor leaves the unit `UNRESOLVED` pending clarification — never invented intent, never speculative `UNCLAIMED`. Missing **designation** is a different case: without any pointed source the affected units are `UNCLAIMED` against the captured contract with `repair_required` recorded (intake-and-scope.md §0.2); `UNRESOLVED` is for a designated source whose purpose/target anchor cannot be established.

A docs-only PR that updates the actual specification is a **real deliverable**: compare the claimed text delta with the actual version, check scope/coherence/precedence, and mark well-anchored spec units `EXPLAINED` even with no executable code change — no phantom code, no behavior claim. A design-only deliverable with no code and no promise to implement code is not automatically a GAP. Multiple roles on one unit do not multiply the denominator; claim verdict and unit attribution stay orthogonal.

## Accounting states (exactly one per changed leaf)

| State | Meaning |
|---|---|
| `EXPLAINED` | at least one validated attribution edge to a captured claim (many edges allowed) — roles `implements` / `tests` / `necessary-support` / `removes/changes` / `documents/specifies`; source provenance (`declares`) is not an edge |
| `UNCLAIMED` | inspected delivered change with no defensible clause in the *captured contract*, after the documented claim-directory check: the child returns `UNCLAIMED_CANDIDATE`, the coordinator finalizes after an alternate-surface check |
| `EXCLUDED` | explicit approved waiver of attribution (generated/vendor/whitespace bulk, …), recorded with class, exact units, evidence, producer/source linkage, rationale and policy — a path suffix alone is never sufficient |
| `UNRESOLVED` | initial / unread / truncated / disputed / failed — never quietly relabeled |

Unclaimed is **not** "no lexical match", "no owner assigned", or child silence: if contract-search breadth is inadequate, the unit stays `UNRESOLVED`. Exclusions are waivers of attribution, never assertions of correctness — lock/dependency/security changes and hand-authored behavioral fixtures stay reviewable. Unknown formats and parser errors stay `UNRESOLVED`.

## Coordinator reconciliation

1. Initialize all census units `UNRESOLVED` from the pinned census artifact; load the canonical registry projection (claim IDs/counts/`registry_hash`) **only when the state's `gate-check` report recorded exit 0 with both permission flags**, plus assignments and approved exclusions.
2. Validate each return: output OID, assignment digest, claim/unit references, range containment, a partition with no overlap/hole in the returned set, required rationale/evidence, no self-ratifying or cyclic source→deliverable edge, budget/completion. Conflicts become `UNRESOLVED`; an unrelated claim ID cannot clear a unit.
3. Merge interval edges and claim verdicts separately; route cross-surface contributions to the verdict owner; finalize `UNCLAIMED` only after the alternate attribution check — including every qualifying designated in-diff source clause; keep contradictory claim evidence visible.
4. Compute `D = EXPLAINED ⊎ UNCLAIMED ⊎ EXCLUDED ⊎ UNRESOLVED`; report counts and changed lines/events per state, exclusion classes, claim totals, noncompliant children. Claim totals compare against the canonical registry's IDs/counts/`registry_hash`, never against a locally recomputed set. Enumeration, accounting, attribution and claim conformance are four distinct flags.
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
- **Mechanical completeness sold as semantic proof** — counts prove accounting, not correctness. The producer's bytes/hashes, the `gate-check` permission and the census hash are mechanical pins, not evidence that all authorized sources were selected or that labels are semantically right.
- **Run-authored or hand-patched registry** — canonical IDs/bytes come only from the pinned producer; a coordinator-authored `registry2.py`, a hand-added claim ID or a claims page diverging from the canonical `registry_hash` is a repair-level defect, never an improvisation to acceptance.
- **False completeness without the gate** — a complete claim universe exists only under the state's `gate-check` permission; without it the affected units stay `UNRESOLVED`/incomplete and no "complete coverage" language may be used.
- **Guessed negatives** — every definitive `GAP` / `UNCLAIMED` and every basis blocker needs a concrete witness; a hunch, a high unclaimed ratio, a feature-like filename, "not clear", or the mere absence of a VERIFIED claim never decides. Check alternative attributions — including qualifying designated in-diff clauses — before finalizing.
- **Whole-diff ingestion** — no agent reads the full diff; ledger access is page/range-scoped.

## Disposition on completion

The claim matrix and coverage summary go to `pr-<n>-review` / the state's coverage pages. After the semantic verdicts and attribution reconciliation, and before the gate, the coordinator records the state's **review basis** — a planning disposition, not a finding and not a score:

- `ready` — a grounded basis supports the declared planned continuation (not "all claims VERIFIED" and not full-diff bug coverage).
- `limited-only` — a defensible bounded subset exists; the whole requested review implies unsupported scope.
- `blocked` — no worthwhile requested split exists.
- `unknown` — budget/evidence/source classification is insufficient; not an author-fault verdict and never a pass by default.

The record names the viable candidate surfaces (locked clauses, coherent expected behavior, implementation/absence anchors, material uncertainty), the **basis blockers** (requested surface, unavailable/incompatible source, affected claim IDs/findings/coverage groups, concrete witness, surviving permitted subset), the allowed next scope, and any operator disposition ref; it is bound to the state's base/subject OIDs, source versions/hashes, canonical `registry_hash` + gate report/permissions, `census_hash`, coverage hashes and V1 projection identity. A separate **`repair_required`** status records description defects and unresolved material source contradictions (provisional from Phase 0, final here) — it never computes evidence backing and is never waived by a ready basis. A provisional early-pass finding is never silently upgraded or downgraded at this gate: its witness records (conflicting quotes/offsets/source hashes/affected claim IDs) are carried as-is, and only a new review state with repaired sources can clear them.

Operator gate: Vector 2 proceeds when the basis is `ready` and no `repair_required` status is outstanding. Open gaps and unresolved units still don't block Vector 2 mechanically, but they are carried and disclosed; an accepted finding disposition never establishes readiness, and a ready basis never erases a blocking finding. `limited-only` proceeds only through an explicit, named operator authorization of the exact accepted basis, omissions, rationale, scope guard and state identity; `blocked` or `unknown` cannot proceed to ordinary Vector 2/V3 — the operator requests author repair, chooses a V1-only finish (findings/accounting preserved; V2/V3 recorded "not run — insufficient basis / explicit omission", never passed), authorizes a named bounded investigation, or stops. A blanket "proceed anyway" does not satisfy this gate: an override names the exact affected findings/surfaces/omissions, reason and authority, never waives truthful scope reporting, and never relabels `unknown` as known, a GAP as VERIFIED, or an unclaimed unit as explained. Mechanical completeness is always required for a complete coverage claim; valid `UNRESOLVED` units require explicit operator acceptance (extend / partial-review / stop).
