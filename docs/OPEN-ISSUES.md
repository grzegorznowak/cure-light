# OPEN-ISSUES.md — known open conflicts in the cure-light model

Tracked honestly, so a fresh bootstrap does not re-derive them or present deferred work as fixed.

## 1. Auth-aware group semantics (deferred, design)

Vector 3 flagged four divergent "what can this group do" semantics (validation auth-aware vs derivation auth-blind vs registry gate vs boot prompt). The engine now passes a `ConstraintMemberResolution` snapshot and deliberately leaves auth-aware aggregation as a **recorded operator decision**, not silently resolved. Model gap: the same group can render four different capability answers.

- **Priority**: MED. Affects routing correctness over time as catalogs acquire/remove authenticated members.

## 2. Uncached derivation (deferred, perf)

`resolveConstraintMembers` maps each member through `registry.find` on every read (boot + each agent start + each required spawn-route). No cache/version/invalidation boundary. Long sessions with repeated required spawns re-find members unboundedly.

- **Priority**: LOW (perf); tracked as a follow-up, not part of any review finding.

## 3. re-review over a moving head is inherently racy

If head moves between the manifest capture and a fleet child reading the tree, evidence mixes SHAs. The current guard = "inconclusive" on mismatch + new-run-per-head. Residual: an agent could read the wrong tree if it doesn't verify. Actual improvement path: make the child prompt's first action a `git log` check (currently recommended, not enforced).

## 4. closed-by-operator scope

"Don't re-raise MG-01" style suppression is recorded with a scope, but re-opened-by-evidence is not fully specified (when does new evidence structurally differ?). Recommend: re-open only if the failing code path is rewritten, not if only commentators change.

## 5. notebook as shared memory, not a database

The notebook advertises replay convenience only (no CAS, no audit, no cross-machine). A fresh machine starts a new run; the run frame's SHA is the continuity root, not the notebook. Any multi-machine fleet contract must not assume shared shared-state semantics (children should not rely on shared notebook pages across machines).

## 6. Posting is operator-gated, not automated

There's no auto-draft flow; every `gh pr comment` / `gh issue` waits for operator approval. That's a feature, but it means the pipeline ends awaiting humans. A future version could offer a "wet-batch" mode for trusted repos with clear review-eyes-off.

## 7. Dependency: model-groups plugin presence

Fleet groups (`flash`, `code-review`, `planner`, ...) exist only if the model-groups plugin is present. Requirement check downgrades to inherit-parent spawning otherwise, but that silently changes fleet parallelism. The conservative reading is: a pi runtime WITHOUT the plugin should run the pipeline in single-pass mode, not pretend it has a fleet.