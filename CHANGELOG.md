# Changelog

## Unreleased (working tree)

### v0.4.0 — quality lens (stage 4): maintainable shape, suite strength, consistency

**kernel/**
- NEW `references/quality-lens.md` — one V3-owned advisory lens `quality` with four sub-checks: `tree` (big decision trees that outgrew their shape — long if/else-if chains, switches, deep nesting, boolean-encoded state — with a which-pattern-fits-the-vibe judgment: table-driven/functional, state machine, guard clauses, polymorphism), `test` (coverage-without-assurance; residual suite strength only — a demonstrated gap links to V1/V2 instead), `error` (error-handling consistency), `dupe` (duplication vs the repo's own abstractions). Taste lens: **no repo-config/tool gate** — best absolute judgment on the pinned head, per-hit operator/developer pushback via existing suppression + closure machinery.
- Severity is rated by the **scale of the quality problem itself**, independent of product criticality: LOW default, MED only when the problem's own scale is material, never HIGH, suggestion-only, lens-trail routing.
- `hygiene-lens.md` — family-table row for `quality`; mechanical-preflight rules explicitly scoped to `type`/`dead` only (taste lenses have no config/tool gate); MED exception wording for quality alongside the reachable-`dead` exception.
- `debt-pass.md` — V3 owns `quality`; routing priority (correctness/observability → V2, concrete future-change cost → debt finding, residual advisory → quality); every V3 split records `tree`/`test`/`error`/`dupe` as hit / NOT-A-HIT / n/a-with-reason.
- `pipeline-model.md` + `intake-and-scope.md` — matrix row `quality | v3 split | no | lens`; advisory-severity rule; split + manifest examples.
- `evidence-format.md` + `finding-schema.json` — `quality` added to lens / lens-checked enums (backward-compatible; reserved `test`/`security` slots untouched).
- `child-pass-prompt-template.md` — lens checklist dispatch by owning reference (hygiene-lens.md vs quality-lens.md).
- `SKILL.md` + `BOOTSTRAP.md` + `README.md` — reference lists + lens mention. NO KICKOFF change (not an optional pass).

Background: operator direction "augment Vector 3 with a code quality lens", refined to big decision trees first (rewrite-to-maintainable-pattern judgment), then extended with test strength / error consistency / duplication; design checked by the code-review agent (sound; routing priorities vs V1 Tests surface, V2 test integrity, and V3-debt findings adopted).

### v0.3.0 — optional yagni pass (stage 3.5): size/YAGNI challenge

**kernel/**
- NEW `references/yagni-pass.md` — optional, operator-enabled pass (intake checkbox or on-demand after the Vector 3 gate); runs post-handoff in a fresh context on the same pinned manifest. Grounded, not blind: reads CONTRACT + PR context + V1-V3 findings as leads, never proof. Splits by **distinct functionality unit** (reusing the vectors' contract-surface / sealed-concept partition), one parallel child per unit — no line-count trigger. Owns the `yagni` lens (size-weight is an assessment dimension); LOW default, MED ceiling, non-blocking, routes to the lens trail; contracted scope out, pure-unused surface links to `dead`.
- `pipeline-model.md` — optional-pass section, `yagni` matrix row, active-lens clause (skipped pass deactivates its lens, matrix shows `off`, exempt from coverage assertion), when-NOT bullet.
- `SKILL.md` — reference list + phase diagram + operating rule (optional passes are opt-in).
- `evidence-format.md` + `finding-schema.json` — `yagni` added to vector/lens enums (backward-compatible widening); severity + routing notes for yagni rows.
- `BOOTSTRAP.md` fetches `yagni-pass.md`; `KICKOFF.md` gains the yagni checkbox + fleet group; README + CHANGELOG updated.

Background: operator seed "challenge/justify the physical size in lines changed… candidates for YAGNI" becomes a first-class optional pass; design checked by code-review agent (premise sound, adjusted: one `yagni` lens, leads-not-proof, unit-based split).

### v0.2.0 — lens dimension (stage 3): code-hygiene family forced on every PR

**kernel/**
- NEW `references/hygiene-lens.md` — the lens concept (owner + checklist + route + determinism hint), the code-hygiene family (`type`, `dead`, `read`, `name`), deterministic preflight (run the repo's own strict tsc/lint on the pinned head, never install), and the lens trail routing (detection mandatory, LOW default, operator-suppressible per hit).
- `pipeline-model.md` — adds the lens dimension as cross-cutting: per-lens coverage is a preflight assertion (lens matrix in the run frame, lens without owner blocks the run).
- `implementation-pass.md` — owns the `read` lens; reconciles the old "no style nits" rule: hygiene findings route to the lens trail (detected, never unrouted noise in bug findings).
- `debt-pass.md` — co-owns `dead`/`read`/`name`; a dead feature is future-change cost, its default question.
- `intake-and-scope.md` — Phase 0 compiles + validates the lens matrix; deterministic preflight scheduled for `type`.
- `closure-verification.md` — lens hits close like other findings; non-fix closures don't flip `lens-checked`.

**assets / docs**
- `finding-schema.json` + `evidence-format.md` — optional `lens` and `lens-checked` fields (backward compatible).
- `BOOTSTRAP.md` — fetches `hygiene-lens.md` in the raw kernel list; README + OPEN-ISSUES updated.

Background: this family (dead variables, strict-tsc, readability) was previously surfaced only operator-driven; the lens dimension makes detection mandatory and provable per lens.

### v0.1.0 — initial pipeline

First pass of the cure-light PR review pipeline as a standalone repo, modeled on PhormOS:

**kernel/**
- Skeletons a three-vector review method (conformance / implementation / debt), a pinned-commit manifest, an intake/contract phase, and a closure re-review loop.
- Pass contracts define the per-vector fleet split, child prompt contract, evidence return format, origin classification, and disposition rules.
- Evidence format standardizes findings, severities, statuses (incl. `closed-by-operator` and `deferred-decision`).

**libs/pi-driver/**
- Requirements check for pi runtimes (gh auth, repo, PR OID, checkout-at-head, notebook, fleet groups, diff, optional chunkhound).
- Notebook plan contract: `pipeline-frame-<owner>-<pr>`, findings page, decisions page; coordinator-owns writes; seal-then-handoff.

**templates/assets/docs**
- KICKOFF.md intake template, finding-schema.json, child-pass-prompt-template, example-review (PR #27 worked run), OPEN-ISSUES.md.

Known limitations at v0.1:
- Auth-aware/null-cache derivation deferrals are documented in OPEN-ISSUES, not silently tolerated.
- Fleet group requirement is tolerant (inherit-parent fallback) but semantically changes the run; prefer single-pass without the plugin.
- Bootstrap manifest raw URLs resolve against `main`.

### Roadmap (draft)
- Force `checkout == head` as a hard preflight check (currently recommended, not enforced).
- Option/batch pipeline runs for low-traffic PRs.
- Auto-draft as explicit "strict gate" mode for trusted repos.