# workflows/ — pi `/workflow` scripts for the review engine

Deterministic mechanical workflows for cure-light coordinator phases, written in the
pi-schematic `/workflow` author contract. Host tooling: `kernel/` and the pinned tools
(`verify.mjs`, `chunker.mjs`) stay untouched, and `verify join` remains the sole mechanical
acceptance boundary.

Start here: [`AUTHORING.md`](AUTHORING.md) — the builder loop, the test surfaces and the
purity rules. Then the packages:

| Path | Role |
|---|---|
| `AUTHORING.md` | catchall entry point for anyone building under `workflows/` |
| `run.mjs` | tier runner: `fast \| acceptance \| compile \| host \| prop \| all` |
| `p0/` | the p0-close workflow: merge/validate/p05/envelope ([`p0/SPEC.md`](p0/SPEC.md)) |
| `pack/` | the p0-pack workflow: P0.4 packing bridge — claims-list, assignments, instructions ([`pack/SPEC.md`](pack/SPEC.md)) |
| `review/` | the p0-review workflow: P0.1 source capture + P0.2 claims draft in one run — spec-only, not implemented ([`review/SPEC.md`](review/SPEC.md)) |
| `review-understanding/` | separate two-run PR summary and split suggestions; structured/prose comparison ([usage](review-understanding/README.md)) |
| `architecture-iteration/` | co-located DDD/EventStorming workflow, companion and five skills; project-link installer, fresh rounds and resume ([usage](architecture-iteration/README.md)) |
| `testkit/` | shared host harness: stub host, case runner, real pi CLI driver, smoke cases, CLIs ([`testkit/HOST-HARNESS.md`](testkit/HOST-HARNESS.md)) |

Status: **p0-close is merged**. The `p0-pack` implementation is adopted by the kernel
call site in the uncommitted `mods/p0-pack` worktree, but is not merged or installed. The
engine prompts name it as the only P0.4 packer. `p0-review` is spec-only: no
`p0-review.js`, no `p0-claims` skill and no review test yet. It replaces the separate
P0.1 capture workflow and the spawned P0.2 claims child with one capture-then-claims run.
Review-pass verification (2026-10-19):
fast 60, host 56, prop 41, acceptance 3, compile 4. Rerun the tiers for the current counts.
Compile needs a complete pi-schematic checkout: set `PI_SCHEMATIC_CHECKOUT` if the default
checkout lacks `workflow/types.js`. That missing file is an environment failure, not a
draft failure.

Proposals this follows (workspace root, outside this repo):

- `cure-light-p0-close-workflow-proposal.md` — merge/validate/p05 + envelope
- `cure-light-records-workflow-proposal.md` — stage/state-head page write + read-back (not built; host invocation gap)

## Test tiers

Run these commands from the cure-light repo root.

| Tier | Runs | Role |
|---|---|---|
| fast (default) | `testkit/`, `p0/test/`, `pack/test/`, `review/`, `review-understanding/test/`, `../libs/pi-driver/test/`, `../ddd-iteration/test/` without a tier token | fixture sanity, stub-host self-test, sealed contracts, bounded fleet transport |
| host | `*.host.test.mjs` | the same cases through the real pi CLI + purity reruns |
| prop | `*.prop.test.mjs` | generated-input properties over mutation programs |
| acceptance | `*.acceptance.test.mjs` | frozen-baseline byte equality on a scratch copy; baseline required unless `P0_PACK_ACCEPTANCE_OPTIONAL=1` |
| compile | `*.compile.test.mjs` | `node --check` + canonical compile with a complete pi-schematic checkout |

```bash
node workflows/run.mjs             # fast (default) — the build loop
node workflows/run.mjs host        # real pi CLI, opt-in (seconds per case)
node workflows/run.mjs all         # every tier
```

## Governance

- Not used by the controlled replication arm unless the operator pins this branch; these
  workflows are not an engine tool and add no verify command, registry or schema.
- Workflow files follow the author contract: one top-level `return defineWorkflow(...)`,
  synchronous, no imports, checkpoints for budgets. A pure workflow uses `workflow.shell`
  as its only I/O. `p0-review` is the exception: one `workflow.shell` capture phase plus
  one `workflow.run` claims turn.
- Verification ladder before any install: canonical compile, the simulation suite with a
  fault matrix, then one bounded live run by path (see `p0/SPEC.md`).

## Simple PR understanding

[`review-understanding/`](review-understanding/README.md) is a separate, deliberately small
workflow: understand a PR from its description, linked issues and diff, then suggest
reviewable splits. It uses two model calls, with structured output on the first by default
and `--plain` for comparison. It is not part of the pipeline below and is not auto-installed.

## Architecture iteration

[`architecture-iteration/`](architecture-iteration/README.md) takes an explicit strategic
DDD document through EventStorming rounds. Each round starts in a fresh session with
committed artifacts as its only prior-round domain input. A DDD master, document-grounded
expert and three distinct voices produce event flows, context maps and architecture
candidates, including stressor analysis. Full snapshots support human answers and resume.
The package owns its workflow, companion and five skills in the canonical `ddd-iteration` repo, cloned at `../ddd-iteration` (single source of truth; older local copies are decommissioned). From this repository root, run `node ../ddd-iteration/install.mjs --dry-run` to preview project discovery links, then omit `--dry-run` to create them. The installer links the current working directory's `.pi` folders only (no `--project`; no global mode). Existing same-target links are preserved; conflicting files/directories or links stop installation before writes. Nothing is overwritten or deleted.

Start Pi from the target project root and use `/reload` after installing/changing skills.
Invoke `/workflow architecture-iteration ./workshop.json` or the explicit installed
`./.pi/workflows/architecture-iteration.js` path. Native workflow completion can omit
symlinked files; manually entered names still resolve. Direct source invocation remains
supported from this repository root; global and arbitrary-path launches are unsupported.
See the package README for source binding, configuration and trust checks. Installation
is explicit and does not authorize a live workshop; no provider-backed workshop has run.

## Continuous diagnostic prototype (paused)

The pipeline work below is paused by user direction on 2026-10-29. Its historical evidence
and existing implementation remain unchanged.

[`pipeline/README.md`](pipeline/README.md) documents the new single-command
`/workflow review <JSON>` runner. It uses readonly, group-bound structured skills and a
JS host. Upfront authorization replaces routine vector approvals; evidence/readiness
failures still HOLD and posting stays manual.

This experimental package explicitly selects `structured-review/v1`. It does not claim
legacy delegated `verify join` acceptance or change the legacy boundary described above.
It is locally installed and partially live-tested, not all-vector verified. The sixth
one-shot attempt is CLOSED: collection passed, but the independent audit found seven V1/V2
failures and terminal V2 HOLD. See [sixth-slice evidence](../docs/review-pipeline/CHILD-CONTRACT-LIVE-20261028.md).
That pre-gate V1 baseline accepted a JSON-prefix relay despite a whole-native fidelity gap;
V2 again dispatched a singleton. The [V1 native integrity gate](../docs/review-pipeline/V1-NATIVE-INTEGRITY.md)
is now implemented and changed-part/compiler tested after exact-group `flash` spec approval.
Independent readonly code review returned APPROVE with no blockers. The [closed seventh attempt](../docs/review-pipeline/V1-NATIVE-INTEGRITY.md#closed-seventh-attempt-evidence)
passed V1 native/relay fidelity, including reverse completion; P0/V1/V2 were accepted.
One frozen audit reports 496 pass, 8 not applicable and zero failures: collection/checks
passed, but HOLD, allVectorPass=false and reviewCompleted=false. V3's two concurrent
valid whole native reports became a model-declared complete relay containing only v3-1;
the runner safely held before V3 acceptance, finish or draft. Final closure and freeze
release were confirmed at 2026-10-29T06:06:26.427Z. Workflow cost/time was
$1.915166872/950726 ms, below $3/20 minutes. That historical relay gap led to the implemented,
independently approved [retention policy](../docs/review-pipeline/RELAY-RETENTION.md).
The [eighth attempt](../docs/review-pipeline/RELAY-RETENTION-LIVE-20261029.md) collected safe V3 HOLD,
not completion. The [V3 outcome policy](../docs/review-pipeline/V3-OUTCOMES.md) is implemented,
targeted-tested and independently implementation-approved.

Current checkpoint (2026-10-29 UTC): the [eleventh attempt](../docs/review-pipeline/BOUNDED-AUTHORING-LIVE-20261029.md)
is CLOSED / FREEZE RELEASED, with **capability FAIL at clean P0 HOLD**, not a V3 test.
Corrected NEW infrastructure passed 17 tests and separate final prelaunch APPROVE before parent ONE run;
actual observer READY, five registrations and whole initial capture succeeded. P0 c9 changed a source
LF to SPACE at quote byte 13. Native complete was not host acceptance; the unchanged exact quote guard
correctly held. Both FULL rejected outputs/ledger and `hold_failure:null` were preserved.
Workflow: 35.675 seconds / USD0.010894284. Normal collection passed all 14 gates with 796 immutable files;
ONE actual raw audit exited 0, 91 pass / 7 N/A / 0 fail, classification HOLD. Separate result review,
parent full-report reads and final closure/current freeze/release are DONE. All ELEVEN attempts are
immutable and off limits; never reopen or rerun their evidence.

[V3 bounded authoring](../docs/review-pipeline/BOUNDED-AUTHORING.md) is normative APPROVED,
implemented, targeted-tests PASS and independently implementation-approved; parent full-read is COMPLETE.
V1/V2/V3 were not reached, so bounded authoring remains **UNEXERCISED live**. No accepted V2 finding or
completed draft exists to compare here. Only pre-return worker authoring changed; whole returned values,
host byte authority, all duties, exact groups and budgets stay fixed. The spec's
[verification evidence](../docs/review-pipeline/BOUNDED-AUTHORING.md#verification-evidence) binds current
worker bytes and separate deterministic results, not model compliance or reliability. Fleet formation
and report capacity remain separate; singleton cause is UNPROVED. P0 verbatim quote preservation is
the next observed frontier, with no new policy selected in this documentation update.

No implicit reset, native adoption, atomic report, retry or repair follows, nor a deterministic
batching/all-vector claim. Clean/defective completion, varied/repeated cases, source failures and
explicit incremental absorption remain open; no genuine blocker is proved. FAST includes its
deterministic host and model-stub tests; the real-host tier remains opt-in. See its README for the
nine-pin `/2` profile, supported scope and registration requirements.
