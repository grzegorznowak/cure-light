# blast-lens.md — the `blast` lens: data × call-site blast radius

A diff and a legacy row each look harmless alone; only their interaction is the
incident. Vector 2 owns one always-active advisory lens, **`blast`**, that forces
the question the diff alone cannot answer:

> **What existing data and call sites will meet this change — and is the
> hazard's instance proven?**

The lens is **not hygiene** — nothing in it is style or unused surface. It is
the data-facing half of "does the shipped code actually work safely?", and it
routes differently from the rest of the family: its **rows are advisory, its
instance is a finding** (see Routing).

## Owner and activation

- **Owner:** the Vector 2 split (all five rows) plus the **deterministic
  preflight sweep** for the `sweep` row's mechanical part. A lens without an
  owner is a frame error (hygiene-lens.md).
- **Activation:** always active whenever Vector 2 runs. A data-free diff records
  one whole-lens `n/a`; a Vector-1-only run leaves it inactive (`off` in the
  matrix — the coverage assertion binds active lenses only, pipeline-model.md).
- **Trail discipline:** every split records each row as `hit` / `NOT-A-HIT` /
  `n/a-with-reason` — compact per-row trail, so checklist execution is provable,
  not just the lens (same discipline as `quality`, quality-lens.md).

## The five rows

| Row | Checklist (hit = cite file:line) | Dismiss (NOT-A-HIT) | Determinism |
|---|---|---|---|
| `data` | the changed behavior depends on state the PR does not create — legacy / orphan rows, dangling refs, NULL / empty / anonymous state, zero-value sentinel rows; name the concrete data state that reaches it | the surface is new or self-contained: no pre-existing rows or consumers can reach it | low — entry points are findable; the reachability call is judgment |
| `sweep` | a changed shared sentinel / constant / default: every consumer must be enumerated **in this PR**; a call site named as deferred ("follow-up ticket") or simply uninspected = hit | the sweep ran and returns only diff-local use (cite the sweep) | **high** — literal/symbol sweep with the repo's own tooling (`rg` in the subject tree, or the rail's `search` when `research.mode: chhound-rail`); always available, never installs |
| `semantics` | a comparison where the language's value model differs from the storage engine's (e.g. empty string vs a numeric column): the column type and the engine's own meaning are checked at the site | the comparison is proven type- and engine-consistent (cite the column / schema definition) | medium — schema definitions are findable; the meaning call is judgment |
| `fixture` | a hazard whose trigger is a **single artificial row/state** is being adjudicated on inspection alone → the requirement is a fixture test that reproduces it on the repo's own scratch database | no artificial-state trigger exists, or the PR already ships the reproducing fixture | low (judgment) — the repo's own harness runs the test; the fleet never installs or executes a database |
| `gates` | a "this class is statically detectable" claim where the analyzer / lint gate is **not enabled** in the repo's own config or CI — a dormant analyzer is not a net | no static-detectability claim is made, or the gate is enabled and cited | medium — read the repo's CI + analyzer config; no installs |

Reading finds the hazard **class**; only a fixture proves the **instance**. The
`fixture` row is a row here, not the reserved `test` schema slot — the slot
stays available for a future dedicated test-adequacy lens.

## Routing: advisory rows, blocking findings

- **Rows → lens trail.** LOW by default, MED when the problem's own scale is
  material, **never HIGH**; suggestion-only, operator-suppressible per instance,
  notebook-only. They never enter the bug/debt table and never the comment
  (evidence-format.md, External routing).
- **The concrete instance → the bug table.** A named query / comparison site
  that breaks for a named existing data state is a **Vector 2 finding** at its
  own severity (HIGH possible) with a concrete failure mode. That finding is
  what blocks; the lens only finds the class. Cross-cutting rule 1 holds
  unchanged: **a lens never blocks vector gating by itself** (hygiene-lens.md).
- **A PR deferring its own call-site sweep is in scope.** The PR introduced or
  enforced that path, so the deferred call sites route to **Findings, to be
  addressed** — never auto-downstreamed (evidence-format.md, Scope routes the
  comment). The `sweep` row links to that rule instead of restating it.

## Determinism

The `sweep` row is the lens's mechanical part: a literal/symbol sweep over the
subject tree with the repo's own tooling, cited verbatim like the `type` / `dead`
preflight, and always available (a repo without a rail uses `rg`). `semantics`
and `gates` are reads of files that exist on the subject tree (schema /
migration definitions, CI and analyzer config). `data` and `fixture` are fleet
judgment. A sweep that cannot run marks the lens `inconclusive-mechanical` in
the trail (evidence-format.md) — never a silent skip. The matrix renders the
lens as `partial` (only some rows have a mechanical accelerator).

Sweep rules follow the hygiene preflight (hygiene-lens.md) — the repo's own
tooling, no installs.

## Boundaries (dedupe map)

- **`dead` lens** — unused surface that never runs; `blast.data` is *existing
  data* reaching code that does run.
- **`type` / `dead` preflight** — the compiler/lint net; the `sweep` row is a
  different mechanical net (a changed literal's consumers, not unused symbols).
- **`quality.test`** — residual suite strength (vacuous assertions on tests that
  exist); `blast.fixture` names the test that does *not* exist yet for a
  discovered hazard instance.
- **V1 conformance Tests surface** — whether *contract claims* are under test
  (existence); `blast.fixture` is triggered by a hazard the review discovered,
  not by a claim.
- **V2 test integrity** — a *demonstrated* regression that stays green; the
  `fixture` row is the proof requirement for a hazard whose only evidence is
  inspection.
- **V3 debt** — repo-wide consistency and future-change cost; a repo-wide sweep
  completeness claim is V3's search-extensive territory (debt-pass.md) when the
  operator wants the extra coverage — the default owner stays V2 + preflight.
- **`quality` / `yagni`** — shape and existence of what should exist; the `blast`
  lens asks whether what exists is safe against the data already in the
  database.
