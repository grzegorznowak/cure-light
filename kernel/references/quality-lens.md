# quality-lens.md — the `quality` lens: maintainable shape, suite strength, consistency

Vector 3 owns one always-active advisory lens, **`quality`** — the stage-4
answer to "is this code built to last?" It is a **taste lens** (low
determinism): the fleet applies its best absolute judgment — never a tool, a
repo-config threshold, or a complexity metric gate — and the operator /
developer pushes back per hit. Detection is mandatory whenever Vector 3 runs:
every V3 split records each sub-check below as `hit` / `NOT-A-HIT` /
`n/a-with-reason` (compact per-row trail, so checklist execution is
provable, not just the lens).

## The four sub-checks

| Sub-check | Checklist (hit = cite file:line) | Dismiss (NOT-A-HIT) | Severity guidance |
|---|---|---|---|
| `tree` | a decision tree that outgrew its maintainable shape: long `if/else-if` chains or switches dispatching on one discriminator, deep nesting, state encoded as boolean flags. When it fits, name the pattern the logic's vibe calls for: **table-driven / strategy dispatch** (pure data-in → data-out), a **state machine** (events / phases / transitions), **guard clauses** (plain deep nesting), **polymorphism** (type dispatch) | a short chain where the alternative would be more complex; a shape that already matches a better pattern | LOW for a wart; **MED when the tree is material at its own scale** (large, or this PR grew it a lot) |
| `test` | coverage-without-assurance — *residual suite strength / maintainability*: vacuous assertions, tests too weak to fail if the code were broken (hypothetical weakness; a *demonstrated* regression that stays green → V2). Claim-not-under-test gaps — skipped/disabled tests, happy-path-only where the contract has failure paths, mock-reality mismatches on contract-mandated behavior — are V1 existence gaps; link, don't duplicate | tests that genuinely pin behavior | LOW; **MED when the vacuous coverage is material at its own scale** (systemic, or a substantial share of the PR's changed behavior unpinned) |
| `error` | failure handling that diverges from the diff's own established idiom: swallowed errors, a different error vocabulary/types, missing logging where siblings log | deliberate, documented divergence; a correctness / observability failure belongs to V2; a concrete future-change cost to a V3 debt finding | LOW; **MED when inconsistent handling is widespread across the diff** |
| `dupe` | copy-paste of a shape the repo already abstracts, or a new abstraction duplicating an existing one | coincidence (same shape, different meaning); "the repo already abstracts this" is valid evidence but never a hidden style gate | LOW; **MED when duplication is systemic across the diff** |

## Routing + severity

- All hits route to the **lens trail**: suggestion-only, operator-suppressible
  per instance, closure-classifiable. Never the bug/debt table.
- **Severity is rated by the scale of the quality problem itself**, independent
  of functional / product criticality: a spaghetti tree in a payments feature is
  not elevated because payments is critical. LOW default; **MED only when the
  problem's own scale is material** (per-row guidance above); never HIGH.
- Developer pushback uses the existing per-hit suppression + closure machinery
  (evidence `note`, `closed-by-operator`); no new status.

## Determinism: judgment, not gates

`quality` is a taste lens — no mechanical accelerator, **no repo-config gate**.
The reviewer applies best absolute judgment on the subject tree; the mechanical
preflight rules in [hygiene-lens.md](hygiene-lens.md) bind only the `type` /
`dead` sweep. Evidence is file:line in the subject tree plus the base..subject
diff; origin by base-diff like every vector.

## Boundaries (dedupe map)

- **`read` lens** — local statement density (can one glance parse it?);
  `quality.tree` is the whole control-flow *shape*. A deep-nesting hit may
  qualify for both: route local density to `read`, tree-level structure to
  `quality.tree`, and link the rows.
- **V3 axis 1 (pluggability)** — an *advertised* extensibility claim the code
  does not back; `quality.tree` is structure cost *regardless of claims*. An
  unbacked claim routes to axis 1; link, don't duplicate.
- **V1 conformance Tests surface** — whether contract claims are *under test*
  (existence); `quality.test` is residual suite *strength / maintainability*
  with no demonstrated contract gap.
- **V2 test integrity** — a *demonstrable* behavioral regression that stays
  green; `quality.test` is advisory strength only.
- **`yagni` lens** — existence / size; `quality` is the shape of logic that
  *should* exist. A rewrite suggestion is not a YAGNI challenge.
