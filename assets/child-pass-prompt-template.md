# child-pass-prompt-template.md

The per-vector fleet-child prompt contract. Every child receives a prompt shaped from this template; the coordinator fills the bracketed slots from the run manifest and the vector's split.

## Base template

```text
You are a {vector} review agent in a fleet. The review subject tree is
{SUBJECT_PATH} — subject OID {SUBJECT_OID} (stable for this review state;
record it on every finding row).

THIRD: read the contract from {contract_ref} (the relevant section only).
Then read the assigned files: {file_list}.
Then read the diff slices for your surface: {diff_paths} (base..subject).

YOUR ANGLE: {angle}. Inspect completely and report per
{return}.

YOUR LENSES: {lenses}. Run each lens checklist from
its owning reference — hygiene family: kernel/references/hygiene-lens.md; the
`quality` lens: kernel/references/quality-lens.md; a lens you check and clear
is explicitly NOT-A-HIT. Hygiene hits go to the lens trail, never the bug table.

RESEARCH STEP: then execute the research step per {research_protocol} when the
slot is present (Vector 2: code-research protocol; Vector 3: search-extensive
protocol; Vector 1: omitted). The slot carries the exact registered tool names,
the namespace binding, the fallback rule, and the mandatory RESEARCH TRACE
footer. MCP output is discovery only — every cited line is re-read in the
subject tree at {SUBJECT_OID} before it becomes evidence.

Your contract is the verbatim locked decisions + PR description — never a
summary of intent. Cite file:line in the subject tree. Do NOT run tests unless
told; do NOT propose large refactors; keep style mentions on the lens trail
(unrouted style noise is dropped).

Return: a numbered list of GAP|F|D findings conforming to the vector contract,
plus a VERIFIED | NOT-A-BUG | NONE closing for any surface you check and clear,
plus the RESEARCH TRACE footer when {research_protocol} is present.
Under {budget} lines.
```

## Slot map

| Slot | Filled from |
|---|---|
| vector | conformance / implementation / debt |
| SUBJECT_PATH | the subject tree root (sandbox or worktree dir) — run manifest `subject_path` |
| SUBJECT_OID | run manifest subject_oid |
| owner/repo | the review target `<owner>/<repo>` (intake `owner/repo`) — Variants A/C subject description |
| contract_ref | run-manifest `contract_ref`: the notebook page `contract-<owner>-<pr>` (pi runs) or the disk CONTRACT slice (fallback runs) |
| file_list | the assigned files for this surface/split |
| diff_paths | the focused diff hunks for the surface |
| angle | the surface (conformance) / sealed invariant (implementation) / bigger concept (debt) |
| lenses | the lens list this split owns, from the run lens matrix (pipeline-model.md; checklists per owning reference: hygiene-lens.md, quality-lens.md) |
| return | from the pass contract: `VERIFIED/GAP/NONE`, `[F] file:line`, `[D] concept` |
| budget | output-size cap (lines); enforced; truncation = inconclusive |
| research_protocol | run-manifest `research` block rendered per the variants below (Vector 2: Variant A; Vector 3: Variant C; Vector 1: omitted) |
| ch_prefix | the frame's exact tool prefix (`chh_pr<n>`) when `research.mode: chhound-rail`; `none` in direct-tree |
| ch_daemon_status_tool / ch_code_research_tool / ch_search_tool | `{ch_prefix}_daemon_status` / `_code_research` / `_search` — exact registered names |
| excluded_namespaces | other live `chh_*` prefixes (other sandboxes) — never to be used |
| BASE_OID | run manifest base_oid (for origin checks) |

## Child contract invariants (always)

1. Analyze the **subject tree** at {SUBJECT_PATH} only; every row carries `subject_oid`; a tree whose HEAD differs from {SUBJECT_OID} is `inconclusive` (should not happen — the tree is stable for the state).
2. Compare against the **verbatim** contract, never a paraphrase.
3. Evidence = file:line in the subject tree, plus base evidence for origin (Vector 2+).
4. No **unrouted** style nits, no redesign, no unrequested tests. Style hits go to the lens trail.
5. Explicitly label `NOT-A-BUG` when a checked suspicion clears — that keeps the coordinator from re-checking.
6. Return compact records; do not write the notebook (coordinator owns writes).
7. When {research_protocol} is present, run it and close with the RESEARCH TRACE footer; a missing trace is `inconclusive`, never a pass.

## Given budget & cost

- Set a per-child timeout and line budget at spawn. Over-budget or timed-out output is recorded as `inconclusive`, never `pass`.
- The coordinator fans out children per vector with a concurrency cap and merges their records into the findings page.

## Research protocol variants (filler for {research_protocol})

Vector 2 always fills the slot with Variant A; Vector 3 always fills it with Variant C (search-extensive); Vector 1 omits the slot. In `direct-tree` runs (no rail) the coordinator fills Variant B for both vectors. The coordinator resolves every placeholder (exact prefixed tool names, subject path, prefix, excluded namespaces, HEAD/base OID) before spawning — children see exact registered names, never generic aliases.

### Variant A — Vector 2, rail index (`research.mode: chhound-rail`)

```text
SUBSYSTEM RESEARCH (required — Vector 2)
The subject tree {SUBJECT_PATH} ({owner/repo} at {SUBJECT_OID}) is covered by the
sandbox index bound under prefix {ch_prefix}. Use ONLY these exact tools:
1. {ch_daemon_status_tool}
2. {ch_code_research_tool}
3. {ch_search_tool}
Do NOT use any other chhound namespace, including {excluded_namespaces} — those
index other repositories or review states.

Call {ch_daemon_status_tool}. If query_ready, call {ch_code_research_tool} to
trace "{angle}" end-to-end (callers, state transitions, failure paths,
persistence/version boundaries, tests, correlated sites), then {ch_search_tool}
(regex or semantic) to pinpoint at least one correlated site. Verify every
relevant line with read/grep in {SUBJECT_PATH}. The index may lag {SUBJECT_OID}:
never cite it as evidence and never decide origin from it. Origin requires
`git show {BASE_OID}:<path>`.

If the mapped tool is unavailable, not ready, or errors: make one honest
direct-tree fallback and record the reason; do not substitute another namespace.

Close your output with:

RESEARCH TRACE
mode: chhound-rail | direct-tree
tools-invoked-first-use: <exact names in order>
tool-call-count: <n>
daemon-query-ready: true | false | error
orientation-question: <one line>
pinpoint-query: <type + query, or n/a with reason>
search-log: n/a
search-call-count: n/a
code_research-used: n/a
verified-correlated-sites: <path:line list, or checked-none>
fallback/error: none | <exact reason>
```

### Variant B — no rail index (`research.mode: direct-tree`)

```text
SUBSYSTEM RESEARCH (required — direct-tree)
The manifest records no chhound rail covering this review; mode is direct-tree.
Do NOT invoke any chhound namespace, including {excluded_namespaces} — they
index other repositories or review states. Trace "{angle}" with git diff,
rg/grep, and direct reads in {SUBJECT_PATH}; follow the invariant/concept to
correlated sites beyond the assigned files. Verify origin only with
`git show {BASE_OID}:<path>`.

Close your output with:

RESEARCH TRACE
mode: direct-tree
tools-invoked-first-use: <exact names in order>
tool-call-count: n/a
daemon-query-ready: n/a
orientation-question: n/a
pinpoint-query: n/a
search-log: n/a
search-call-count: n/a
code_research-used: n/a
verified-correlated-sites: <path:line list, or checked-none>
fallback/error: no covering index
```

### Variant C — Vector 3, rail index search-extensive (`research.mode: chhound-rail`)

```text
SEARCH-EXTENSIVE RESEARCH (required — Vector 3)
The subject tree {SUBJECT_PATH} ({owner/repo} at {SUBJECT_OID}) is covered by the
sandbox index bound under prefix {ch_prefix}. Use ONLY these exact tools:
1. {ch_daemon_status_tool}
2. {ch_search_tool}
3. {ch_code_research_tool}   # allowed, never required
Do NOT use any other chhound namespace, including {excluded_namespaces}.

Call {ch_daemon_status_tool} first. If query_ready, lead every owned concept and
lens with {ch_search_tool}:
- regex queries for concrete symbols/patterns (usage sites, imports, duplicated
  literals/keys, version numbers);
- semantic queries for concept-level correlation (touch points for a second
  constraint, sites reading a config key, candidate consumers of a surface);
- iterate: refine queries from hits instead of stopping at the first result.
Minimum: at least TWO distinct search calls per owned concept/lens, and every
repo-wide claim (usage counts, absence of consumers, vocabulary duplication)
must be preceded by a logged search attempt. {ch_code_research_tool} may orient
a concept; it is never required.

Verify every cited line with read/grep in {SUBJECT_PATH}. The index may lag
{SUBJECT_OID}: search results are leads, never evidence. PR-specific vs
pre-existing stays base-diff based (`git show {BASE_OID}:<path>`).

If the mapped tool is unavailable, not ready, or errors: make one honest
direct-tree fallback and record the reason; do not substitute another namespace.

Close your output with:

RESEARCH TRACE
mode: search-extensive | direct-tree
tools-invoked-first-use: <exact names in order>
tool-call-count: <n>
daemon-query-ready: true | false | error
orientation-question: n/a
pinpoint-query: n/a
search-log: <type + query per call, first-use order>
search-call-count: <n>
code_research-used: true | false
verified-correlated-sites: <path:line list, or checked-none>
fallback/error: none | <exact reason>
```

### Shadow control (only when the operator opts in)

When the manifest sets `research.shadow: on` for a split, the coordinator additionally spawns one control child with the direct-tree variant (Variant B), prefixed `SHADOW CONTROL — your output is compared for measurement only and excluded from the review.` Its findings never enter aggregation; the comparison lands in the Vector-2/3 compliance record.