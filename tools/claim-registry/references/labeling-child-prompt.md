# Labeling-child prompt template (claim proposals)

The coordinator spawns one labeling child per designated source or bounded
window. The child's only output is a `claim-proposals/1` JSON file. Tools
compute; children propose.

## Child rules (state these verbatim)

- You receive frame/window JSON produced by the `claim-registry` unit. Copy
  `unit_id` strings from it exactly. Never invent, edit, hash, or compute an ID,
  span, or sha256.
- Every unit is owned exactly once: either inside a claim (a run of
  **consecutive whole units**, no separators, no gaps) or as a nonclaim with a
  label (`context`, `advisory`, `example`, `baseline`), a non-empty `rationale`,
  and a `role_ref`. Units you cannot judge may be left unassigned; they remain
  `pending` and surface in validation rather than being silently claimed.
- Separators are mechanically nonclaim `context`; do not assign them.
- A claim is an independently adjudicable assertion/constraint/scope
  declaration from the designated source — not a heading, not navigation, not
  reviewer inference. Cite the exact source text in the rationale when useful.
- If you decompose a parent span, every parent unit not covered by a child must
  have explicit nonclaim ownership, or assembly fails.
- Output **only** the JSON object. No prose, no markdown fences, no commentary.

## Skeleton

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

The coordinator merges child outputs mechanically (`assemble --proposals a.json
--proposals b.json`), never by editing JSON by hand. Validation errors name the
offending `unit_id`; the fix always goes back into a proposal file.
