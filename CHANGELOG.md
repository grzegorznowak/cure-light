# Changelog

## Unreleased (working tree)

### v0.5.13 — contract adequacy: designated sources, pre-V1 consistency pause, review-basis gate

**kernel/**
- `intake-and-scope.md` — §0.2 gains **designated in-diff sources** (an explicit pointer in the PR body / linked issue / locked decision is the trust stamp; repo convention only interprets a designated package), **immutable source pinning** (subject/base blob OIDs, spans/hashes, body/issue version refs; drift → new state) and the **early source-consistency pass** (bounded within-/cross-source comparison after claim extraction; a material unresolved contradiction → provisional `repair_required` + default pause before Vector 1, with a named operator-recorded **evidence-only V1 run** as the narrow exception; non-material wording recorded without pause). §0.4 records the pause/authorization, judges thinness across designated sources and applies the repair-pause default to any `repair_required` defect; the manifest gains `contract_sources` / `source_consistency` / `review_basis` records; a contract-only repair is a new review state.
- `conformance-pass.md` — Vector 1 adds `documents/specifies` as a delivery role and the **no-self-proof** rule (`declares` is source provenance, not an EXPLAINED edge; doc/spec units need an independent purpose/target anchor; no same-unit or mutual cycles; docs-only spec rewrites are real deliverables); witness discipline for definitive `GAP`/`UNCLAIMED`/basis blockers; the completion disposition becomes the **review-basis gate** — `ready` / `limited-only` / `blocked` / `unknown` plus a separate `repair_required` status, with `limited-only`/`blocked`/`unknown` barred from ordinary V2/V3 unless explicitly named by the operator.
- `pipeline-model.md` / `kernel/SKILL.md` — the phase order carries the source-consistency pause and the V1 basis gate; operating rules for designated sources, a recorded basis, and contract repair as a new state.
- `implementation-pass.md` / `debt-pass.md` — the V2 compiler validates only named grounded splits under the gate result; unmet clear requirements stay valid invariants; docs-only deliverables are not forced into code invariants; generic debt axes never reconstruct inadequate intent.
- `closure-verification.md` — “no work pulled” is reconciled as “no **code** work pulled”: a body/issue repair with an unchanged subject OID is a new state with a recaptured contract and identity-checked census reuse; in-diff source repair repulls a new subject; code-unchanged findings stay open unless specifically reclassified.
- `evidence-format.md` — contract adequacy is a gate disposition, not a finding kind; the comment Summary renders the review basis / repair requirement; claim-registry pages carry per-source designation/interpretation and consistency records.

**pi-driver**
- `notebook-plan-contract.md` — frame/contract/claims pages record source pins/designation, the consistency outcome and the `review_basis`; contract repair writes a new `-s<n>` set. `requirements-check.md` — the notebook-less fallback cannot assert `ready`; contract-adequacy dispositions stay separate from the bootstrap requirement table.

**top-level** — `README.md` / `templates/KICKOFF.md` expectation sync; `assets/child-pass-prompt-template.md` carries the captured-sources contract, the `documents/specifies` anchor rule and the designation-aware `UNCLAIMED_CANDIDATE` check; `docs/contract-adequacy-validation-plan.md` adds the fixture scenarios.

Background: operator direction — a PR contract is only as good as its designated sources; a half-assed description defaults to a repair pause, and V1's accounting completion is not by itself a continuation/readiness verdict.

### v0.5.12 — Vector 1 detects both ends; yagni refocuses on over-engineering

**kernel/**
- `conformance-pass.md` — Vector 1 now owes **claim adjudication** (every captured claim gets a verdict) *and* **changed-unit accounting** (every census range/event gets exactly one of `EXPLAINED` / `UNCLAIMED` / `EXCLUDED` / `UNRESOLVED`). The child return is two orthogonal blocks — `CLAIM` verdicts plus unit records closed by `CLOSE <digest>` — with coordinator validation/reconciliation rules, the claim matrix kept distinct from the coverage ledger, a paged **matrix projection** for V2, an honest partial-review gate, and grouped **blocking** `unclaimed-delivery` findings the owner addresses in the PR body (declare/justify the delivered behavior or remove it).
- `yagni-pass.md` — refocused from size accounting to **over-engineering of the claimed delivery**: the untraceable-hunk atom and the "traceable = NOT-A-HIT" dismissal are gone; the return replaces `SIZE` with `ENGINEERING: JUSTIFIED | CHALLENGED`; EXPLAINED range groups and the claim matrix are leads; the historical operator launch quote is preserved.
- `pipeline-model.md` / `intake-and-scope.md` — Phase 0 gains **0.3a mechanical changed-range census** (pinned `-U0` patch recipe, parent edit blocks + metadata events, totals by side) before the **0.3b** capacity-bounded split compile; four completeness flags; the V1 coverage assertion is separate from the lens table; immutable claim-registry capture; the Phase-0 gate shows counts and approves exclusions/budgets; a thin/empty contract stops planning.
- `evidence-format.md` / `assets/finding-schema.json` — additive optional `conformance_kind: claim-gap | unclaimed-delivery`, `coverage_ref`, and evidence `side` / `range_or_event` / `oid` anchors for deletions and metadata events; unclaimed severity LOW default / MED material / never HIGH from absence alone; coverage accounting renders in the comment Summary, grouped unclaimed delivery in Findings (no fourth section).
- `chhound-driver.md` — the symbol sweep may reuse the census inventory but stays distinct from V1 attribution; `in-diff` is navigation, not coverage. `blast-lens.md` / `quality-lens.md` — boundaries: attribution ≠ outside-consumer clearance; yagni ≠ quality. `implementation-pass.md` / `debt-pass.md` — V2/V3 consume the bounded matrix projection and prior facts, never census breadth.
- `kernel/SKILL.md` / `templates/KICKOFF.md` — phase sequences carry the census and the two-ended Vector 1; operating rules for blocking unclaimed delivery, honest partial coverage, and closure disclosure.

**pi-driver**
- `notebook-plan-contract.md` — coverage pages (`coverage-<owner>-<pr>-s<n>` summary/index + `-p<k>` ledger shards) are the authoritative **in-notebook** store for changed-unit accounting; the compiled claim registry gets `claims-<owner>-<pr>-s<n>`; coverage pages stay through the closure/finalization window and retire after durable snapshots.
- `closure-verification.md` — newly added unexplained ranges are surfaced or V1 coverage is declared not re-run; `unclaimed-delivery` closes only through a recaptured contract / recorded author declaration.
- `requirements-check.md` — notebook-less fallback: no authoritative coverage ledger or claim registry; Vector 1 completeness flags cannot all clear, so the run must not assert complete coverage.

**top-level** — `README.md` / `BOOTSTRAP.md` descriptions synced; `assets/child-pass-prompt-template.md` gains the Vector 1 coverage assignment/return block and yagni coverage inputs (A/B/C research variants and coordinator-only writing unchanged).

Background: operator direction — V1 must detect both claim-without-code and code-without-claim; untraceable-hunk accounting moves out of yagni, which now challenges over-engineering of the claimed delivery. Coverage records live in the notebook (no ambient scratch state); confirmed unclaimed delivery is a blocking in-scope finding.

### v0.5.11 — re-pull updates the subject tree in place: same tree, same bridge, live index

**kernel/**
- `intake-and-scope.md` §0.1 + subject rule — the **re-pull branch**: a new review state for an already-pulled PR updates the existing `subject_path` **in place** (fetch + detached checkout) instead of creating a fresh tree; a fresh pull is the fallback for a gone/broken tree or a mechanism change. The invariant is stated precisely: the tree is stable *within* a state — the operator-gated state boundary is its only mutation. The capture records the same `subject_path` with the new `subject_oid`; prior-state content stays reachable at its own OID.
- `chhound-driver.md` — §Re-pull is in-place-first (no `/ch` command, no reconnect, no fresh baseline copy; the live daemon re-indexes, the bridge stays); fresh sandbox + disconnect/reconnect as the fallback; Phase 0's unique `--dest` applies to sandboxes being created; the Evidence rule notes the transient old/new-subject mix while the live re-index converges.
- `closure-verification.md` / `evidence-format.md` — the moved-tree rule: old-state content is read at its own `subject_oid` (`git show <oid>:<path>`), never from the current checkout; rows keep their own OID until re-validated; a checkout whose HEAD differs from the row's OID is a different tree.
- `SKILL.md` / `pipeline-model.md` / `README.md` — "never re-pull in place" becomes "nothing mutates mid-state; the gated re-pull updates in place"; `libs/pi-driver/references/notebook-plan-contract.md` / `requirements-check.md` — pages stay per state (same `subject_path`, new `subject_oid`), row 5 covers the first-pull create/connect and the in-place re-pull (bridge kept).

**Model-tool rail setup (same branch)**
- `chhound-driver.md` — the rail is driven through the pi-chhound **`ch-chhound` model tool** where the build provides it (read actions need no consent; mutations are consent-gated and blocked headless): presence becomes a `ch-chhound status` probe (install detection + the operator's `/ch-status` report move to the older-build fallback lane); Phase 0's one-go create is `worktree.create {pr, connect: true}` with the `/ch` commands as per-step fallbacks; the registered tool prefix is read from `ch-chhound status` (a model connect derives `chh_<checkout folder>`, e.g. `chh_pull-123`) instead of a fixed `/ch-mcp --prefix`; the tool table marks `websearch`/`fetchurl` global (unprefixed); Fallbacks cover blocked mutations and stale baselines.
- `SKILL.md` / `intake-and-scope.md` / `libs/pi-driver` (`SKILL.md`, `requirements-check.md` rows 4/5/9 + row-4 semantics) / `KICKOFF.md` / `README.md` / `BOOTSTRAP.md` / `assets/child-pass-prompt-template.md` — presence and Phase 0 reworded to the model-tool path with the `/ch` fallback; row 4 probes `ch-chhound status` first; the child template's `ch_prefix` slot reads the registered prefix.

Background: operator direction — a top-up review should continue in the same worktree. The rail's index updates live from the checkout (Watchman) and the MCP bridge binds to the sandbox dir, so a fresh sandbox + reconnect + re-index per state was pure overhead. The old rule's purpose (subject immutability during a review) is preserved: the only mutation is the operator-gated state boundary, and old-state evidence stays addressable by OID.

### v0.5.10 — the symbol map: the preflight builds one shared usage artifact (census + heat), reused by V2 blast, V3 debt, yagni, and the comment

**kernel/**
- `chhound-driver.md` (§Symbol sweep) — the artifact is the review state's **symbol map**: the diff-extracted symbol set plus a complete occurrence **census** (`rg -n -w` over the tracked files at `subject_oid`; scope/exclusions, match unit, and completion recorded; literal names, not resolved symbols) plus a bounded heat table `symbol | change | total | in-diff | outside | outside locations (capped) | note`. The paginated chunkhound sample is **triage, not coverage**: the `sweep` row clears only when every `outside` occurrence is tree-read and accounted; a routed uninspected occurrence keeps it a hit — chunk triage is navigation, never clearance. Stored at `symbol-map-<owner>-<pr>-s<n>` (one per review state; scratch file in fallback runs); caps bounded, drill-down via the recorded census command.
- `blast-lens.md` / `intake-and-scope.md` / `pipeline-model.md` / `implementation-pass.md` — the symbol map is the manifest's `symbol_sweep` artifact; the consumers are named (V2 `sweep` row, V3 debt seed, the yagni pass) without changing lens ownership or the matrix; the comment's `Symbol impact` renders the map.
- `debt-pass.md` / `yagni-pass.md` / `assets/child-pass-prompt-template.md` — V3 and yagni children read the map before their own work (leads only; V3's search-extensive protocol is unchanged — no search-credit carve-out); yagni treats an outside-empty row as a candidate hint, never an unused verdict.
- `evidence-format.md` — `Symbol impact` renders outside-occurrence counts with census scope/provenance/caps (no triage labels, heuristic splits, verdicts, or unread-remainder clearance claims); the state's map page joins the Notebook layout.
- `closure-verification.md` — a closure render regenerates the new state's census (or omits `Symbol impact`); old-state counts are never carried forward.
- `libs/pi-driver/references/notebook-plan-contract.md` — the state-qualified map page: a bounded cache kept through the state's consumers.
- `README.md` — the blast-lens paragraph names the shared symbol map.
- **Holistic flow pass (same branch)** — one `sweep` clearance rule across `blast-lens.md` / `chhound-driver.md` / this entry (a routed uninspected occurrence keeps the row a hit); frame + contract pages state-qualified `-s<n>`; the deterministic preflight explicit in the phase sequences (`kernel/SKILL.md`, `pipeline-model.md`, `KICKOFF.md`); the child template covers yagni; closure closes `quality`/`yagni` rows and names the regenerated census; stale refs and overloaded wording fixed.

### v0.5.9 — the `blast` lens: data × call-site blast radius + the chunkhound symbol sweep (V2-owned; advisory rows, blocking instances)

**kernel/**
- `blast-lens.md` (new) — a Vector 2-owned always-active lens distilled from an operator investigation of a data-dependent production bug: five rows — `data` (what pre-existing state reaches this change), `sweep` (a changed sentinel/constant/default obliges a call-site sweep **in the same PR**; a sweep deferred to a "follow-up ticket" is the hit), `semantics` (comparisons judged in the storage engine's value model, not the language's), `fixture` (a single-artificial-row trigger requires the PR to ship a fixture test on the repo's own scratch DB — the review flags the absence, it never runs it), `gates` (a "statically detectable" claim counts only where the analyzer/lint gate is actually enabled). Routing: rows are advisory (lens trail, LOW default, MED ceiling, never HIGH, notebook-only); the **concrete instance is a Vector 2 finding** at its own severity (HIGH possible) — the lens finds the class, the finding is what blocks; a PR deferring its own sweep is **in scope** (v0.5.8 route) → Findings, to be addressed. Determinism: `sweep` is mechanical, `semantics`/`gates` are schema/CI-config reads, `data`/`fixture` are judgment.
- `chhound-driver.md` — **Symbol sweep** (new preflight recipe): the changed-line identifiers extracted by bash from `git diff -U0 base..subject` (keywords and <3-char names dropped, deduped, ≈30–40 cap, optional operator list), one `{ch_prefix}_search` regex `\b<symbol>\b` per symbol with hits read from the footer's `of <total>` (chunks), hit chunks classified `in-diff` / `outside` against the changed ranges, and a compact `symbol | hits | in-diff | outside | locations | truncation` table — run once per state by a dedicated sweep child, artifact `symbol_sweep`; without a confirmed rail the same recipe runs `rg -n -w`, marked `mode: rg`.
- `hygiene-lens.md` / `pipeline-model.md` / `intake-and-scope.md` / `implementation-pass.md` / `closure-verification.md` — the lens dimension points at the non-hygiene references; the matrix gains the `blast` row (`preflight + v2 split`, `yes (sweep)`), the manifest example gains `blast: preflight+v2`, and the preflight schedule names the symbol sweep. Vector 2's owned-lens section covers the four judgment rows plus the consumed sweep table and the advisory-rows / blocking-instance split; closure revalidation covers `blast` rows (a concrete instance follows ordinary finding closure).
- **Planner-fix pass (same branch)** — `blast-lens.md`: the `sweep` clear case is the cited table with every `outside` consumer accounted for; whole-lens `n/a` is run-level and cited (no runtime data path, shared value, or gate claim in the diff), per-split `n/a` carries a reason; an unrecorded required row outcome = frame error / `inconclusive`; the `fixture` requirement is on the PR (the review flags absence, never runs it); a *concrete instance* = named file:line mechanism + named trigger (data / input / config) + concrete failure mode, and a deferred / uninspected consumer posts as an in-scope V2 finding (the coverage row stays trail-only). `pipeline-model.md` rule 1 generalizes `off` to any lens whose activating pass does not run; `implementation-pass.md` drops the duplicated five-row prose for a pointer.
- `evidence-format.md` — schema line + severity bullet for `blast` rows (advisory, never HIGH) and the routing rule: lens rows stay in the notebook, the concrete instance is a bug-table finding; the comment gains the mechanical **`Symbol impact`** section (top outside-use rows, provenance, caps — never a lens row).

**assets/**
- `finding-schema.json` — `blast` added to the `lens` / `lens-checked` enums (backward compatible); the reserved `test` / `security` slots are unchanged — fixture-adequacy lives in the `blast` lens, not the `test` slot.
- `child-pass-prompt-template.md` — the `YOUR LENSES` paragraph names the `blast` reference and splits advisory lens hits from a concrete `blast` instance (a Vector 2 finding); the `lenses` slot row lists the reference; a **preflight sweep child** section documents the once-per-state prompt (recipe reference, exact tool name or `mode: rg`, caps; dumps stay in the child).

**README / SKILL / BOOTSTRAP** — the lens paragraph, layout line, and statuses rule name the `blast` lens; the remote-boot fetch manifest gains `blast-lens.md` (entries renumbered); the README blast paragraph names the mechanical symbol sweep, and the `chhound-driver.md` reference descriptions gain the symbol-sweep recipe.

Background: operator investigation of a data-dependent production bug — the code change and the legacy rows each looked harmless alone; only their interaction was a P1. Condensed into one five-row lens; the source's "must block" maps onto existing machinery instead of engine-level blocking (advisory rows, concrete instance = V2 finding, deferred sweep = the v0.5.8 in-scope route). The same investigation's second point — a changed sentinel is an API-wide change — became the preflight symbol sweep: a recipe over the rail's `search` (no new tool), `rg` as the no-rail fallback, its mechanical table surfaced as the comment's `Symbol impact` section.

### v0.5.8 — comment scope routing: in-scope (introduced or enforced) is addressed, never auto-downstreamed

**kernel/**
- `evidence-format.md` — **scope routes the comment**: `origin` (base-diff) is evidence, not the routing key. An item **in scope** — the PR owns it: introduced by the PR, or pre-existing on a path the PR's own change now depends on, routes through, or claims to guarantee — goes to **Findings · to be addressed**, never a follow-up suggestion. `## Potential follow-up issues` is now **out of this PR's scope, optional, never required**, with two row kinds: **recommended** (easy / best bang for the buck — worth addressing while the area is open) and **downstream** (only low-impact + heavy implementation, or pre-existing issues this PR did not introduce). Disposition annotation: `fix-in-PR` = in scope; `pre-existing-debt` = out-of-scope follow-up, moving to `deferred-decision` / `track-separately` only when that resolution is accepted.
- `implementation-pass.md` / `debt-pass.md` — aggregation rules reworded to the same scope route: in scope → Findings / `fix-in-PR`; out of scope → `pre-existing-debt` — `recommended` or a downstream candidate.
- `pipeline-model.md` — cross-cutting disposition list now matches the schema (`track-separately` added).
- `SKILL.md` — operating rule: base-diff classification feeds scope routing; introduced-or-enforced items are addressed, never deferred downstream.

Background: operator direction — the previous split (Findings = PR-introduced, follow-ups = pre-existing debt) automatically pushed every pre-existing item downstream, even ones the PR enforces or makes load-bearing, and framed cheap high-value items the same as heavy low-impact ones. Reworded in place: same three comment sections, no new taxonomy layer; the added text is the scope definition plus the two follow-up row kinds.

### v0.5.7 — research enforcement: mandatory-if-ready chhound protocols (V2 code-research, V3 search-extensive) + RESEARCH TRACE gate

**kernel/ + assets/**
- `pipeline-model.md` — new cross-cutting **research accelerator** section: `research.mode` (`chhound-rail` | `direct-tree`) compiled from the planned subject mechanism, frozen at the plan gate, and **re-recorded at the Phase 0 gate when the rail pull falls back** (mode flips to `direct-tree`, `ch_prefix: none`); Vector 2 runs the code-research protocol **mandatory-if-ready and uniform across every split** (including test-integrity concepts); Vector 3 runs the **search-extensive** protocol (`search` leads every concept/lens sweep; `code_research` allowed, never required); authority rules — index output is discovery only (every cited line re-read in the subject tree at `subject_oid`), origin stays base-diff based, Vector 1 remains optional; shadow splits **off by default** (`research.shadow: on` = explicit operator choice).
- `implementation-pass.md` — **Subsystem research protocol (Vector 2)**: per split, one scoped `{ch_prefix}_code_research` orientation question (callers, state transitions, failure paths, persistence/version boundaries, tests, correlated sites) + at least one `{ch_prefix}_search` pinpoint + tree verification; canonical **RESEARCH TRACE footer** schema (modes `chhound-rail` | `search-extensive` | `direct-tree`; all-mode field `tool-call-count`; V3 fields `search-log` / `search-call-count` / `code_research-used`); enforcement — missing/noncompliant trace = `inconclusive`, rerun once, then operator gate; traces are self-report (no child telemetry) → coordinator spot-audits `verified-correlated-sites`; cost recorded per child (wall-clock by the coordinator + trace call counts, self-reported), no preset budget until pilot data.
- `debt-pass.md` — **Search-extensive research protocol (Vector 3)**: `{ch_prefix}_search` is the default lead generator for every owned concept/lens (regex for symbols/patterns, semantic for concept correlation; iterate from hits); minimum two distinct search calls per concept/lens and every repo-wide claim (usage counts, absence of consumers, vocabulary duplication) preceded by a logged search attempt; `code_research` optional; same evidence/fallback/trace rules.
- `assets/child-pass-prompt-template.md` — soft "RESEARCH TOOLS" paragraph replaced by the mandatory `{research_protocol}` step; slot-map rows (`research_protocol`, `ch_prefix`, exact tool-name slots, `excluded_namespaces`, `BASE_OID`, `owner/repo`) with keys matching the template tokens they fill; invariant 7 (missing trace = inconclusive); **Variant A** (V2 rail protocol), **Variant B** (direct-tree), **Variant C** (V3 search-extensive), shadow-control note. Vector 1 omits the slot.
- `evidence-format.md` — research traces are **process metadata**, not finding evidence; index-derived lines/origin labels invalid until tree/base-diff verified.
- `intake-and-scope.md` — plan gate + manifest gain the `research:` block (mode, `ch_prefix`, excluded live prefixes, per-vector protocols, `shadow`).
- `SKILL.md` — compile step freezes the research mode (re-recorded as `direct-tree` at the Phase 0 gate on rail fallback); operating rule: mandatory-if-ready on the rail, `direct-tree` never invokes a `chh_*` namespace.

**libs/pi-driver/**
- `SKILL.md` — research enforcement bullet: render exact prefixed names (`chh_pr<n>_daemon_status`/`_code_research`/`_search`) into the `{research_protocol}` slot (never generic aliases), trace gate at each vector, self-report audit against the subject tree.
- `notebook-plan-contract.md` — frame carries the research binding; per-split RESEARCH TRACE compliance table appends to `pr-<n>-review` (shadow comparisons when enabled).

`requirements-check.md` intentionally unchanged — its rows already gate the rail with `chh_pr<n>_daemon_status` (v0.5.6); `chhound-driver.md` stays the rail-mechanics doc (enforcement lives in the pass contracts + template).

Background: operator direction after a tool-adoption experiment series (spawned children, fresh contexts): children **never voluntarily invoke research tools** (0/6 without exact registered tool names in the prompt; full adoption only when the prompt names the exact tool, binds the namespace, scripts the sequence, and preempts freshness/cost objections). cure-light's previous soft encouragement (discovery-optional paragraph) could not drive use. Decision: mandatory-if-ready protocols with a verifiable footer, uniform across Vector-2 splits (incl. test-integrity — deeper understanding yields better insights regardless of split type), search-extensive for Vector 3 (debt claims are repo-wide: usage counts, absence of consumers, duplicated vocabulary). Shadow splits (paired direct-only controls) measure the accelerator's quality delta — operator opt-in only. No preset latency budget: measured and reported until pilot data exists. Evidence discipline unchanged: the index is an accelerator, never an evidence source.

### v0.5.6 — rail presence probe fix: operator-confirmed `/ch-status`

**kernel/**
- `chhound-driver.md` — presence is now a **two-step check**: (1) install detection the coordinator can actually run — pi-chhound in the pi settings `packages` / extension dirs + `chunkhound` CLI on PATH; (2) operator rail confirmation — the coordinator instructs the operator to run `/ch-status` and report the output at the frame gate (authoritative for the session). The rail's `/ch` commands are **operator-side slash commands**: not model-invokable, UI-output only. Phase-0 recipe + re-pull note the operator/coordinator division (operator runs the `/ch` commands; coordinator captures with `git` and verifies with `chh_*` tools); step-3 verify split: operator footer + coordinator `chh_pr<n>_daemon_status` (tool-list registration alone is not a response).
- `SKILL.md` + `intake-and-scope.md` — "presence probes (`/ch-status`)" wording → install checks + operator `/ch-status` at the frame gate; sandbox-selection summaries say "rail confirmed" (installed + operator report), never bare "plugin present"; §0.1 pull bullet marks `/chworktree` + `/ch-mcp` as **operator-run** with coordinator verification of the `chh_*` tools.

**libs/pi-driver/** + **templates/** + **README**
- `requirements-check.md` — row 4 check/command cells: `/ch-status` (unexecutable by the model) → install detection (pi settings / extension dirs + `chunkhound` on PATH); row 4 plans the chunkhound sandbox only **pending the operator's `/ch-status` confirmation at the frame gate** (unconfirmed → plain detached worktree); row 4 semantics note: two-step check, planned mechanism stays a plan not a guarantee; row 5 command cell splits operator (`/ch-mcp`) vs coordinator (`chh_pr<n>_daemon_status`), "when operator-confirmed".
- `KICKOFF.md` §7 — expectation note: when the rail is detected, the agent asks the operator to run `/ch-status` once at the frame gate (checkbox semantics unchanged).
- `README.md` quick-requirements paragraph — mechanism phrase: "plugin present" → "plugin detected and rail operator-confirmed via `/ch-status` at the frame gate".

Background: operator direction — a live boot recorded "fallback planned (plain detached worktree)" although the pi-chhound plugin was installed: the presence probe told the coordinator to run `/ch-status`, which is an operator-side slash command the model can never invoke (and whose `ui.notify` output does not reach the model unless reported). Fix = model-executable install detection + explicit operator instruction at the frame gate (option A). Draft checked by an independent #code-review facts+consistency pass (HIGH + 2 MED fixed); PR reviewed by a #code-review size/simplicity pass (wording simplifications applied in the review-fix round).

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