// kernel/tools/verify.envelope.test.mjs — RED-first contract tests for the
// `envelope` prep subcommand of kernel/tools/verify.mjs (fixpass spec §E).
//
// The subcommand PRINTS a candidate run-manifest.json document: compact JSON +
// one LF on stdout, exit 0, silent stderr. It is a document, never a verdict:
// it never writes files, never repairs artifacts, and ignores any existing
// run-manifest.json. Refusals exit 2 with summary "REFUSE envelope: <reason>".
//
// Run with:
//   node --test kernel/tools/verify.envelope.test.mjs
//
// Every spawn goes through the testkit's trap-PATH runVerifier (no git/network).
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { copyFileSync, existsSync, rmSync } from "node:fs";
import path from "node:path";
import {
  RUN_MANIFEST,
  artifactSha,
  cleanupTempDirs,
  findFailedCheck,
  materializeEmptyRun,
  materializeOpaqueRun,
  materializeRun,
  readBoxRows,
  readJson,
  runVerifier,
  setJoinAttempts,
  snapshotTree,
  splitIntoTwoBoxes,
  writeAttemptOutput,
  writeJson,
} from "./verify-testkit.mjs";

after(cleanupTempDirs);

// The two non-derivable inputs (fixpass spec §E test 1): the synthetic chunker
// pin recorded by the fixture seed and the S28 gate operator reference.
const CHUNKER_SHA = "925792df40294d2e4727bd4ebf7227ab3853f5c7f2bc8796bf6784dddc4c0f5a";
const OPERATOR_REF = "fixture:s28-gate-0";
const ENVELOPE_USAGE_PREFIX = "usage: verify envelope";

function envelopeArgs(runRoot, opts = {}) {
  const args = [
    "envelope",
    "--run", runRoot,
    "--operator-ref", opts.operatorRef ?? OPERATOR_REF,
    "--chunker-sha256", opts.chunkerSha ?? CHUNKER_SHA,
    "--input-ceiling-bytes", opts.inputCeiling ?? "196608",
    "--output-ceiling-bytes", opts.outputCeiling ?? "none",
  ];
  if (opts.attempts !== undefined) args.push("--attempts", opts.attempts);
  return args;
}

/** Remove one `--flag value` pair from an argument list. */
function withoutFlag(args, flag) {
  const index = args.indexOf(flag);
  assert.ok(index >= 0, `flag ${flag} not in args`);
  return args.slice(0, index).concat(args.slice(index + 2));
}

function report(r) {
  return [
    `command: ${r.command}`,
    `status: ${r.status} signal: ${r.signal} error: ${r.error?.message ?? "none"}`,
    `parseError: ${r.parseError}`,
    `stdout: ${JSON.stringify(r.stdout)}`,
    `stderr: ${JSON.stringify(r.stderr)}`,
  ].join("\n");
}

/** Success: exit 0, compact JSON document + LF on stdout, nothing on stderr. */
function expectDocument(r) {
  assert.equal(r.status, 0, `expected a document with exit 0\n${report(r)}`);
  assert.equal(r.stderr, "", `success must write nothing to stderr\n${report(r)}`);
  assert.ok(r.stdout.endsWith("\n"), `stdout must end with one LF\n${report(r)}`);
  return JSON.parse(r.stdout);
}

/** Refusal: exit 2, ok:false verdict, summary "REFUSE envelope: <reason>". */
function expectRefusal(r, { detailPrefix } = {}) {
  assert.equal(r.status, 2, `expected refusal exit 2\n${report(r)}`);
  assert.ok(r.verdict, `expected exactly one JSON verdict on stdout\n${report(r)}`);
  assert.equal(r.verdict.ok, false, `ok must be false\n${report(r)}`);
  assert.match(r.verdict.summary, /^REFUSE envelope: /, `summary\n${report(r)}`);
  if (detailPrefix) {
    const failed = r.verdict.checks.find((c) => c.ok === false);
    assert.ok(failed, `expected a failed check\n${report(r)}`);
    assert.ok(
      failed.detail.startsWith(detailPrefix),
      `failed check detail ${JSON.stringify(failed.detail)} must start with ${JSON.stringify(detailPrefix)}\n${report(r)}`,
    );
  }
  return r.verdict;
}

describe("envelope prep subcommand: generation", () => {
  it("P1 round-trips a materialized seed envelope (deep-equal)", () => {
    const runRoot = materializeRun("envelope-roundtrip");
    const r = runVerifier(envelopeArgs(runRoot), { runRoot });
    const document = expectDocument(r);
    assert.deepEqual(document, readJson(runRoot, RUN_MANIFEST));
  });

  it("P2 generated envelope passes claims/units/join", () => {
    const runRoot = materializeRun("envelope-verifies");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot), { runRoot }));
    writeJson(runRoot, RUN_MANIFEST, document);
    for (const command of ["claims", "units", "join"]) {
      const v = runVerifier([command, "--run", runRoot], { runRoot });
      assert.equal(v.status, 0, `${command} must exit 0\n${report(v)}`);
      assert.equal(v.verdict?.ok, true, `${command} must be ok\n${report(v)}`);
    }
  });

  it("P3 never writes to the run root", () => {
    const runRoot = materializeRun("envelope-nowrites");
    const before = snapshotTree(runRoot);
    expectDocument(runVerifier(envelopeArgs(runRoot), { runRoot }));
    assert.deepEqual(snapshotTree(runRoot), before, "the run root tree must be byte-identical");
  });

  it("P4 two invocations produce byte-identical stdout", () => {
    const runRoot = materializeRun("envelope-determinism");
    const first = runVerifier(envelopeArgs(runRoot), { runRoot });
    const second = runVerifier(envelopeArgs(runRoot), { runRoot });
    expectDocument(first);
    expectDocument(second);
    assert.equal(second.stdout, first.stdout);
  });
});

describe("envelope prep subcommand: refusals", () => {
  it("P5 strict parsing refusals (exit 2, REFUSE envelope)", () => {
    const runRoot = materializeRun("envelope-refusals");
    const cases = [
      { name: "missing --operator-ref", args: withoutFlag(envelopeArgs(runRoot), "--operator-ref"), usage: true },
      { name: "missing --chunker-sha256", args: withoutFlag(envelopeArgs(runRoot), "--chunker-sha256"), usage: true },
      { name: "short --chunker-sha256", args: envelopeArgs(runRoot, { chunkerSha: "abc" }), usage: true },
      { name: "non-hex --chunker-sha256", args: envelopeArgs(runRoot, { chunkerSha: "z".repeat(64) }), usage: true },
      { name: "non-numeric --output-ceiling-bytes", args: envelopeArgs(runRoot, { outputCeiling: "abc" }), usage: true },
      { name: "negative --input-ceiling-bytes", args: envelopeArgs(runRoot, { inputCeiling: "-1" }), usage: true },
      { name: "fractional --input-ceiling-bytes", args: envelopeArgs(runRoot, { inputCeiling: "1.5" }), usage: true },
      { name: "unknown flag", args: [...envelopeArgs(runRoot), "--force"], usage: true },
      { name: "duplicate flag", args: [...envelopeArgs(runRoot), "--run", runRoot], usage: true },
      { name: "missing flag value", args: [...envelopeArgs(runRoot), "--attempts"], usage: true },
      { name: "missing --run", args: withoutFlag(envelopeArgs(runRoot), "--run"), usage: true },
    ];
    for (const testCase of cases) {
      const r = runVerifier(testCase.args, { runRoot });
      expectRefusal(r, testCase.usage ? { detailPrefix: ENVELOPE_USAGE_PREFIX } : {});
    }
  });

  it("P5 input ceiling differing from the recorded artifacts refuses", () => {
    const runRoot = materializeRun("envelope-ceiling-mismatch");
    const r = runVerifier(envelopeArgs(runRoot, { inputCeiling: "1" }), { runRoot });
    const verdict = expectRefusal(r);
    assert.ok(
      verdict.summary.includes("input ceiling mismatch"),
      `summary must name the mismatch\n${report(r)}`,
    );
  });
});

describe("envelope prep subcommand: pilot/output and attempts", () => {
  it("P6 records --output-ceiling-bytes 1, then verify join enforces it", () => {
    const runRoot = materializeRun("envelope-output-ceiling");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot, { outputCeiling: "1" }), { runRoot }));
    assert.equal(document.pilot.output_ceiling_bytes, 1);
    writeJson(runRoot, RUN_MANIFEST, document);
    const v = runVerifier(["join", "--run", runRoot], { runRoot });
    assert.equal(v.status, 1, `output ceiling must fail the join\n${report(v)}`);
    assert.equal(v.verdict?.ok, false, report(v));
    const failed = findFailedCheck(v.verdict, "join.budget");
    assert.ok(failed, `missing failed join.budget check\n${report(v)}`);
    assert.equal(failed.detail, 'output budget exceeded: "box-0000"');
  });

  it("P7 --attempts round-trips the generated default history byte-identically", () => {
    const runRoot = materializeRun("envelope-attempts");
    const first = runVerifier(envelopeArgs(runRoot), { runRoot });
    const document = expectDocument(first);
    writeJson(runRoot, "join/attempts.json", document.join_attempts);
    const second = runVerifier(envelopeArgs(runRoot, { attempts: "join/attempts.json" }), { runRoot });
    expectDocument(second);
    assert.equal(second.stdout, first.stdout);
  });

  it("P7 malformed --attempts refs refuse", () => {
    const runRoot = materializeRun("envelope-attempts-bad");
    writeJson(runRoot, "join/attempts.json", { not: "an array" });
    expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: "join/attempts.json" }), { runRoot }));

    writeJson(runRoot, "join/attempts.json", [
      {
        attempt_id: "box-0000-a1",
        box_id: "box-0000",
        parent_box_id: null,
        attempt: 1,
        units: ["u0000"],
        output: { ref: "join/missing-output.jsonl", sha256: "00" },
        status: "accepted",
      },
    ]);
    expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: "join/attempts.json" }), { runRoot }));
  });
});

describe("envelope prep subcommand: opaque approval binding", () => {
  const APPROVAL_REF = "approvals/operator-approval.json";

  it("b16: --approval accepts a present operator-approval/1 artifact and pins exact bytes", () => {
    const { runRoot } = materializeOpaqueRun("envelope-approval");
    const env = readJson(runRoot, RUN_MANIFEST);
    writeJson(runRoot, APPROVAL_REF, {
      schema_version: "operator-approval/1", run: env.run, review_state: env.review_state,
      base_oid: env.base_oid, subject_oid: env.subject_oid,
      operator_ref: OPERATOR_REF, approved: [],
    });
    const before = snapshotTree(runRoot);
    const document = expectDocument(runVerifier([...envelopeArgs(runRoot), "--approval", APPROVAL_REF], { runRoot }));
    assert.equal(document.units_manifest.schema_version, "code-units-sim/3");
    assert.deepEqual(document.pilot.approval, { ref: APPROVAL_REF, sha256: artifactSha(runRoot, APPROVAL_REF) });
    assert.deepEqual(snapshotTree(runRoot), before, "approval prep must remain read-only");
  });

  it("b16: --approval missing artifact refuses rather than recording an unverifiable pin", () => {
    const { runRoot } = materializeOpaqueRun("envelope-approval-missing");
    const r = runVerifier([...envelopeArgs(runRoot), "--approval", APPROVAL_REF], { runRoot });
    const verdict = expectRefusal(r);
    assert.match(verdict.summary, /approval artifact missing/);
  });

  it("b17: partial coverage without --approval refuses before preparing a V1 run", () => {
    const { runRoot } = materializeOpaqueRun("envelope-partial-no-approval", {
      bodies: [Buffer.alloc(7000, 0x51)], sides: ["added"], pairId: null,
      states: ["unpaired"],
      coverage: { status: "partial", machine_occurrences: 0, skips: ["skip-0000"] },
      skips: [{ skip_id: "skip-0000", reason: "unpaired", occurrence_ids: ["occ-0000"] }],
    });
    const r = runVerifier(envelopeArgs(runRoot), { runRoot });
    const verdict = expectRefusal(r);
    assert.match(verdict.summary, /approval required for partial coverage/);
  });
});

describe("envelope prep subcommand: stage-dependent slices", () => {
  it("P8 empty inventory generates and verifies empty units/join slices", () => {
    const runRoot = materializeEmptyRun("envelope-empty");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot), { runRoot }));
    assert.deepEqual(document.join_boxes, []);
    assert.deepEqual(document.join_attempts, []);
    writeJson(runRoot, RUN_MANIFEST, document);
    for (const command of ["units", "join"]) {
      const v = runVerifier([command, "--run", runRoot], { runRoot });
      assert.equal(v.status, 0, `${command} must exit 0\n${report(v)}`);
    }
  });

  it("P9 claims-only stage omits units/join slices and verify claims passes", () => {
    const runRoot = materializeRun("envelope-claims-only");
    rmSync(path.join(runRoot, "units"), { recursive: true, force: true });
    rmSync(path.join(runRoot, "join"), { recursive: true, force: true });
    const document = expectDocument(runVerifier(envelopeArgs(runRoot), { runRoot }));
    for (const key of ["chunker", "units_manifest", "unit_payloads", "join_draft", "join_boxes", "join_attempts"]) {
      assert.ok(!(key in document), `claims-only document must omit ${key}`);
    }
    assert.ok(document.claims_draft, "claims slice must be present");
    writeJson(runRoot, RUN_MANIFEST, document);
    const v = runVerifier(["claims", "--run", runRoot], { runRoot });
    assert.equal(v.status, 0, `claims must exit 0\n${report(v)}`);
  });
});

// ---------------------------------------------------------------------------
// Recovered halves + explicit attempt history (post-review hardening).
//
// splitIntoTwoBoxes rewrites the join draft to two child boxes that share the
// parent's join/box-0000.instructions.md and keep the seed's global p05 files
// alongside the new per-box ones. The accepted children carry parent_box_id,
// so `--attempts` must drive instructions discovery and per-box p05 discovery
// must win over the stale globals.
// ---------------------------------------------------------------------------

/** Recovered-halves run: join.test.mjs J9 fixture, attempts serialized. */
function recoveredHalvesRun(label) {
  const runRoot = materializeRun(label);
  const rows = readBoxRows(runRoot);
  const ids = rows.map((r) => r.unit_id);
  const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
  writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
  writeAttemptOutput(runRoot, "join/box-0000.attempt2.jsonl", rows);
  setJoinAttempts(runRoot, [
    { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
    { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: "join/box-0000.attempt2.jsonl", status: "failed" },
    { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
    { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.jsonl", status: "accepted" },
  ]);
  writeJson(runRoot, "join/attempts.json", readJson(runRoot, RUN_MANIFEST).join_attempts);
  return runRoot;
}

describe("envelope prep subcommand: recovered splits and attempt coherence", () => {
  it("R1 recovered halves with explicit attempt history generate and verify join", () => {
    const runRoot = recoveredHalvesRun("envelope-recovered-halves");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot, { attempts: "join/attempts.json" }), { runRoot }));
    writeJson(runRoot, RUN_MANIFEST, document);
    const v = runVerifier(["join", "--run", runRoot], { runRoot });
    assert.equal(v.status, 0, `join must exit 0 for recovered halves\n${report(v)}`);
    assert.equal(v.verdict?.ok, true, report(v));
  });

  it("R2 per-box p05 files win over coexisting global files in a recovered split", () => {
    const runRoot = recoveredHalvesRun("envelope-recovered-p05");
    assert.ok(existsSync(path.join(runRoot, "join/p05-check.json")), "the seed global check must survive the split");
    assert.ok(existsSync(path.join(runRoot, "join/p05-evidence.json")), "the seed global evidence must survive the split");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot, { attempts: "join/attempts.json" }), { runRoot }));
    for (const box of document.join_boxes) {
      assert.equal(box.p05_check.ref, `join/${box.box_id}.p05-check.json`, `check ref for ${box.box_id}`);
      assert.equal(box.p05_evidence.ref, `join/${box.box_id}.p05-evidence.json`, `evidence ref for ${box.box_id}`);
    }
  });

  it("R3 single-box seed keeps the global-only p05 discovery path", () => {
    const runRoot = materializeRun("envelope-single-box-p05");
    const document = expectDocument(runVerifier(envelopeArgs(runRoot), { runRoot }));
    assert.deepEqual(
      document.join_boxes.map((box) => [box.p05_check.ref, box.p05_evidence.ref]),
      [["join/p05-check.json", "join/p05-evidence.json"]],
    );
    assert.deepEqual(document, readJson(runRoot, RUN_MANIFEST));
  });

  it("R4 attempt coherence refusals: duplicate accepted, duplicate id, unknown box, missing accepted", () => {
    const runRoot = materializeRun("envelope-attempts-coherence");
    const attemptsRef = "join/attempts.json";
    const entry = readJson(runRoot, RUN_MANIFEST).join_attempts[0];

    // Reviewer repro: [entry, entry] used to be emitted verbatim and produced
    // an envelope that fails `verify join` with a stale accepted attempt.
    writeJson(runRoot, attemptsRef, [entry, entry]);
    const dupAccepted = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
    assert.match(dupAccepted.summary, /duplicate accepted attempt/);

    // Duplicate attempt_id must still refuse when no accepted entry exists
    // (so the check is not merely a consequence of duplicate acceptance).
    const rows = readBoxRows(runRoot);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    const failed = {
      attempt_id: "box-0000-a1",
      box_id: "box-0000",
      parent_box_id: null,
      attempt: 1,
      units: entry.units,
      output: { ref: "join/box-0000.attempt1.jsonl", sha256: "0".repeat(64) },
      status: "failed",
    };
    writeJson(runRoot, attemptsRef, [failed, { ...failed, output: { ...failed.output } }]);
    const dupId = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
    assert.match(dupId.summary, /duplicate attempt_id/);

    // Accepted entry for a box that is not a current join box.
    writeJson(runRoot, attemptsRef, [{ ...entry, attempt_id: "box-9999-a1", box_id: "box-9999" }]);
    const unknown = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
    assert.match(unknown.summary, /unknown accepted attempt box/);

    // A current join box whose history has no accepted attempt.
    writeJson(runRoot, attemptsRef, [failed]);
    const missing = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
    assert.match(missing.summary, /missing accepted attempt/);
  });

  it("R5 attempt structural validation stays strict", () => {
    const runRoot = materializeRun("envelope-attempts-structural");
    const attemptsRef = "join/attempts.json";
    const base = readJson(runRoot, RUN_MANIFEST).join_attempts[0];
    const cases = [
      { name: "missing parent_box_id", entry: { ...base, parent_box_id: undefined } },
      { name: "unknown status", entry: { ...base, status: "pending" } },
      { name: "attempt zero", entry: { ...base, attempt: 0 } },
      { name: "non-string unit", entry: { ...base, units: [42] } },
      { name: "empty attempt_id", entry: { ...base, attempt_id: "" } },
      { name: "non-object output", entry: { ...base, output: null } },
    ];
    for (const testCase of cases) {
      writeJson(runRoot, attemptsRef, [testCase.entry]);
      const verdict = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
      assert.match(verdict.summary, /malformed attempts entry/, testCase.name);
    }
  });

  it("R7 accepted/history coherence refusals keep unusable histories out", () => {
    const runRoot = materializeRun("envelope-attempts-coherence2");
    const attemptsRef = "join/attempts.json";
    const rows = readBoxRows(runRoot);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    const accepted = readJson(runRoot, RUN_MANIFEST).join_attempts[0];
    const failed = {
      ...accepted,
      attempt_id: "box-0000-a1",
      attempt: 1,
      output: { ref: "join/box-0000.attempt1.jsonl" },
      status: "failed",
    };
    const retryAccepted = { ...accepted, attempt_id: "box-0000-a2", attempt: 2 };
    const cases = [
      {
        name: "accepted units mismatch",
        entries: [failed, { ...retryAccepted, units: ["u9999"] }],
        reason: /accepted units mismatch/,
      },
      {
        name: "accepted output mismatch",
        entries: [failed, { ...retryAccepted, output: { ref: "join/box-0000.attempt1.jsonl" } }],
        reason: /accepted output mismatch/,
      },
      {
        name: "unknown parent box",
        entries: [{ ...failed, parent_box_id: "box-9999" }, retryAccepted],
        reason: /unknown parent box/,
      },
      {
        name: "attempt sequence mismatch",
        entries: [failed, { ...retryAccepted, attempt: 3 }],
        reason: /attempt sequence mismatch/,
      },
      {
        name: "out-of-order ordinals",
        entries: [retryAccepted, failed],
        reason: /attempt sequence mismatch/,
      },
    ];
    for (const testCase of cases) {
      writeJson(runRoot, attemptsRef, testCase.entries);
      const verdict = expectRefusal(runVerifier(envelopeArgs(runRoot, { attempts: attemptsRef }), { runRoot }));
      assert.match(verdict.summary, testCase.reason, testCase.name);
    }
  });

  it("R6 shared instructions are only shared when no box has its own file", () => {
    // Legitimate shared file: neither child has a per-box instructions file, so
    // the single candidate is the deliberately shared one for both boxes.
    const shared = materializeRun("envelope-instructions-shared");
    const { boxIds } = splitIntoTwoBoxes(shared, 23, ["box-0000-h1", "box-0000-h2"]);
    const sharedDoc = expectDocument(runVerifier(envelopeArgs(shared), { runRoot: shared }));
    for (const boxId of boxIds) {
      const box = sharedDoc.join_boxes.find((entry) => entry.box_id === boxId);
      assert.equal(box.instructions.ref, "join/box-0000.instructions.md", `${boxId} must reuse the shared instructions file`);
    }

    // Mixed case: only h1 owns an instructions file (the parent file is gone).
    // h2 must NOT silently borrow h1's file; the generator refuses instead of
    // misrecording evidence.
    const mixed = materializeRun("envelope-instructions-mixed");
    splitIntoTwoBoxes(mixed, 23, ["box-0000-h1", "box-0000-h2"]);
    copyFileSync(
      path.join(mixed, "join/box-0000.instructions.md"),
      path.join(mixed, "join/box-0000-h1.instructions.md"),
    );
    rmSync(path.join(mixed, "join/box-0000.instructions.md"));
    const refusal = expectRefusal(runVerifier(envelopeArgs(mixed), { runRoot: mixed }));
    assert.match(refusal.summary, /missing instructions/);
  });
});
