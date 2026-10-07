# chunker.md — Phase-0 code units

The chunker is the small zero-dependency engine tool shipped at
[`kernel/tools/chunker.mjs`](../tools/chunker.mjs). It supplies the unit inventory
for P0.4 joining and V1 accounting; it does not extract claims, judge links,
finalize UNCLAIMED or implement the coordinator's P0.5 gate. The recorded
units-manifest/payload field contracts and their path bases are in
[artifact-contracts.md](artifact-contracts.md).

## Identity and invocation

The compiled frame records the engine script path, sha256 of its exact bytes,
and recipe, bound to `cure_light_source_head_oid`. Use the script from that
cure-light source, never a copy from the review subject. Run with Node and git;
no package install, parser library, Python environment or census plugin is needed.

```text
node <cure-light>/kernel/tools/chunker.mjs <repo> <base> <subject> <outDir>
  → <outDir>/units2/manifest.json
  → <outDir>/units2/u0000.txt …
```

`repo` is the pulled subject repo; pass the state's frozen `base_oid` and
`subject_oid`, not moving remote names. `outDir` is a fresh run-artifact location
outside the subject. The manifest's `units[].file` paths are relative to this
root. Missing positional arguments exit 2; a failed git/read/write exits
non-zero and never publishes a manifest — a failed chunking step is never an
empty successful inventory. Stdout reports counts and one compact line per unit;
consumers use artifact paths, and a failure never counts as coverage of the
changed surface.

## Recipe

Use two-dot `base..subject`, not a merge-base substitution:

```text
git -C <repo> -c core.quotepath=false -c diff.suppressBlankEmpty=false \
    diff -U3 --src-prefix=a/ --dst-prefix=b/ --inter-hunk-context=0 \
    --submodule=short --ignore-submodules=none \
    --no-ext-diff --no-color --no-renames --no-textconv \
    --diff-algorithm=myers <base>..<subject>
```

`--no-textconv` and `--no-ext-diff` keep subject-configured diff filters (which
are subject-tree executables) out of the run; `core.quotepath=false` keeps paths
stable. The recipe is also pinned against subject- and runner-side configuration
that would otherwise change the inventory: explicit `--src-prefix`/`--dst-prefix`
defeat `diff.noprefix`/`diff.srcPrefix`/`diff.dstPrefix`; `GIT_DIFF_OPTS` is
cleared for the git child (it overrides `-U3`); `--submodule=short
--ignore-submodules=none` keeps pointer changes visible even under a committed
`ignore=all`; `--inter-hunk-context=0` and `-c diff.suppressBlankEmpty=false`
pin hunk partitioning and payload bytes. Partition in diff file order into
windows, target 4096 bytes / ceiling
6144 bytes. Prefer file-end → hunk-end → block-end → line-end, never mid-line.
Whole hunks fit together when within the ceiling; oversized hunks are grouped at
logical block boundaries before line fallback. Block detection is a lexical
heuristic: definition-start lines (`def`, `class`, `function`, `export`, etc.),
otherwise blank-line paragraphs — not AST ownership. Definition-start detection
is column-0 only: an indented definition (`    def f()`) is not recognized and
falls to the blank-line paragraph rule; the consequence is grouping only, never
unit coverage. Units never cross files.
P0.4 packs whole units in manifest order and never splits a unit between children.

An indivisible line larger than the ceiling cannot fit any code window. The
chunker never splits it mid-line and never copies its bytes into a model-facing
payload: the line becomes an opaque occurrence whose whole body (marker
stripped, terminator excluded, CR retained) is captured before UTF-8 decoding
and stored machine-side at units2/raw/occ-NNNN.bin, while the reviewable
remainder of its hunk is chunked normally. No-hunk file metadata remains visible
as a `file` unit, not silently excluded; metadata units are not code windows and
are exempt from the window ceiling. Determinism means identical frozen inputs
and effective diff recipe produce the same ordered units; model-authored
claims/links do not share this guarantee.

## Manifest and payload contract

The emitted manifest is code-units-sim/3 always, never code-units-sim/2 (hard
schema migration; the pinned verifier refuses `/2` with exit 2 and has no
compatibility path). It records `recipe`, `identity`, `counts`, ordered `units`,
opaque_occurrences[], `skips[]` and `coverage`. `recipe` records chunker name,
target/ceiling bytes, context and block preference. `identity` records repo,
input refs and resolved base/subject OIDs. Each unit records `unit_id`, relative
`file`, target `path`, `ranges`, `hunk_count`, `byte_len`, `blocks` and
boundary_kind: opaque — alongside `file`, `block` and `line-split`. Ranges
contain old/new start/count pairs from contributing hunk headers. Unit IDs are
sequential and state-bound, not globally canonical identities.

Opaque occurrences record `{occurrence_id, path, side, state, pair_id,
byte_length, sha256, ref}` where `ref` is units2/raw/occ-NNNN.bin — a
machine-only raw store that never matches the `uNNNN.txt` payload namespace.
Body bytes are the diff line without its single marker and without the line
terminator (a CR is retained; capture happens before decoding so invalid UTF-8
round-trips exactly). Removed/added occurrences whose bodies are byte-identical
are certified as one pair with a shared `pair_id`; ambiguous duplicates,
one-sided occurrences and failed byte equality are recorded in `skips[]` with a
`reason` (`unpaired`, `ambiguous`, `not-byte-equal`).

coverage.status: partial marks a run whose recorded skips still need operator
review; `complete` marks a fully certified machine result, and
`machine_occurrences` counts the recorded occurrences. A partial run may not
prepare a V1 envelope without the operator approval artifact
(`approvals/operator-approval.json`, schema `operator-approval/1`) pinned as
`pilot.approval`; the delegated `verify join` re-binds its bytes and identity to
the recorded skips.

Every opaque run also carries first-class descriptor units in `units[]` with
`boundary_kind: opaque`. The descriptor payload is metadata-only JSON, schema
opaque-descriptor/1 (`{schema, unit_id, occurrences, pairing}`), bounded by the
1024-byte opaque descriptor limit, and contains no occurrence bytes. counts
records units, diff files, line-split units, opaque occurrences,
counts.opaque_bytes (the raw occurrence total, separate from the payload-only
`total_bytes`) and the payload total. Model-facing payloads, stdout and the
manifest never contain opaque bytes: the raw store is machine-side evidence,
not review input.

Payloads are diff fragments with context. `byte_len` is the exact stored payload
size (`lines.join("\n")`, no trailing newline) and matches the payload file. Hunk
ranges can repeat across units; `hunk_count` is the number of recorded range
entries, not necessarily distinct hunks. Neither context lengths nor repeated
ranges are unique changed-line counts. `blocks` is a grouping counter (whole
hunks count 1; split logical blocks increment), not an AST count.

The script emits no SHA fields, engine OID or self-verification; the coordinator
wrapper records path + sha256 + recipe at `cure_light_source_head_oid` and binds
manifest/payload bytes to retained run evidence. Those recorded wrapper pins and
payload bytes are consumed mechanically by the pinned verifier — the delegated
`verify join` boundary validates them through its internal units prerequisite,
and `verify units` remains available as an optional diagnostic command
(`kernel/tools/verify.mjs`); this script still emits no unit-payload SHA or
engine OID — occurrence sha256 values are body-matching evidence inside the
machine lane, never payload pins or model input.

## Validation and limits

Verify the manifest resolves to this state's OIDs and every referenced payload
exists; verify all diff file surfaces are represented, order is preserved,
payloads are within bounds (or the step failed), and replay under the same frozen
inputs and effective recipe is identical. Unknown or unrepresented surfaces remain
explicit limitations; they never become complete coverage or a speculative
negative.

Port deltas over the reference simulation, already applied in the shipped script:
exact payload byte measure; buffered emission preserves diff order; `line-split`
does not stick past the buffer that produced it; `--no-textconv` /
`core.quotepath=false` hardening; an over-ceiling indivisible line is captured
to the machine-only raw store instead of a hard error. Remaining limits: paths
that are not valid UTF-8 may be mangled by text decoding; diff content is
decoded as UTF-8 for reviewable payloads and invalid byte sequences are replaced
(lossy), so a payload `byte_len` measures the replacement bytes rather than the
subject's original bytes (opaque occurrence bodies are captured before decoding
and preserve them exactly); a path git still C-quotes (embedded quotes, backslashes
or control characters) is stored as the raw header text rather than a decoded path;
splitting can repeat a hunk's full range in several units, so ranges are not a
disjoint line denominator; and runner-specific git configuration beyond the
explicit flags above is not asserted. These are port-validation checkpoints, not
permissions to import the retired changed-line census semantics.

The coordinator checks join completeness under
[intake-and-scope.md](intake-and-scope.md) §0.3; only V1 finalizes accounting under
[conformance-pass.md](conformance-pass.md).
