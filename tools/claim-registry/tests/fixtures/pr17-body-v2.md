## Targets (what this PR is for)

**1. Vector 1 gains a second, independent obligation: code → contract.**
Before, V1 only proved claims → code (*does the code deliver what the PR says?*). Now it must also prove code → claims: **every changed unit in the diff is accounted for against the captured contract**, so a PR can no longer ship behavior the contract never declares without that surfacing. This is the "detect both ends" aim.
Mechanism: a mechanical changed-range census as the denominator; every changed leaf gets exactly one state (`EXPLAINED` / `UNCLAIMED` / `EXCLUDED` / `UNRESOLVED`); attribution edges tie ranges to claims; the coordinator validates and reconciles, the gate shows the matrix plus exception groups.

**2. Undeclared delivered behavior becomes an actionable, blocking review outcome.**
A confirmed unclaimed unit is not a statistic: it becomes a grouped Vector 1 finding the **owner must address in the PR body** — declare/justify the behavior or remove it. A declaration changes the contract, so it lands as a recapture/new state at closure. Additive schema/format support (`conformance_kind: unclaimed-delivery`, coverage refs, old-side/metadata evidence anchors, LOW default / MED material / never HIGH from absence alone, coverage totals in Summary, findings in Findings — no fourth section).

**3. Yagni stops owning coverage and refocuses on over-engineering.**
The untraceable-hunk atom and the "traceable = NOT-A-HIT" dismissal are removed — hunk accounting is V1's job now. Yagni asks the narrower question: *is the engineering used to deliver the claimed behavior justified, or over-built?* Still optional, fresh-context, non-blocking LOW/MED lens trail.

**4. Coverage state lives in the notebook.**
Coverage ledger and claim registry are coordinator-owned **paged notebook pages** — the authoritative store, no ambient scratch/global state; kept through the closure/finalization window, retired after durable snapshots. A notebook-less fallback cannot assert complete coverage.

**5. Contract adequacy (v0.5.13 continuation): designated sources, pre-V1 consistency pause, review-basis gate.**
A contract is only as good as its designated sources. In-diff spec/design material enters the contract only through an explicit pointer (PR body / linked issue / locked decision — the pointer is the trust stamp; repository convention only **interprets** a designated package, never authorizes one). Before any Vector 1 spend, a bounded within-/cross-source consistency pass compares material purpose/scope/behavior declarations; a material unresolved contradiction without explicit precedence marks the state provisionally `repair_required` and **defaults the run to pause before Vector 1** — the narrow exception is an operator-recorded, named, bounded **evidence-only Vector 1 run**. After Vector 1, completion is a **review-basis gate** (`ready` / `limited-only` / `blocked` / `unknown` plus a separate `repair_required`): accounting completeness is not by itself a continuation/readiness verdict, and `limited-only`/`blocked`/`unknown` cannot reach ordinary V2/V3 without an explicit, named operator authorization. A contract-only repair is a new review state, never an in-place reconciliation.

**Designated in-diff source (explicit pointer).** `docs/contract-adequacy-validation-plan.md`, added by the v0.5.13 commit, is explicitly designated as an in-diff claim source: the fixture-based validation plan for the contract-adequacy rules, whose F1–F10 scenario clauses are its operative content. It is authored design intent, not proof of implementation, and it is delivered by this PR.

## What changed (by file)

Two commits: `6f2a408` (v0.5.12 — code→contract accounting + yagni refocus) and `50dbaf5` (v0.5.13 — contract-adequacy rules + the validation plan); all 21 changed files are covered below.

**v0.5.12 — `6f2a408`**

**Core passes** — `kernel/references/conformance-pass.md` (two obligations, two-block child return, accounting states, reconciliation, matrix projection, blocking unclaimed delivery), `kernel/references/yagni-pass.md` (over-engineering question, `ENGINEERING: JUSTIFIED|CHALLENGED`; historical launch quote preserved).

**Pipeline + storage** — `kernel/references/pipeline-model.md`, `kernel/references/intake-and-scope.md`, `kernel/SKILL.md`, `templates/KICKOFF.md` (Phase 0.3a census → 0.3b capacity-bounded split, immutable claim registry, four completeness flags, Phase-0 gate counts/exclusions/budgets, thin/empty-contract stop), `libs/pi-driver/references/notebook-plan-contract.md` + `libs/pi-driver/references/requirements-check.md` (paged `coverage-…-s<n>`/`-p<k>` + `claims-…-s<n>` pages, closure-window retention, no-notebook fallback rule).

**Findings + schema** — `kernel/references/evidence-format.md`, `assets/finding-schema.json` (optional `conformance_kind`, `coverage_ref`, evidence `side`/`oid`/`range_or_event`; severity and comment-render rules), `assets/child-pass-prompt-template.md` (Vector 1 coverage assignment/return block, yagni coverage inputs).

**Boundaries + closure + sync** — `kernel/references/implementation-pass.md`, `debt-pass.md` (V2/V3 consume the bounded matrix projection, never census breadth), `chhound-driver.md` (symbol sweep may reuse the census; attribution ≠ correctness), `blast-lens.md`, `quality-lens.md`, `kernel/references/closure-verification.md` (new-range disclosure or explicit "V1 not re-run"), `README.md`, `BOOTSTRAP.md`, `CHANGELOG.md` (v0.5.12).

**v0.5.13 — `50dbaf5`**

**Kernel contract adequacy** — `kernel/references/intake-and-scope.md` (designated in-diff sources, immutable source pins, early source-consistency pass; repair-pause default; contract-only repair as a new review state), `kernel/references/conformance-pass.md` (`documents/specifies` delivery role, no-self-proof and witness discipline, the review-basis gate with separate `repair_required`), `kernel/references/pipeline-model.md` and `kernel/SKILL.md` (the phase order carries the consistency pause and the basis gate), `kernel/references/closure-verification.md` ("no work pulled" reconciled as "no **code** work pulled"; body-only same-OID repair opens a new state), `kernel/references/evidence-format.md` (a gate disposition, not a finding kind), `kernel/references/implementation-pass.md` and `debt-pass.md` (the V2 compiler validates only named grounded splits).

**pi-driver** — `libs/pi-driver/references/notebook-plan-contract.md` (frame/contract/claims pages record source pins, designation, consistency records and the basis; contract repair writes a new `-s<n>` set), `libs/pi-driver/references/requirements-check.md` (a notebook-less fallback cannot assert `ready`; dispositions stay separate from the bootstrap table).

**Top level + deliverable** — `assets/child-pass-prompt-template.md` (captured-sources contract, designation-aware `UNCLAIMED_CANDIDATE` check, `authorized_scope` slot for V2/V3), `templates/KICKOFF.md` and `README.md` (expectation sync), `CHANGELOG.md` (v0.5.13), and the added **designated in-diff source** `docs/contract-adequacy-validation-plan.md` (F1–F10 validation scenarios).

## Decisions encoded

1. Unclaimed delivery = **blocking**, owner declares/justifies in the PR body or removes it; contract recapture at closure.
2–4. Mechanical completeness always / explicit partial acceptance; evidence-linked exclusions (never suffix rules); thin/empty contract stops planning.
5. Coverage data **in-notebook** (paged), not global scratch.
6. Pilot priority: false-coverage avoidance → unclaimed recall → cost/latency; no numeric presets in docs.
7. Contract adequacy: in-diff spec/design material is intent only under an explicit designation (PR body / linked issue / locked decision); repository convention only interprets a designated package, never authorizes one; missing designation ⇒ `repair_required` and the affected units stay unclaimed.
8. Early source-consistency pass before Vector 1: material unresolved contradiction ⇒ provisional `repair_required` + default pause (a recorded operator-authorized evidence-only V1 run is the narrow exception); non-material wording is recorded without pause. After Vector 1: review basis `ready | limited-only | blocked | unknown` with a **separate** `repair_required`; no blanket "proceed anyway".
9. A contract-only repair is a **new review state** (body-only: same subject OID, identity-checked census reuse, re-adjudicated affected claims). Docs-only spec rewrites are real deliverables (`documents/specifies` against an independent anchor); `declares` is provenance, never an EXPLAINED edge — no self-proof, no cycles.

## Verification

Independent verifier plus a narrow re-verification pass. 10 issues found (4 should-fix, 6 nits), all fixed; the should-fix set included the notebook-less fallback contradiction, the undefined `assignment_ref`, the missing "no suffix rules" clause, and coverage-page retirement vs closure. JSON valid, markdown fences balanced, invariant set preserved (3-vector identity, optional vector-shaped yagni, single writer, leads-never-evidence + `subject_oid` re-read, base-diff origin, gates, one gated comment, budgeted fleets, inconclusive ≠ pass).

The v0.5.13 continuation passed an independent read-only verification plus a narrow re-verification (2 should-fix + 2 nits fixed: intake subject-rule repull scope; the template's missing V2/V3 authorized-scope carrier; validation-plan execution scope; KICKOFF pause note), was pushed as a fast-forward, and is mechanically clean (fences balanced, `git diff --check` clean, no schema change). This description was revised 2026-09-24 to cover both commits and to carry the explicit designation above — the earlier revision omitted the added plan document, which the engine's own self-review flagged (R1 missing designation, R2 undeclared delivered artifact); the revision opens a new review state.

Out of scope (post-pilot per the approved design): census/ledger machine schema, executable fixtures/harness, scripts, claim-extraction tooling, numeric budgets. The delivered `docs/contract-adequacy-validation-plan.md` designs those fixtures; it is not the harness. `docs/example-review.md` and historical CHANGELOG entries are untouched; the 3-vector identity, one-gated-comment model, lens ownership and vector identity are preserved.
