# intake-and-scope.md — Phase 0: pin the subject, build the contract

Phase 0 runs once per review. Its output is the **run manifest** — the single source of truth for every subsequent vector and the closure loop.

## 0.1 Verify the subject (preflight, ground truth)

Before any analysis:

- [ ] `gh auth status` — logged in, `repo` scope.
- [ ] `gh repo view <owner>/<repo>` reachable.
- [ ] `gh pr view <pr> --json headRefOid,baseRefOid,state,title` — PR exists and is OPEN; capture `headRefOid` + `baseRefOid` verbatim.
- [ ] Local checkout: either already present or cloneable. **If present, verify `git log -1` == headRefOid.** If it differs, fetch and checkout the pinned head. If the operator policy is `require_pr_head`, refuse to review a diverged tree.
- [ ] (pi) `notebook_index` responds.
- [ ] (pi, optional) chunkhound index readiness; fallback = bash/rg/grep. Missing index never blocks.

If any hard requirement fails: state the fallback (git/rg instead of chunkhound; inherit-parent instead of fleet groups) or STOP before fleet cost.

## 0.2 Capture the contract

Create `CONTRACT.md` in a scratch review dir (e.g. `/tmp/cure-<owner>-<pr>/):

1. PR **description** — the claims the implementer makes (feature list, validation counts, behavior promises).
2. Linked **issues/tickets** — full text: bullets, tech context, **locked decisions** (verbatim operator decisions are the durable contract).
3. **Host tech context** worth grounding (existing APIs the PR builds on; caveats the issue itself records).
4. The **changed-file list** and the **per-vector diff slices** (`git diff base..head -- <paths>` split per file, or `gh pr diff --name-only` + targeted hunks).
5. The pinned **head OID / base OID** and a note that everything below analyzes exactly this tree.

Rule: the contract is the PR's own words plus the issue's locked decisions — never the reviewer's paraphrase of intent. Preserve verbatim blocks.

## 0.3 Split vectors into pass slices

Each vector's fleet splits the contract surface. Example split for a model-group/spawn PR:

- conformance: derivation core · persistence/schema guard · spawn/router gate · main-session+TUI · tests
- implementation: sealed concepts the review already established (never open-ended)
- debt: pluggability · boundary ownership · versioning/migrations · projections · perf/operability

Slice granularity is chosen so each child reads a bounded file set + the relevant CONTRACT slice, and returns under a defined evidence budget.

## 0.4 Operator gate

Surface the manifest (head/base OID, vectors, splits, groups, gates, auto-draft policy) to the operator for confirmation **before Phase 0 mutates anything external**.

## Output

The run manifest (also written to the notebook page, see libs/pi-driver/notebook-plan-contract.md):

```text
run: owner/repo pr# @ headRefOid (base baseRefOid)
vectors: [..]  groups: {flash, code-review}
checkout_policy, auto_draft, pauses
changed_files: [...]
contract_path: /tmp/cure-.../CONTRACT.md
notebook: pipeline-frame-<owner>-<pr> + pr-<n>-review
```