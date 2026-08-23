# Changelog

## Unreleased (working tree)

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