// RED-first contract tests for the `units` command of kernel/tools/verify.mjs —
// code-units-sim/2 (plan §3 U1–U7, plan §4 items 7–11). Authored BEFORE the U
// validators exist (P3 batch C): with only the P2 stub in place every case fails
// at `units.not_implemented` / a missing target check; the intended failure mode
// encoded here becomes the regression gate.
//
//   node --test kernel/tools/verify.units.test.mjs
//   node --test "kernel/tools/*.test.mjs"
//
// Payload refs are OUTDIR-relative: a manifest units[].file "units2/uNNNN.txt"
// resolves under <run-root>/units/ (parent of the units2/ manifest directory).
// Fixture note: the seed's u0045 payload legitimately ends with a trailing LF
// (historical chunker output; byte_len accounts for it) — the verifier must
// treat one final LF as a line terminator, never as an empty diff line.
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import {
  CAPTURE_MANIFEST, CLAIMS_DRAFT, RUN_MANIFEST, UNITS_MANIFEST,
  cleanupTempDirs, editJson, findFailedCheck, materializeOpaqueRun, materializeRun,
  readBytes, readJson, resealEnvelope, resealUnitsBinding, runVerifier, sha256, snapshotTree,
  writeBytes,
} from "./verify-testkit.mjs";

after(cleanupTempDirs);

const UNITS_COUNTS = "units=46 files=22 line_split_units=0 total_bytes=171492";
const payloadRel = (id) => `units/units2/${id}.txt`;

function report(r) {
  return [
    `command: ${r.command}`,
    `status: ${r.status} signal: ${r.signal} error: ${r.error?.message ?? "none"}`,
    `parseError: ${r.parseError}`,
    `stdout: ${JSON.stringify(r.stdout)}`,
    `stderr: ${JSON.stringify(r.stderr)}`,
  ].join("\n");
}

function expectVerdict(r, status) {
  assert.equal(r.status, status, `expected exit ${status}\n${report(r)}`);
  assert.ok(r.verdict, `expected exactly one JSON verdict on stdout\n${report(r)}`);
  assert.equal(r.verdict.ok, status === 0, `ok must be ${status === 0}\n${report(r)}`);
  return r.verdict;
}

function expectFailure(r, check, detail) {
  const v = expectVerdict(r, 1);
  assert.match(v.summary, /^FAIL units: \d+ of \d+ checks failed$/, `failure summary\n${report(r)}`);
  const failed = findFailedCheck(v, check);
  assert.ok(failed, `missing failed check "${check}"\n${JSON.stringify(v.checks)}\n${report(r)}`);
  if (detail !== undefined) assert.equal(failed.detail, detail);
  return v;
}

function unitsPass(label = "units-pass") {
  const runRoot = materializeRun(label);
  const r = runVerifier(["units", "--run", runRoot], { runRoot });
  return { runRoot, r };
}

/** Mutate the units manifest, then refresh its envelope pin (and payload pins). */
function mutateManifest(runRoot, fn) {
  editJson(runRoot, UNITS_MANIFEST, fn);
  resealEnvelope(runRoot);
}

describe("units pass (plan §4 item 7)", () => {
  it("pass: exit 0, schema code-units-sim/2, all checks true, counts 46/22/0/171492", () => {
    const { r } = unitsPass("units-pass-ok");
    const v = expectVerdict(r, 0);
    assert.equal(v.schema, "code-units-sim/2");
    assert.equal(v.tool_version, "1.0.0");
    assert.match(v.summary, /^PASS units: \d+ checks$/);
    for (const check of v.checks) assert.equal(check.ok, true, `check ${check.name} must pass: ${check.detail}`);
    assert.ok(v.checks.some((c) => c.ok && c.detail === UNITS_COUNTS), `counts detail ${UNITS_COUNTS} missing\n${JSON.stringify(v.checks)}`);
  });

  it("units command is read-only (run root byte-identical)", () => {
    const { runRoot, r } = unitsPass("units-no-writes");
    expectVerdict(r, 0);
    const before = snapshotTree(runRoot);
    const again = runVerifier(["units", "--run", runRoot], { runRoot });
    expectVerdict(again, 0);
    assert.deepEqual(snapshotTree(runRoot), before, "run root must be byte-identical after read-only verify");
  });

  it("units works with the claims draft absent and no subject/PATH execution (PATH trap)", () => {
    const runRoot = materializeRun("units-no-claims");
    rmSync(path.join(runRoot, CLAIMS_DRAFT));
    const before = snapshotTree(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    for (const check of v.checks) assert.equal(check.ok, true, `check ${check.name} must pass: ${check.detail}`);
    assert.deepEqual(snapshotTree(runRoot), before, "units must not write or execute against the subject");
  });
});

describe("P10 regressions — falsy manifest top levels fail shape (F14)", () => {
  it("units manifest null/0/false/empty-string: exit 1 with the object shape check", () => {
    for (const [label, text] of [["null", "null"], ["zero", "0"], ["false", "false"], ["empty-string", '""']]) {
      const runRoot = materializeRun(`p10-units-${label}`);
      writeBytes(runRoot, UNITS_MANIFEST, Buffer.from(text));
      // resealEnvelope() parses the manifest; pin its raw bytes instead.
      editJson(runRoot, RUN_MANIFEST, (env) => { env.units_manifest.sha256 = sha256(readBytes(runRoot, UNITS_MANIFEST)); });
      const r = runVerifier(["units", "--run", runRoot], { runRoot });
      expectFailure(r, "shape", "invalid field: / expected object");
    }
  });
});

describe("units.payload (U3, plan §4 items 8–10)", () => {
  it("missing units/units2/u0000.txt fails payload missing (exit 1)", () => {
    const runRoot = materializeRun("units-missing-payload");
    rmSync(path.join(runRoot, payloadRel("u0000")));
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'payload missing: "u0000"');
  });

  it("manifest byte_len +1 (manifest + envelope resealed) fails byte_len mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-byte-len");
    mutateManifest(runRoot, (m) => { m.units[0].byte_len += 1; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'payload byte_len mismatch: "u0000"');
  });

  it("same-length payload tamper with stale SHA pin fails sha256 mismatch, not byte_len (exit 1)", () => {
    const runRoot = materializeRun("units-sha-tamper");
    const before = readBytes(runRoot, payloadRel("u0000"));
    const tampered = Buffer.from(before);
    tampered[0] = tampered[0] === 0x69 ? 0x68 : 0x69; // flip one content byte, same length
    writeBytes(runRoot, payloadRel("u0000"), tampered); // pins deliberately NOT resealed
    assert.equal(tampered.length, before.length, "premise: same byte length");
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    const v = expectFailure(r, "units.payload", 'payload sha256 mismatch: "u0000"');
    assert.ok(
      !v.checks.some((c) => c.ok === false && c.detail === 'payload byte_len mismatch: "u0000"'),
      "length check must not mask the SHA check",
    );
  });

  it("isolated wrong payload SHA pin fails sha256 mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-sha-pin");
    editJson(runRoot, RUN_MANIFEST, (env) => {
      env.unit_payloads.find((p) => p.unit_id === "u0000").sha256 = "0".repeat(64);
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'payload sha256 mismatch: "u0000"');
  });

  it("missing payload pin fails payload sha256 pin missing (exit 1)", () => {
    const runRoot = materializeRun("units-pin-missing");
    editJson(runRoot, RUN_MANIFEST, (env) => {
      env.unit_payloads = env.unit_payloads.filter((p) => p.unit_id !== "u0000");
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'payload sha256 pin missing: "u0000"');
  });

  it("extra payload pin for an unknown unit fails unassigned payload (exit 1)", () => {
    const runRoot = materializeRun("units-extra-pin");
    editJson(runRoot, RUN_MANIFEST, (env) => {
      env.unit_payloads.push({ unit_id: "u9999", ref: "units2/u9999.txt", sha256: "0".repeat(64) });
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'unassigned payload: "units2/u9999.txt"');
  });

  it("unreferenced uNNNN.txt in the payload directory fails unassigned payload (exit 1)", () => {
    const runRoot = materializeRun("units-extra-file");
    copyFileSync(path.join(runRoot, payloadRel("u0000")), path.join(runRoot, payloadRel("u9998")));
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'unassigned payload: "units2/u9998.txt"');
  });

  it("F7: unreferenced uNNNN.txt in a nested units subdirectory fails unassigned payload (exit 1)", () => {
    const runRoot = materializeRun("units-nested-payload");
    const dir = path.join(runRoot, "units/other");
    mkdirSync(dir, { recursive: true });
    copyFileSync(path.join(runRoot, payloadRel("u0000")), path.join(dir, "u9999.txt"));
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'unassigned payload: "other/u9999.txt"');
  });

  it("payload pin ref that does not match the manifest file fails ref mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-pin-ref");
    editJson(runRoot, RUN_MANIFEST, (env) => {
      env.unit_payloads.find((p) => p.unit_id === "u0000").ref = "units2/u0001.txt";
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.payload", 'payload ref mismatch: "u0000"');
  });
});

describe("units.identity (U2)", () => {
  it("engine OID mismatch across envelope/chunker pin fails units.identity (exit 1)", () => {
    const runRoot = materializeRun("units-engine-oid");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.chunker.cure_light_source_head_oid = "0".repeat(40); });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.identity", "identity mismatch: /chunker/cure_light_source_head_oid");
  });

  it("base OID mismatch fails units.identity (exit 1)", () => {
    const runRoot = materializeRun("units-base-oid");
    mutateManifest(runRoot, (m) => { m.identity.base_oid = "a".repeat(40); });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.identity", "identity mismatch: /identity/base_oid");
  });

  it("subject OID mismatch fails units.identity (exit 1)", () => {
    const runRoot = materializeRun("units-subject-oid");
    mutateManifest(runRoot, (m) => { m.identity.subject_oid = "b".repeat(40); });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.identity", "identity mismatch: /identity/subject_oid");
  });

  it("manifest chunker recipe drift fails chunker recipe mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-recipe");
    mutateManifest(runRoot, (m) => { m.recipe.target_bytes = 4097; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.identity", "chunker recipe mismatch: /recipe/target_bytes");
  });

  it("envelope chunker recipe drift fails chunker recipe mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-env-recipe");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.chunker.recipe.context = 4; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.identity", "chunker recipe mismatch: /chunker/recipe/context");
  });
});

describe("units.counts (U4)", () => {
  it("declared counts that disagree with the manifest fail unit count mismatch (exit 1)", () => {
    const cases = [
      ["units", (m) => { m.counts.units = 45; }],
      ["files", (m) => { m.counts.files = 21; }],
      ["line_split_units", (m) => { m.counts.line_split_units = 1; }],
      ["total_bytes", (m) => { m.counts.total_bytes += 1; }],
    ];
    for (const [field, mutate] of cases) {
      const runRoot = materializeRun(`units-count-${field}`);
      mutateManifest(runRoot, mutate);
      const r = runVerifier(["units", "--run", runRoot], { runRoot });
      expectFailure(r, "units.counts", `unit count mismatch: ${field}`);
    }
  });

  it("unit path set not equal to capture changed_files fails the sweep (exit 1)", () => {
    const runRoot = materializeRun("units-sweep");
    editJson(runRoot, CAPTURE_MANIFEST, (capture) => { capture.changed_files[0] = "not/a/changed-file.md"; });
    resealEnvelope(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.counts", "changed file sweep mismatch");
  });

  it("changed_files_count that disagrees with the list fails the sweep (exit 1)", () => {
    const runRoot = materializeRun("units-sweep-count");
    editJson(runRoot, CAPTURE_MANIFEST, (capture) => { capture.changed_files_count = 21; });
    resealEnvelope(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.counts", "changed file sweep mismatch");
  });
});

describe("units.ranges (U5)", () => {
  it("hunk_count disagreeing with ranges.length fails (exit 1)", () => {
    const runRoot = materializeRun("units-hunk-count");
    mutateManifest(runRoot, (m) => { m.units[0].hunk_count = 0; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.ranges", 'hunk_count mismatch: "u0000"');
  });

  it("unknown boundary_kind fails (exit 1)", () => {
    const runRoot = materializeRun("units-boundary-kind");
    mutateManifest(runRoot, (m) => { m.units[0].boundary_kind = "hunk"; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.ranges", 'invalid boundary_kind: "u0000"');
  });
});

describe("units.bounds (U6)", () => {
  it("block payload over recipe.ceiling_bytes fails payload ceiling exceeded (exit 1)", () => {
    const runRoot = materializeRun("units-over-ceiling");
    const id = "u0026"; // seed's largest payload: 6125 B, ceiling 6144
    const before = readBytes(runRoot, payloadRel(id));
    const grown = Buffer.concat([before, Buffer.from(`\n+${"x".repeat(6100)}`, "utf8")]);
    assert.ok(grown.length > 6144, "premise: grown payload exceeds the ceiling");
    writeBytes(runRoot, payloadRel(id), grown);
    mutateManifest(runRoot, (m) => {
      const unit = m.units.find((u) => u.unit_id === id);
      m.counts.total_bytes += grown.length - unit.byte_len;
      unit.byte_len = grown.length;
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.bounds", 'payload ceiling exceeded: "u0026"');
  });

  it("relabelling a hunk payload as boundary_kind file fails invalid metadata exemption (exit 1)", () => {
    const runRoot = materializeRun("units-bogus-file");
    mutateManifest(runRoot, (m) => { m.units[0].boundary_kind = "file"; });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.bounds", 'invalid metadata exemption: "u0000"');
  });

  it("genuine no-hunk metadata file unit over the ceiling passes bounds (exit 0)", () => {
    // Runtime synthesis (documented, non-invasive): u0000 becomes a metadata-only
    // `file` unit for a new binary file with a very long (but exact) path. The
    // 2x path in the `diff --git` line alone exceeds 6144 bytes, so the unit is
    // over-ceiling yet has no hunks and no content lines. capture.changed_files
    // swaps .gitignore -> long path so the U4 sweep stays coherent; manifest
    // counts/byte_len and all envelope pins are recomputed. No other seed
    // invariant is touched.
    const runRoot = materializeRun("units-metadata-file");
    const manifestBefore = readJson(runRoot, UNITS_MANIFEST);
    const oldLen = manifestBefore.units[0].byte_len;
    const component = "d".repeat(250);
    const longPath = `${Array.from({ length: 13 }, (_, i) => `${component}${i}`).join("/")}/file.bin`;
    const payload = [
      `diff --git a/${longPath} b/${longPath}`,
      "new file mode 100644",
      "index 0000000..1111111",
      `Binary files /dev/null and b/${longPath} differ`,
    ].join("\n");
    const payloadBuf = Buffer.from(payload, "utf8");
    assert.ok(payloadBuf.length > 6144, "premise: metadata payload exceeds the ceiling");
    writeBytes(runRoot, payloadRel("u0000"), payloadBuf);
    editJson(runRoot, UNITS_MANIFEST, (m) => {
      const unit = m.units[0];
      unit.path = longPath;
      unit.boundary_kind = "file";
      unit.ranges = [];
      unit.hunk_count = 0;
      unit.blocks = 1;
      unit.byte_len = payloadBuf.length;
      m.counts.total_bytes += payloadBuf.length - oldLen;
    });
    editJson(runRoot, CAPTURE_MANIFEST, (capture) => {
      capture.changed_files[capture.changed_files.indexOf(".gitignore")] = longPath;
    });
    resealEnvelope(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    for (const check of v.checks) assert.equal(check.ok, true, `check ${check.name} must pass: ${check.detail}`);
  });
});

describe("units.opaque — /3 raw-store quarantine and certificates", () => {
  it("b1: opaque unit with certified byte-identical pair passes", () => {
    const { runRoot, unitId, occurrenceIds, rawRefs, bodies, descriptorRef } = materializeOpaqueRun("opaque-pair");
    const manifest = readJson(runRoot, UNITS_MANIFEST);
    assert.equal(manifest.schema_version, "code-units-sim/3");
    assert.equal(manifest.units.at(-1).boundary_kind, "opaque");
    assert.deepEqual(manifest.coverage, { status: "complete", machine_occurrences: 2, skips: [] });
    assert.equal(manifest.counts.opaque_occurrences, 2);
    assert.equal(manifest.counts.opaque_bytes, bodies[0].length + bodies[1].length);
    assert.deepEqual(manifest.opaque_occurrences.map((o) => o.occurrence_id), occurrenceIds);
    for (let i = 0; i < bodies.length; i++) {
      assert.deepEqual(readBytes(runRoot, `units/${rawRefs[i]}`), bodies[i]);
      assert.equal(manifest.opaque_occurrences[i].sha256, sha256(bodies[i]));
      assert.doesNotMatch(path.basename(rawRefs[i]), /^u\d{4}\.txt$/, "raw files must never be model payloads");
    }
    const descriptorBytes = readBytes(runRoot, `units/${descriptorRef}`);
    assert.ok(descriptorBytes.length <= 1024, "descriptor must be bounded");
    assert.equal(JSON.parse(descriptorBytes.toString("utf8")).schema, "opaque-descriptor/1");
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    assert.ok(v.checks.some((c) => c.name === "units.opaque" && c.ok), `opaque validation missing\n${report(r)}`);
    assert.equal(unitId, "u0046");
  });

  it("b2/CB4: same-length raw byte tamper fails occurrence sha256 without echoing raw bytes", () => {
    const body = Buffer.from(`ZZBLOB7K${"q".repeat(6992)}`);
    const { runRoot, rawRefs } = materializeOpaqueRun("opaque-tamper", { bodies: [body, body] });
    const tampered = Buffer.from(body);
    tampered[123] ^= 1;
    writeBytes(runRoot, `units/${rawRefs[0]}`, tampered); // deliberately leave occurrence hash/pins stale
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.opaque", 'opaque occurrence sha256 mismatch: "occ-0000"');
    assert.ok(!`${r.stdout}\n${r.stderr}`.includes("ZZBLOB7K"), "verdict must not disclose raw bytes");
  });

  it("b3/CB3: unpinned extra raw occurrence is rejected, not silently ignored", () => {
    const extra = "units/units2/raw/occ-9999.bin";
    // Unlike the existing unassigned-uNNNN.txt check, this targets *.bin:
    // the old /2 payload walker ignores such files (schema gate is RED now).
    const { runRoot } = materializeOpaqueRun("opaque-extra");
    writeBytes(runRoot, extra, Buffer.from("extra unpinned opaque bytes"));
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.opaque", 'unpinned raw occurrence: "units2/raw/occ-9999.bin"');
  });

  it("b4: pair certificate over differing recorded raw buffers fails byte equality", () => {
    const left = Buffer.alloc(7000, 0x51);
    const right = Buffer.from(left);
    right[3500] = 0x52;
    const { runRoot } = materializeOpaqueRun("opaque-mismatch", { bodies: [left, right] });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.opaque", 'opaque certificate byte mismatch: "pair-0000"');
  });

  it("b5: partial coverage with no corresponding skips fails accounting", () => {
    const { runRoot } = materializeOpaqueRun("opaque-coverage", {
      coverage: { status: "partial", machine_occurrences: 2, skips: ["skip-0000"] },
      skips: [], // claimed skip id has no skips[] record; pair itself stays valid
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.opaque", "coverage/skips mismatch");
  });

  it("b6: a valid JSON opaque descriptor over 1024 bytes fails its size cap", () => {
    const { runRoot, unitId, descriptorRef } = materializeOpaqueRun("opaque-descriptor-size");
    const rel = `units/${descriptorRef}`;
    const grown = Buffer.concat([readBytes(runRoot, rel), Buffer.from(" ".repeat(1025))]);
    JSON.parse(grown.toString("utf8")); // still valid metadata-only JSON
    writeBytes(runRoot, rel, grown);
    editJson(runRoot, UNITS_MANIFEST, (m) => {
      const unit = m.units.find((u) => u.unit_id === unitId);
      m.counts.total_bytes += grown.length - unit.byte_len;
      unit.byte_len = grown.length;
    });
    resealUnitsBinding(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.opaque", `opaque descriptor too large: "${unitId}"`);
  });
});

describe("units schema hard migration", () => {
  it('a plain /2 units manifest refuses with unsupported schema_version: "code-units-sim/2" (exit 2)', () => {
    const runRoot = materializeRun("units-v2-refusal");
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 2);
    assert.equal(v.summary, 'REFUSE units: unsupported schema_version: "code-units-sim/2"');
  });
});

describe("units.diff (U7)", () => {
  it("payload line without a diff marker fails diff marker missing (exit 1)", () => {
    const runRoot = materializeRun("units-marker");
    const original = readBytes(runRoot, payloadRel("u0000"));
    writeBytes(runRoot, payloadRel("u0000"), Buffer.from("x".repeat(original.length), "utf8"));
    resealEnvelope(runRoot); // keep the pin/byte_len satisfied so U7 is the failing check
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.diff", 'diff marker missing: "u0000"');
  });

  it("block unit whose payload has metadata but no hunk/content fails framing (exit 1)", () => {
    const runRoot = materializeRun("units-framing");
    const id = "u0000";
    const original = readBytes(runRoot, payloadRel(id));
    const metadataOnly = Buffer.from(`index ${"0".repeat(original.length - "index ".length)}`, "utf8");
    assert.equal(metadataOnly.length, original.length, "premise: same length keeps byte_len coherent");
    writeBytes(runRoot, payloadRel(id), metadataOnly);
    resealEnvelope(runRoot);
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.diff", 'diff marker missing: "u0000"');
  });

  it("diff path that does not match the manifest unit path fails path mismatch (exit 1)", () => {
    const runRoot = materializeRun("units-diff-path");
    const id = "u0000";
    const before = readBytes(runRoot, payloadRel(id));
    const payload = Buffer.from("--- a/wrong/path.md\n+++ b/wrong/path.md\n+hello\n", "utf8");
    writeBytes(runRoot, payloadRel(id), payload);
    mutateManifest(runRoot, (m) => {
      const unit = m.units.find((u) => u.unit_id === id);
      m.counts.total_bytes += payload.length - before.length;
      unit.byte_len = payload.length;
    });
    const r = runVerifier(["units", "--run", runRoot], { runRoot });
    expectFailure(r, "units.diff", 'diff path mismatch: "u0000"');
  });
});
