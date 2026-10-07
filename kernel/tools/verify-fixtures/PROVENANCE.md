# Pinned-verifier fixture seed — provenance

`seed/` is a **synthetic compatibility fixture** for the pinned mechanical
verifier (`kernel/tools/verify.mjs`). It is derived from the raw S28 run
artifacts, but it is **not a historical successful FR run** and must never be
presented as one. The raw vault corpus remains the rejection/regression
evidence for the original run (markerless witnesses, single box, no zero-link
or unresolved rows, no retry history).

## Source

- Raw corpus (read-only): `/home/vscode/cure-light-pr17-s28-vault/run-artifacts/`
- Run: `grzegorznowak/cure-light#17`, `review_state: s1`
- Subject `afe5145da30fa7d5d2e212296f2c458d2bf7e941`, base `c79a54c57322b45498ffd01db45a876a4712e138`
- Historical engine OID: `cda939bab1e953e9e2f189d22d7bae995463816f` (replaced, see below)
- Schema versions: `claims-draft/3`, `code-units-sim/3`, `join-draft/1`; the
  capture manifest, assignment, p05 check and p05 evidence are unversioned
  legacy support objects parsed by the `run-verification/1` envelope profile.

### Original SHA-256 of each copied/derived artifact

| Artifact | Bytes | SHA-256 |
|---|---|---|
| `claims/claims-draft.v3.json` | 28570 | `0c4fcc36a973499dd04231e25b7d81cd904ae71ea0e375c9a1ac1dd0bc87ea83` |
| `claims/sources/capture-manifest.json` | 3888 | `e8fa8ed36d9ac6bcf303e239d6eb69c0028a0ca7e66df83370f6386f757ac967` |
| `claims/sources/pr-body.md` | 20413 | `4910224c9fbe2d1ef12bd00923ba983b2cf0c6f1fc30d2360fde55a1b03314e0` |
| `claims/sources/pr-title.txt` | 245 | `8c7a847d7a39904d0ea7fee40f151d05265d10417d1a563a533c3765f22d6060` |
| `claims/sources/designated-contract-adequacy-validation-plan.md` | 10736 | `2636ac18bf39c4bc756a39a0b82d95e7e26791bfe1cf67a60726589fa94104af` |
| `units/units2/manifest.json` | 29156 | `7266b92f33e441899bdfef59ef15cc3364655be4697caf8df44331e92a85a826` |
| `units/units2/u0000..u0045.txt` (46 payloads) | 171492 total | per-payload pins in `run-manifest.json` |
| `join/box-0000.assignment.json` | 1075 | `fb24ffe2f71b9327a9c467667b2adc59b3a487892e7bd55c621f737953194840` |
| `join/box-0000.instructions.md` | 847 | `f53886f7aafa644fe1971b206c6b74129d240636a33bf36afe2557e7eaaaa427` |
| `join/box-0000.jsonl` | 41125 | `24d38cdf482d3f2c127cd06b78fc2a2dc9e28c0b6ec2e0e5d3cdae95065105ef` |
| `join/claims-list.json` | 6660 | `5df6c58a212e06874bc1ab21dd5b084d4252783c5dfb7c0ba5347e43164ea876` |
| `join/join-draft.v1.json` | 60142 | `d0c60ae41d9c9b93c88a6db44b33e757ca641c865780b7ed494a7a16650a751c` |
| `join/p05-check.json` | 658 | `4abeca55b2c5d66c543939047e1b0d5d649c0354abc72b293e9eb6e4a2fc6581` |
| `join/p05-evidence.json` | 677 | `d09a7c1640120fa302c3edb4f51707d69c6213380f418858cceb6e59648f0cc4` |

## Synthetic identities (deliberate, documented)

The committed seed pins a **synthetic coherent engine identity**; it does not
claim historical provenance and does not pin live repository bytes as if they
were historical.

- `cure_light_source_head_oid` (in `capture-manifest.json` and `run-manifest.json`):
  `5eedc0de5eedc0de5eedc0de5eedc0de5eedc0de`.
- `chunker.sha256` (envelope): `925792df40294d2e4727bd4ebf7227ab3853f5c7f2bc8796bf6784dddc4c0f5a`
  — SHA-256 of the documented ASCII string `cure-light synthetic chunker pin (fixture)\n`.
  The recipe object is the real `code-units-sim/3` recipe (4096/6144/3/true).
- `verifier.sha256` (envelope): placeholder
  `2a891cce63f56263cc2ff92c4eaed43bd022a1e3a2b5fcf87684e7b49e967003`
  — SHA-256 of `placeholder: kernel/tools/verify.mjs absent at fixture seed time\n`.
  **`verify-testkit.mjs` rewrites this single pin at runtime** from the actual
  `kernel/tools/verify.mjs` bytes whenever that file exists; tests never rely on
  the placeholder. `verifier.tool_version` stays `1.0.0` (frozen contract).
- `subject_path` (capture) and `identity.repo` (units manifest) retain the
  historical `/tmp/cure-grzegorznowak-cure-light-17/tree` value. The contract
  forbids the verifier from reading either field, so they are inert; they are
  kept only as historical provenance.

## Exact transformations applied (migration, 2026-10-04)

1. **Byte-identical copies**: all three `claims/sources/*` documents, all 46
   payloads, `join/claims-list.json`, `join/p05-check.json`. Their original
   hashes above still hold; `units/units2/manifest.json` was later migrated to
   `/3` (item 7), so its table hash is historical.
2. **Absolute path migration** `/work/runs/s28-run-p0/` → run-root-relative:
   `claims/sources/*.json` `sources[].path` → `claims/sources/...`;
   assignment `output_path` → `join/box-0000.jsonl`, `units_dir` →
   `units/units2`, `claims_list_path` → `join/claims-list.json`; the
   `box-0000.instructions.md` prose writer path → `join/box-0000.jsonl`
   (847 → 825 bytes). `units/units2/manifest.json` `units[].file` was already
   relative to the chunker OUTDIR and is unchanged.
3. **Witness mechanical correction** in `join/box-0000.jsonl` and
   `join/join-draft.v1.json` (identical rows): every witness now starts at a
   payload line start whose first character is a legitimate diff marker
   (`+`, `-`, space context, or `@@ `). Correction = prefix of the containing
   line from its start through the original witness end, truncated to 160
   Unicode code points when longer. Results: 18 kept already-valid, 231
   corrected, of which 100 hit the 160-codepoint cap. All 249 remain nonempty,
   single-line, ≤160 code points, and byte substrings of their payloads.
4. **Regenerated derived hashes/counts/budget**: `join/box-0000.jsonl` bytes
   (41125 → 51394) and SHA in `join-draft.v1.json` `boxes[0].sha256`;
   `join/join-draft.v1.json` SHA; `p05-evidence.json` budget
   `output_bytes=51394`, `instructions_bytes=825`,
   `box_input_bytes=178977`, `headroom_bytes=17631` (unit/claims bytes and
   `output_links=249` unchanged); `capture-manifest.json` SHA after the
   synthetic engine identity swap; `claims-draft.v3.json` SHA after path
   migration; `box-0000.assignment.json` SHA after path migration (its
   `manifest_sha256` still equals the byte-identical units manifest).
5. **`run-manifest.json` envelope** (schema `run-verification/1`) written per
   plan §2 with coherent pins: capture, claims draft, units manifest, per
   payload, join draft, all box input artifacts, and the accepted
   `join_attempts[0]` output pin. `pilot` records the independently approved
   196608-byte input ceiling, `witness_max_chars=160`, `retry_limit=1`,
   `resplit='halves'`, `max_resplit_depth=1`, `output_ceiling_bytes=null`.
6. **No remaining `/work/runs/...` string** exists under `seed/` (grep-checked).
7. **`code-units-sim/3` migration (2026-10-07)**: `units/units2/manifest.json`
   gained `opaque_occurrences: []`, `skips: []`, `coverage` (complete, 0, []) and
   `counts.opaque_occurrences`/`counts.opaque_bytes`; `join-draft.v1.json` and
   `run-manifest.json` bind schema `/3`. Re-pinned: units manifest
   `730ec8b4badd32887acfb707bdcddd7dd1e891db9cc764cca1202845f3517bc9`
   (29330 bytes), join draft
   `6cb635f8cad87c0c0fa63d318912c93c6d42dfc040e43dac0e525828ad27d78e`,
   assignment `manifest_sha256`, envelope units/join pins.

## Rejection/regression evidence kept

`raw-s28-witnesses.json` preserves the original markerless witness samples
(e.g. `u0000 → C21 = "__pycache__/"`) so a regression test can prove the
verifier rejects them (`witness diff marker missing`). The raw corpus itself is
untouched in the vault.

## Coverage gaps later phases must add

S28 alone is insufficient for plan §4's full matrix. The committed seed covers
one all-`block` box, no zero-link rows (all 46 units are linked), no zero-link
claims, no unresolved rows, offset-null conflicts, no retry/split history, and
no metadata (`boundary_kind: 'file'`) payloads. Later phases must add minimal
synthesized variants for: zero-link unit + zero-link claim + unresolved row;
two boxes (including assignment sweep/duplicate unit cases); metadata/binary
payload exemption; successful retry and half-split recovery history; declared
numeric output ceiling; and an empty-diff run with complete empty evidence.
