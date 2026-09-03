# chhound-driver.md — the chunkhound research rail (pi-chhound plugin)

When the pi runtime provides the **pi-chhound** plugin, the review subject is pulled as a
chunkhound **PR sandbox**: a git worktree with its **own chunkhound index** — baseline
anchored at the PR's base branch, incremental top-up of the PR's own diff. The sandbox's
index is the primary *discovery* rail for the coordinator and fleet children; everything
else in the pipeline is unchanged. Plugin absent or broken → the plain detached worktree
(intake-and-scope.md §0.1) and git/rg research — the rail never blocks a review.

Check presence with `/ch-status` (plugin installed + chunkhound CLI on PATH). Nothing here
is a hard requirement; each step has a recorded fallback.

## Phase 0 recipe (plugin present)

1. **Create the sandbox** (one-go, non-interactive):
   `/chworktree https://github.com/<owner>/<repo>/pull/<n> --dest <dir>`
   The PR URL carries the repo identity; the sandbox branch is `pull/<n>`. Use a **unique
   `--dest` per review state** — fresh sandboxes for the same PR must never collide in the
   shared root.
2. **Capture the subject**: `git -C <sandbox-path> rev-parse HEAD` → manifest `subject_oid`;
   the sandbox dir → `subject_path`. Whatever SHA the pull has **is** the review subject
   (subject rule, intake-and-scope.md §0.1) — no refusal ladder when it differs from the
   gh-reported remote head; record the difference in the manifest as informational context.
3. **Connect the index**: `/ch-mcp <path-or-storage-id printed by /chworktree> --prefix chh_pr<n>`
   (`pull/<n>` is not a reliable selector — use the printed path/id). The fixed `--prefix`
   makes tool names deterministic. Verify: footer `🔌 ch-mcp: 1 connected` + `/ch-status`.
4. **MCP lifecycle**: one live bridge per sandbox. Before connecting a fresh sandbox for
   the same PR, disconnect the old one: `/ch-mcp <old-id> --disconnect`. Two live bridges
   with the same prefix would be ambiguous.

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
baseline and top-up can lag the checkout — so:

- every `file:line` surfaced by a research tool is **re-read in the subject checkout**
  before it may become finding evidence;
- evidence anchors are files in the subject tree at `subject_oid` (evidence-format.md);
- a research tool that errors or returns stale-looking results is a fallback trigger
  (git/rg), never a finding on its own.

## Fallbacks (never block)

- Plugin absent: `/ch-status` errors → plain-worktree pull (intake-and-scope.md §0.1).
- Connect fails / daemon dies: reconnect once; else record the fallback in the run frame
  and use git/rg.
- `chh_*` tools missing in a child session: fall back to git/rg and note it in the child's
  return record.

## Re-pull (new review state)

New commits on the PR are **not an error** — the operator decides at a gate. A re-pull is
a **strict state transition**: after all children of the current state have settled,

1. fresh sandbox: `/chworktree <PR-URL> --dest <new-unique-dir>` (or plain worktree),
2. disconnect the old bridge (`/ch-mcp <old-id> --disconnect`),
3. capture the new subject OID into a new manifest/frame,
4. re-validate the old findings against the new tree via the closure loop
   (closure-verification.md) — old children's outputs never roll into the new state.
