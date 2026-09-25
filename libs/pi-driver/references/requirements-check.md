# requirements-check.md — preflight, ground truth not optimism

Run BEFORE the fleet spends anything. Each line is a hard gate with a fallback or a stop.

Two groups: **pre-pull rows** run at boot and feed the frame gate (they need only gh + the runtime, never a local tree); **deferred rows** (5/8/9) need the pulled subject and run at the **Phase 0 gate** — the check is marked complete only after they have run. Nothing in the target repo is cloned, checked out, or read locally before the subject pull (subject-first, kernel/SKILL.md §2).

**Declared environment + toolchain rows (10–11).** The initial environment description declares python ≥3.11, uv/venv, the exact producer dependency pins (`tree-sitter==0.26.0`, `tree-sitter-markdown==0.5.1`) and network access to fetch the engine's pinned tool copies; rows 10–11 verify that declaration before Phase 0. The tools are engine-side, so fetching them is not target-repo access. Missing/wrong pinned dependencies fail loud (exit 2) — there is no hand-built registry fallback.

## Hard requirements

| # | Runs | Check | Command(s) | Fail → |
|---|---|---|---|---|
| 1 | pre-pull | gh authenticated, repo scope | `gh auth status` | STOP (review needs review-comment drafting) |
| 2 | pre-pull | target repo reachable | `gh repo view <owner>/<repo>` | STOP |
| 3 | pre-pull | PR exists, OPEN; base OID + remote head OID captured (informational) | `gh pr view <pr> --json headRefOid,baseRefOid,state,title` | STOP or ask |
| 4 | pre-pull | subject mechanism planned: rail live via the `ch-chhound status` model probe → chunkhound PR sandbox; where the probe is blocked (`modelTools=off`) or absent (older build) install detected (pi settings `packages` / extension dirs + `chunkhound` CLI on PATH) → sandbox **pending the operator's `/ch-status` confirmation at the frame gate**; neither → plain detached worktree | `ch-chhound {action: "status"}`; inspect pi settings / extension dirs; `chunkhound` on PATH | record the fallback mechanism in the frame; never a stop by itself |
| 5 | Phase 0 | (chhound rail) sandbox/bridge ready; prefixed tool responds (an in-place re-pull retains the bridge) | first pull: `ch-chhound {action: "worktree.create", pr: "<PR-URL>", connect: true}` (fallback `/ch-mcp … --prefix chh_pr<n>`); re-pull: `git -C <subject_path> fetch/checkout`; then `{ch_prefix}_daemon_status` | reconnect once (`ch-chhound {action: "mcp.connect", target: "…"}` or operator `/ch-mcp`); else record fallback (plain worktree + git/rg), never stop |
| 6 | pre-pull | notebook writable (pi) | `notebook_index` returns pages | fallback: session-scratch dir (frame/findings) + contract on disk; **no authoritative coverage ledger, claim registry, source pins or gate-disposition store** — Vector 1's completeness flags cannot all clear and `review_basis` cannot be asserted `ready`; note durability loss |
| 7 | pre-pull | fleet groups present (pi + model-groups) | inspect group list (flash/code-review/…) | fallback: inherit-parent spawn, note in frame |
| 8 | Phase 0 | git diff base..subject works on the **pulled** tree | `git -C <subject-path> diff <base_oid>..<subject_oid> --stat` | fetch the base ref into the tree's repo and retry; if still failing → STOP |
| 9 | Phase 0 | (chhound rail) index health | `{ch_prefix}_daemon_status` | use bash/rg/grep; never block |
| 10 | pre-pull | pinned toolchain fetched + verified: `claim-registry` 0.3.0, `gate-check` 0.2.0, `census` 0.1.0 — artifact sha256 equals `TOOL.json.artifact.sha256` and the artifact verifies itself | `sha256sum <unit>.pyz`; `python3 <unit>.pyz --check-pin "$(python3 -c 'import json;print(json.load(open("TOOL.json"))["artifact"]["sha256"])')"` | STOP: a pin mismatch is never relaxed — re-fetch by pin; never substitute the subject tree's `tools/` copy |
| 11 | pre-pull | producer environment ready: python ≥3.11, `uv`/venv available, exact deps importable from the pre-set-up env (`uv venv` + `pip install 'tree-sitter==0.26.0' 'tree-sitter-markdown==0.5.1'`) | `python3 <producer>.pyz --describe`; `python3 -c "import tree_sitter, tree_sitter_markdown, importlib.metadata as m; print('tree-sitter', m.version('tree-sitter'), 'tree-sitter-markdown', m.version('tree-sitter-markdown'))"` | fail-loud exit 2 → STOP the producer path (no fallback registry; a degraded Phase 0 needs explicit operator authorization and can never claim a complete claim universe) |

Row 4 semantics: the `ch-chhound` probe and the fallback ladder are defined in chhound-driver.md §Presence. The frame's planned mechanism is a **plan**, never a sandbox guarantee — a sandbox failure at Phase 0 falls back per chhound-driver.md (plain worktree + git/rg). Row 8 is a post-pull check on the pulled tree only: `gh pr diff` NEVER substitutes the subject diff — the remote head may differ from the pulled subject, and diffing the wrong tree would corrupt scope and origin classification.

## Fallback policy

- Research tools missing → git diff, `rg`, `grep`, direct `read`. Evidence quality stays the same; cost rises a little.
- Fleet groups missing → single-agent review with inherit-parent spawning; the pipeline still runs, each "child" is a serialized pass. Note the downgrade in the frame.
- Notebook missing → scratch dir for frame/findings (same layout minus the authoritative coverage store); findings survive until context compaction (warning given). Vector 1 accounting has no authoritative ledger and the run must not assert complete coverage; the source-designation/consistency and `review_basis` records also lack an authoritative store — record the limitation and never assert `ready` (conformance-pass.md; notebook-plan-contract.md).
- Pinned toolchain absent/unverifiable or producer deps missing → STOP the producer path. `gate-check`/`census` are stdlib + git and still run, but the producer cannot: there is no hand-built registry fallback, and the run cannot assert a complete claim universe or `review_basis: ready`. The operator may authorize an explicitly limited diagnostic that discloses Phase 0 ran without the pinned producer.

## Stop conditions

- gh auth or repo unreachable → stop; the review has no output channel and no evidence base.
- (Phase 0) the subject tree cannot be pulled at all → stop; no evidence base (intake-and-scope.md §0.1). Pre-pull there is deliberately no subject tree — a missing tree stops the run only when the Phase-0 pull itself fails.
- (Phase 0, row 8) the pulled tree still cannot diff base..subject after a fetch retry → stop; origin classification needs the base diff, and `gh pr diff` never substitutes it.
- (chhound rail) rail confirmed but sandbox/connect/index broken → recorded fallback (plain worktree + git/rg), never a stop by itself.
- (pre-pull, rows 10–11) a pinned artifact's sha256/`--check-pin` fails, or the exact producer deps are missing/wrong → stop; re-fetch by pin / provision the pinned venv. Never relax the pin, never install a different version, and never substitute the subject tree's `tools/`.

## Output of the check

A short table written into the run frame: `requirement (ok | fallback | deferred-to-Phase-0) | evidence`. The frame's **planned subject mechanism** line gives the operator boot-time visibility of how the subject will be pulled — presence, not a guarantee. The toolchain rows record artifact versions + sha256 and the `--check-pin`/dependency result. Rows never mix pre/post-pull results; the check is marked complete only after the deferred rows ran at the Phase 0 gate. If anything fell back, the frame says so — the closure loop and any later context must know the evidence base was narrower. The check records requirement rows only: contract-adequacy dispositions are separate, later records — the provisional source-consistency/`repair_required` outcome at the Phase-0 gate and the `review_basis` at the V1 gate (intake-and-scope.md §0.2/§0.4; conformance-pass.md) — never folded into this table or the boot-time frame seal.
