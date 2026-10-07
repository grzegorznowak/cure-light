// RED contract suite for opaque over-ceiling diff lines.  This suite deliberately
// describes the /3 behavior; it must fail until the opaque-line implementation lands.
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync } from "node:fs";
import path from "node:path";
import {
  CEILING_BYTES, branch, cleanupTempDirs, commitAll, createFixtureRepo,
  gitDiffRaw, manifestPath, readManifest, runChunker, tempDir, write,
} from "./chunker-testkit.mjs";

after(cleanupTempDirs);

const MARKER = "ZZBLOB7K";
const BODY_LENGTH = 7000;
const markerBytes = Buffer.from(MARKER);
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const opaqueBody = () => Buffer.concat([markerBytes, Buffer.alloc(BODY_LENGTH - markerBytes.length, 0x78)]);
const toBuffer = (line) => Buffer.isBuffer(line) ? line : Buffer.from(line);

function fileBytes(lines, { eol = "\n", finalNewline = true } = {}) {
  const out = [];
  lines.forEach((line, i) => {
    out.push(toBuffer(line));
    if (i + 1 < lines.length || finalNewline) out.push(Buffer.from(eol));
  });
  return Buffer.concat(out);
}

function changedRepo(name, rel, base, subject) {
  const repo = createFixtureRepo(name);
  write(repo, rel, base);
  commitAll(repo, "base");
  branch(repo, "subject");
  write(repo, rel, subject);
  commitAll(repo, "subject");
  return repo;
}

function moveRepo(name, { rel = "move.css", body = opaqueBody(), baseOptions, subjectOptions } = {}) {
  return {
    repo: changedRepo(
      name,
      rel,
      fileBytes(["top", "a", body, "b", "tail"], baseOptions),
      fileBytes(["top", "a", "b", body, "tail"], subjectOptions),
    ),
    body,
  };
}

function assertSuccess(run) {
  assert.equal(run.status, 0, `chunker must complete successfully:\n${run.stderr}`);
  assert.equal(run.stderr, "", "successful opaque handling must not warn on stderr");
  assert.ok(existsSync(manifestPath(run.outDir)), "successful run publishes manifest last");
  const manifest = readManifest(run.outDir);
  assert.equal(manifest.schema_version, "code-units-sim/3", "opaque handling uses the /3 manifest");
  return manifest;
}

function assertNoLeak(run, body, { manifest = true } = {}) {
  const publicBytes = [Buffer.from(run.stdout), Buffer.from(run.stderr)];
  if (manifest && existsSync(manifestPath(run.outDir))) {
    publicBytes.push(readFileSync(manifestPath(run.outDir)));
    const unitsDir = path.join(run.outDir, "units2");
    for (const name of readdirSync(unitsDir)) {
      if (/^u\d{4}\.txt$/.test(name)) publicBytes.push(readFileSync(path.join(unitsDir, name)));
    }
  }
  const publicText = Buffer.concat(publicBytes);
  assert.equal(publicText.includes(markerBytes), false, "public output must not contain the blob marker");
  for (const start of [0, Math.floor(body.length / 2), body.length - 64]) {
    assert.equal(
      publicText.includes(body.subarray(start, start + 64)), false,
      `public output must not contain a 64-byte blob slice at ${start}`,
    );
  }
}

function opaqueUnits(manifest) {
  return manifest.units.filter((unit) => unit.boundary_kind === "opaque");
}

function assertDescriptor(run, manifest) {
  const [unit] = opaqueUnits(manifest);
  assert.ok(unit, "opaque occurrences have a first-class opaque descriptor unit");
  const bytes = readFileSync(path.join(run.outDir, unit.file));
  assert.ok(bytes.length <= 1024, "CB2: opaque descriptor payload is bounded to 1024 bytes");
  const descriptor = JSON.parse(bytes.toString("utf8"));
  assert.deepStrictEqual(Object.keys(descriptor).sort(), ["occurrences", "pairing", "schema", "unit_id"]);
  assert.equal(descriptor.schema, "opaque-descriptor/1");
  assert.equal(descriptor.unit_id, unit.unit_id);
  assert.ok(Array.isArray(descriptor.occurrences));
  return descriptor;
}

function assertRawNamespace(run, manifest) {
  const rawDir = path.join(run.outDir, "units2", "raw");
  const names = readdirSync(rawDir).sort();
  const refs = manifest.opaque_occurrences.map((occurrence) => path.basename(occurrence.ref)).sort();
  assert.deepStrictEqual(names, refs, "CB3: raw store contains exactly the occurrence refs");
  assert.ok(names.every((name) => /^occ-\d{4}\.bin$/.test(name) && !/^u\d{4}\.txt$/.test(name)), "CB3: raw files use only the occurrence namespace");
}

function occurrence(manifest, id) {
  const found = manifest.opaque_occurrences.find((entry) => entry.occurrence_id === id);
  assert.ok(found, `opaque occurrence ${id} exists`);
  return found;
}

function assertRaw(run, entry, expected) {
  const actual = readFileSync(path.join(run.outDir, entry.ref));
  assert.deepStrictEqual(actual, expected, `${entry.occurrence_id} raw bytes exact`);
  assert.equal(entry.byte_length, expected.length, `${entry.occurrence_id} byte length`);
  assert.equal(entry.sha256, sha256(expected), `${entry.occurrence_id} sha256`);
}

describe("opaque over-ceiling lines (/3 RED contract)", () => {
  it("a1 pure move: paired occurrences, exit 0", () => {
    const { repo, body } = moveRepo("opaque-a1");
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 2);
    const [removed, added] = manifest.opaque_occurrences;
    assert.equal(removed.side, "removed");
    assert.equal(added.side, "added");
    assert.equal(removed.state, "paired");
    assert.equal(added.state, "paired");
    assert.ok(removed.pair_id && removed.pair_id === added.pair_id, "move has one shared certificate");
    assertRaw(run, removed, body);
    assertRaw(run, added, body);
    assert.equal(manifest.coverage.status, "complete");
    assert.deepStrictEqual(manifest.coverage.skips, []);
    assertDescriptor(run, manifest);
    assertRawNamespace(run, manifest);
    assertNoLeak(run, body); // CB1
  });

  it("a2 context occurrence: giant unchanged, edits elsewhere", () => {
    const body = opaqueBody();
    const repo = changedRepo(
      "opaque-a2", "ctx.txt",
      fileBytes(["top", "near", body, "one", "two", "old", "tail"]),
      fileBytes(["top", "near", body, "one", "two", "new", "tail"]),
    );
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 1);
    const [entry] = manifest.opaque_occurrences;
    assert.equal(entry.side, "context");
    assert.equal(entry.state, "context");
    assert.equal(entry.pair_id, null);
    assert.equal(manifest.coverage.status, "complete");
    assert.deepStrictEqual(manifest.skips, []);
    assert.ok(manifest.units.some((unit) => unit.boundary_kind !== "opaque" && readFileSync(path.join(run.outDir, unit.file), "utf8").includes("+new")), "edited sibling remains reviewable");
    assertNoLeak(run, body); // CB1
  });

  it("a3 duplicate identical occurrences: ambiguous, no certificate", () => {
    const body = opaqueBody();
    // The blob pair moves across six unique anchors. Matching a blob would
    // discard every anchor, so Myers emits two removals and two additions.
    const anchors = ["anchor-a", "anchor-b", "anchor-c", "anchor-d", "anchor-e", "anchor-f"];
    const repo = changedRepo(
      "opaque-a3", "dupes.txt",
      fileBytes([body, body, ...anchors]),
      fileBytes([...anchors, body, body]),
    );
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 4);
    assert.ok(manifest.opaque_occurrences.every((entry) => entry.state === "ambiguous" && entry.pair_id === null));
    assert.equal(manifest.coverage.status, "partial");
    assert.equal(manifest.skips.length, 1);
    assert.equal(manifest.skips[0].reason, "ambiguous");
    assert.equal(manifest.skips[0].occurrence_ids.length, 4);
  });

  it("a4 one-sided addition", () => {
    const body = opaqueBody();
    const repo = changedRepo("opaque-a4", "add.txt", fileBytes(["small"]), fileBytes(["small", body]));
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 1);
    const [entry] = manifest.opaque_occurrences;
    assert.equal(entry.side, "added");
    assert.equal(entry.state, "unpaired");
    assert.equal(entry.pair_id, null);
    assertRaw(run, entry, body);
    assert.equal(manifest.coverage.status, "partial");
    assert.equal(manifest.skips[0].reason, "unpaired");
    assertNoLeak(run, body); // CB1
  });

  it("a5 one-sided deletion", () => {
    const body = opaqueBody();
    const repo = changedRepo("opaque-a5", "delete.txt", fileBytes([body, "small"]), fileBytes(["small"]));
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 1);
    const [entry] = manifest.opaque_occurrences;
    assert.equal(entry.side, "removed");
    assert.equal(entry.state, "unpaired");
    assertRaw(run, entry, body);
    assert.equal(manifest.coverage.status, "partial");
    assert.equal(manifest.skips[0].reason, "unpaired");
  });

  it("a6 one-byte mutation", () => {
    const baseBody = opaqueBody();
    baseBody[3500] = 0x71; // q
    const subjectBody = Buffer.from(baseBody);
    subjectBody[3500] = 0x72; // r
    const repo = changedRepo(
      "opaque-a6", "mutate.txt",
      fileBytes(["top", "a", baseBody, "b", "tail"]),
      fileBytes(["top", "a", "b", subjectBody, "tail"]),
    );
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 2);
    assert.ok(manifest.opaque_occurrences.every((entry) => entry.pair_id === null && entry.state === "unpaired"));
    assert.equal(manifest.coverage.status, "partial");
    assert.equal(manifest.skips[0].reason, "not-byte-equal");
    const [removed, added] = manifest.opaque_occurrences;
    const left = readFileSync(path.join(run.outDir, removed.ref));
    const right = readFileSync(path.join(run.outDir, added.ref));
    assert.equal(left.length, right.length);
    assert.equal(left.reduce((n, byte, i) => n + (byte !== right[i]), 0), 1, "raw buffers differ in exactly one byte");
  });

  it("a7 CRLF identical", () => {
    const body = opaqueBody();
    const { repo } = moveRepo("opaque-a7", { rel: "crlf.txt", body, baseOptions: { eol: "\r\n" }, subjectOptions: { eol: "\r\n" } });
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    const [removed, added] = manifest.opaque_occurrences;
    assert.equal(removed.state, "paired");
    assert.equal(added.state, "paired");
    const expected = Buffer.concat([body, Buffer.from("\r")]);
    assertRaw(run, removed, expected);
    assertRaw(run, added, expected);
    assert.equal(readFileSync(path.join(run.outDir, removed.ref)).at(-1), 0x0d, "raw body retains CR");
  });

  it("a8 CRLF to LF asymmetry", () => {
    const body = opaqueBody();
    const repo = changedRepo(
      "opaque-a8", "eol.txt",
      fileBytes(["top", "a", body, "b", "tail"], { eol: "\r\n" }),
      fileBytes(["top", "a", "b", body, "tail"]),
    );
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.opaque_occurrences.length, 2);
    assert.ok(manifest.opaque_occurrences.every((entry) => entry.pair_id === null && entry.state === "unpaired"));
    assert.equal(manifest.skips[0].reason, "not-byte-equal", "CR must not be normalized away");
  });

  it("a9 invalid UTF-8 is captured before decode", () => {
    const body = opaqueBody();
    body[20] = 0xe9;
    const { repo } = moveRepo("opaque-a9", { rel: "bytes.txt", body });
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    const [removed, added] = manifest.opaque_occurrences;
    assert.equal(removed.state, "paired");
    assert.equal(added.state, "paired");
    assertRaw(run, removed, body);
    assertRaw(run, added, body);
    assert.doesNotThrow(() => JSON.parse(readFileSync(path.join(run.outDir, opaqueUnits(manifest)[0].file), "utf8")), "descriptor remains valid UTF-8 JSON");
  });

  it("a10 no final newline", () => {
    const body = opaqueBody();
    // A delete/add across paths is a move under --no-renames, keeping the
    // oversized line at EOF without an LF on both sides.
    const repo = createFixtureRepo("opaque-a10");
    write(repo, "old.txt", fileBytes([body], { finalNewline: false }));
    commitAll(repo, "base");
    branch(repo, "subject");
    rmSync(path.join(repo, "old.txt"));
    write(repo, "new.txt", fileBytes([body], { finalNewline: false }));
    commitAll(repo, "subject");
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    const [removed, added] = manifest.opaque_occurrences;
    assert.equal(removed.state, "paired");
    assert.equal(added.state, "paired");
    assertRaw(run, removed, body);
    assertRaw(run, added, body);
    assert.notEqual(readFileSync(path.join(run.outDir, removed.ref)).at(-1), 0x0a, "raw EOF body has no LF");
  });

  it("a11 C-quoted path", () => {
    const body = opaqueBody();
    const rel = 'quote"name.txt';
    const { repo } = moveRepo("opaque-a11", { rel, body });
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    const header = gitDiffRaw(repo).split("\n").find((line) => line.startsWith("diff --git "));
    assert.ok(header.includes('"a/'), "fixture forces git C quoting");
    assert.ok(manifest.opaque_occurrences.every((entry) => entry.path === header));
    assertRawNamespace(run, manifest);
  });

  it("a12 bounded raw-write error output", () => {
    const { repo, body } = moveRepo("opaque-a12");
    const outDir = tempDir("opaque-a12-out");
    mkdirSync(path.join(outDir, "units2", "raw", "occ-0000.bin"), { recursive: true });
    const run = runChunker({ repo, outDir });
    assert.equal(run.status, 1, "raw write failure exits 1");
    assert.match(run.stderr, /^chunker: cannot write raw occurrence occ-0000\.bin:/);
    assertNoLeak(run, body, { manifest: false }); // CB1, including error output
    assert.ok(!existsSync(manifestPath(run.outDir)), "manifest-last prevents publication on raw write failure");
  });

  it("a13 accounting", () => {
    const { repo } = moveRepo("opaque-a13");
    const run = runChunker({ repo });
    const manifest = assertSuccess(run);
    assert.equal(manifest.counts.opaque_occurrences, 2);
    assert.equal(manifest.counts.opaque_bytes, 14000);
    const payloadBytes = manifest.units.reduce((sum, unit) => sum + unit.byte_len, 0);
    assert.equal(manifest.counts.total_bytes, payloadBytes, "raw bytes are excluded from total_bytes");
  });
});
