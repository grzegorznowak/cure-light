# chhound-driver.md — the chunkhound research rail (pi-chhound plugin)

When the pi runtime provides the **pi-chhound** plugin (installed, rail operator-confirmed — see presence below), the review subject is pulled as a
chunkhound **PR sandbox**: a git worktree with its **own chunkhound index** — baseline
anchored at the PR's base branch, incremental top-up of the PR's own diff. The sandbox's
index is the primary *discovery* rail for the coordinator and fleet children; everything
else in the pipeline is unchanged. Rail unconfirmed or broken → the plain detached worktree
(intake-and-scope.md §0.1) and git/rg research — the rail never blocks a review.

The rail's commands — `/ch-status`, `/chworktree`, `/ch-mcp` — are **operator-side slash
commands**: the coordinator cannot run them, and their UI output reaches the model only
when the operator reports it. Presence is therefore checked in two steps:

1. **Install detection (coordinator, at boot)** — model-executable, no `/ch` invocation:
   pi-chhound appears in the pi settings `packages` (or an extension dir) and the
   `chunkhound` CLI is on PATH.
2. **Rail confirmation (operator, at the frame gate)** — when the install detection is
   positive, the coordinator instructs the operator to run `/ch-status` and report the
   output: the authoritative check that the rail is live in this session. No confirmed
   rail → the plain-worktree plan stands.

Nothing here is a hard requirement; each step has a recorded fallback.

## Phase 0 recipe (rail confirmed)

The operator executes the `/ch` commands below (slash commands) — a first pull only: an
in-place re-pull needs no `/ch` command (see Re-pull). The coordinator verifies with
model-side checks — capture commands, `chh_*` tool responses, fallback rules.

1. **Create the sandbox** (one-go, non-interactive):
   `/chworktree https://github.com/<owner>/<repo>/pull/<n> --dest <dir>`
   The PR URL carries the repo identity; the sandbox branch is `pull/<n>`. Use a **unique
   `--dest` per sandbox** — fresh sandboxes for the same PR must never collide in the
   shared root (a re-pull reuses its own sandbox, so this applies only when one is created).
2. **Capture the subject**: `git -C <sandbox-path> rev-parse HEAD` → manifest `subject_oid`;
   the sandbox dir → `subject_path`. Whatever SHA the pull has **is** the review subject
   (subject rule, intake-and-scope.md §0.1) — no refusal ladder when it differs from the
   gh-reported remote head; record the difference in the manifest as informational context.
3. **Connect the index**: `/ch-mcp <path-or-storage-id printed by /chworktree> --prefix chh_pr<n>`
   (`pull/<n>` is not a reliable selector — use the printed path/id). The fixed `--prefix`
   makes tool names deterministic. The operator verifies the footer `🔌 ch-mcp: 1
   connected`; the coordinator confirms the prefixed tools respond (`chh_pr<n>_daemon_status`
   — a tool-list registration alone does not prove a response).
4. **MCP lifecycle**: one live bridge per sandbox; an in-place re-pull keeps its bridge.
   Before connecting a *fresh* sandbox for the same PR, disconnect the old one:
   `/ch-mcp <old-id> --disconnect`. Two live bridges with the same prefix would be ambiguous.

## Tool names (prefix `chh_pr<n>`, fixed at connect)

| Tool | Purpose | When |
|---|---|---|
| `chh_pr<n>_code_research` | architecture / data-flow research ("how does X work end-to-end?") | **first**, before deep reading; follow-up queries chain on it |
| `chh_pr<n>_search` | pinpointing (regex / semantic) | after research, to locate exact symbols and lines |
| `chh_pr<n>_daemon_status` | index health only | when results look stale; never proof of index freshness vs the subject |
| `chh_pr<n>_websearch`, `chh_pr<n>_fetchurl` | external / host documentation | never for the subject tree |

Spawned children **inherit the live `chh_*` tools automatically** (extension-factory
replay) while the parent session holds the connection — no per-child setup; children never
spawn daemons. A resumed session auto-restores its recorded connections.

## Evidence rule (mandatory)

MCP output is **discovery only**. The index carries no manifest-SHA provenance — its
baseline and top-up can lag the checkout (after an in-place re-pull the live re-index
converges on the new subject, transiently mixing old- and new-subject chunks) — so:

- every `file:line` surfaced by a research tool is **re-read in the subject checkout**
  before it may become finding evidence;
- evidence anchors are files in the subject tree at `subject_oid` (evidence-format.md);
- a research tool that errors or returns stale-looking results is a fallback trigger
  (git/rg), never a finding on its own.

## Symbol sweep — the state's symbol map

A changed shared sentinel / constant / identifier is an API-wide change: the `blast` lens's
`sweep` row needs every consumer enumerated, and the **deterministic preflight** produces
that enumeration once per review state as the manifest's `symbol_sweep` artifact
(blast-lens.md / intake-and-scope.md). The artifact is the state's **symbol map**: the
diff-extracted symbols, a complete occurrence census, and the usage heat that every pass
needing usage knowledge reuses (V3 debt and the yagni pass read it as a lead inventory;
the comment renders it) — instead of re-deriving "where is this used?" with separate
searches. A **dedicated sweep child** executes it — chunk dumps, pagination, and noise
stay inside that child, which returns the map only; the coordinator writes it to the
state's page `symbol-map-<owner>-<pr>-s<n>` on pi runs, or a scratch file recorded in
the manifest in fallback runs (notebook-plan-contract.md).

1. **Extract the symbol set** — bash on the subject tree: `git diff -U0 <base_oid>..<subject_oid>`
   gives the per-file changed line ranges and the identifiers on added/removed lines.
   Drop language keywords and names shorter than 3 characters, dedupe, cap at ≈30–40
   (record drops), and lead with any explicit symbols the operator supplied (manifest
   `symbol_sweep_symbols`, or the sweep-child prompt). Keep the changed ranges for steps 3–4.
2. **Probe per symbol, never batched** (one symbol per query keeps every hit attributable).
   Call `{ch_prefix}_daemon_status` once; if not `query_ready`, or the rail is absent,
   skip the chunk sample — the census (step 4) always runs, and accounting moves fully
   to tree reads (step 5). For each
   symbol call `{ch_prefix}_search` with
   `type: regex`, query `\b<symbol>\b` (RE2; escape metacharacters), `page_size: 3–5`.
   The hit count is the footer's `of <total>` — **chunks, not occurrences**. Page
   further whenever `total` exceeds the fetched results, capped (e.g. ≤3 pages per
   symbol, ≤15 extra pages total), prioritizing symbols showing `outside` occurrences.
   The paginated sample is **triage, not coverage**: its caps bound how many enclosing
   chunks are read for the worth-ingesting call, are recorded as triage metadata, and
   never bound the census (step 4).
3. **Classify against the diff** — a hit chunk whose `Lx–Ly` range intersects a changed
   range for the same file is `in-diff`, else `outside`. Chunk granularity is coarse: a
   chunk spanning both counts `in-diff` (under-counts outside use, never over-counts) and
   can be re-read in the tree.
4. **Coverage census (always runs)** — enumerate every occurrence of each symbol with
   `rg -n -w` (one `-e`-joined pass is enough) over the **census scope**: the tracked
   files at `subject_oid` (`git ls-files`-driven), exclusions recorded (ignored / hidden /
   binary / vendored), and the exact command. The match unit is the **symbol-line**: a
   `(path, line)` counts once per selected symbol whose literal name occurs there — each
   returned line is attributed to every selected symbol it matches; `\b` boundaries match
   **literal names, not resolved symbols** (same-name declarations elsewhere are
   included, and the symbol's own definition counts). Classify each occurrence against
   the same changed ranges. The census is the coverage claim: complete **over the
   declared scope**, tree-accurate even when the index lags; completion and any errors
   are recorded — a scope that could not be fully searched is never silently narrowed.
5. **Symbol map (the artifact)** — a header: owner/repo PR, review state, `base_oid` /
   `subject_oid`, selected / dropped / operator-added symbols, census scope + command +
   provenance (`rg census @ <subject_oid>`), completion notes, and the rail triage
   metadata (`chhound index, review state <subject_oid>`; records the state, not a
   freshness guarantee — the index carries no SHA provenance, Evidence rule) marked
   **discovery-only**. Then the bounded heat table:

   ```text
   symbol | change | total | in-diff | outside | outside locations (capped) | note
   ```

   `change` is lexical (added / removed / both from the diff lines); `total` / `in-diff` /
   `outside` are census matching-line counts; a capped row keeps its counts and puts the
   census command that re-derives the full list in `note`. Bounds: the heat table lists
   every selected symbol; per-symbol locations and the whole map are budgeted (e.g. ≈25
   locations per symbol, ≈400 lines per map) — the rail caps bound the triage sample
   only, never the census.

   Every `outside` occurrence gets a disposition from the owning V2 split: tree-read and
   accounted — verified as a consumer (a lead, tree-verified like any index output,
   Evidence rule) or judged not a consumer at the site — or routed as an uninspected
   finding → the in-scope route (blast-lens.md), which leaves the row a hit.
   **Enumeration complete is not inspection clear**: a chunk-triaged occurrence is
   navigation metadata, never clearance — the `sweep` row clears only when every
   `outside` occurrence is tree-read and accounted; the in-diff occurrences are covered
   by the diff review.
6. **No confirmed rail → `mode: rg`** — the census is the same `rg -n -w` pass; without
   chunk triage, occurrences are triaged by reading their lines in the tree. The map is
   marked `mode: rg`, which never invokes a `chh_*` namespace.

## Fallbacks (never block)

- Rail unconfirmed (install detection negative, or the operator's `/ch-status` report shows no rail) → plain-worktree pull (intake-and-scope.md §0.1).
- Connect fails / daemon dies: reconnect once; else record the fallback in the run frame
  and use git/rg.
- `chh_*` tools missing in a child session: fall back to git/rg and note it in the child's
  return record.

## Re-pull (new review state)

New commits on the PR are **not an error** — the operator decides at a gate. A re-pull is
a **strict state transition** (the operator decides; the coordinator executes and captures):
after all children of the current state have settled,

1. update the existing subject **in place**: fetch the new head into the tree's repo and
   check it out detached (`git -C <subject_path> fetch …` + `git -C <subject_path> checkout --detach <new head>`).
   A rail sandbox updates the same way — plain git, no `/ch` command: its live daemon
   re-indexes the sandbox automatically and the MCP bridge stays connected (same dir, no
   reconnect, no fresh baseline copy).
2. pull fresh instead when the tree is gone/broken, the mechanism changes, or the operator
   prefers a clean tree: `/chworktree <PR-URL> --dest <new-dir>` and/or `/ch-mcp` — a new
   sandbox means disconnect the old bridge (`/ch-mcp <old-id> --disconnect`) and connect
   the new one; the plain path gets a fresh worktree/clone (intake-and-scope.md §0.1).
3. capture the new subject OID (and the base OID) into a new manifest/frame — an in-place
   re-pull records the same `subject_path` with the new `subject_oid`; the previous state's
   content stays reachable at its own OID (`git show`).
4. re-validate the old findings against the new tree via the closure loop
   (closure-verification.md) — old-state content is read at its own OID (the working tree
   now holds the new subject), and old children's outputs never roll into the new state.
