// RED-first contract tests for the `join` command of kernel/tools/verify.mjs —
// join-draft/1 (plan §3 J1–J12, plan §4 items 12–28). Authored BEFORE the J
// validators exist (P4a): with only the P2/P3 `join.not_implemented` stub in
// place every case below fails at that stub or a missing target check, and the
// intended failure mode encoded here becomes the regression gate.
//
//   node --test kernel/tools/verify.join.test.mjs
//   node --test "kernel/tools/*.test.mjs"
//
// Scope split: P4a implements J1–J7 and leaves explicit per-check failures for
// J8 `join.budget`, J9 `join.recovery`, J10 `join.merge`, J11 `join.p05` and
// J12 `join.candidates`. Every J8–J12 case therefore asserts the plan's exact
// failure detail (a name-only assertion would be fooled by the stub), and the
// full-pass cases stay red until P4b lands. J1–J7 cases assert the targeted
// check with its exact detail and are expected to be green after P4a.
//
// P4b implements J8–J12; the fixture cases that previously expected exit 1
// only because of the per-check stubs (unmodified seed, metadata-file witness,
// 160-codepoint/astral/NFD witnesses, monitoring-only output ceiling) now
// expect the full pass (exit 0), and the budget boundary fixture records the
// zero headroom its approved ceiling implies.
//
// Fixture synthesis (verify-testkit.mjs helpers) derives every variant in a
// per-test tmpdir from the committed seed; the committed seed is never edited.
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, rmSync } from "node:fs";
import path from "node:path";
import {
  BOX_0000, BOX_0000_ASSIGNMENT, CLAIMS_DRAFT, CLAIMS_LIST, JOIN_DRAFT,
  P05_CHECK, P05_EVIDENCE, RAW_WITNESSES_PATH, RUN_MANIFEST, UNITS_MANIFEST,
  addOpaqueMachineRow, appendPayloadLine, cleanupTempDirs, editBoxRow, editJson,
  findFailedCheck, makeMetadataFileUnit, materializeEmptyRun, materializeOpaqueRun,
  materializeRun, readBoxRows, readBytes, readJson, resealEnvelope, resealRun,
  resealUnitsBinding, runVerifier, setJoinAttempts, setRowUnlinked, snapshotTree,
  splitIntoTwoBoxes, writeAttemptOutput, writeBoxRows, writeBytes, writeJson,
  writeOperatorApproval, writeText,
} from "./verify-testkit.mjs";

after(cleanupTempDirs);

const JOIN_ROW_UNIT = "u0000";
const JOIN_ROW_CLAIM = "C21";
const BUDGET_TOTAL = 171492 + 6660 + 825; // unit_bytes + claims_list_bytes + instructions_bytes
const SEED_OUTPUT_BYTES = 51394;

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
  assert.match(v.summary, /^FAIL join: \d+ of \d+ checks failed$/, `failure summary\n${report(r)}`);
  const failed = findFailedCheck(v, check);
  assert.ok(failed, `missing failed check "${check}"\n${JSON.stringify(v.checks)}\n${report(r)}`);
  assert.equal(failed.detail, detail);
  return v;
}

function expectRefusal(r, check, detail) {
  const v = expectVerdict(r, 2);
  assert.match(v.summary, /^REFUSE (join|usage): /, `refusal summary\n${report(r)}`);
  const failed = findFailedCheck(v, check);
  assert.ok(failed, `missing failed check "${check}"\n${JSON.stringify(v.checks)}\n${report(r)}`);
  assert.equal(failed.detail, detail);
  return v;
}

/** Named check must exist and pass (exact detail optional). */
function expectCheckOk(verdict, name, detail) {
  const check = verdict.checks.find((c) => c.name === name);
  assert.ok(check, `missing check "${name}"\n${JSON.stringify(verdict.checks)}`);
  assert.equal(check.ok, true, `check ${name} must pass: ${check.detail}`);
  if (detail !== undefined) assert.equal(check.detail, detail);
  return check;
}

function joinRun(label) {
  const runRoot = materializeRun(label);
  const r = runVerifier(["join", "--run", runRoot], { runRoot });
  return { runRoot, r };
}

function opaqueJoinRun(label, options) {
  const fixture = materializeOpaqueRun(label, options);
  addOpaqueMachineRow(fixture.runRoot, fixture.unitId);
  return fixture;
}

function partialOpaqueJoinRun(label) {
  return opaqueJoinRun(label, {
    bodies: [Buffer.alloc(7000, 0x51)],
    sides: ["added"],
    pairId: null,
    states: ["unpaired"],
    coverage: { status: "partial", machine_occurrences: 1, skips: ["skip-0000"] },
    skips: [{ skip_id: "skip-0000", reason: "unpaired", occurrence_ids: ["occ-0000"] }],
  });
}

function twoSkipPartialOpaqueJoinRun(label) {
  return opaqueJoinRun(label, {
    bodies: [Buffer.alloc(7000, 0x51), Buffer.alloc(7000, 0x52)],
    sides: ["added", "removed"],
    pairId: null,
    states: ["unpaired", "unpaired"],
    coverage: { status: "partial", machine_occurrences: 2, skips: ["skip-0000", "skip-0001"] },
    skips: [
      { skip_id: "skip-0000", reason: "unpaired", occurrence_ids: ["occ-0000"] },
      { skip_id: "skip-0001", reason: "unpaired", occurrence_ids: ["occ-0001"] },
    ],
  });
}

/** Mutate exactly one link's witness via editBoxRow + full reseal. */
function mutateWitness(runRoot, unitId, claimId, fn) {
  editBoxRow(runRoot, "box-0000", unitId, (row) => {
    const link = row.links.find((l) => l.claim_id === claimId);
    if (!link) throw new Error(`no link ${unitId}/${claimId}`);
    fn(link);
  });
  resealRun(runRoot);
}

function setWitness(runRoot, unitId, claimId, witness) {
  mutateWitness(runRoot, unitId, claimId, (link) => { link.witness = witness; });
}

function mutateAssignment(runRoot, fn) {
  editJson(runRoot, BOX_0000_ASSIGNMENT, fn);
  resealEnvelope(runRoot);
}

function mutateJoinDraft(runRoot, fn) {
  editJson(runRoot, JOIN_DRAFT, fn);
  resealEnvelope(runRoot);
}

function mutateP05Check(runRoot, fn) {
  editJson(runRoot, P05_CHECK, fn);
  resealEnvelope(runRoot);
}

function mutateP05Evidence(runRoot, fn) {
  editJson(runRoot, P05_EVIDENCE, fn);
  resealEnvelope(runRoot);
}

function mutatePilot(runRoot, fn) {
  editJson(runRoot, RUN_MANIFEST, (env) => fn(env.pilot, env));
}

/** Rewrite + reseal the claims draft (join-prerequisite schema regressions). */
function mutateClaimsDraft(runRoot, fn) {
  editJson(runRoot, CLAIMS_DRAFT, fn);
  resealEnvelope(runRoot);
}

/**
 * Cap the approved pilot input ceiling at `boxId`'s exact recomputed input so
 * its following unit cannot fit (greedy packing satisfied) while every
 * assignment/p05 ceiling stays coherent with the pilot.
 */
function capCeilingToBoxInput(runRoot, boxId) {
  const approved = readJson(runRoot, `join/${boxId}.p05-evidence.json`).budget.box_input_bytes;
  editJson(runRoot, RUN_MANIFEST, (env) => { env.pilot.input_ceiling_bytes = approved; });
  const env = readJson(runRoot, RUN_MANIFEST);
  for (const entry of env.join_boxes) {
    editJson(runRoot, entry.assignment.ref, (a) => { a.input_ceiling_bytes = approved; });
    editJson(runRoot, entry.p05_evidence.ref, (p05) => {
      p05.budget.input_ceiling_bytes = approved;
      p05.budget.headroom_bytes = approved - p05.budget.box_input_bytes;
    });
  }
  resealEnvelope(runRoot);
  return approved;
}

/** Rewrite the box JSONL and (by default) the join-draft.units mirror, then reseal. */
function rewriteBoxRows(runRoot, rows, { mirror = true } = {}) {
  writeBoxRows(runRoot, BOX_0000, rows);
  if (mirror) {
    editJson(runRoot, JOIN_DRAFT, (join) => { join.units = structuredClone(rows); });
  }
  resealRun(runRoot);
}

describe("join pass and J1-J7 baseline (plan §4 items 12–13)", () => {
  it("pass: exit 0, schema join-draft/1, every check true (RED until P4b)", () => {
    const { r } = joinRun("join-pass");
    const v = expectVerdict(r, 0);
    assert.equal(v.schema, "join-draft/1");
    assert.equal(v.tool_version, "1.0.0");
    assert.match(v.summary, /^PASS join: \d+ checks$/);
    for (const check of v.checks) assert.equal(check.ok, true, `check ${check.name} must pass: ${check.detail}`);
  });

  it("J1-J7 checks all pass on the migrated seed (full pass after P4b)", () => {
    const { r } = joinRun("join-j1-j7-green");
    const v = expectVerdict(r, 0);
    for (const name of [
      "identity", "join.identity", "join.assignments", "join.rows",
      "join.order", "join.pairs", "join.witness", "join.claim_list",
    ]) {
      expectCheckOk(v, name);
    }
  });

  it("join is read-only (run root byte-identical across runs)", () => {
    const runRoot = materializeRun("join-no-writes");
    const before = snapshotTree(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectVerdict(r, 0); // full pass; read-only still holds
    assert.deepEqual(snapshotTree(runRoot), before, "run root must be byte-identical after join verify");
  });
});

describe("join prerequisites — claims+units fatal (P3 open question 2)", () => {
  it("corrupted claims draft makes join fail at the prerequisite, never optional", () => {
    const runRoot = materializeRun("join-prereq-claims");
    writeBytes(runRoot, CLAIMS_DRAFT, Buffer.from("{"));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.prerequisites", "prerequisite failed: claims");
  });

  it("missing unit payload makes join fail at the prerequisite", () => {
    const runRoot = materializeRun("join-prereq-units");
    rmSync(path.join(runRoot, "units/units2/u0000.txt"));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.prerequisites", "prerequisite failed: units");
  });

  it("F2: unknown claims prerequisite schema refuses join with exit 2 naming it", () => {
    const runRoot = materializeRun("join-prereq-claims-unknown");
    mutateClaimsDraft(runRoot, (claims) => { claims.schema_version = "claims-draft/999"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectRefusal(r, "join.prerequisites", 'prerequisite refused: claims: unsupported schema_version: "claims-draft/999"');
  });

  it("F2: wrong-kind claims prerequisite schema refuses join with exit 2", () => {
    const runRoot = materializeRun("join-prereq-claims-wrong-kind");
    mutateClaimsDraft(runRoot, (claims) => { claims.schema_version = "code-units-sim/2"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectRefusal(r, "join.prerequisites", 'prerequisite refused: claims: wrong schema kind: "code-units-sim/2" for claims');
  });

  it("F2: unknown units prerequisite schema refuses join with exit 2 naming it", () => {
    const runRoot = materializeRun("join-prereq-units-unknown");
    editJson(runRoot, UNITS_MANIFEST, (manifest) => { manifest.schema_version = "code-units-sim/999"; });
    resealEnvelope(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectRefusal(r, "join.prerequisites", 'prerequisite refused: units: unsupported schema_version: "code-units-sim/999"');
  });
});

describe("join support-artifact schema dispatch (F3)", () => {
  const cases = [
    ["assignment", BOX_0000_ASSIGNMENT],
    ["p05-check", P05_CHECK],
    ["p05-evidence", P05_EVIDENCE],
  ];

  it("unknown schema_version refuses (exit 2) for assignment/p05-check/p05-evidence", () => {
    for (const [label, ref] of cases) {
      const runRoot = materializeRun(`join-support-unknown-${label}`);
      editJson(runRoot, ref, (obj) => { obj.schema_version = `${label}/999`; });
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectRefusal(r, "schema", `unsupported schema_version: "${label}/999"`);
    }
  });

  it("known wrong-family support schema refuses (exit 2)", () => {
    const runRoot = materializeRun("join-support-wrong-family");
    editJson(runRoot, P05_EVIDENCE, (p05) => { p05.schema_version = "claims-draft/3"; });
    resealEnvelope(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectRefusal(r, "artifact.discovery", 'wrong schema kind: "claims-draft/3" for join');
  });

  it("registered schemas on unversioned support records refuse (exit 2, F15)", () => {
    for (const [label, ref, sv] of [
      ["assignment-join-draft", BOX_0000_ASSIGNMENT, "join-draft/1"],
      ["p05-check-join-draft", P05_CHECK, "join-draft/1"],
      ["p05-check-envelope", P05_CHECK, "run-verification/1"],
      ["p05-evidence-claims-draft", P05_EVIDENCE, "claims-draft/3"],
      ["p05-evidence-units", P05_EVIDENCE, "code-units-sim/2"],
    ]) {
      const runRoot = materializeRun(`join-support-registered-${label}`);
      editJson(runRoot, ref, (obj) => { obj.schema_version = sv; });
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectRefusal(r, "artifact.discovery", `wrong schema kind: "${sv}" for join`);
    }
  });

  it("object-form claims-list schema_version dispatches before the array shape check (F15)", () => {
    for (const [label, sv, check, detail] of [
      ["unknown", "claims-list/999", "schema", 'unsupported schema_version: "claims-list/999"'],
      ["registered", "join-draft/1", "artifact.discovery", 'wrong schema kind: "join-draft/1" for join'],
    ]) {
      const runRoot = materializeRun(`join-claims-list-${label}`);
      writeJson(runRoot, CLAIMS_LIST, { schema_version: sv });
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectRefusal(r, check, detail);
    }
  });
});

describe("P10 regressions — falsy join/support top levels fail shape (F14)", () => {
  const SHAPE_OBJECT = "invalid field: / expected object";
  const SHAPE_ARRAY = "invalid field: / expected array";

  it("join draft null/0/false/empty-string: exit 1 with the object shape check", () => {
    for (const [label, text] of [["null", "null"], ["zero", "0"], ["false", "false"], ["empty-string", '""']]) {
      const runRoot = materializeRun(`p10-join-${label}`);
      writeText(runRoot, JOIN_DRAFT, text);
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "shape", SHAPE_OBJECT);
    }
  });

  it("assignment/p05-check/p05-evidence null: exit 1 with the object shape check", () => {
    for (const [label, ref] of [["assignment", BOX_0000_ASSIGNMENT], ["p05-check", P05_CHECK], ["p05-evidence", P05_EVIDENCE]]) {
      const runRoot = materializeRun(`p10-support-null-${label}`);
      writeText(runRoot, ref, "null");
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "shape", SHAPE_OBJECT);
    }
  });

  it("claims-list null/0/false/empty-string/object: exit 1 with the array shape check", () => {
    for (const [label, text] of [["null", "null"], ["zero", "0"], ["false", "false"], ["empty-string", '""'], ["object", "{}"]]) {
      const runRoot = materializeRun(`p10-claims-list-${label}`);
      writeText(runRoot, CLAIMS_LIST, text);
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "shape", SHAPE_ARRAY);
    }
  });
});

describe("join.identity and artifact pin binding (J1)", () => {
  it("join draft state identity is compared against envelope+capture", () => {
    const runRoot = materializeRun("join-identity");
    mutateJoinDraft(runRoot, (join) => { join.subject_oid = "0".repeat(40); });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "identity", "identity mismatch: /subject_oid");
  });

  it("units_manifest ref/sha/schema/unit_count binding mismatch fails join.identity", () => {
    const cases = [
      ["ref", (um) => { um.ref = "units/units2/other.json"; }],
      ["sha256", (um) => { um.sha256 = "0".repeat(64); }],
      ["schema_version", (um) => { um.schema_version = "code-units-sim/9"; }],
      ["unit_count", (um) => { um.unit_count = 45; }],
    ];
    for (const [field, mutate] of cases) {
      const runRoot = materializeRun(`join-binding-${field}`);
      mutateJoinDraft(runRoot, (join) => mutate(join.units_manifest));
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.identity", "join manifest binding mismatch");
    }
  });

  it("box output sha pin mismatch is reported before parsing", () => {
    const runRoot = materializeRun("join-box-pin");
    writeBytes(runRoot, BOX_0000, Buffer.concat([readBytes(runRoot, BOX_0000), Buffer.from("\n")]));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.sha256", `sha256 mismatch: "${BOX_0000}"`);
  });

  it("envelope join_boxes assignment pin mismatch is reported before parsing", () => {
    const runRoot = materializeRun("join-assignment-pin");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.join_boxes[0].assignment.sha256 = "0".repeat(64); });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.sha256", `sha256 mismatch: "${BOX_0000_ASSIGNMENT}"`);
  });

  it("join draft sha pin mismatch is reported", () => {
    const runRoot = materializeRun("join-draft-pin");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.join_draft.sha256 = "0".repeat(64); });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.sha256", `sha256 mismatch: "${JOIN_DRAFT}"`);
  });

  it("attempt output sha pin mismatch is reported", () => {
    const runRoot = materializeRun("join-attempt-pin");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.join_attempts[0].output.sha256 = "0".repeat(64); });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.sha256", `sha256 mismatch: "${BOX_0000}"`);
  });
});

describe("join.assignments — bijection, binding, sweep (J2)", () => {
  it("missing assignment artifact stops the join", () => {
    const runRoot = materializeRun("join-missing-assignment");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.join_boxes[0].assignment.ref = "join/missing.assignment.json"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.read", "cannot read artifact: join/missing.assignment.json");
  });

  it("assignment output_path that is not the boxed path fails binding", () => {
    const runRoot = materializeRun("join-output-path");
    mutateAssignment(runRoot, (a) => { a.output_path = "join/other.jsonl"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", 'box assignment binding mismatch: "box-0000"');
  });

  it("assignment manifest/units_dir/claims_list_path drift fails binding", () => {
    const cases = [
      ["manifest_ref", (a) => { a.manifest_ref = "units/units2/other.json"; }],
      ["manifest_sha256", (a) => { a.manifest_sha256 = "0".repeat(64); }],
      ["units_dir", (a) => { a.units_dir = "units/elsewhere"; }],
      ["claims_list_path", (a) => { a.claims_list_path = "join/other-list.json"; }],
    ];
    for (const [field, mutate] of cases) {
      const runRoot = materializeRun(`join-binding-assignment-${field}`);
      mutateAssignment(runRoot, mutate);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.assignments", 'box assignment binding mismatch: "box-0000"');
    }
  });

  it("assignment unit_count that disagrees with units fails (exit 1)", () => {
    const runRoot = materializeRun("join-unit-count");
    mutateAssignment(runRoot, (a) => { a.unit_count = 45; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", 'assignment unit count mismatch: "box-0000"');
  });

  it("assignment that omits a manifest unit fails the sweep", () => {
    const runRoot = materializeRun("join-omitted-unit");
    mutateAssignment(runRoot, (a) => {
      a.units = a.units.filter((id) => id !== "u0005");
      a.unit_count = a.units.length;
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", "assigned unit sweep mismatch");
  });

  it("assignment with an unknown unit fails", () => {
    const runRoot = materializeRun("join-unknown-unit");
    mutateAssignment(runRoot, (a) => {
      a.units = [...a.units, "u9999"];
      a.unit_count = a.units.length;
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", 'assigned unit not found: "u9999"');
  });

  it("assignment with a duplicated unit fails", () => {
    const runRoot = materializeRun("join-duplicate-unit");
    mutateAssignment(runRoot, (a) => {
      a.units = [...a.units, "u0000"];
      a.unit_count = a.units.length;
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", 'assigned unit duplicate: "u0000"');
  });

  it("reversed assignment order fails the sweep", () => {
    const runRoot = materializeRun("join-reversed-assignment");
    mutateAssignment(runRoot, (a) => { a.units = [...a.units].reverse(); });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", "assigned unit sweep mismatch");
  });

  it("a coherent two-box split passes join.assignments/order/rows", () => {
    const runRoot = materializeRun("join-two-box-pass");
    splitIntoTwoBoxes(runRoot, 23, ["box-0000", "box-0001"]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 1);
    expectCheckOk(v, "join.assignments");
    expectCheckOk(v, "join.rows");
    expectCheckOk(v, "join.order");
  });

  it("a unit duplicated across boxes fails the global sweep", () => {
    const runRoot = materializeRun("join-cross-box-duplicate");
    splitIntoTwoBoxes(runRoot, 23, ["box-0000", "box-0001"]);
    const right = readJson(runRoot, "join/box-0001.assignment.json");
    editJson(runRoot, "join/box-0001.assignment.json", (a) => {
      a.units = ["u0000", ...a.units];
      a.unit_count = a.units.length;
    });
    assert.deepEqual(right.units[0], "u0023", "test premise: right box starts at u0023");
    resealEnvelope(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", "assigned unit sweep mismatch");
  });
});

describe("join.rows — strict row/link shapes and enums (J3)", () => {
  it("extra outer row field fails", () => {
    const runRoot = materializeRun("join-row-extra");
    editBoxRow(runRoot, "box-0000", JOIN_ROW_UNIT, (row) => { row.extra = 1; });
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", "unexpected field: /rows/box-0000/0/extra");
  });

  it("links that is not an array fails (missing links cannot become [])", () => {
    for (const [label, mutate] of [
      ["object", (row) => { row.links = {}; }],
      ["missing", (row) => { delete row.links; }],
    ]) {
      const runRoot = materializeRun(`join-links-${label}`);
      editBoxRow(runRoot, "box-0000", JOIN_ROW_UNIT, mutate);
      resealRun(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.rows", "invalid field: /rows/box-0000/0/links expected array");
    }
  });

  it("unresolved that is neither null nor a nonempty string fails", () => {
    for (const [label, value] of [["number", 5], ["empty", ""], ["missing", undefined]]) {
      const runRoot = materializeRun(`join-unresolved-${label}`);
      editBoxRow(runRoot, "box-0000", JOIN_ROW_UNIT, (row) => {
        if (value === undefined) delete row.unresolved; else row.unresolved = value;
      });
      resealRun(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.rows", "invalid field: /rows/box-0000/0/unresolved expected null or nonempty string");
    }
  });

  it("empty unit_id fails", () => {
    const runRoot = materializeRun("join-empty-unit-id");
    editBoxRow(runRoot, "box-0000", JOIN_ROW_UNIT, (row) => { row.unit_id = ""; });
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", "invalid field: /rows/box-0000/0/unit_id expected nonempty string");
  });

  it("invalid closeness enum fails", () => {
    const runRoot = materializeRun("join-bad-closeness");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.closeness = "extreme"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", 'invalid closeness: "box-0000":"u0000":"extreme"');
  });

  it("invalid role_hint enum (slash drift removes/changes) fails", () => {
    const runRoot = materializeRun("join-bad-role");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.role_hint = "removes/changes"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", 'invalid role_hint: "box-0000":"u0000":"removes/changes"');
  });

  it("non-string closeness/role_hint fails as a type error", () => {
    for (const [field, value] of [["closeness", 3], ["role_hint", null]]) {
      const runRoot = materializeRun(`join-bad-enum-type-${field}`);
      mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link[field] = value; });
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.rows", `invalid field: /rows/box-0000/0/links/0/${field} expected string`);
    }
  });

  it("link with an extra field fails", () => {
    const runRoot = materializeRun("join-link-extra");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.confidence = 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", "unexpected field: /rows/box-0000/0/links/0/confidence");
  });

  it("link with a non-string witness fails as a type error (empty stays a J6 failure)", () => {
    const runRoot = materializeRun("join-witness-type");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.witness = 42; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", "invalid field: /rows/box-0000/0/links/0/witness expected string");
  });

  it("link with a non-string claim_id fails", () => {
    const runRoot = materializeRun("join-claim-id-type");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.claim_id = 42; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.rows", "invalid field: /rows/box-0000/0/links/0/claim_id expected nonempty string");
  });

  it("a row with links=[] (zero-link row) is valid", () => {
    const runRoot = materializeRun("join-zero-link-row");
    editBoxRow(runRoot, "box-0000", JOIN_ROW_UNIT, (row) => { row.links = []; });
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 1);
    expectCheckOk(v, "join.rows");
    expectCheckOk(v, "join.order");
    expectCheckOk(v, "join.witness");
  });
});

describe("join.order — exact assignment sweep (J4)", () => {
  it("missing final box row fails even though p05/merge still record success", () => {
    const runRoot = materializeRun("join-missing-row");
    const rows = readBoxRows(runRoot).slice(0, -1);
    rewriteBoxRows(runRoot, rows);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });

  it("duplicated row fails", () => {
    const runRoot = materializeRun("join-duplicate-row");
    const rows = readBoxRows(runRoot);
    rewriteBoxRows(runRoot, [...rows, structuredClone(rows[0])]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });

  it("reordered rows fail", () => {
    const runRoot = materializeRun("join-row-order");
    const rows = readBoxRows(runRoot);
    const swapped = [...rows];
    [swapped[0], swapped[1]] = [swapped[1], swapped[0]];
    rewriteBoxRows(runRoot, swapped);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });

  it("an extra row fails", () => {
    const runRoot = materializeRun("join-extra-row");
    const rows = readBoxRows(runRoot);
    rewriteBoxRows(runRoot, [...rows, { unit_id: "u9999", links: [], unresolved: null }]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });

  it("truncated row set fails", () => {
    const runRoot = materializeRun("join-truncated-rows");
    rewriteBoxRows(runRoot, readBoxRows(runRoot).slice(0, 44));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });

  it("a reordered assignment with reordered rows still fails (output cannot define its own set)", () => {
    const runRoot = materializeRun("join-reversed-both");
    const rows = readBoxRows(runRoot);
    rewriteBoxRows(runRoot, [...rows].reverse());
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.order", 'box unit sweep/order mismatch: "box-0000"');
  });
});

describe("join.pairs — claim resolution and pair uniqueness (J5)", () => {
  it("unknown claim id fails", () => {
    const runRoot = materializeRun("join-unknown-claim");
    mutateWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, (link) => { link.claim_id = "C99"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.pairs", 'join claim id not found: "u0000" -> "C99"');
  });

  it("duplicate (unit_id,claim_id) pair fails", () => {
    const runRoot = materializeRun("join-duplicate-pair");
    editBoxRow(runRoot, "box-0000", "u0002", (row) => {
      const first = row.links.find((l) => l.claim_id === "C31");
      row.links.push(structuredClone(first));
    });
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.pairs", 'duplicate unit/claim pair: "u0002" -> "C31"');
  });

  it("the same claim id linked from different units stays valid", () => {
    const { r } = joinRun("join-pairs-valid");
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.pairs");
  });
});

describe("join.witness — nonempty/single-line/160/byte-substring/marker (J6)", () => {
  it("raw S28 markerless witness is rejected (rejection evidence kept)", () => {
    const raw = JSON.parse(readFileSync(RAW_WITNESSES_PATH, "utf8"));
    const sample = raw.cases.find((c) => c.unit_id === "u0000" && c.claim_id === "C21");
    assert.ok(sample, "raw witness sample u0000 -> C21 must exist");
    const runRoot = materializeRun("join-raw-witness");
    setWitness(runRoot, sample.unit_id, sample.claim_id, sample.witness);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", `witness diff marker missing: "${sample.unit_id}" -> "${sample.claim_id}"`);
  });

  it("witness that is not a byte substring fails", () => {
    const runRoot = materializeRun("join-witness-absent");
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, "+fixture-absent-witness-xyz");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", 'witness not in unit: "u0000" -> "C21"');
  });

  it("empty witness fails", () => {
    const runRoot = materializeRun("join-witness-empty");
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, "");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", 'empty witness: "u0000" -> "C21"');
  });

  it("witness containing LF, CR or CRLF fails as multiline", () => {
    for (const [label, value] of [["lf", "+line1\n+line2"], ["cr", "+line1\r+line2"], ["crlf", "+line1\r\n+line2"]]) {
      const runRoot = materializeRun(`join-witness-multiline-${label}`);
      setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, value);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.witness", 'multiline witness: "u0000" -> "C21"');
    }
  });

  it("mid-line witness (plus never counts) fails the marker check", () => {
    const runRoot = materializeRun("join-witness-midline");
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, "pycache");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", 'witness diff marker missing: "u0000" -> "C21"');
  });

  it("metadata line start is not a valid marker for a block unit", () => {
    const runRoot = materializeRun("join-witness-metadata-block");
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, "index a47d77e..57227e7");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", 'witness diff marker missing: "u0000" -> "C21"');
  });

  it("metadata line start is a valid marker for a genuine file unit", () => {
    const runRoot = materializeRun("join-witness-metadata-file");
    const witness = makeMetadataFileUnit(runRoot, JOIN_ROW_UNIT);
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, witness);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.witness");
  });

  it("161 codepoints fail, exactly 160 passes", () => {
    const runRoot = materializeRun("join-witness-160");
    appendPayloadLine(runRoot, JOIN_ROW_UNIT, `+${"x".repeat(200)}`);
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, `+${"x".repeat(160)}`); // 161 codepoints
    const tooLong = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(tooLong, "join.witness", 'witness exceeds 160 characters: "u0000" -> "C21"');
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, `+${"x".repeat(159)}`); // exactly 160
    const ok = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(ok, 0);
    expectCheckOk(v, "join.witness");
  });

  it("astral characters count as one codepoint (160 passes, 161 fails; bytes are irrelevant)", () => {
    const runRoot = materializeRun("join-witness-astral");
    appendPayloadLine(runRoot, JOIN_ROW_UNIT, `+${"😀".repeat(200)}`);
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, `+${"😀".repeat(159)}`); // 160 codepoints, 321 UTF-16 units, 641 bytes
    const ok = runVerifier(["join", "--run", runRoot], { runRoot });
    expectCheckOk(expectVerdict(ok, 0), "join.witness");
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, `+${"😀".repeat(160)}`); // 161 codepoints
    const tooLong = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(tooLong, "join.witness", 'witness exceeds 160 characters: "u0000" -> "C21"');
  });

  it("no Unicode normalization is applied to witnesses", () => {
    const nfd = `+cafe${String.fromCharCode(0x301)}`; // "cafe" + combining acute
    const nfc = "+caf\u00e9"; // precomposed é
    const runRoot = materializeRun("join-witness-normalization");
    appendPayloadLine(runRoot, JOIN_ROW_UNIT, nfd); // payload carries NFD
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, nfc); // NFC witness must not match
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.witness", 'witness not in unit: "u0000" -> "C21"');
    appendPayloadLine(runRoot, JOIN_ROW_UNIT, nfc); // payload now carries both forms
    setWitness(runRoot, JOIN_ROW_UNIT, JOIN_ROW_CLAIM, nfd); // NFD witness matches the NFD bytes
    const ok = runVerifier(["join", "--run", runRoot], { runRoot });
    expectCheckOk(expectVerdict(ok, 0), "join.witness");
  });

  it("all seed witnesses pass the J6 rules", () => {
    const { r } = joinRun("join-witness-seed");
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.witness");
  });
});

describe("join.claim_list — exact claims projection + byte length (J7)", () => {
  it("shortened claims list fails even if box/p05 stay consistent", () => {
    const runRoot = materializeRun("join-claims-short");
    editJson(runRoot, CLAIMS_LIST, (list) => { list.pop(); });
    resealEnvelope(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.claim_list", 'claims list mismatch: "box-0000"');
  });

  it("changed statement or extra field fails the projection", () => {
    for (const [label, mutate] of [
      ["statement", (list) => { list[0].statement = "changed statement"; }],
      ["extra", (list) => { list[0].extra = 1; }],
    ]) {
      const runRoot = materializeRun(`join-claims-${label}`);
      editJson(runRoot, CLAIMS_LIST, mutate);
      resealEnvelope(runRoot);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.claim_list", 'claims list mismatch: "box-0000"');
    }
  });

  it("claims_list_bytes that disagrees with the actual bytes fails", () => {
    const runRoot = materializeRun("join-claims-bytes");
    mutateAssignment(runRoot, (a) => { a.claims_list_bytes += 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.claim_list", 'claims_list_bytes mismatch: "box-0000"');
  });
});

describe("corrupt JSONL forms leave stale merge/p05 unable to pass", () => {
  it("fenced first line is invalid JSONL", () => {
    const runRoot = materializeRun("join-jsonl-fence");
    const lines = readBytes(runRoot, BOX_0000).toString("utf8").split("\n");
    writeText(runRoot, BOX_0000, ["```json", ...lines].join("\n"));
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectFailure(r, "artifact.jsonl", `invalid JSONL: "${BOX_0000}":1`);
    assert.equal(v.ok, false, "a corrupt box can never yield a passing join");
  });

  it("blank interior line is invalid JSONL", () => {
    const runRoot = materializeRun("join-jsonl-blank");
    const lines = readBytes(runRoot, BOX_0000).toString("utf8").split("\n");
    lines[2] = "";
    writeText(runRoot, BOX_0000, lines.join("\n"));
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.jsonl", `invalid JSONL: "${BOX_0000}":3`);
  });

  it("truncated tail is invalid JSONL", () => {
    const runRoot = materializeRun("join-jsonl-truncated");
    const buf = readBytes(runRoot, BOX_0000);
    writeBytes(runRoot, BOX_0000, buf.subarray(0, buf.length - 12));
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.jsonl", `invalid JSONL: "${BOX_0000}":46`);
  });

  it("F9: BOM-prefixed box JSONL is invalid JSONL (never silently stripped)", () => {
    const runRoot = materializeRun("join-jsonl-bom");
    const buf = readBytes(runRoot, BOX_0000);
    writeBytes(runRoot, BOX_0000, Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), buf]));
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "artifact.jsonl", `invalid JSONL: "${BOX_0000}":1`);
  });
});

describe("join.budget — input/output ceilings (J8, RED until P4b)", () => {
  it("pilot ceiling one below the recomputed total fails input budget exceeded", () => {
    const runRoot = materializeRun("join-budget-low-ceiling");
    mutatePilot(runRoot, (pilot) => { pilot.input_ceiling_bytes = BUDGET_TOTAL - 1; });
    mutateAssignment(runRoot, (a) => { a.input_ceiling_bytes = BUDGET_TOTAL - 1; });
    mutateP05Evidence(runRoot, (p05) => { p05.budget.input_ceiling_bytes = BUDGET_TOTAL - 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'input budget exceeded: "box-0000"');
  });

  it("raising the assignment ceiling alone fails pilot ceiling mismatch", () => {
    const runRoot = materializeRun("join-budget-assignment-raised");
    mutateAssignment(runRoot, (a) => { a.input_ceiling_bytes = 200000; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'pilot ceiling mismatch: "box-0000"');
  });

  it("falsified p05 byte metrics fail budget metric mismatch", () => {
    const runRoot = materializeRun("join-budget-falsified-metrics");
    mutateP05Evidence(runRoot, (p05) => { p05.budget.unit_bytes = 171491; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'budget metric mismatch: "box-0000":unit_bytes');
  });

  it("ceiling exactly equal to the recomputed total passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-budget-boundary-pass");
    mutatePilot(runRoot, (pilot) => { pilot.input_ceiling_bytes = BUDGET_TOTAL; });
    mutateAssignment(runRoot, (a) => { a.input_ceiling_bytes = BUDGET_TOTAL; });
    mutateP05Evidence(runRoot, (p05) => {
      p05.budget.input_ceiling_bytes = BUDGET_TOTAL;
      p05.budget.headroom_bytes = 0;
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectVerdict(r, 0);
  });

  it("output bytes that disagree with the recorded output fail", () => {
    const runRoot = materializeRun("join-budget-output-bytes");
    mutateP05Evidence(runRoot, (p05) => { p05.budget.output_bytes += 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'budget metric mismatch: "box-0000":output_bytes');
  });

  it("a declared output ceiling one below the output fails output budget exceeded", () => {
    const runRoot = materializeRun("join-budget-output-cap");
    mutatePilot(runRoot, (pilot) => { pilot.output_ceiling_bytes = SEED_OUTPUT_BYTES - 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'output budget exceeded: "box-0000"');
  });

  it("null output ceiling stays monitoring-only with the measured bytes detail (RED until P4b)", () => {
    const { r } = joinRun("join-budget-monitoring");
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.budget", `output_bytes=${SEED_OUTPUT_BYTES}; output ceiling not declared (monitoring only)`);
  });
});

// P12 fail-closed pilot fields (post-push review, fix 1): pilot.operator_ref is
// a required nonempty string, and pilot.output_ceiling_bytes must be exactly
// null or a nonnegative integer. Wrong types used to silently disable output
// enforcement (non-number) or go unread (operator_ref); both now fail closed.
describe("join.budget — fail-closed pilot fields (P12, fix 1)", () => {
  for (const [label, value] of [
    ["string", "1"], ["boolean", true], ["array", []], ["object", {}],
    ["negative", -1], ["fractional", 1.5], ["absent", undefined],
  ]) {
    it(`output_ceiling_bytes ${label} fails pilot output ceiling invalid (exit 1)`, () => {
      const runRoot = materializeRun(`p12-ceiling-${label}`);
      editJson(runRoot, RUN_MANIFEST, (env) => {
        if (value === undefined) delete env.pilot.output_ceiling_bytes;
        else env.pilot.output_ceiling_bytes = value;
      });
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.budget", "pilot output ceiling invalid");
    });
  }

  it("output_ceiling_bytes null passes monitoring-only with the measured bytes", () => {
    const { r } = joinRun("p12-ceiling-null");
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.budget", `output_bytes=${SEED_OUTPUT_BYTES}; output ceiling not declared (monitoring only)`);
  });

  it("output_ceiling_bytes equal to the measured output passes with the declared ceiling", () => {
    const runRoot = materializeRun("p12-ceiling-equal");
    mutatePilot(runRoot, (pilot) => { pilot.output_ceiling_bytes = SEED_OUTPUT_BYTES; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.budget", `output_bytes=${SEED_OUTPUT_BYTES}; output ceiling=${SEED_OUTPUT_BYTES}`);
  });

  it("output_ceiling_bytes above the measured output passes with the declared ceiling", () => {
    const runRoot = materializeRun("p12-ceiling-above");
    mutatePilot(runRoot, (pilot) => { pilot.output_ceiling_bytes = SEED_OUTPUT_BYTES + 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.budget", `output_bytes=${SEED_OUTPUT_BYTES}; output ceiling=${SEED_OUTPUT_BYTES + 1}`);
  });

  it("output_ceiling_bytes one below the measured output fails output budget exceeded", () => {
    const runRoot = materializeRun("p12-ceiling-below");
    mutatePilot(runRoot, (pilot) => { pilot.output_ceiling_bytes = SEED_OUTPUT_BYTES - 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.budget", 'output budget exceeded: "box-0000"');
  });

  for (const [label, value] of [["absent", undefined], ["empty", ""], ["numeric", 42]]) {
    it(`operator_ref ${label} fails pilot operator_ref missing (exit 1)`, () => {
      const runRoot = materializeRun(`p12-operator-${label}`);
      editJson(runRoot, RUN_MANIFEST, (env) => {
        if (value === undefined) delete env.pilot.operator_ref;
        else env.pilot.operator_ref = value;
      });
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.budget", "pilot operator_ref missing");
    });
  }
});

describe("join.recovery — structured retry/split history (J9, RED until P4b)", () => {
  const allUnitIds = (runRoot) => readBoxRows(runRoot).map((r) => r.unit_id);

  /** Seed with structured attempt history; output files are caller-created. */
  function retryAccepted(runRoot) {
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: BOX_0000, status: "accepted" },
    ]);
  }

  it("first attempt failed, retry accepted with the same units passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-retry-accepted");
    retryAccepted(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectVerdict(r, 0);
  });

  it("exhausted retry split into ordered halves passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-halves-accepted");
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
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectVerdict(r, 0);
  });

  it("F5: non-floor 45/1 split of a 46-unit parent fails resplit halves mismatch", () => {
    const runRoot = materializeRun("join-nonfloor-split");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 45, ["box-0000-h1", "box-0000-h2"]);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    writeAttemptOutput(runRoot, "join/box-0000.attempt2.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: "join/box-0000.attempt2.jsonl", status: "failed" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
      { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'resplit halves mismatch: "box-0000"');
  });

  it("a third retry fails retry limit exceeded", () => {
    const runRoot = materializeRun("join-third-retry");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    for (const n of [1, 2, 3]) writeAttemptOutput(runRoot, `join/box-0000.attempt${n}.jsonl`, rows);
    setJoinAttempts(runRoot, [1, 2, 3].map((n) => ({
      attemptId: `box-0000-a${n}`, boxId: "box-0000", attempt: n, units: ids,
      outputRef: `join/box-0000.attempt${n}.jsonl`, status: "failed",
    })));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'retry limit exceeded: "box-0000"');
  });

  it("splitting before the retry attempt fails retry policy mismatch", () => {
    const runRoot = materializeRun("join-split-before-retry");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
      { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", "retry policy mismatch");
  });

  it("a dropped half fails resplit halves mismatch", () => {
    const runRoot = materializeRun("join-dropped-half");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    writeAttemptOutput(runRoot, "join/box-0000.attempt2.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: "join/box-0000.attempt2.jsonl", status: "failed" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'resplit halves mismatch: "box-0000"');
  });

  it("wrong half order fails resplit halves mismatch", () => {
    const runRoot = materializeRun("join-wrong-half-order");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    writeAttemptOutput(runRoot, "join/box-0000.attempt2.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: "join/box-0000.attempt2.jsonl", status: "failed" },
      { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.jsonl", status: "accepted" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'resplit halves mismatch: "box-0000"');
  });

  it("a stale accepted parent attempt fails", () => {
    const runRoot = materializeRun("join-stale-parent");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
    writeAttemptOutput(runRoot, "join/box-0000.parent.jsonl", rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.parent.jsonl", status: "accepted" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
      { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'stale accepted attempt: "box-0000"');
  });

  it("splitting a single-unit box fails resplit halves mismatch", () => {
    const runRoot = materializeRun("join-single-unit-split");
    // Root boxes: box-0000 holds 45 units, box-0001 is a genuine singleton root.
    const { unitIds } = splitIntoTwoBoxes(runRoot, 45, ["box-0000", "box-0001"]);
    const tailRow = readBoxRows(runRoot, "join/box-0001.jsonl")[0];
    writeAttemptOutput(runRoot, "join/box-0001.attempt1.jsonl", [tailRow]);
    writeAttemptOutput(runRoot, "join/box-0001.attempt2.jsonl", [tailRow]);
    writeAttemptOutput(runRoot, "join/box-0001-c1.jsonl", [tailRow]);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: BOX_0000, status: "accepted" },
      { attemptId: "box-0001-a1", boxId: "box-0001", attempt: 1, units: unitIds[1], outputRef: "join/box-0001.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0001-a2", boxId: "box-0001", attempt: 2, units: unitIds[1], outputRef: "join/box-0001.attempt2.jsonl", status: "failed" },
      // attempt to "split" the singleton: one child still holding the whole single unit
      { attemptId: "box-0001-c1", boxId: "box-0001-c1", parentBoxId: "box-0001", attempt: 1, units: unitIds[1], outputRef: "join/box-0001-c1.jsonl", status: "accepted" },
    ]);
    // Keep J8 greedy packing honest: the approved ceiling is box-0000's exact
    // input, so its neighbour cannot fit and only J9 fails.
    capCeilingToBoxInput(runRoot, "box-0000");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'resplit halves mismatch: "box-0001"');
  });

  it("recovery depth above max_resplit_depth fails (floor-valid 11/12 split)", () => {
    const runRoot = materializeRun("join-depth-exceeded");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    const { unitIds } = splitIntoTwoBoxes(runRoot, 23, ["box-0000-h1", "box-0000-h2"]);
    const h2Rows = readBoxRows(runRoot, "join/box-0000-h2.jsonl");
    const half = Math.floor(h2Rows.length / 2); // 23 units -> left 11, right 12
    writeAttemptOutput(runRoot, "join/box-0000.attempt1.jsonl", rows);
    writeAttemptOutput(runRoot, "join/box-0000.attempt2.jsonl", rows);
    writeAttemptOutput(runRoot, "join/box-0000-h2.attempt1.jsonl", h2Rows);
    writeAttemptOutput(runRoot, "join/box-0000-h2.attempt2.jsonl", h2Rows);
    writeAttemptOutput(runRoot, "join/q1.jsonl", h2Rows.slice(0, half));
    writeAttemptOutput(runRoot, "join/q2.jsonl", h2Rows.slice(half));
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: "join/box-0000.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-a2", boxId: "box-0000", attempt: 2, units: ids, outputRef: "join/box-0000.attempt2.jsonl", status: "failed" },
      { attemptId: "box-0000-h1-a1", boxId: "box-0000-h1", parentBoxId: "box-0000", attempt: 1, units: unitIds[0], outputRef: "join/box-0000-h1.jsonl", status: "accepted" },
      { attemptId: "box-0000-h2-a1", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 1, units: unitIds[1], outputRef: "join/box-0000-h2.attempt1.jsonl", status: "failed" },
      { attemptId: "box-0000-h2-a2", boxId: "box-0000-h2", parentBoxId: "box-0000", attempt: 2, units: unitIds[1], outputRef: "join/box-0000-h2.attempt2.jsonl", status: "failed" },
      { attemptId: "box-0000-h2-q1", boxId: "box-0000-h2-q1", parentBoxId: "box-0000-h2", attempt: 1, units: unitIds[1].slice(0, half), outputRef: "join/q1.jsonl", status: "accepted" },
      { attemptId: "box-0000-h2-q2", boxId: "box-0000-h2-q2", parentBoxId: "box-0000-h2", attempt: 1, units: unitIds[1].slice(half), outputRef: "join/q2.jsonl", status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'resplit depth exceeded: "box-0000-h2"');
  });

  it("missing structured retry history fails retry evidence missing", () => {
    const runRoot = materializeRun("join-no-history");
    editJson(runRoot, RUN_MANIFEST, (env) => { env.join_attempts = []; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'retry evidence missing: "box-0000"');
  });

  it("F6: accepted attempt output must be the current box artifact (stale accepted attempt)", () => {
    const runRoot = materializeRun("join-accepted-output-stale");
    const rows = readBoxRows(runRoot);
    const ids = rows.map((r) => r.unit_id);
    // Same rows recorded under a different output ref: identical bytes, wrong binding.
    const alternative = "join/box-0000.accepted-elsewhere.jsonl";
    writeAttemptOutput(runRoot, alternative, rows);
    setJoinAttempts(runRoot, [
      { attemptId: "box-0000-a1", boxId: "box-0000", attempt: 1, units: ids, outputRef: alternative, status: "accepted" },
    ]);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.recovery", 'stale accepted attempt: "box-0000"');
  });
});

describe("join.merge — canonical merge vs box rows (J10, RED until P4b)", () => {
  it("merged row divergence fails even when the join draft is resealed", () => {
    const runRoot = materializeRun("join-merge-divergence");
    mutateJoinDraft(runRoot, (join) => { join.units[0].links[0].closeness = "medium"; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.merge", "merged join differs from boxes");
  });

  it("object key reordering passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-merge-key-order");
    mutateJoinDraft(runRoot, (join) => {
      join.units = join.units.map((row) => ({
        unresolved: row.unresolved,
        links: row.links.map((link) => ({
          witness: link.witness,
          role_hint: link.role_hint,
          closeness: link.closeness,
          claim_id: link.claim_id,
        })),
        unit_id: row.unit_id,
      }));
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectVerdict(r, 0);
  });

  it("row reordering fails", () => {
    const runRoot = materializeRun("join-merge-row-order");
    mutateJoinDraft(runRoot, (join) => {
      [join.units[0], join.units[1]] = [join.units[1], join.units[0]];
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.merge", "merged join differs from boxes");
  });

  it("declared box rows/links that disagree with the box file fail", () => {
    for (const [field, mutate] of [
      ["rows", (box) => { box.rows = 45; }],
      ["links", (box) => { box.links = 248; }],
    ]) {
      const runRoot = materializeRun(`join-merge-count-${field}`);
      mutateJoinDraft(runRoot, (join) => mutate(join.boxes[0]));
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.merge", `box count mismatch: "box-0000":${field}`);
    }
  });
});

describe("join.p05 — recomputed coordinator evidence (J11, RED until P4b)", () => {
  it("p05 evidence expected_rows mismatch fails", () => {
    const runRoot = materializeRun("join-p05-expected");
    mutateP05Evidence(runRoot, (p05) => { p05.expected_rows = 45; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 count mismatch: "box-0000":expected_rows');
  });

  it("p05 evidence received_rows mismatch fails", () => {
    const runRoot = materializeRun("join-p05-received");
    mutateP05Evidence(runRoot, (p05) => { p05.received_rows = 45; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 count mismatch: "box-0000":received_rows');
  });

  it("p05-check file_rows mismatch fails", () => {
    const runRoot = materializeRun("join-p05-file-rows");
    mutateP05Check(runRoot, (p05) => { p05.file_rows = 45; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 count mismatch: "box-0000":file_rows');
  });

  it("recorded p05 errors fail even if error_count stays zero", () => {
    const runRoot = materializeRun("join-p05-errors");
    mutateP05Evidence(runRoot, (p05) => { p05.error_count = 1; p05.errors = ["forged"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 errors recorded: "box-0000"');
  });

  it("forged zero_claims/unresolved sets fail", () => {
    for (const [field, mutate] of [
      ["zero_claims", (p05) => { p05.zero_claims = ["C01"]; }],
      ["unresolved", (p05) => { p05.unresolved = ["u0000"]; }],
    ]) {
      const runRoot = materializeRun(`join-p05-${field}`);
      mutateP05Check(runRoot, mutate);
      const r = runVerifier(["join", "--run", runRoot], { runRoot });
      expectFailure(r, "join.p05", `p05 zero/unresolved mismatch: "box-0000":${field}`);
    }
  });

  it("claim_link_counts that are not exactly recomputed fail", () => {
    const runRoot = materializeRun("join-p05-claim-counts");
    mutateP05Check(runRoot, (p05) => { p05.claim_link_counts.C01 += 1; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 claim_link_counts mismatch: "box-0000"');
  });

  it("total_links drift fails", () => {
    const runRoot = materializeRun("join-p05-total-links");
    mutateP05Evidence(runRoot, (p05) => { p05.total_links = 248; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.p05", 'p05 count mismatch: "box-0000":total_links');
  });
});

describe("join.candidates — candidate_unclaimed encoding (J12, RED until P4b)", () => {
  it("a linked unit listed as candidate_unclaimed fails", () => {
    const runRoot = materializeRun("join-candidate-linked");
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u0000"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.candidates", 'invalid candidate_unclaimed unit: "u0000"');
  });

  it("a zero-link but unresolved unit listed as candidate_unclaimed fails", () => {
    const runRoot = materializeRun("join-candidate-unresolved");
    setRowUnlinked(runRoot, "u0000", "needs a human decision");
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u0000"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.candidates", 'invalid candidate_unclaimed unit: "u0000"');
  });

  it("an unknown candidate unit fails", () => {
    const runRoot = materializeRun("join-candidate-unknown");
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u9999"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.candidates", 'invalid candidate_unclaimed unit: "u9999"');
  });

  it("a duplicated candidate unit fails", () => {
    const runRoot = materializeRun("join-candidate-duplicate");
    setRowUnlinked(runRoot, "u0000", null);
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u0000", "u0000"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.candidates", 'invalid candidate_unclaimed unit: "u0000"');
  });

  it("a missing eligible zero-link unit fails the exhaustive set check", () => {
    const runRoot = materializeRun("join-candidate-missing");
    setRowUnlinked(runRoot, "u0000", null);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.candidates", "candidate_unclaimed set mismatch");
  });

  it("a valid zero-link decidable candidate passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-candidate-valid");
    setRowUnlinked(runRoot, "u0000", null);
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u0000"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 1);
    expectCheckOk(v, "join.candidates");
  });

  it("a zero-link unresolved unit is excluded from candidates and passes (RED until P4b)", () => {
    const runRoot = materializeRun("join-candidate-unresolved-excluded");
    setRowUnlinked(runRoot, "u0000", "unresolved reason");
    setRowUnlinked(runRoot, "u0001", null);
    mutateJoinDraft(runRoot, (join) => { join.candidate_unclaimed = ["u0001"]; });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 1);
    expectCheckOk(v, "join.candidates");
  });
});

describe("join.machine and join.approval — opaque units are machine-only (plan §3 b7-b15)", () => {
  it("b7: a machine row accounts for the opaque unit in manifest order", () => {
    const { runRoot } = opaqueJoinRun("join-machine-row");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.machine", "machine units: 1");
  });

  it("b8: an opaque unit assigned to a model box fails join.assignments", () => {
    const { runRoot, unitId } = opaqueJoinRun("join-machine-in-box");
    const rows = readBoxRows(runRoot);
    const row = { unit_id: unitId, links: [], unresolved: null };
    writeBoxRows(runRoot, BOX_0000, [...rows, row]);
    editJson(runRoot, JOIN_DRAFT, (join) => { join.units.push(row); });
    editJson(runRoot, BOX_0000_ASSIGNMENT, (assignment) => {
      assignment.units.push(unitId);
      assignment.unit_count = assignment.units.length;
    });
    resealUnitsBinding(runRoot);
    resealRun(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.assignments", `opaque unit assigned to a model box: ${JSON.stringify(unitId)}`);
  });

  it("b9: omitting an opaque machine row fails join.machine", () => {
    const fixture = materializeOpaqueRun("join-machine-missing");
    const r = runVerifier(["join", "--run", fixture.runRoot], { runRoot: fixture.runRoot });
    expectFailure(r, "join.machine", `machine row missing: ${JSON.stringify(fixture.unitId)}`);
  });

  it("b9: a machine row must never carry model links", () => {
    const { runRoot } = opaqueJoinRun("join-machine-links");
    editJson(runRoot, JOIN_DRAFT, (join) => {
      join.machine[0].links = [{ claim_id: "C21" }];
    });
    resealEnvelope(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.machine", "machine row must have links: []");
  });

  it("CB5: oversized machine-row unresolved text is refused without echoing raw bytes", () => {
    const blob = Buffer.from(`ZZBLOB7K${"q".repeat(6992)}`);
    const { runRoot, unitId } = opaqueJoinRun("join-machine-unresolved-bound", {
      bodies: [blob, blob],
    });
    const unresolved = `needs review: ${blob.subarray(0, 256).toString("utf8")}`;
    setRowUnlinked(runRoot, "u0000", null); // one legitimate model-side candidate
    editJson(runRoot, JOIN_DRAFT, (join) => {
      join.machine[0].unresolved = unresolved;
      join.candidate_unclaimed = ["u0000"];
    });
    resealEnvelope(runRoot);

    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectFailure(r, "join.machine", `machine unresolved exceeds 200 characters: ${JSON.stringify(unitId)}`);
    const output = r.stdout + r.stderr;
    assert.ok(!output.includes("ZZBLOB7K"), "verifier output must not echo the raw blob marker");
    assert.ok(!output.includes(unresolved.slice(0, 64)), "verifier output must not echo a 64-character unresolved slice");
    assert.ok(!output.includes(blob.subarray(64, 128).toString("utf8")), "verifier output must not echo a 64-byte raw blob slice");
    assert.ok(v.checks.every(({ detail }) => detail === undefined || detail.length <= 200),
      "verifier check details must remain bounded");
    const candidates = readJson(runRoot, JOIN_DRAFT).candidate_unclaimed;
    assert.deepEqual(candidates, ["u0000"], "candidate_unclaimed contains only the decidable model unit id");
    assert.ok(!candidates.includes(unitId), "opaque machine units are not candidates");
  });

  it("b10: partial opaque coverage without an approval fails join.approval", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-missing");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", 'skip not approved: "skip-0000"');
  });

  it("b11: a pinned approval with a different subject_oid fails its binding", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-subject");
    writeOperatorApproval(runRoot, { subject_oid: "0".repeat(40) });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", "approval binding mismatch: subject_oid");
  });

  it("b12: approval bytes must match the envelope approval pin", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-pin");
    const { ref } = writeOperatorApproval(runRoot);
    writeBytes(runRoot, ref, Buffer.concat([readBytes(runRoot, ref), Buffer.from(" ")]));
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", "approval artifact sha256 mismatch");
  });

  it("b13: approval operator_ref must bind to pilot.operator_ref", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-operator");
    writeOperatorApproval(runRoot, { operator_ref: "fixture:other-operator" });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", "approval binding mismatch: operator_ref");
  });

  it("b14: an unknown approval policy_class fails closed", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-policy");
    writeOperatorApproval(runRoot, {
      approved: [{
        skip_id: "skip-0000", occurrence_ids: ["occ-0000"], policy_class: "automatic",
        rationale: "invalid fixture policy", basis: "partial-review",
      }],
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", 'invalid policy_class: "automatic"');
  });

  it("b14: a duplicate policy_class across approvals fails closed", () => {
    const { runRoot } = twoSkipPartialOpaqueJoinRun("join-approval-duplicate-policy");
    writeOperatorApproval(runRoot, {
      approved: [
        { skip_id: "skip-0000", occurrence_ids: ["occ-0000"], policy_class: "big-blob", rationale: "first", basis: "partial-review" },
        { skip_id: "skip-0001", occurrence_ids: ["occ-0001"], policy_class: "big-blob", rationale: "duplicate", basis: "partial-review" },
      ],
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", 'invalid policy_class: "big-blob"');
  });

  it("b14: an extra approval entry for an unrecorded skip fails closed", () => {
    const { runRoot } = partialOpaqueJoinRun("join-approval-extra");
    writeOperatorApproval(runRoot, {
      approved: [
        { skip_id: "skip-0000", occurrence_ids: ["occ-0000"], policy_class: "big-blob", rationale: "recorded", basis: "partial-review" },
        { skip_id: "skip-9999", occurrence_ids: [], policy_class: "vendor", rationale: "extra", basis: "excluded" },
      ],
    });
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    expectFailure(r, "join.approval", 'unapproved skip reference: "skip-9999"');
  });

  it("b15: a coherent approval passes and leaves the machine unit out of candidates", () => {
    const { runRoot, unitId } = partialOpaqueJoinRun("join-approval-pass");
    writeOperatorApproval(runRoot);
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    expectCheckOk(v, "join.machine", "machine units: 1");
    assert.equal(readJson(runRoot, JOIN_DRAFT).candidate_unclaimed.includes(unitId), false);
  });
});

describe("empty inventory (plan §4 item 28; representation documented)", () => {
  // Empty-inventory representation per the envelope profile: units=[],
  // join-draft boxes/units/candidate_unclaimed=[], envelope join_boxes=[],
  // join_attempts=[], capture changed_files=[]; no box/p05/assignment files.
  // Claims stay nonempty (zero-link claims are reported globally, J12).
  it("a complete empty diff passes join mechanics (RED until P4b)", () => {
    const runRoot = materializeEmptyRun("join-empty-inventory");
    const r = runVerifier(["join", "--run", runRoot], { runRoot });
    const v = expectVerdict(r, 0);
    for (const check of v.checks) assert.equal(check.ok, true, `check ${check.name} must pass: ${check.detail}`);
  });

  it("empty-inventory units/claims prerequisites still validate", () => {
    const runRoot = materializeEmptyRun("join-empty-prereq");
    for (const command of ["claims", "units"]) {
      const r = runVerifier([command, "--run", runRoot], { runRoot });
      const v = expectVerdict(r, 0);
      assert.equal(v.schema, command === "units" ? "code-units-sim/2" : "claims-draft/3");
    }
  });

  it("join without the required run root refuses (usage)", () => {
    const r = runVerifier(["join"], {});
    expectRefusal(r, "cli", "usage: verify <claims|units|join> --run <run-root>");
  });
});
