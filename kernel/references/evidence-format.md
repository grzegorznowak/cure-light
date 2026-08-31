# evidence-format.md — finding schema, severity, origin

Every finding in a cure-light run conforms to this shape. It is the interop contract between fleet children, the coordinator, the notebook, and gh artifacts.

## Finding schema

```yaml
id: <vector-letter><#>            # V1-V3 + seq, e.g. F2-03 or D3-01 (yagni: Y-01)
vector: conformance | implementation | debt | yagni
lens: type | dead | read | name | test | security | yagni | quality | none   # optional; see hygiene-lens.md + quality-lens.md
lens-checked: [<lens>, ...]       # lenses proven exercised on this artifact
summary: one line
evidence:
  file: path:line            # primary anchor in the pinned tree
  code: <verbatim or exact shape>
severity: HIGH | MED | LOW
origin: PR-introduced | pre-existing   # Vector 2+ ; conformance is PR-only by definition
disposition: fix-in-PR | pre-existing-debt | deferred-decision | track-separately
failure_mode: <concrete user-visible or future failure>
status: open | verified-fixed | re-classified | test-only | doc-only | deferred-decision | closed-by-operator | re-opened
owner: <implementer | operator | subsystem>
linked: <external follow-up URL | none>
```

`assets/finding-schema.json` is the machine form. `lens` and `lens-checked`
are optional (a conformance finding usually has `lens: none`); when they are
absent the row still counts toward the vector, but the **lens matrix** (see
pipeline-model.md) is what proves per-lens coverage of the run.

A mechanical sweep that cannot run on the pinned head marks its lens
`inconclusive-mechanical` in the **lens trail** — checked by static sight, not
compiler output — never a silent skip and never a finding-status by itself.

## Severity semantics

- **HIGH** — data loss / security / wrong routing / a contract-mandated behavior is contradicted or unverifiable at the core and no backstop exists.
- **MED** — real user-visible defect or race, or a behavior claim missing the test that would catch its regression; backstopped so not catastrophic.
- **LOW** — brittle, fragile, or coverage-without-assurance; cosmetic; deferred by design.
- **Yagni rows (`yagni` lens)**: LOW default, MED ceiling — existence questions are advisory (non-blocking); current harm is V2's, future-change cost is V3's.
- **Quality rows (`quality` lens)**: LOW default, MED only when the quality problem's *own scale* is material — never HIGH, rated independently of product criticality (a spaghetti tree in a payments feature is not elevated because payments is critical); advisory (non-blocking), lens-trail only.

## Origin rule (Vector 2+)

Decide by **base diff**, never vibes:
`git show <base>:<path>` → is the mechanics present at base? If yes and the PR only touches it in passing → pre-existing. If the path (field/gate/logic/README-claim) is new → PR-introduced.

## Writing findings

- Every finding needs a **concrete failure mode** — not a style opinion.
- `NOT-A-BUG` results are listed too (checked and dismissed), cheap honesty that keeps the fleet honest.
- Hygiene hits follow the **lens trail** (hygiene-lens.md): detection mandatory, LOW by default, operator-suppressible per instance — they never pollute the bug table.
- `yagni` rows (yagni pass) follow the same lens trail with the same suppression/closure semantics — suggestion-only, never bug/debt tables.
- `quality` rows (V3 lens) follow the same lens trail — suggestion-only, rated by the problem's own scale, never bug/debt tables.
- Evidence must be at the **pinned head**; if a child read a different tree, its output is `inconclusive`.

## Notebook layout

- `pipeline-frame-<owner>-<pr>` — frozen run options, head/base OID, manifest. Written once at intake.
- `pr-<n>-review` — findings table (schema rows) + closure table. Appended per vector.
- `decisions` (durable, survives the PR) — deferred-decision and closed-by-operator records with author/time/rationale/scope, plus the leading subarea open questions.

The coordinator owns writes. Children return compact records; they never race the notebook.

## External routing

Finalization is **one aggregated review comment per run** — never per-finding comments, never separate issue drafts. The pipeline drafts it only when the intake field `draft_comment` is `true`; with `false`, the run is review-only: findings and suggested issues stay in the notebook, and a draft is prepared only on explicit request.

The single review comment contains:

```text
## Summary                     — owner/repo pr# @ head OID, vectors run
## Findings                    — in-scope, PR-introduced: file:line evidence, severity, origin
## Potential follow-up issues  — pre-existing debt, phrased as suggestions (marked
                                "pre-existing, out of this PR's scope") for the
                                developer to open themselves
[attribution footer — see below]
```

- **Never auto-post.** The single draft is operator-gated at the `before_post` pause — mandatory whenever `draft_comment` is enabled — and the operator may edit, split, or veto it.
- **Lens-trail rows stay in the notebook** (hygiene / quality / yagni): never part of the comment unless the operator explicitly requests them.
- **Issues are suggested, not drafted.** cure-light never composes `gh issue` bodies; the developer opens follow-up issues from the "Potential follow-up issues" section. A `linked` value may be added later, when a developer or operator has created the issue.
- **Attribution footer.** The single review comment ends with the cure-light attribution footer, composed **solely from run-manifest values**:

  ```text
  _Reviewed with [cure-light](https://github.com/grzegorznowak/cure-light) @ <cure_light_source_head_oid short form> — pinned PR head <headRefOid>_
  ```

  - `cure_light_source_head_oid` (intake-and-scope.md, §Output) is the cure-light source checkout's HEAD at intake — the "version at the time of reviewing", frozen once so it survives handoffs. Never re-derived per vector (no live `git rev-parse`, `gh` lookup, or CHANGELOG semver).
  - The footer appears only on the review comment — never on notebook pages.
  - If the source commit could not be established at intake, **omit the footer rather than fabricate one**.
  - A new-head review state (closure loop) uses its own pinned `headRefOid` in the footer.