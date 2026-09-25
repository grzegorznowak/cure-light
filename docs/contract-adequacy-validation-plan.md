# contract-adequacy-validation-plan.md — fixture-based validation of the contract-adequacy gates

> Design artifact for the contract-adequacy rules drafted in `kernel/references/intake-and-scope.md` §0.2/§0.4,
> `conformance-pass.md` (§Sources declare, §Disposition), `closure-verification.md` (§1, §Coverage in closure),
> `implementation-pass.md` (split compile) and `pipeline-model.md` §10. Frozen terminology: `review_basis = ready | limited-only | blocked | unknown`,
> separate `repair_required`; early "source-consistency pass"; "evidence-only V1 run" (operator-recorded, named, bounded); source role `declares`
> versus delivery roles `implements | tests | necessary-support | removes/changes | documents/specifies`.

## Harness status

The repo ships **no F1–F10 campaign harness**: no CI config and no build/test manifest for the validation scenarios.
The pilot tool units under `tools/` (`claim-registry`, `gate-check`, `census`) ship with their own unit/E2E tests and a
built-artifact demo, but this plan remains the deliverable for the scenarios; F1–F10 fixtures become executable only
when the campaign harness is built — the implementation checkpoint in the converged direction §8.

## Scenarios (F1–F5)

### F1 — Stamped in-diff spec happy path
- **Rule**: intake-and-scope.md §0.2 (designation + pinning); conformance-pass.md §Sources declare; implementation-pass.md split compile.
- **Setup**: synthetic target repo; the PR body explicitly designates an openspec-style package changed in the diff; one `specs/**/spec.md` delta clause defines expected behavior; a code unit in the same diff implements it.
- **Assert**: the package is captured with designating pointer + blob OID/hash/spans; the code unit is `ATTRIBUTED implements` → the clause and VERIFIED on independent evidence; the spec unit is `EXPLAINED` only via `documents/specifies` + an independent purpose/target anchor; `declares` is provenance, never an edge (no self-proof); no unit `UNCLAIMED`.
- **Expected**: `source_consistency: clean`; `review_basis: ready`; no `repair_required`; the V2 compiler accepts the named invariant and planning proceeds.
- **Guards against**: a false repair stop — penalizing a short body or demanding reviewer re-derivation of intent the explicit designation already supplies; self-ratifying spec units.

### F2 — Un-stamped spec lookalike
- **Rule**: intake-and-scope.md §0.2 ("convention interprets, never authorizes"); conformance-pass.md negative-attribution rules.
- **Setup**: the diff changes a spec-looking file (`specs/…`, `design/…`, behavior-describing prose) that **nothing points at**; code in the same area also changes.
- **Assert**: no claim IDs are compiled from the lookalike; affected code/spec units are not attributed or explained through it; the alternate-attribution check runs against the complete designated registry; no reviewer-invented claim appears; missing designation/orientation records `repair_required`.
- **Expected**: `repair_required` records the missing-designation reason; the affected units keep their evidenced accounting state (no invented edge); the reviewer never invents a claim to clear code.
- **Guards against**: convention-as-authority (openspec/ADR layout granting source status), and clearing real code with an unpointed doc or a reviewer-supplied claim. **Asserted boundary**: the affected units are `UNCLAIMED` against the captured contract (never explained through the lookalike or a reviewer-invented claim) with `repair_required` recorded; `UNRESOLVED` is reserved for a designated source whose purpose/target anchor cannot be established. The missing-designation defect defaults to the repair pause before V1, with an explicit limited V1-only review as the operator alternative (intake-and-scope.md §0.2/§0.4; conformance-pass.md §Sources declare).

### F3 — Material cross-source contradiction → pause before V1
- **Rule**: intake-and-scope.md §0.2 (early source-consistency pass) / §0.4 (Phase-0 gate); pipeline-model.md rule 10.
- **Setup (material)**: the PR body says "removes X" while a designated, pinned spec says "requires X"; no explicit/locked precedence anywhere.
- **Assert (material)**: the early pass records the contradiction with exact conflicting quotes, byte offsets, source hashes (blob OIDs / version pins) and affected claim IDs, plus a materiality witness; provisional `repair_required` is set and **no Vector 1 child is spawned**; no reviewer-resolved precedence is written.
- **Control (non-material)**: an equivalent wording-only difference ("must" vs "shall") is recorded as a defect **without** pausing.
- **Evidence-only exception**: same as material, but the operator records a named, bounded evidence-only V1 run (scope, rationale, state identity); it runs without clearing provisional `repair_required` or authorizing ordinary downstream work.
- **Expected**: `source_consistency: provisional-repair-required` with the record ref; `evidence_only_v1: none` or the operator ref + scope; author clarification or a repaired contract opens a new state.
- **Guards against**: spending V1 on an incoherent contract; reviewer-chosen winners ("spec wins"/"body wins"); a blanket override disguising a contradiction as clean.

### F4 — Repair lifecycle: body-only vs in-diff (new state)
- **Rule**: closure-verification.md §1 / §Coverage in closure; intake-and-scope.md subject rule; conformance-pass.md §Disposition.
- **Setup (body-only)**: state `s<n>` has claim verdicts and UNCLAIMED findings; the PR body is edited and no new subject OID is pulled.
- **Setup (in-diff)**: the same, but a designated spec blob changes while every executable code blob is byte-identical.
- **Assert**: both open a new review state `s<n+1>` with a recaptured contract snapshot/hash — the same subject OID for the body-only edit, a normally-new subject OID for the in-diff edit, same treatment either way; reuse is limited to identity-checked mechanical census (base/subject/recipe/unit identity); affected claim verdicts, attributions, negative searches and V2/V3 projections are re-adjudicated, not inherited; code-unchanged findings stay open unless specifically reclassified on valid new authority; prior-state evidence stays addressable at its own pins.
- **Expected**: old findings are not silently closed or flipped green; the new state's basis is recomputed.
- **Guards against**: the closure shortcut "same subject OID ⇒ no work pulled"; in-place reconciliation; green-washing unchanged code via a prose/spec edit.

### F5 — Limited-only + named override
- **Rule**: conformance-pass.md §Disposition; implementation-pass.md split compile; pipeline-model.md rule 10.
- **Setup**: V1 yields a defensible narrow subset but the whole requested review is unsupported → `review_basis: limited-only`; separately, a confirmed blocking `unclaimed-delivery` finding exists while the basis could otherwise be `ready`.
- **Assert**: the default is no ordinary V2/V3; a blanket "proceed anyway" is refused and elicits named choices (exact accepted basis, omissions, rationale, scope guard, state identity); a recorded named authorization runs only the bounded scope it names; V3/skip routes cannot expand that scope; accepting the blocking finding does not make the basis `ready`; a `ready` basis does not erase the blocking finding.
- **Expected**: the limited run proceeds only under the recorded authorization; basis and findings stay independent.
- **Guards against**: scope laundering through generic debt axes or a late vector; "accepted finding = readiness"; "ready = blocker gone".

## Supplementary fixtures (one-liners; from direction §5 pilot list)

| # | Fixture | Asserted classification |
|---|---|---|
| F6 | synth18 replay: contradictory body/title + unpointed kernel docs | material contradiction caught pre-V1; `limited-only`/`blocked` after V1 — never ordinary continuation |
| F7 | self-ratifying / mutually ratifying docs | no source→deliverable edge is accepted; the units stay unexplained |
| F8 | docs-only spec rewrite with an independent anchor | spec units `EXPLAINED` as a real deliverable; no phantom code or behavior claim; no forced code invariant |
| F9 | stale body rescued by a locked issue, and the inverse (half-assed body + authoritative package) | basis follows grounded sources; the description defect still records `repair_required` |
| F10 | generated bulk + large `UNRESOLVED` residue | `EXCLUDED` only with evidence-linked policy; residue `UNRESOLVED`, basis `unknown` — not speculative `UNCLAIMED` |

## Later execution (when the pilot tooling exists)

Each fixture is exercised as a **synthetic target repo** (base commit → subject commit + a PR body/issue/locked-decision stub) plus **scripted
Phase-0 inputs** (frame/manifest with contract-source pins and the Phase-0 gate decision), driving the pipeline only up to the gate under test
(Phase 0 for F3, a V1 run up to the gate for F1–F2, the state transition for F4, the V1 gate for F5). Assertions read classifications from run records — the manifest fields
`contract_sources` / `source_consistency` / `review_basis`, the claim registry, coverage states per unit, and spawn decisions — not prose:

- source capture: designation pointer, blob OIDs/hash, normative/advisory interpretation (F1, F2);
- consistency: contradiction-record completeness (quotes/offsets/hashes/claim IDs) and the material-vs-non-material class (F3);
- attribution/accounting: role enums, edge presence/absence, per-unit states, `UNRESOLVED` vs `UNCLAIMED` (F2, F4, supplementary);
- state identity: new state id + pins on repair, census-reuse scope (F4);
- gate output: `review_basis`, `repair_required`, blockers, V2 child spawn (F1, F3, F5).

**Assertion granularity is classification outcomes** — enums, IDs, counts, edge presence, spawn/no-spawn. A fixture passes on the expected
classification with the forbidden alternative asserted absent; no snapshot diffs of comment prose, no LLM-judged text similarity, no numeric
threshold baked in here. Each fixture must also assert at least one **negative** outcome (the wrong state/edge/spawn does not occur), so a run
that "passes by accident" on wording cannot pass the fixture.

## Scope note

This plan changes no pipeline code and commits to no numeric budgets; the pilot budget and acceptance criteria remain an operator checkpoint
(direction §8) — the fixtures only pin the classification behavior the drafted rules promise.
