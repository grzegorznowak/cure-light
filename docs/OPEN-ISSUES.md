# OPEN-ISSUES.md — known open conflicts in the cure-light model

Tracked honestly, so a fresh bootstrap does not re-derive them or present deferred work as fixed.

## 1. Auth-aware group semantics (deferred, design)

Vector 3 flagged four divergent "what can this group do" semantics (validation auth-aware vs derivation auth-blind vs registry gate vs boot prompt). The engine now passes a `ConstraintMemberResolution` snapshot and deliberately leaves auth-aware aggregation as a **recorded operator decision**, not silently resolved. Model gap: the same group can render four different capability answers.

- **Priority**: MED. Affects routing correctness over time as catalogs acquire/remove authenticated members.

## 2. Uncached derivation (deferred, perf)

`resolveConstraintMembers` maps each member through `registry.find` on every read (boot + each agent start + each required spawn-route). No cache/version/invalidation boundary. Long sessions with repeated required spawns re-find members unboundedly.

- **Priority**: LOW (perf); tracked as a follow-up, not part of any review finding.

## 3. Moving-head race — RESOLVED by design (v0.5.3)

Closed by the subject model: cure-light reviews a dedicated **pulled tree** (chunkhound sandbox or plain worktree) that nothing mutates mid-run; the pull's SHA is captured once at Phase 0 (`subject_oid`) and is the version under review — reviewing the latest is the point, not a risk. New commits only enter through a deliberate, operator-gated re-pull that starts a new review state, and every finding row carries the `subject_oid` its evidence was read from. The old race (a tree moving under an active review) cannot occur by construction. Residual: children still record `subject_oid` per row; a tree differing from the state's subject is `inconclusive` (evidence-format.md).

## 4. closed-by-operator scope

"Don't re-raise MG-01" style suppression is recorded with a scope, but re-opened-by-evidence is not fully specified (when does new evidence structurally differ?). Recommend: re-open only if the failing code path is rewritten, not if only commentators change.

## 5. notebook as shared memory, not a database

The notebook advertises replay convenience only (no CAS, no audit, no cross-machine). A fresh machine starts a new run; the run frame's SHA is the continuity root, not the notebook. Any multi-machine fleet contract must not assume shared shared-state semantics (children should not rely on shared notebook pages across machines).

## 6. Posting is operator-gated, not automated

There's no auto-post flow; the single review comment waits for operator approval (`before_post` is mandatory whenever drafting is enabled). That's a feature, but it means the pipeline ends awaiting humans. A future version could offer a "wet-batch" mode for trusted repos with clear review-eyes-off.

## 7. Dependency: model-groups plugin present

Fleet groups (`flash`, `code-review`, `planner`, ...) exist only if the model-groups plugin is present. Requirement check downgrades to inherit-parent spawning otherwise, but that silently changes fleet parallelism. The conservative reading is: a pi runtime WITHOUT the plugin should run the pipeline in single-pass mode, not pretend it has a fleet.

## 8. Hygiene lens: deterministic preflight is repo-dependent

The `type`/`dead` lenses have a deterministic accelerator (run the repo's own strict tsc / lint on the subject tree), but repos self-host very differently: some have no tsc/build at all, some pin a lax config, some need a long install. The fallback (static sight, flagged `inconclusive-mechanical`) is honest but weaker evidence. Consequence: lens *coverage* is guaranteed (named atoms + lens matrix); only the *determinism* of the mechanical lenses varies. Acceptable at v0.2; a future step could vendor a pinned minimal lint/type narrow for common stacks.

- **Priority**: LOW. Coverage guaranteed regardless; only mechanical strength varies.
