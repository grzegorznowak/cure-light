# artifact-contracts.md — recorded artifact field contracts

The compact, operator-facing field contracts for the Phase-0 recorded artifacts that the pinned mechanical verifier (`kernel/tools/verify.mjs`) reads. This page documents existing tool behavior; the tool remains the executable authority and no new CLI exists — there is no `verify describe` or `verify --schema` mode. Every example below is **synthetic and current-profile-specific**: copy the shape, never the values.

Read this page when preparing or repairing P0.2/P0.4 artifacts and when V1 validates/freezes claims. Reconcile a failure with the error→field map (§7) before changing anything: a repair fixes the recorded field to the recorded meaning, never the meaning to pass the check (protocol in §8).

## 1. Capture manifest — `claims/sources/capture-manifest.json`

The capture manifest is **schema-less**: identity, source pins and the changed-file inventory only. **Omit `schema_version`.**

In every case, any declared value is refused by `verify envelope` (exit 2, `REFUSE envelope: unsupported capture schema_version: ...`, no document emitted). If a declared value reaches a validator through the envelope capture pin or the capture file, a nonempty unknown or wrong-family declaration refuses exit 2 (`unsupported schema_version` / `wrong schema kind`), while an empty or wrong-typed declaration fails shape with exit 1 (`invalid field: /capture_manifest/schema_version expected nonempty string`). The envelope capture pin is likewise exactly `{ref, sha256}` — no `schema_version`.

| Field | Required | Type | Rule |
|---|---|---|---|
| `run` | yes | nonempty string | must equal the claims/units/envelope `run` |
| `review_state` | yes | nonempty string | must equal the review state everywhere |
| `base_oid`, `subject_oid` | yes | 40-char lowercase hex | identity tuple; must agree across artifacts |
| `cure_light_source_head_oid` | yes | 40-char lowercase hex | engine source identity; must agree |
| `sources[]` | yes | array | at least one captured source |
| `sources[].locator` | yes | nonempty string | joins the claims-draft `sources[].source_ref` |
| `sources[].path` | yes | path under `claims/` | exact source bytes, e.g. `sources/pr-body.md` |
| `sources[].capture_sha256` | yes | 64-char lowercase hex | sha256 of the exact bytes at `path` |
| `sources[].capture_byte_length` | yes | nonneg integer | length of the exact bytes at `path` |
| `sources[].title_path` | optional | path under `claims/` | declared title bytes, e.g. `sources/pr-title.txt` |
| `sources[].title_sha256`, `sources[].title_byte_length` | with `title_path` | hex / integer | exact title bytes |
| `sources[].class`, `role`, `designating_pointer`, `version_ref` | provenance | strings | recorded designation context, not cross-checked byte-wise |
| `changed_files[]`, `changed_files_count` | recorded | array / integer | base..subject changed-file inventory |

**Path bases (the most common repair).** In a capture manifest, `path` and `title_path` resolve relative to `claims/` (the directory above `sources/`). In a claims draft, claims-draft `sources[].path` resolves relative to the run root. A path written with the wrong base fails `artifact.read`; the capture-side wrong-base fingerprint is `cannot read artifact: claims/claims/...`, and a claims-side path written capture-style resolves against the run root and misses.

<!-- capture-manifest-example -->
```json
{
  "run": "owner/repo#1",
  "review_state": "s1",
  "cure_light_source_head_oid": "1111111111111111111111111111111111111111",
  "subject_oid": "2222222222222222222222222222222222222222",
  "base_oid": "3333333333333333333333333333333333333333",
  "sources": [
    {
      "locator": "pr:body",
      "class": "api-document",
      "role": "declares",
      "designating_pointer": "the PR body itself",
      "path": "sources/pr-body.md",
      "capture_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "capture_byte_length": 42,
      "title_path": "sources/pr-title.txt",
      "title_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "title_byte_length": 7
    }
  ],
  "changed_files": ["README.md"],
  "changed_files_count": 1
}
```

## 2. Claims draft — `claims/claims-draft.v3.json` (`claims-draft/3`)

The root's `schema_version: "claims-draft/3"` is required. A missing or empty value fails shape with exit 1 (`invalid field: /schema_version expected nonempty string`); an unknown value refuses exit 2 (`unsupported schema_version`); a registered value of another family refuses exit 2 (`wrong schema kind`). The envelope `claims_draft` pin must carry the same nonempty `schema_version`.

Identity: `run`, `review_state` (nonempty strings), `subject_oid`, `base_oid` (lowercase OIDs) must agree with the envelope. Nested profile:

- `sources[]`: `{source_ref, locator, path, role, sha256, byte_length [, blob_subject]}` — `path` is **run-root relative** (e.g. `claims/sources/pr-body.md`); `sha256`/`byte_length` must equal both the capture record (`capture_sha256`/`capture_byte_length` for the matching `locator`) and the actual bytes.
- `claims[]`: `{id, statement, source_ref, quote, also_in}`; `nonclaims[]`: `{id, statement, source_ref, quote, reason}`.
- `conflicts[]`: `{id, kind, materiality, quotes[{source_ref, quote, offset_bytes}], affected_claim_ids, precedence, witness, reasoning}`.
- `notes[]`: `{note}` (a quote-bearing note carries the defined optional `source_ref` + `quote` pair).
- `missing_source_candidates[]`: `{resource, affected_claim_ids, reference_quote, why_it_matters}`.
- `source_consistency`: optional; **omit the key rather than record an empty value**. When present it must be an object: `status` (optional; nonempty string when present), `records[]` (optional; array of objects whose `id` must be a nonempty string that **resolves to a recorded `conflicts[].id`** — an unresolved id fails `claims.conflicts` with `consistency record not found: "<id>"`), and `notes` (optional; nonempty string when present). Empty strings fail shape (`invalid field: /source_consistency/... expected nonempty string`); a wrong container or wrong-typed `records` fails shape (`expected object` / `expected array`).

<!-- claims-draft-example -->
```json
{
  "schema_version": "claims-draft/3",
  "run": "owner/repo#1",
  "review_state": "s1",
  "subject_oid": "2222222222222222222222222222222222222222",
  "base_oid": "3333333333333333333333333333333333333333",
  "sources": [
    {
      "source_ref": "pr:body",
      "locator": "pr:body",
      "path": "claims/sources/pr-body.md",
      "role": "declares",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "byte_length": 42
    }
  ],
  "claims": [
    {
      "id": "C01",
      "statement": "The PR adds the documented flag.",
      "source_ref": "pr:body",
      "quote": "adds a flag",
      "also_in": []
    }
  ],
  "nonclaims": [],
  "conflicts": []
}
```

## 3. Units manifest and payloads — `units/units2/manifest.json` (`code-units-sim/2`)

The manifest carries `schema_version`, `identity: {base_oid, subject_oid}` agreeing with the envelope, and `recipe` (field-by-field equal to the verifier's fixed recipe). `units[]` entries carry `unit_id` and `file` (the payload ref). Payload refs are the manifest's own `file` values resolved under the chunker OUTDIR — the parent of the `units2/` directory — not the run root. The envelope pins each payload as `unit_payloads[] = {unit_id, ref, sha256}` in manifest order; `chunker = {path: kernel/tools/chunker.mjs, sha256, recipe, cure_light_source_head_oid}` is the engine pin (external to the manifest).

## 4. Run envelope — `run-manifest.json` (`run-verification/1`)

The envelope is the recorded-input projection generated by `verify envelope` (prep/recording, stdout only, never a verdict). Stage-dependent slices are absent until produced; each command needs only its own evidence slice. Discovery: the capture manifest is fixed at `claims/sources/capture-manifest.json`; the generator discovers the claims draft under `claims/` (a single `claims-draft*.json`) and the join draft under `join/` (a single `join-draft*.json`), while the units manifest is looked up at `units/units2/manifest.json` then `units2/manifest.json`; more than one candidate refuses as ambiguous, and absent slices are omitted (not defaulted).

| Slice | Fields | Notes |
|---|---|---|
| identity | `run`, `review_state`, `base_oid`, `subject_oid`, `cure_light_source_head_oid` | must agree with every primary/capture artifact |
| `verifier` | `{path, sha256, tool_version}` | path is exactly `kernel/tools/verify.mjs`; sha/sha of actual bytes; `tool_version` `1.0.0` |
| `capture_manifest` | `{ref, sha256}` | capture pin — exactly two fields, no `schema_version` |
| `claims_draft` | `{ref, sha256, schema_version}` | primary pin; `schema_version` nonempty and equal to the file's |
| `chunker` | `{path, sha256, recipe, cure_light_source_head_oid}` | engine pin; recipe must equal the units manifest recipe |
| `units_manifest` | `{ref, sha256, schema_version}` | primary pin |
| `unit_payloads[]` | `{unit_id, ref, sha256}` | manifest order |
| `join_draft` | `{ref, sha256, schema_version}` | primary pin |
| `join_boxes[]` | `{box_id, assignment:{ref,sha256}, instructions:{ref,sha256}, claims_list:{ref,sha256}, p05_check:{ref,sha256}, p05_evidence:{ref,sha256}}` | per-box pins |
| `join_attempts[]` | `{attempt_id, box_id, parent_box_id, attempt, units[], output:{ref,sha256}, status}` | explicit recovery history; `status` records acceptance |
| `pilot` | `{operator_ref, input_ceiling_bytes, witness_max_chars: 160, retry_limit: 1, resplit: "halves", max_resplit_depth: 1, output_ceiling_bytes}` | approved policy; `output_ceiling_bytes` is `null` (monitoring-only) or a nonneg integer |

<!-- run-envelope-example -->
```json
{
  "schema_version": "run-verification/1",
  "run": "owner/repo#1",
  "review_state": "s1",
  "base_oid": "3333333333333333333333333333333333333333",
  "subject_oid": "2222222222222222222222222222222222222222",
  "cure_light_source_head_oid": "1111111111111111111111111111111111111111",
  "verifier": {
    "path": "kernel/tools/verify.mjs",
    "sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "tool_version": "1.0.0"
  },
  "capture_manifest": {
    "ref": "claims/sources/capture-manifest.json",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "claims_draft": {
    "ref": "claims/claims-draft.v3.json",
    "sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "schema_version": "claims-draft/3"
  },
  "chunker": {
    "path": "kernel/tools/chunker.mjs",
    "sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "recipe": {"target_bytes": 4096, "ceiling_bytes": 6144, "context": 3, "block_preference": true},
    "cure_light_source_head_oid": "1111111111111111111111111111111111111111"
  },
  "units_manifest": {
    "ref": "units/units2/manifest.json",
    "sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    "schema_version": "code-units-sim/2"
  },
  "unit_payloads": [
    {"unit_id": "u0000", "ref": "u0000.txt", "sha256": "9999999999999999999999999999999999999999999999999999999999999999"}
  ],
  "join_draft": {
    "ref": "join/join-draft.v1.json",
    "sha256": "8888888888888888888888888888888888888888888888888888888888888888",
    "schema_version": "join-draft/1"
  },
  "join_boxes": [
    {
      "box_id": "box-0000",
      "assignment": {"ref": "join/box-0000.assignment.json", "sha256": "7777777777777777777777777777777777777777777777777777777777777777"},
      "instructions": {"ref": "join/box-0000.instructions.md", "sha256": "6666666666666666666666666666666666666666666666666666666666666666"},
      "claims_list": {"ref": "join/claims-list.json", "sha256": "5555555555555555555555555555555555555555555555555555555555555555"},
      "p05_check": {"ref": "join/p05-check.json", "sha256": "4444444444444444444444444444444444444444444444444444444444444444"},
      "p05_evidence": {"ref": "join/p05-evidence.json", "sha256": "aaaa000000000000000000000000000000000000000000000000000000000000"}
    }
  ],
  "join_attempts": [
    {
      "attempt_id": "box-0000-a1",
      "box_id": "box-0000",
      "parent_box_id": null,
      "attempt": 1,
      "units": ["u0000"],
      "output": {"ref": "join/box-0000.jsonl", "sha256": "1111000000000000000000000000000000000000000000000000000000000000"},
      "status": "accepted"
    }
  ],
  "pilot": {
    "operator_ref": "operator:s1",
    "input_ceiling_bytes": 196608,
    "witness_max_chars": 160,
    "retry_limit": 1,
    "resplit": "halves",
    "max_resplit_depth": 1,
    "output_ceiling_bytes": null
  }
}
```

## 5. Join draft and P0.4/P0.5 files — `join-draft/1`

The merged `join/join-draft.v1.json` carries `schema_version: "join-draft/1"`, identity agreeing with the envelope, `units_manifest` (ref/hash identity), `boxes[]` (entries below), `units[]` rows (`{unit_id, links[], unresolved}`) in manifest order, and `candidate_unclaimed[]` (unique unit-ID strings in manifest order, exhaustive against all zero-link decidable units). Each link is `{claim_id, closeness: high|medium|low, role_hint: implements|tests|necessary-support|removes|changes, witness}`.

`boxes[]` entries carry five required fields. Envelope prep records `box_id` and `path` with the draft; the merged check pins all five:

| Field | Type | Rule |
|---|---|---|
| `box_id` | nonempty string | box identity used by every assignment, pin and output ref (`join/<box_id>.jsonl`); joins its `join_boxes[]` entry |
| `path` | nonempty string | the child-written output ref (e.g. `join/box-0000.jsonl`); must equal the assignment's `output_path` |
| `sha256` | nonempty string | box output pin: must equal the sha256 of the exact `path` bytes |
| `rows` | nonnegative integer | must equal the actual row count of the box JSONL (`box count mismatch: "<box_id>":rows`) |
| `links` | nonnegative integer | must equal the actual total `links[]` count across the box's rows (`box count mismatch: "<box_id>":links`) |

**Envelope prep (pre-recording).** The generator discovers exactly one `join/join-draft*.json` under `join/` — two or more refuse `REFUSE envelope: ambiguous join draft` (§4) — requires `boxes` to be an array (`malformed join draft: boxes`), and requires every entry to be an object with nonempty `box_id` and `path` (`malformed join draft: boxes entry`). It then resolves each box's assignment, instructions, claims list and P0.5 files, refusing with their own `REFUSE envelope: <reason>` details (`assignment box`/`output`/`manifest mismatch`, `malformed assignment`, `ambiguous instructions` / `missing instructions`, `missing p05 check` / `missing p05 evidence`, `malformed p05 evidence`, `input ceiling mismatch`) when those bindings fail. `sha256`, `rows` and `links` are enforced by the delegated `verify join` (shape failures plus pin/count mismatches), not by the generator — but a draft must carry `box_id` and `path` for prep to record it.

Per-box inputs and outputs (all pinned in `join_boxes`): `box-<id>.assignment.json`, `box-<id>.instructions.md`, `join/claims-list.json`, the child-written `box-<id>.jsonl`, and the P0.5 records `p05-check.json` / `p05-evidence.json`. JSONL is one row per assigned unit in listed order; retains original attempts and retry/split records in `join_attempts[]` — the explicit history the generator cannot infer without `--attempts`.

## 6. Budget, witness and recovery rules

- Packing is by input length only: instructions + the full `claims[].id`/`statement` list + whole units in manifest order; no unit-count cap, no reserved answer space, no unit split. Greedy box packing is enforced (`non-greedy box packing: <box>`); recovery halves are exempt.
- Witnesses are ≤160 Unicode code points (pilot constant), nonempty, single-line, and a byte-substring of the exact unit payload starting at a line boundary with a real diff marker (`+`, `-`, context space, `@@ `); `boundary_kind: 'file'` metadata units additionally allow the recognized metadata prefixes.
- Recovery is one retry on the same units, then halves: left = floor(n/2) units, right = the remainder (right larger for odd n), nonempty, order preserved, no unit split, depth ≤ 1; only accepted leaf attempts are the current sweep.

## 7. Error → field → doc anchor

| Observed check / detail | Field or cause | Anchor in this page |
|---|---|---|
| `schema`, `invalid field: /schema_version ...` | claims root `schema_version` missing/empty | §2 |
| `schema`, `invalid field: /capture_manifest/schema_version ...` | capture declared schema, empty/wrong-typed | §1 |
| `schema`, `unsupported schema_version` | unknown nonempty schema | §1/§2 |
| `artifact.discovery`, `wrong schema kind` | registered schema of another family | §1/§2 |
| `artifact.read`, `cannot read artifact` | path base or missing byte ref | §1/§2 |
| `artifact.path` | traversal/escape/URI/nonregular ref | §1 |
| `artifact.sha256`, `sha256 mismatch` / `sha256 pin missing` | stale pin after an edit | §1/§4 |
| `identity`, `identity mismatch: /<field>` | run/review_state/base_oid/subject_oid/engine OID disagree | §1/§2/§4 |
| `join.prerequisites`, `prerequisite failed: <class>` | an upstream claims/units slice failed | §2/§3 |
| `shape`, `invalid field: /boxes/<i>/<field> ...` | merged join-draft entry missing/empty `box_id`/`path`/`sha256`, or `rows`/`links` not nonnegative integers | §5 |
| `artifact.sha256`, `sha256 mismatch: "join/<box_id>.jsonl"` (may cascade into `join.recovery`, `stale accepted attempt`) / `join.merge`, `box count mismatch: "<box_id>":rows` or `:links` | box output pin or row/link counts changed without resealing the draft | §5 |
| `envelope`, `malformed join draft: boxes` / `malformed join draft: boxes entry` / `malformed join draft: schema_version` / `malformed join draft: /<field>` | pre-recording join draft: `boxes` not an array / entry without nonempty `box_id`+`path` / missing identity field | §4/§5 |
| `envelope`, `ambiguous join draft` / `ambiguous instructions` | more than one candidate draft / instructions file | §4/§5 |
| `envelope`, `assignment ... mismatch` / `missing instructions` / `missing p05 check` / `missing p05 evidence` / `input ceiling mismatch` | per-box assignment/instructions/P0.5 bindings refused at prep | §5 |
| `shape`, `invalid field: /source_consistency/...` | `source_consistency` present but empty-string or wrong-typed object/array | §2 |
| `claims.conflicts`, `consistency record not found: "<id>"` | `source_consistency.records[].id` not a recorded `conflicts[].id` | §2 |

## 8. Repair protocol — a distinct `fast` artifact-preparation/repair child

The mechanical verifier child stays read-only: it verifies, runs the pinned tool and returns the verdict; it never interprets, repairs or normalizes. Repair is a different role. When an artifact failure needs a fix, the coordinator spawns a distinct `fast` artifact-preparation/repair child, passing the exact verdict/error refs, the pinned docs (this page) and the authorized artifact paths. The repair child is never the verification child and never the coordinator itself; it works over the run artifacts only and returns a bounded receipt, then the boundary is re-delegated.

The repair child never changes captured source meaning, witness bytes, policy or claims semantics just to pass: it restores the recorded field to the recorded meaning and regenerates/refreezes the envelope only under the existing rewrite rules (regeneration after the frame freeze is not verification, and a changed envelope needs a fresh frame pin and a fresh delegated verdict). Ambiguity or an identity/refusal case pauses for the operator — no guessing, no parent source reading and no parent verifier rerun. Tool-source diagnosis, if genuinely necessary, is isolated child work with a bounded return and requires operator escalation; it is not a new checker and there is no coordinator source reading.
