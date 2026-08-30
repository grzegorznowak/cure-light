# cure-light

> A **diagnostic** PR review pipeline: it reviews a pull request against its own
> stated contract, the surrounding code, and how the feature is built — it does
> not modify code. Findings become PR comments / issues only through operator-
> gated drafting and, on the implementer's cut take, re-verified through a
> closure loop.

cure-light encodes the three-vector method: **conformance** (does the code deliver
what the PR claims?), **implementation** (does the shipped code work?), **debt**
(is the way it's built sustainable?). A cross-cutting **lens** dimension forces
coverage of the code-hygiene family (dead code, strict-type hygiene, readability,
naming) — detected by named lens atoms and accelerated by the repo's
own deterministic tooling where cheap — the full sweep runs when Vectors 2-3 do,
and a V1-only shortcut still exercises the mechanical `type`/`dead` preflight
(pipeline-model.md). An optional **yagni** pass challenges the PR's size and
speculative surface when the operator enables it (yagni-pass.md). It is a small OS for the review process itself: pin the pull, hold a
pinned-commit manifest, spawn scoped fleets,
and re-verify on the next head — not the whole pipeline.

## Layout

```
cure-light/
├── BOOTSTRAP.md              ← the remote manifest + bootstrap prompt
├── kernel/                   ← the review method (the master skill)
│   ├── SKILL.md              ← dispatcher: phases, gates, rules
│   └── references/           ← pipeline-model, intake, the 3 pass contracts,
│                               hygiene-lens, yagni-pass, closure-verification, evidence-format
├── libs/pi-driver/           ← pi binding (notebook + handoff + model-groups)
│   ├── SKILL.md
│   └── references/           ← requirements-check, notebook-plan-contract
├── templates/KICKOFF.md      ← fill-in fields for a new episode
├── assets/                   ← finding-schema.json, child-pass-prompt-template
├── docs/
│   ├── example-review.md      ← worked run (PR #27)
│   └── OPEN-ISSUES.md         ← known open model conflicts
└── CHANGELOG.md
```

## How to boot a new review

### Option A — remote boot (nothing cloned or installed)

Paste into the fresh session (also `templates/KICKOFF.md`):

> Boot a cure-light PR review episode from the remote manifest at
> `https://raw.githubusercontent.com/grzegorznowak/cure-light/main/BOOTSTRAP.md`
> Fetch the manifest, follow its instructions exactly: fetch every listed file
> as raw markdown (no summarization, preserve bytes), report each file's line
> count, run the quick requirements check, ask the intake fields once (owner/
> repo, PR number, vectors, auto-draft policy), compile the run plan into the
> notebook, and — because this runtime provides the pi notebook + handoff —
> seal the compiled frame and hand off so the next context kicks off Phase 0
> then Vector 1. Report the requirements result and compiled plan back before
> proceeding. No clone or install.

### Option B — local (clone or vendor)

1. Read `kernel/SKILL.md` and its references completely before acting.
2. Fill `templates/KICKOFF.md`.
3. Paste the launch prompt above.

## The quick requirements check (pi)

`libs/pi-driver/references/requirements-check.md` verifies: gh auth, target repo
reach, PR head/base OID, checkout at head, notebook writable, fleet groups
present, git diff works, optional chunkhound index. Fall back (git/rg,
inherit-parent spelling) or **stop before fleet cost** when a hard requirement
fails — the review never spends a fleet on an unverified subject.

## Why the notebook + handoff

State (frame, findings, decisions) lives in the pi session notebook — the
always-present shared store that survives compaction and handoff. When
`handoff` is available, the driver marks the compiled frame and hands off so
the next context starts post-boot and runs Phase 1 → Vector 1 without re-reading
the kernel. See `libs/pi-driver/SKILL.md`.

## Operating principles (short)

- **Pinned, one subject.** Review the head OID captured at intake; a
  regression winds into a new run, never overridden.
- **Three vector separations.** Later vectors build on a verified substrate.
  Gates between, operator-gated.
- **ORIGIN classification is mandatory** — base-diff decides pre-existing vs
  PR-introduced, never prose.
- **Deferred is not closed.** Recorded, with rationale — never presented as an
  engineering fix.
- **Statuses / opinion excluded.** Findings need file:line + concrete failure
  mode; hygiene hits route to the lens trail (LOW, operator-suppressible), never
  pollute the bug trail — but the lens *itself* is always checked, never skipped.

## CHANGELOG

See [CHANGELOG.md](CHANGELOG.md).