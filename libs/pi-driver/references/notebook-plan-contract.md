# notebook-plan-contract.md — where review state lives

The notebook is the shared memory between phases, children, and handoff contexts. The coordinator owns writes; children return compact records and never race pages.

## Page layout

| Page | Owner | Contents | Lifetime |
|---|---|---|---|
| `pipeline-frame-<owner>-<pr>-s<n>` | coordinator (seal → Phase 0) | frozen run options + planned subject mechanism (chhound sandbox | plain worktree) — no tree fields at the pre-pull gate; `subject_path` / `subject_oid`, changed-file list, contract ref (page or path), research binding (mode chhound-rail | direct-tree, `ch_prefix`, exact tool names, excluded namespaces, fallback reason), contract-source pins/designation, the source-consistency outcome (provisional `repair_required` / evidence-only authorization) and the post-V1 `review_basis` record, and fallback notes recorded at their gates once the pull lands | one review state; a deliberate re-pull or a contract-only repair starts a NEW frame (linked by diff), never overwritten in place |
| `contract-<owner>-<pr>-s<n>` | coordinator (Phase 0) | the verbatim contract (§0.2): PR description, linked issues + locked decisions, explicitly designated in-diff sources with designating pointer/role/interpretation, source pins (blob OIDs/hashes/version refs), changed-file list, subject/base OIDs | one review state, like the frame; a re-pull or a contract-only repair compiles the new state's contract |
| `claims-<owner>-<pr>-s<n>` | coordinator (Phase 0) | the compiled **claim registry**: deterministic claim IDs (source block + UTF-8 offsets + quote hash), per-source class/designating pointer/selection rule/interpretation (normative vs advisory, precedence), parent/group links, context/nonclaim labels, source-window provenance — plus the **source-consistency records** (conflicting quotes/offsets/source hashes/affected claim IDs, materiality witness) — the queryable complete claim directory for V1 negative attribution (paged `-p<k>` when it exceeds a page) | one review state, like the contract |
| `symbol-map-<owner>-<pr>-s<n>` | coordinator (preflight, before V2) | the state's symbol map: selected symbols, census heat table, capped outside locations, provenance/caps (chhound-driver.md, Symbol sweep) | one review state; kept through the state's consumers (V2 sweep, V3 seed, yagni), discarded when the state closes |
| `coverage-<owner>-<pr>-s<n>` (summary/index) | coordinator (Vector 1) | Vector 1 changed-unit accounting: denominator + counts by state and side, claims refs, per-shard assignment refs/digests, exclusion classes/policy, completion flags, exact refs to the `-p<k>` ledger shards — the authoritative store, never scratch files | one review state; kept through the state's closure/finalization window, retired after durable snapshots land in findings/decisions |
| `coverage-<owner>-<pr>-s<n>-p<k>` (bounded ledger shards) | coordinator (Vector 1) | structured per-unit records: unit/range, accounting state, attribution edges, evidence refs + pinned census recipe identity; workers read only their assigned pages/slices | one review state; a re-pull writes a new `-s<n>` set, never overwrites; kept through the closure/finalization window, retired after durable snapshots land |
| `pr-<n>-review` | coordinator (append per vector) | findings table (schema rows, each carrying `subject_oid`) + closure table | one PR, all review states |
| `dis-<n>-review` (or the durable `decisions` page when follow-ups survive) | coordinator | deferred-decision + closed-by-operator records: author/time/rationale/scope | durable |

A re-pull starts the next review state and writes **distinct** frame + contract pages for it — never overwrite an earlier state's pages in place (the new frame reuses `subject_path` with the new `subject_oid`; the tree itself is updated in place).

Reference pages by name. Children `notebook_read` on demand; they do not preload bodies. The coordinator serializes writes with a process-local ordering so same-name writes don't race.

### Coverage pages

`coverage-<owner>-<pr>-s<n>` is the summary/index for a state's Vector 1
changed-unit accounting; `coverage-<owner>-<pr>-s<n>-p<k>` are its ledger
shards, paged by surface/shard/claim group so a mega-diff ledger stays inside
a notebook page (50 KB / 2000 lines). The index carries the denominator,
counts, exclusion policy and completion flags plus exact shard refs, so
closure and finalization can cite the accounting without loading every shard.

## Content rules

- **Findings are recoverable facts** — keep the evidence-format rows; discard tender re-derivable code trivia freely at handoff.
- **The symbol map is a bounded state cache.** Structured artifact data (symbols, counts, capped locations) that survives the state's handoffs because V3 and the post-handoff yagni pass consume it — never raw search logs. A re-pull is a new state: a new `-s<n>` page, never an overwrite or silent reuse.
- **Coverage records are structured machine records, not findings.** Vector 1's changed-unit accounting (unit/range, accounting state, attribution edges, evidence refs — conformance-pass.md) lives in the `coverage-<owner>-<pr>-s<n>` summary/index and its bounded `-p<k>` shards; these in-notebook pages are the authoritative store — never findings rows, raw logs, or scratch files. Workers read only their assigned pages/slices. A re-pull is a new state with its own `-s<n>` coverage pages, never an overwrite. The summary page carries the denominator + counts + completion flags + per-shard assignment refs/digests so closure/finalization can cite the accounting without the shards; coverage pages stay through the closure/finalization window and retire after durable snapshots land — a closure run never depends on a dead link.
- **The claim registry is the complete claim universe.** `claims-<owner>-<pr>-s<n>` holds the deterministic claim directory compiled at Phase 0 (intake-and-scope.md §0.2) — a summary or a slice is never a substitute; negative attribution that cannot query it returns `UNRESOLVED` (conformance-pass.md).
- **Sources enter the contract only by explicit designation.** In-diff spec/design material is a claim source only when the PR body, linked issue or a locked decision points at it; repo convention interprets a designated package (normative vs advisory, delta vs baseline), never authorizes one (intake-and-scope.md §0.2). Non-capturable pointed material is context with a stated limitation. Source/consistency/`review_basis` records are coordinator process records, not findings.
- **Contract repair is a new state, not an overwrite.** A changed PR body/issue or in-diff source — even with an unchanged subject OID when no code changed — writes a new `-s<n>` contract/claims set; prior states stay addressable at their own pins (closure-verification.md).
- **Decisions are non-recoverable** — always persist: operator deferrals, closed-by-operator records, locked decisions from the issue. Never let them go stale or vanish on compaction.
- **The contract page is verbatim, bounded.** The Phase-0 contract is the one long-form page: PR claims + locked decisions preserved byte-exact (intake-and-scope.md §0.2). Never paste raw diffs, logs, or kernel text into it.
- **No raw transcripts/logs.** A vector's dead ends and working notes do not belong in the notebook; the closure table's `re-opened` row records the reason concisely.
- **Research compliance is part of the record.** Per-split Vector-2/3 RESEARCH TRACE outcomes (compliance table) append to `pr-<n>-review` with the vector; shadow-split comparisons land there too when enabled.

## The seal-then-handoff step

When `handoff` is available and the operator confirms the frame:

1. Write `pipeline-frame-<owner>-<pr>-s<n>` (compiled options + planned subject mechanism — the manifest's tree fields land at the Phase 0 gate) and `pr-<n>-review` (findings skeleton).
2. Discard recoverable code-trivia pages; refresh the durable decision page.
3. Draft the handoff prompt that carries ONLY: the frame's location, the current state (intake complete, requirements pass/fallback), the immediate next step (Phase 0 pull subject + contract → Vector 1), and any blocker or failed path worth avoiding.
4. Call `handoff` with `discardPages` for code-trivia pages and the task prompt pointing at the frame page by name.

The next context reads the frame page, loads kernel references on demand, and kicks off Phase 0 → Vector 1 — it does not re-fetch the kernel.

## If no handoff

Continue in-session; the frame and findings pages still carry the state. The operator sees the compiled plan inline instead of via a fresh context.