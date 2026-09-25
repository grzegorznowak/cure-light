# claim-registry — minimal pilot producer (tool unit v0.2.0)

Standalone, tested tool implementing the pilot producer for the cure-light
claim registry: the strict atomic-unit Markdown **frame**, verbatim **capture**
identity, **canonical JSON** registry assembly, an independent **validator**,
bounded **ingestion windows**, and a sealed **run manifest**.  It is also a
pluggable **tool unit** (DESIGN §1): self-describing (`--describe`), fetchable
by pin (`TOOL.json` + `--check-pin`), exact-pinned dependencies, and file/JSON
in → file/JSON out.

Design of record: `cure-light-claim-registry-spec.md` (workspace proposal,
not yet shipped in the repo; see the toolkit `DESIGN.md` for the tool-unit
contract).
(§§1–3).  This package is the "minimal frame extractor, canonical serializer,
machine schema and independent validator" required by the spec's pilot scope
(section 3).  It does **not** implement repair mapping (spec §4), LLM labeling,
or the full fixture harness.

No git repository, branch, PR or review artifact was touched; all artifacts
live here and the test fixtures are committed in-tree.

## Layout

```
claim-registry/
  claim_registry/
    frame.py          deterministic walker (tree-sitter-markdown block grammar)
    capture.py        verbatim capture, raw sha256, synthetic git blob OID, source_ref
    canonical.py      claim-json/1 canonical serialization + recipe/registry hashes
    registry.py       proposals -> registry (claims, labels, ownership, witness)
    validator.py      independent recomputation; blocks finalized UNCLAIMED on failure
    windows.py        bounded window manifests + reconciliation
    tool_manifest.py  static tool-unit/1 manifest (importable without tree-sitter)
    cli.py            thin CLI (--describe/--check-pin, 0/1/2 exit codes)
  build.py            deterministic .pyz + TOOL.json builder
  dist/               claim-registry-0.2.0.pyz (+ .sha256)
  TOOL.json           describe payload + artifact pin
  SKILL.md            agent skill snippet for this unit
  tests/              pytest suite (99 tests) + ported 32-doc stress corpus
  tools/
    corpus_smoke.py   frames all bodies in a corpus directory
  pyproject.toml
```

Requirements: Python 3.11, `tree-sitter` **0.26.0**, `tree-sitter-markdown`
**0.5.1** (exact pins; both already installed for system `python3`).  No other
dependencies.

## Quick start

```bash
cd <unit-root>

# unit + acceptance tests
python3 -m pytest tests/

# deterministic artifact + pin (writes dist/*.pyz, TOOL.json, dist/*.sha256)
python3 build.py
python3 dist/claim-registry-0.2.0.pyz --describe
python3 dist/claim-registry-0.2.0.pyz --check-pin "$(cut -d' ' -f1 dist/claim-registry-0.2.0.pyz.sha256)"

# corpus smoke (918 real PR bodies; 15 empty)
python3 tools/corpus_smoke.py --corpus /tmp/prcorpus --determinism

# CLI
python3 -m claim_registry.cli capture --in body.md --locator 'repo#17:body' --out captures/
python3 -m claim_registry.cli frame   --in body.md --locator 'repo#17:body'
python3 -m claim_registry.cli assemble --captures captures/ --proposals proposals.json \
    --out registry.json
python3 -m claim_registry.cli validate --registry registry.json --captures captures/ \
    --report-out report.json
python3 -m claim_registry.cli windows  --registry registry.json --out windows.json
python3 -m claim_registry.cli hash     --in registry.json
python3 -m claim_registry.cli manifest --captures captures/ --proposals proposals.json \
    --registry registry.json --report report.json --out run-manifest.json
```

**`--proposals` is repeatable** on `assemble` (and recorded repeatably by
`manifest`): files merge in CLI order — `assignments`, `decomposition`,
`groups`, `precedence`, and `uncaptured_source_refs` concatenate (the latter
with first-seen de-duplication).  A single `--proposals` behaves exactly as
before; duplicate ownership across files still fails assembly.

`assemble` writes canonical bytes with **no trailing newline**.  `validate`
exits 0 only when every check passes; a failed report always carries
`"permission": {"finalized_unclaimed": false, "complete_registry_claims": false}`.

## Tool unit (v0.2.0)

* `--describe` prints the canonical `tool-unit/1` JSON; `--check-pin SHA256`
  hashes the running `.pyz` (0 ok, 1 mismatch, 2 not running from a `.pyz`).
  Both are handled before argparse and **work without tree-sitter installed**,
  so an agent can learn what to install.
* `build.py` builds `dist/claim-registry-0.2.0.pyz` deterministically (same
  sources → same sha256), runs the built artifact's `--describe`, and writes
  `TOOL.json` (describe + `artifact {file, sha256, size}`) and
  `dist/claim-registry-0.2.0.pyz.sha256` (`"<sha>  <artifact filename>\n"`).
* Dependencies are exact-pinned in `TOOL.json`: `tree-sitter==0.26.0`,
  `tree-sitter-markdown==0.5.1`.  Every command except `--describe`,
  `--check-pin`, and `--help` checks them and fails loud with exit **2**,
  the package names, and the install line
  `python3 -m pip install 'tree-sitter==0.26.0' 'tree-sitter-markdown==0.5.1'`.
* Exit codes: **0** ok; **1** semantic/validation failure (actionable message;
  `validate` reports carry `errors[]` naming the exact `unit_id`/field/check);
  **2** usage/environment (bad args, missing/unreadable files, missing or wrong
  pinned dependency, invalid window recipe).
* `manifest` seals a completed run into canonical `claim-run-manifest/1`
  (no trailing newline): tool identity + `describe_sha256` + artifact pin
  (from `--tool-manifest`, else self-hash when run from a `.pyz`, else null),
  the capture-manifest sha256, each proposal sha256, registry
  `{path, sha256, registry_hash}`, report
  `{path, sha256, valid, finalized_unclaimed, complete_registry_claims,
  registry_hash}`, and the optional windows sha256.  Missing/unreadable inputs
  exit 2; malformed JSON or a non-canonical registry exits 1.
* `SKILL.md` is the agent-facing invocation, verification, and failure-handling
  snippet for this unit.

## Frame rules (strict reading of spec §1.2)

* Unit kinds: `atx_heading`, `setext_heading`, `paragraph`, `list_item`
  (simple items), smallest child blocks of compound list items (first child
  includes the item marker), `fenced_code_block`, `indented_code_block`,
  `html_block`, `thematic_break`, `link_reference_definition`,
  `pipe_table_header`, `pipe_table_delimiter_row`, `pipe_table_row`, plus
  `separator` for whitespace-only gaps.
* **Extensions:** `minus_metadata`/`plus_metadata` (front matter) are emitted
  as opaque units.  The block grammar parses them, and not inventorying them
  would silently drop bytes; the spec explicitly allows "other supported opaque
  blocks … with explicit kinds".
* Every span begins at a physical line start and ends after its final line
  terminator (LF terminates a line; a preceding CR stays in the span) or at
  EOF.  Line terminators are therefore **inside** block spans, which is why the
  plan-doc golden reads 56 blocks + 11 separators instead of the lenient
  prototype's 56 + 17 (details under Acceptance evidence).
* Block-quote prefixes (`> `) and list indentation are absorbed into the child
  unit span by extending its start to the physical line start.  tree-sitter
  attaches the next line's indentation/prefix to the preceding block as a
  trailing `block_continuation` child; the walker strips exactly those trailing
  continuation bytes before snapping to the line boundary and gives them to the
  following unit.
* Marker-only lines (`>` runs on otherwise blank lines) inside a block quote
  are not whitespace.  They are attributed to the following sibling unit inside
  the same `block_quote` when possible (else to the preceding unit, else a
  loud `ExtractionError`).  No separator ever contains non-whitespace bytes.
* STRICT partition: `[0, len)` is covered exactly once, gapless and without
  overlap.  A non-whitespace gap that is not container-attributable raises
  `ExtractionError` with byte offset and snippet.  A tree containing
  ERROR/MISSING nodes raises the same.  An unclosed fence is valid CommonMark
  (fence to EOF) and frames normally.
* Everything else is not walked: `document`/`section` recurse,
  `list`/`block_quote`/`pipe_table` are structural ancestry only, empty list
  items (`-` alone) are their own `list_item` unit.
* `ancestor_refs` entries are strings `<container-kind>:<start>-<end>`,
  outermost-first (containers are ancestry metadata, never units).
* `unit_id = <source_ref>:<start>-<end>:<sha256(hex, exact span bytes)>`.
  Identical source bytes + identical walker script ⇒ identical units and IDs,
  in any process, run, or output format.
* **Recipe pin:** `frame_recipe()` carries walker name/version, parser name +
  version (`tree-sitter-markdown 0.5.1`), runtime name + version
  (`tree-sitter 0.26.x`), flags `[]`, the sha256 of `frame.py`, and the sorted
  unit-kind list.  The validator compares this pin with the running code; a
  walker/parser change invalidates the registry instead of silently
  re-extracting.

## Capture and identity (spec §1.1)

* `capture_bytes`/`capture_file` keep bytes verbatim: no added trailing
  newline, no CRLF conversion, no Unicode normalization, no trimming.
* Raw `sha256` and `byte_length` are recorded separately from the Git blob
  identity; API documents get a synthetic blob OID
  `sha256(ASCII("blob ") + ASCII(decimal(len)) + NUL + bytes)`, labeled
  `git-blob-sha256`.
* `source_ref = src:<pct(locator)>:git-blob-sha256:<oid>` with UTF-8 percent
  encoding: unreserved `[A-Za-z0-9._~-]` unchanged, every other byte
  uppercase `%HH`.
* Distinct locators stay distinct even when bytes are identical.
* Zero-byte sources produce zero units plus an explicit `"empty": true`
  source record (`empty_source` in the witness); completeness is allowed but
  emptiness never proves an adequate contract.

## Proposals input (`claim-proposals/1`)

```json
{
  "schema_version": "claim-proposals/1",
  "assignments": [
    {"source_ref": "src:...", "unit_ids": ["..."], "state": "claim",
     "rationale": ""},
    {"source_ref": "src:...", "unit_ids": ["..."], "state": "nonclaim",
     "label": "context", "rationale": "...", "role_ref": "..."}
  ],
  "decomposition": [
    {"parent": {"source_ref": "src:...", "unit_ids": ["..."]},
     "children": [{"unit_ids": ["..."], "rationale": "..."}]}
  ],
  "groups": [],
  "precedence": [],
  "uncaptured_source_refs": []
}
```

* A claim is a run of **consecutive whole units** (consecutive ordinals) in one
  source; a claim cannot contain a `separator` and cannot jump over one.
* Every unit is owned exactly once: a claim or a nonclaim
  (`context|advisory|example|baseline`, each with non-empty `rationale` and
  `role_ref`).  Unowned units are recorded `pending`; double ownership is an
  assembly error.
* Separators are mechanically nonclaim `context`; unassigned separators are
  auto-assigned with `role_ref = spec:claim-registry/1#separator`.
* `decomposition` declares a parent span that becomes an **inactive,
  non-owning container** and child claims strictly contained in it.  Every
  parent unit not covered by a child must have explicit nonclaim ownership
  ("any remainder MUST have explicit nonclaim ownership"), otherwise assembly
  fails.  Children may omit `source_ref` (inherited from the parent).
* `groups` and `precedence` are pass-through arrays with stable `group_id` /
  `precedence_id` ordering; group `unit_ids`/`claim_ids` are sorted by UTF-8
  bytes.  `uncaptured_source_refs` records non-capturable designated sources and
  forces `complete: false`.
* `default_proposals(source_ref, frame)` is a helper producing one claim per
  non-separator block plus explicit separator context.

## Registry and canonicalization

`claim-json/1` (spec §2) is implemented literally: ASCII keys sorted at every
depth, `,`/`:` without whitespace, lowercase literals, nonnegative integers
≤ 2^53−1, `"`/`\` escaping, C0 controls as lowercase `\u00xx`, literal UTF-8
elsewhere, no trailing newline, duplicate keys rejected.  `recipe_hash` is the
sha256 of the canonical recipe; `registry_hash` is the sha256 of the canonical
payload and is excluded from its own input.  The envelope is
`{"payload": ..., "registry_hash": ...}` serialized with the same rules.

Payload ordering: sources by `source_ref` bytes; units by `source_ref` then
ordinal; claims by `source_ref`/start/end/ID; labels follow unit order;
witness entries by source order then unit order.

The witness records per source: sha256, byte length, blob algorithm/OID, frame
recipe hash, unit count, covered unit/byte counts, pending/conflict/error
counts, `empty_source`, `complete`; globally it records
`uncaptured_source_refs`, `complete` and `errors`.

## Validator (spec §2 checklist)

`validate_registry(envelope, captures, raw_bytes=..., windows_manifests=...)`
recomputes rather than trusts:

1. envelope/payload shape, unknown-key rejection, canonical bytes (with
   `raw_bytes`, a trailing newline fails), schema version, both hashes,
   recipe shape and **recipe pins vs the running walker**;
2. source set reconciles with the capture mapping; recorded length/hash/blob
   OID and locator→source_ref reproduce from the actual bytes;
3. re-extraction under the pinned recipe reproduces units, kinds, ordinals,
   spans, ancestors, hashes and IDs exactly;
4. strict byte partition, line alignment, no dropped separator or trailing
   bytes;
5. claim IDs/spans/hashes reproduce, members are consecutive whole units, no
   separator membership, every unit intersecting a claim span is a member,
   containment-only hierarchy (inactive parent + `parent_ref`), no crossing
   overlaps, no duplicate membership;
6. ownership is exclusive and exhaustive; nonclaim labels/rationale/role_ref
   valid; separators are `context`; pending counts recomputed;
7. the serialized witness is compared field-by-field with the recomputation;
   `complete` is regenerated and compared (a producer-supplied `true` is not
   trusted);
8. group/precedence references exist; window manifests reconcile by unit ID
   when supplied.

`permission.finalized_unclaimed` (and `complete_registry_claims`) is `true`
only when every check passed and the recomputed witness is complete.  A failed
validation report blocks the permission flag.

## Windows (spec §1.4)

Positive `max_units`, `max_bytes`, `overlap_units < max_units`.  From ordinal
zero, take the longest prefix satisfying both bounds; continue from the tail
overlap; reduce the actual overlap until at least one new unit is admitted and
record the actual value; stop once the last unit is included (never an
overlap-only terminal window).  A unit larger than `max_bytes` raises the named
`OversizedUnitError` instead of being split.  Manifests list `source_ref`,
ordinal bounds, unit IDs, actual overlap, `context_only_ids` (empty for the
pilot) and the recipe hash; `validate_windows` reconciles them against the
frame.

## Documented ambiguity decisions

* **Golden separator drift:** the lenient research prototype counted six
  single-LF pseudo-separators after the plan doc's table rows and one
  non-whitespace `> ` separator.  The spec requires spans to end after their
  final line terminator and separators to be whitespace-only, so the strict
  walker yields 56 + 11.  The test asserts the strict number and explains the
  delta; no rounding to the prototype value.
* **Front matter** is an explicit opaque unit kind (see above).
* **Marker-only quote lines** are attributed to the following unit inside the
  same quote; if none, to the preceding unit; unattributable non-whitespace
  gaps are errors.
* **Trailing `block_continuation`** bytes (next-line indent/prefix) are always
  assigned to the following unit's span start, never to the previous unit's
  end.
* **Empty list items** (bare `-`) become `list_item` units with no content
  children.
* **BOM** is absorbed into the first unit via physical line start (or into a
  leading separator if the document begins with BOM + blank lines); `bom` is
  explicit capture metadata.
* **Claim rationale** lives on the unit labels (the spec's claim sketch has no
  rationale field).
* **`ancestor_refs`** use `<kind>:<start>-<end>` strings because containers are
  not units and have no stable IDs.
* **Validator version:** the report carries the recomputed witness and the
  check list; the recipe pins (including the walker script hash) are the
  reproducibility boundary.  A separate validator-version field is deferred
  with the full validation report artifact.

## Acceptance evidence

Environment: Python 3.11.2, tree-sitter 0.26.0, tree-sitter-markdown 0.5.1.

```
$ python3 -m pytest tests/
# 99 passed

$ python3 tools/corpus_smoke.py --corpus /tmp/prcorpus --determinism
files=7 bodies=918 empty=15 framed=918
blocks=16071 separators=5739 total_units=21810
largest_body=65653 bytes (openai_openai-python.json#27)
errors=0
```

Tool-unit contract tests (9) cover: `--describe` schema + deterministic bytes,
working without tree-sitter + fail-loud exit 2, golden
`capture→assemble→validate→manifest` round-trip with per-file sha256 checks and
tamper rejection, repeatable `--proposals` merge, build determinism,
`TOOL.json` ⇔ `--describe` consistency, `--check-pin` (0/1) on the built
`.pyz`, and identical frame recipes between the source package and the built
`.pyz` (zipapp self-hash fallback).

Golden frames (tested):

* `tests/fixtures/pr17-body-v2.md` (10,385 B, sha256 `10b5b301…`) → **29 block
  units + 22 separators**, covered 10,385 B, 3 runs byte-identical.
* `.../contract-adequacy-validation-plan.md` (10,428 B, sha256 `62460fba…`) →
  **56 blocks + 11 separators**, covered 10,428 B; the delta vs the prototype's
  17 is explained above.

Strict negatives (tested): appended transport newline changes length/hash/OID/
ref and frame; CRLF vs LF produce different span bytes; multibyte offsets are
byte-exact; nested lists partition with marker inclusion; manufactured
non-whitespace gap and a real parse-error input (`b"\x00\x01\x02 text\n"`)
raise `ExtractionError` with offset + snippet; unclosed fence frames to EOF.

Registry negatives (tested): dropped unit, double-owned unit, mid-unit claim
boundary, claim jumping over a separator, tampered unit hash and tampered
`registry_hash` are all rejected; a producer-supplied `complete: true` with a
missing owner is rejected and the permission flag stays false.

## TODOs / deferred

* **Repair mapping (spec §4) is deferred** with this README as the TODO: no
  old/new state mapping, no monotonicity checks, no similarity links.
* Validator report artifact binding (validator version/hash, per-check output
  persistence) and state-binding checks (checklist item 10) are post-pilot.
* The `windows` CLI derives manifests from registry units; context-only
  ancestor-heading copies and cross-window proposal reconciliation are not
  exercised in the pilot.
* Full F1–F10 executable fixture harness and fleet budgets remain post-pilot
  per the spec.
