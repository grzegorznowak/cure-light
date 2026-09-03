# Changelog

## Unreleased (working tree)

### v0.5.5 — subject-first: no pre-subject orientation

**kernel/**
- **Subject-first rule** (SKILL.md operating rules + §2; intake-and-scope.md §0.1): no orientation or reading in the target repo's local checkouts before the subject pull — per review state (a deliberate re-pull starts a new state under the same rule). Pre-pull access is remote-only (`gh repo view` / `gh pr view` / `gh pr diff --name-only`) plus presence probes (`/ch-status`); the only pre-pull local git command is the cure-light source provenance capture. The pulled subject is the first tree cure-light reads for context or evidence.
- **Gate split** (SKILL.md phase diagram + §3; intake-and-scope.md §0.4; pi-driver SKILL step 3; notebook-plan-contract frame row; evidence-format notebook layout): the pre-pull frame gate approves the PLAN — subject mechanism (chhound sandbox | plain worktree), planned location, vectors/gates/output policy — with no tree fields yet; the Phase 0 gate records REALITY into the manifest/frame (`subject_path` / `subject_oid`, changed-file list, deferred-row outcomes). Contradictory pre-existing wording (frame gate before Phase 0 vs tree fields known only post-pull) fixed.
- `intake-and-scope.md` §0.1 — plain-worktree source policy: the detached worktree at `<scratch>/tree` is added FROM the developer's existing local clone when one exists (plumbing only — git object source; that clone's working tree is never read as context or evidence); otherwise the target repo is cloned into `<scratch>/tree` at Phase 0 and detached at the PR head — the clone is the subject. Previously undocumented.

**libs/pi-driver/**
- `requirements-check.md` — rows re-scoped and split **pre-pull vs deferred-to-Phase-0** (rows 5/8/9): row 4 = rail presence only (reachability stays row 2), outcome recorded as the **planned subject mechanism** (presence ≠ sandbox guarantee — sandbox failure falls back per chhound-driver.md); `git -C <dir> rev-parse` dropped; "clone if missing" moved to the Phase 0 pull. Row 8 = post-pull check on the pulled tree (`base_oid..subject_oid`); `gh pr diff` NEVER substitutes the subject diff (the remote head may differ from the pulled subject — that would corrupt scope/origin); fail → fetch retry, else STOP. Stop conditions moved to the pull; no early "check done", no mixing pre/post-pull results (check lifecycle closes at the Phase 0 gate).
- `SKILL.md` step 3 + `notebook-plan-contract.md` — frame at seal = frozen options + planned subject mechanism (no tree fields); `subject_path` / `subject_oid` recorded at the Phase 0 gate.

**templates / docs**
- `BOOTSTRAP.md` after-fetch steps + `KICKOFF.md` steps 2/6 — aligned to the pre-pull subset: subject-tree rows defer to Phase 0; the subject is the first tree read. §7 checkbox semantics unchanged; bootstrap paste-quote lines untouched.
- `README.md` quick-requirements paragraph — "git diff works" reworded to the deferred subject-tree rows; "subject pullable" → planned subject mechanism; subject-first note added.

Background: operator direction — a fresh boot oriented in local target-repo checkouts after intake before the subject pull, which is counterproductive when the run reviews a dedicated subject (chhound PR sandbox when the pi-chhound plugin is present, else a plain worktree). Design decided by the operator: subject-first per review state, worktree source = developer's existing clone when present (plumbing only), recommended gate split (plan approval pre-pull, reality recording post-pull), full-sweep scope incl. BOOTSTRAP/KICKOFF/README; an independent #code-review weak-spot pass on the plan had its HIGH/MED findings folded into the decisions. Draft checked by an independent #code-review facts+consistency pass before opening the PR.

### v0.5.4 — notebook-first state store (pi runs)

**kernel/**
- `intake-and-scope.md` §0.2 — the contract lives in the **run store**: when the runtime's requirements check confirms the notebook, Phase 0 writes the verbatim contract to the notebook page `contract-<owner>-<pr>` (one per review state, named like the frame); CONTRACT.md in the scratch dir is the fallback. Manifest field `contract_path` → `contract_ref` (page name | disk path); item 4 clarified — the contract stores the changed-file list; per-child diff slices are derived at spawn from the subject tree, not stored.
- `conformance-pass.md` — child intake reads the relevant contract section via the manifest's `contract_ref` (stray "CONTRACT.js" wording dropped).
- `yagni-pass.md` — reads the contract at `contract_ref`.
- `SKILL.md` — reference-list annotation aligned to the phase naming (`pull subject + contract`).

**libs/pi-driver/**
- `notebook-plan-contract.md` — page table gains the `contract-<owner>-<pr>` row (coordinator, Phase 0, one per review state) + content rule (the one long-form verbatim page; no raw diffs/logs/kernel text). Frame row stores the contract ref; a re-pull writes distinct pages, never overwriting earlier states.
- `requirements-check.md` — row-6 fallback extended: notebook missing → frame/findings in session-scratch + contract on disk.

**templates/assets**
- `child-pass-prompt-template.md` — `contract_path` slot → `contract_ref` (run-manifest field: notebook page on pi runs, disk CONTRACT slice in fallback).
- `KICKOFF.md` step 6 — wording aligned: pull the subject, compile the contract (notebook page on pi runs, CONTRACT.md otherwise).

Background: operator direction — the pi runtime has the notebook; stop building ephemeral state files (CONTRACT.md) beside the subject when the notebook is available; disk remains the fallback for runtimes without it. Kernel fetch-hold and priming unchanged: a session is primed once at boot and re-primed by starting a new boot session — no mid-run re-fetch of cure-light instructions.

### v0.5.3 — chhound research rail + subject model

**kernel/**
- NEW `references/chhound-driver.md` — the chunkhound research rail (pi-chhound plugin): when the plugin is present, Phase 0 pulls the review subject as a chunkhound **PR sandbox** (own index: base-branch baseline + PR-diff top-up), connects it over MCP with a deterministic `--prefix chh_pr<n>`, and documents the tool names (`chh_pr<n>_code_research|search|daemon_status|websearch|fetchurl`) with the mandatory **discovery-only rule** (every cited line re-read in the subject checkout; daemon_status proves health only). MCP lifecycle: one live bridge per sandbox, disconnect before connecting a fresh one; fresh sandbox per review state (unique `--dest`). Plugin absent/broken → plain worktree + git/rg, never blocks.
- **Subject model**: the tree cure-light pulls IS the review subject — whatever SHA the pull has at Phase 0 is the version reviewed (reviewing the latest is the point, not a risk); `subject_oid`/`subject_path` replace the pinned-at-intake `headRefOid` ceremony (remote head kept as informational context). The tree is stable for the whole review state; new commits enter only via a deliberate, operator-gated **re-pull** = new review state (fresh sandbox, strict transition, closure re-validates old findings against the new tree). `require_pr_head` checkout policy dropped. OPEN-ISSUES #3 (moving-head race) closed resolved-by-design.
- `evidence-format.md` + `finding-schema.json` — optional `subject_oid` field (rule-required on every new/updated row: which state's tree the evidence was read from); backward-compatible.
- `child-pass-prompt-template.md` — subject path/OID slots, chhound tool guidance block (which tool when, discovery-only, fallback never blocks).
- Consistency: pipeline-model (rule 1), closure-verification (re-pull delta last-reviewed..new), intake-and-scope (subject rule + manifest), hygiene/quality/yagni lens references, requirements-check (rows 3-5, 8-9), notebook-plan-contract (frames per state), pi-driver SKILL, KICKOFF §7 (checkout policy → chhound rail), BOOTSTRAP fetch list, README, example-review note.

Background: operator direction — integrate tightly with the pi-chhound plugin at the operational level (instruct the operator to create a `/chworktree` PR sandbox for the review and point it at it, incl. the MCP tool names) and at the prompt level (children told what the tools are and when). Surfaced the subject-model revision (review the latest pulled version, controlled pull → review → deliberate re-pull); design checked by two independent #code-review passes (state-boundary invariant, freshness honesty, MCP lifecycle, provenance field).

### v0.5.2 — finalization: one aggregated review comment

- Output drafts **one aggregated review comment** per run (Summary / Findings / "Potential follow-up issues" / footer); issues are suggested to the developer, never drafted as `gh issue` bodies.
- Intake field `auto_draft` → `draft_comment` (boolean; alias accepted). `before_post` is enforced whenever drafting is enabled; lens-trail rows are never included in the comment; `linked` reworded to `external follow-up URL | none`.
- Closure updates the review comment **in place** by default (new/changed dispositions + new head OID in the footer); a separate comment only when the operator prefers one.

### v0.5.1 — intake defaults: per-vector pauses

**templates/** + **kernel/**
- `KICKOFF.md` — §6 pause checkboxes now default to "after each vector" only; extra checkpoints (after intake / before posting / after closure) are opt-in ticks. SKILL.md intake table example updated to `[per_vector]`.
- Auto-draft policy default unchanged (`comments: false, issues: false`).

Background: operator direction — pauses should gate per vector by default; intake question clarified in plain language (auto-draft means "prepare drafts for approval", never auto-post).

### v0.5.0 — pipeline mechanics: worktree review suggestion + attribution footer

**kernel/**
- `intake-and-scope.md` — §0.1 (recommended) reviews in a dedicated git worktree: `git worktree add <scratch>/tree <headRefOid>`, detached HEAD at the pinned head, temp location outside the main checkout (e.g. the review scratch dir). The review never disturbs the developer's working tree, and `require_pr_head` is satisfied by construction. Recommendation only — clone/checkout stays the documented fallback, never blocks; supplements, not relaxes, the pinned-head rule. Lifecycle: keep for the run, capture the new head then re-point the tree on the closure loop, remove after closure.
- `intake-and-scope.md` — run manifest gains `cure_light_source_head_oid`: the cure-light source checkout's HEAD captured once at intake, frozen for the run.
- `evidence-format.md` — External routing: every operator-approved draft body ends with the attribution footer `_Reviewed with [cure-light](https://github.com/grzegorznowak/cure-light) @ <source OID> — pinned PR head <headRefOid>_`, composed solely from run-manifest values (never re-derived per vector); omitted — never fabricated — when the source commit is unestablishable; drafts only, never notebook pages.
- `docs/OPEN-ISSUES.md` — #3 rewritten: a pinned worktree reduces but does not eliminate moving-head risk (checkout-drift prevented for the run; child-side HEAD verification still required; fallback remains exposed to concurrent checkout movement).

Background: operator direction — two small pipeline-mechanics mods (suggest worktree-based reviews; attribute reviews with a cure-light footer). Design answered via plain-language questions and checked by an independent code-review agent (adopted: precise worktree ordering + closure re-point/removal, "supplements not relaxes" require_pr_head, provenance field name, no-fabrication caveat).

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

Background: operator direction "augment Vector 3 with a code quality lens", refined to big decision trees first (rewrite-to-maintainable-pattern judgment), then extended with test strength / error consistency / duplication; design checked by the code-review agent (sound; routing priorities vs V1 Tests surface, V2 test integrity, and V3-debt findings adopted). Post-merge-gate review round (independent code-review + planner reviews, both CHANGES-REQUESTED): severity cells reworded to own-scale materiality only (no "hot path" / "high-risk surface"); `test` checklist restricted to residual suite strength with V1/V2 link-out for claim-not-under-test and demonstrated-regression gaps; observability failure routed to V2 (not V3 debt); per-row outcome token standardized to `n/a-with-reason`.

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