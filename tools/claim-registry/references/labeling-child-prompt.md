# Labeling-child prompt template (claim proposals)

The coordinator spawns one labeling child per designated source or bounded
slice. The child's only output is a proposal JSON file — `claim-proposals/1`
for whole-source labeling, `slice-proposals/1` for a slice — authored against
the pinned `claim-registry` **0.3.0** producer. Tools compute; children propose.

## Shared child rules (state these verbatim)

- You receive JSON produced by the `claim-registry` unit. Copy `source_ref`,
  `unit_id`, `slice_id` and `input_sha256` strings from it exactly. Never
  invent, edit, hash, or compute an ID, span, or sha256.
- Every unit is owned exactly once: an assignment is either inside a claim (a
  run of **consecutive whole units**, no separators, no gaps) or a nonclaim
  with a label (`context`, `advisory`, `example`, `baseline`), a non-empty
  `rationale`, and a `role_ref`. Units you cannot judge may be left unassigned;
  they remain `pending` and surface in validation rather than being silently
  claimed.
- Separators are mechanically nonclaim `context`; do not assign them.
- A claim is an independently adjudicable assertion/constraint/scope
  declaration from the designated source — not a heading, not navigation, not
  reviewer inference. Cite the exact source text in the rationale when useful.
- If you decompose a parent span (Mode A only), every parent unit not covered
  by a child must have explicit nonclaim ownership, or assembly fails.
- Output **only** the JSON object. No prose, no markdown fences, no commentary.
- You never run the producer or any tool, never reconcile, never write a
  registry/manifest/reconciliation file, and never edit another child's output.

## Mode A — whole-source labeling (`claim-proposals/1`)

Use when the source is within the full-label caps: **≤16 KiB raw bytes, ≤80
units, and ≤64 KiB complete serialized worker input**. If any cap is exceeded,
the coordinator must use Mode B (`frame-slices`), never a hand-cut source.

Skeleton:

```json
{
  "schema_version": "claim-proposals/1",
  "assignments": [
    {"source_ref": "src:...", "unit_ids": ["<id1>", "<id2>"], "state": "claim",
     "rationale": "declares X because <quote/paraphrase>"},
    {"source_ref": "src:...", "unit_ids": ["<id3>"], "state": "nonclaim",
     "label": "context", "role_ref": "section:overview", "rationale": "introductory context"}
  ],
  "decomposition": [],
  "groups": [],
  "precedence": [],
  "uncaptured_source_refs": []
}
```

## Mode B — sliced labeling (`slice-proposals/1`)

One child per slice payload (`frame-slice-input/1`). The payload carries the
slice's exact unit records with their byte-exact `text`, plus `core_ids` (the
units this child owns) and `overlap_ids` (preceding audit units owned by the
previous slice, ≤4). Keep `slice_id` and `input_sha256` verbatim from the
payload. The coordinator passes the payload file path; the child never
re-reads the source.

Rules:

- **Own only core non-separators.** Assignments own exactly the `core_ids`
  non-separators (claims may span multiple consecutive whole core units), plus
  explicit nonclaim ownership where needed. Never assign a separator, never
  assign or own an overlap unit, and never leave a core non-separator silently
  unowned.
- **Vote on every overlap non-separator.** Write exactly one `overlap_votes`
  entry per overlap non-separator: `{unit_id, state, label, role_ref,
  rationale}` — `label`/`role_ref` are `null` for a claim vote. The vote must
  agree with the owning slice's assignment; do not restate or re-own it.
- **Vote on every visible adjacency pair.** Write exactly one `grouping_votes`
  entry per mechanically visible non-separator adjacency pair in
  `overlap_ids + core_ids` order: `{left_unit_id, right_unit_id, grouping,
  rationale}` with `grouping` ∈ `same | separate | uncertain`. Adjacent slices
  must agree on shared pairs.
- **Declare the slice's seams.** `boundary.left` / `boundary.right` ∈
  `clear | spanning | uncertain` state whether the slice's first/last core unit
  continues a claim into the unshown neighbouring slice.
- **Never split or guess across a core boundary.** A possible multiunit claim
  that cannot fit inside this core, a cross-core grouping you cannot prove, or
  a `spanning`/`uncertain` seam is declared, not resolved: leave the affected
  units unassigned (pending) and set the boundary value. Boundaries never
  straddle sources.
- **Fail loud, never silently repair.** State, nonclaim subtype/role and
  grouping disagreements between slices hard-fail reconciliation with the exact
  `unit_ids`/`slice_ids`; a differing *rationale* for the same state is kept as
  a warning, never replaced. A failed reconciliation publishes a failure report
  and never a usable merged artifact — the coordinator fixes the proposal files
  and reruns, never edits the merged output or the registry.

Skeleton:

```json
{
  "schema_version": "slice-proposals/1",
  "slice_id": "sha256:<from payload>",
  "input_sha256": "<from payload>",
  "assignments": [ /* Mode A assignment shapes, core non-separators only */ ],
  "overlap_votes": [
    {"unit_id": "<overlap-id>", "state": "nonclaim", "label": "context",
     "role_ref": "section:...", "rationale": "..."}
  ],
  "grouping_votes": [
    {"left_unit_id": "<id>", "right_unit_id": "<id>", "grouping": "separate",
     "rationale": "..."}
  ],
  "boundary": {"left": "clear", "right": "clear"}
}
```

## Budget rule (D3)

One label call per slice; the default run budget is **≤32 slices** with **≤4
concurrent** children, and each slice carries **≤4 preceding overlap units**.
The coordinator preflights the slice count before spawning; raising the budget
is an explicit recorded decision that changes the slice recipe/IDs. An
oversized indivisible unit, an overlap-only slice, or an unresolved
boundary-spanning claim **stops the run** — never hand-split a unit, never
widen a cap, never invent a child.

## Producer pin

`claim-registry` **0.3.0** (version + sha256 declared in the run frame;
`frame-slices` / `proposal-reconcile` / `manifest` / `gate-check` are
coordinator-run). Children author proposals only: canonical registry bytes,
IDs and hashes are computed by the tool, and no child output substitutes for
them.
