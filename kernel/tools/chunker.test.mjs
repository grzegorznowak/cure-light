// Contract suite for kernel/tools/chunker.mjs. Run with:
//
//   node --test "kernel/tools/*.test.mjs"
//
// Golden creation/refresh:
//
//   UPDATE_GOLDENS=1 node --test "kernel/tools/*.test.mjs"
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  CEILING_BYTES, CHUNKER_PATH, FIXTURES_DIR, RECIPE, TOOLS_DIR,
  assertRunContract, assertRunMatchesGolden, assertRunsEquivalent,
  branch, buildFixture, cleanupTempDirs, commitAll, createFixtureRepo,
  discoverFixtures, gitChangedFileOrder, gitDiffRaw, loadFixture,
  manifestPath, readManifest, readRunArtifacts, revParse, runChunker,
  runGit, spawnChunker, symlink, tempDir, write,
} from "./chunker-testkit.mjs";

after(cleanupTempDirs);

const fixtureRuns = new Map();
function fixtureRunOnce(name) {
  if (!fixtureRuns.has(name)) {
    fixtureRuns.set(name, (async () => {
      const { repo } = await buildFixture(name);
      return { repo, run: runChunker({ repo }) };
    })());
  }
  return fixtureRuns.get(name);
}

const unitText = (run, unit) => readFileSync(path.join(run.outDir, unit.file), "utf8");
const unitsForPath = (manifest, filePath) => manifest.units.filter((u) => u.path === filePath);

// A small diff with blank context lines, changes at lines 4 and 14: two hunks
// baseline, fusable by interHunkContext, blank-context sensitive.
function buildHostileRepo(name) {
  const repo = createFixtureRepo(name);
  const base = [
    "line 01", "", "line 03", "line 04", "", "line 06",
    "line 07", "line 08", "line 09", "line 10", "", "line 12",
    "line 13", "line 14", "line 15", "line 16", "line 17", "line 18",
    "line 19", "line 20",
  ];
  write(repo, "text.txt", `${base.join("\n")}\n`);
  commitAll(repo, "base");
  branch(repo, "subject");
  const lines = [...base];
  lines[3] = "line 04 changed";
  lines[13] = "line 14 changed";
  write(repo, "text.txt", `${lines.join("\n")}\n`);
  commitAll(repo, "subject");
  return repo;
}

describe("CLI and failure surfaces", () => {
  it("exits 2 with usage for 0-3 missing args and for an empty argument", () => {
    const out = tempDir("cli-out");
    const candidates = [[], [os.tmpdir()], [os.tmpdir(), "main"], [os.tmpdir(), "main", "subject"]];
    for (const args of candidates) {
      const res = spawnChunker(args);
      assert.equal(res.status, 2, `${args.length} args must exit 2`);
      assert.match(res.stderr, /^usage: chunker\.mjs <repo> <base> <subject> <outDir>\n$/, `${args.length} args usage line`);
      assert.equal(res.stdout, "", `${args.length} args stdout`);
    }
    const empty = spawnChunker([os.tmpdir(), "", "subject", out]);
    assert.equal(empty.status, 2, "empty base arg must exit 2");
    assert.match(empty.stderr, /^usage: chunker\.mjs/);
    assert.ok(!existsSync(path.join(out, "units2")), "rejected args must not write output");
  });

  it("bogus base or subject refs: exit 1, chunker: diagnostic, no manifest", async () => {
    const { repo } = await fixtureRunOnce("basic-multi-file");
    for (const [base, subject] of [["no-such-base", "subject"], ["main", "no-such-subject"]]) {
      const res = runChunker({ repo, base, subject });
      assert.equal(res.status, 1, `${base}..${subject} exits 1`);
      // git's own `fatal:` line is inherited by the chunker's stderr first;
      // the chunker-owned diagnostic is the prefixed line.
      const diagnostic = res.stderr.split("\n").find((line) => line.startsWith("chunker: "));
      assert.ok(diagnostic, `${base}..${subject} chunker: diagnostic present`);
      assert.match(diagnostic, /^chunker: git diff failed:/);
      assert.equal(res.stdout, "", `${base}..${subject} stdout`);
      assert.ok(!existsSync(manifestPath(res.outDir)), `${base}..${subject} must not publish a manifest`);
    }
  });

  it("nonexistent repo: exit 1, chunker: diagnostic, no manifest", () => {
    const res = runChunker({ repo: path.join(os.tmpdir(), "cure-light-no-such-repo") });
    assert.equal(res.status, 1);
    const diagnostic = res.stderr.split("\n").find((line) => line.startsWith("chunker: "));
    assert.ok(diagnostic, "chunker: diagnostic present");
    assert.match(diagnostic, /^chunker: git diff failed:/);
    assert.ok(!existsSync(manifestPath(res.outDir)));
  });

  it("indivisible line over the ceiling: exit 1, named ceiling error, no manifest", () => {
    const repo = createFixtureRepo("ceiling-line");
    write(repo, "huge.txt", "base\n");
    commitAll(repo, "base");
    branch(repo, "subject");
    write(repo, "huge.txt", `${"A".repeat(7000)}\n`);
    commitAll(repo, "subject");
    const res = runChunker({ repo });
    assert.equal(res.status, 1);
    assert.match(res.stderr, new RegExp(`^chunker: indivisible line exceeds the ${CEILING_BYTES}-byte ceiling`));
    assert.ok(!existsSync(manifestPath(res.outDir)), "failed run must not publish a manifest");
  });

  it("outDir is an existing regular file: mkdir fails with chunker: prefix", async () => {
    const { repo } = await fixtureRunOnce("basic-multi-file");
    const outFile = path.join(tempDir("fs-file"), "outfile");
    writeFileSync(outFile, "not a directory");
    const res = runChunker({ repo, outDir: outFile });
    assert.equal(res.status, 1);
    assert.match(res.stderr, /^chunker: cannot create output directory:/);
    assert.ok(!existsSync(manifestPath(outFile)));
  });

  it("pre-created payload path is a directory: payload write fails, no manifest", async () => {
    const { repo } = await fixtureRunOnce("basic-multi-file");
    const out = tempDir("fs-payload");
    mkdirSync(path.join(out, "units2", "u0000.txt"), { recursive: true });
    const res = runChunker({ repo, outDir: out });
    assert.equal(res.status, 1);
    assert.match(res.stderr, /^chunker: cannot write unit payload u0000\.txt:/);
    assert.ok(!existsSync(manifestPath(out)), "failed run must not publish a manifest");
  });

  it("pre-created manifest path is a directory: manifest write fails, no file published", async () => {
    const { repo } = await fixtureRunOnce("basic-multi-file");
    const out = tempDir("fs-manifest");
    mkdirSync(path.join(out, "units2", "manifest.json"), { recursive: true });
    const res = runChunker({ repo, outDir: out });
    assert.equal(res.status, 1);
    assert.match(res.stderr, /^chunker: cannot write manifest:/);
    assert.ok(statSync(manifestPath(out)).isDirectory(), "manifest path stayed a directory");
  });
});

describe("manifest and payload contract", () => {
  it("schema is code-units-sim/2 and the recipe is pinned exactly", async () => {
    const { repo: repository, run } = await fixtureRunOnce("basic-multi-file");
    const manifest = assertRunContract(run, { label: "basic" });
    assert.equal(manifest.schema_version, "code-units-sim/2");
    assert.deepStrictEqual(manifest.recipe, RECIPE);
    assert.deepStrictEqual(manifest.recipe, {
      chunker: "chunker.mjs",
      target_bytes: 4096,
      ceiling_bytes: 6144,
      context: 3,
      block_preference: true,
    });
    assert.equal(manifest.identity.repo, repository);
    assert.equal(manifest.identity.base_ref, "main");
    assert.equal(manifest.identity.subject_ref, "subject");
    assert.equal(manifest.identity.base_oid, revParse(repository, "main"));
    assert.equal(manifest.identity.subject_oid, revParse(repository, "subject"));
  });

  it("counts agree with units, payload files and the raw diff file count", async () => {
    const { repo, run } = await fixtureRunOnce("basic-multi-file");
    const manifest = readManifest(run.outDir);
    const payloadNames = readdirSync(path.join(run.outDir, "units2")).filter((n) => /^u\d{4}\.txt$/.test(n));
    assert.equal(manifest.counts.units, manifest.units.length);
    assert.equal(manifest.counts.units, payloadNames.length);
    assert.equal(manifest.counts.line_split_units, manifest.units.filter((u) => u.boundary_kind === "line-split").length);
    assert.equal(
      manifest.counts.files,
      gitDiffRaw(repo).split("\n").filter((l) => l.startsWith("diff --git ")).length,
      "counts.files == diff --git block count",
    );
    const payloadBytes = [...readRunArtifacts(run.outDir, repo).payloads.values()].reduce((n, b) => n + b.length, 0);
    assert.equal(manifest.counts.total_bytes, payloadBytes);
  });

  it("unit records are sequential, resolve, and match their payload bytes", async () => {
    const { run } = await fixtureRunOnce("basic-multi-file");
    const manifest = readManifest(run.outDir);
    manifest.units.forEach((unit, i) => {
      assert.equal(unit.unit_id, `u${String(i).padStart(4, "0")}`);
      assert.equal(unit.file, `units2/${unit.unit_id}.txt`);
      assert.ok(existsSync(path.join(run.outDir, unit.file)), `${unit.unit_id} payload exists`);
      const bytes = readFileSync(path.join(run.outDir, unit.file));
      assert.equal(bytes.length, unit.byte_len, `${unit.unit_id} byte_len == payload size`);
      assert.equal(unit.hunk_count, unit.ranges.length, `${unit.unit_id} hunk_count == ranges.length`);
      for (const range of unit.ranges) {
        assert.deepStrictEqual(Object.keys(range).sort(), ["new_count", "new_start", "old_count", "old_start"]);
        for (const value of Object.values(range)) assert.equal(typeof value, "number");
      }
    });
    assert.ok(manifest.units.length > 0, "fixture has units");
    assert.equal(manifest.counts.total_bytes, manifest.units.reduce((n, u) => n + u.byte_len, 0));
  });

  it("stdout smoke: counts JSON first, then exactly one line per unit", async () => {
    const { run } = await fixtureRunOnce("basic-multi-file");
    assert.equal(run.status, 0);
    assert.equal(run.stderr, "");
    const manifest = readManifest(run.outDir);
    const lines = run.stdout.split("\n");
    assert.equal(lines.at(-1), "", "stdout ends with one newline");
    lines.pop();
    assert.deepStrictEqual(JSON.parse(lines[0]), manifest.counts, "first line is the counts JSON");
    assert.equal(lines.length, 1 + manifest.units.length, "one stdout line per unit");
    manifest.units.forEach((unit, i) => {
      const expected = `${unit.unit_id} ${String(unit.byte_len).padStart(6)}B blocks=${unit.blocks} ${unit.boundary_kind.padEnd(10)} ${unit.path}`;
      assert.equal(lines[i + 1], expected, `stdout line for ${unit.unit_id}`);
    });
  });

  it("determinism: two runs byte-identical, independent of cwd", async () => {
    const { repo, run } = await fixtureRunOnce("basic-multi-file");
    const run2 = runChunker({ repo, outDir: tempDir("det"), cwd: TOOLS_DIR });
    assert.equal(run2.status, 0);
    assert.equal(run2.stdout, run.stdout, "stdout is identical");
    const normalized = (outDir) => readFileSync(manifestPath(outDir), "utf8").split(repo).join("<REPO>");
    assert.equal(normalized(run2.outDir), normalized(run.outDir), "manifest bytes identical after repo normalization");
    assertRunsEquivalent(run, run2, repo, "determinism");
  });
});

describe("S3 line-split labeling", () => {
  it("labels only originating split fragments, both leak shapes stay block", async () => {
    const { repo } = await buildFixture("s3-line-split");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "s3" });
    assert.ok(manifest.counts.line_split_units > 0, "fixture must force line splits");
    assert.equal(
      manifest.counts.line_split_units,
      manifest.units.filter((u) => u.boundary_kind === "line-split").length,
    );
    const raw = readFileSync(manifestPath(run.outDir), "utf8");
    assert.ok(!raw.includes("lineSplit"), "no lineSplit flag anywhere in the manifest");
    for (const marker of ["small-marker-same-hunk", "small-marker-cross-hunk"]) {
      const owners = manifest.units.filter((u) => unitText(run, u).includes(marker));
      assert.equal(owners.length, 1, `${marker} appears in exactly one unit`);
      assert.equal(owners[0].boundary_kind, "block", `${marker} unit must be labeled block, not line-split`);
    }
  });
});

describe("window bounds, grouping and diff order", () => {
  it("every code payload is within the ceiling (block-split fixture)", async () => {
    const { run } = await fixtureRunOnce("window-block-split");
    const manifest = assertRunContract(run, { label: "window-block-split" });
    assert.ok(manifest.units.length > 0);
    for (const unit of manifest.units) {
      assert.ok(unit.byte_len <= CEILING_BYTES, `${unit.unit_id} within ceiling`);
    }
  });

  it("oversized hunks split at block boundaries, never mid-line", async () => {
    const { run } = await fixtureRunOnce("window-block-split");
    const manifest = readManifest(run.outDir);
    const paragraphs = unitsForPath(manifest, "paragraphs.txt");
    const defs = unitsForPath(manifest, "defs.py");
    assert.ok(paragraphs.length > 1, "paragraph file produced multiple block units");
    assert.ok(defs.length > 1, "def file produced multiple block units");
    for (const unit of [...paragraphs, ...defs]) {
      assert.equal(unit.boundary_kind, "block", `${unit.unit_id} block label`);
    }
    assert.equal(manifest.counts.line_split_units, 0, "no line split needed for block-sized windows");
  });

  it("whole hunks fit: one unit per file, hunk_count 2 for the two-hunk file", async () => {
    const { run } = await fixtureRunOnce("window-whole-hunk");
    const manifest = readManifest(run.outDir);
    assert.deepStrictEqual([...new Set(manifest.units.map((u) => u.path))].sort(), ["multi.txt", "one.txt", "two.txt"]);
    assert.equal(manifest.units.length, 3, "each file fit in one unit");
    const multi = unitsForPath(manifest, "multi.txt");
    assert.equal(multi.length, 1);
    assert.equal(multi[0].hunk_count, 2, "both hunks recorded in one unit");
    assert.equal(multi[0].ranges.length, 2);
  });

  it("units never contain two files' markers", async () => {
    const { run } = await fixtureRunOnce("basic-multi-file");
    const manifest = readManifest(run.outDir);
    const markers = ["alpha-marker", "beta-marker", "gamma-marker"];
    for (const unit of manifest.units) {
      const present = markers.filter((m) => unitText(run, unit).includes(m));
      assert.ok(present.length <= 1, `${unit.unit_id} mixes files: ${present.join(", ")}`);
    }
  });

  it("diff file order is preserved in manifest order", async () => {
    const { repo, run } = await fixtureRunOnce("basic-multi-file");
    const manifest = readManifest(run.outDir);
    const seen = [];
    for (const unit of manifest.units) if (seen.at(-1) !== unit.path) seen.push(unit.path);
    assert.deepStrictEqual(seen, gitChangedFileOrder(repo, "main", "subject"));
  });
});

describe("no-hunk and special surfaces", () => {
  it("binary change: one file unit, no code payload, no hunk", async () => {
    const { repo } = await buildFixture("binary-nohunk");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "binary-nohunk" });
    const [blob] = unitsForPath(manifest, "blob.bin");
    assert.ok(blob, "binary file surface is present");
    assert.equal(blob.boundary_kind, "file");
    assert.equal(blob.hunk_count, 0);
    assert.deepStrictEqual(blob.ranges, []);
    const text = unitText(run, blob);
    assert.match(text, /Binary files .* differ/);
    assert.ok(!text.includes("\n+"), "no added code lines in a binary file unit");
  });

  it("mode-only change: single file unit, no ranges, exempt from the ceiling", async () => {
    const { repo } = await buildFixture("mode-only");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "mode-only" });
    assert.equal(manifest.units.length, 1);
    const [unit] = manifest.units;
    assert.equal(unit.path, "mode.txt");
    assert.equal(unit.boundary_kind, "file");
    assert.deepStrictEqual(unit.ranges, []);
    assert.equal(unit.hunk_count, 0);
    const text = unitText(run, unit);
    assert.match(text, /^old mode 100644\nnew mode 100755$/);
  });

  it("submodule pointer change is visible despite committed ignore=all", async () => {
    const { repo } = await buildFixture("submodule-ignore");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "submodule-ignore" });
    const subs = unitsForPath(manifest, "sub");
    assert.equal(subs.length, 1, "pointer change produces exactly one unit");
    assert.equal(subs[0].boundary_kind, "block");
    assert.match(unitText(run, subs[0]), /Subproject commit [0-9a-f]{40}/);
  });

  it("empty diff: valid 0-unit manifest and minimal stdout", async () => {
    const { repo } = await buildFixture("empty-diff");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "empty-diff" });
    assert.deepStrictEqual(manifest.counts, { units: 0, files: 0, line_split_units: 0, total_bytes: 0 });
    assert.deepStrictEqual(manifest.units, []);
    const lines = run.stdout.split("\n");
    assert.equal(lines.at(-1), "");
    lines.pop();
    assert.deepStrictEqual(JSON.parse(lines[0]), manifest.counts);
    assert.deepStrictEqual(lines.slice(1), [""], "empty inventory prints no unit lines");
    assert.deepStrictEqual(readdirSync(path.join(run.outDir, "units2")).filter((n) => /^u\d{4}\.txt$/.test(n)), []);
  });

  it("symlink add: block unit, no crash", { skip: process.platform === "win32" }, async () => {
    const repo = createFixtureRepo("symlink");
    write(repo, "target.txt", "target content\n");
    commitAll(repo, "base");
    branch(repo, "subject");
    symlink(repo, "target.txt", "link.txt");
    commitAll(repo, "subject");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "symlink" });
    const [link] = unitsForPath(manifest, "link.txt");
    assert.ok(link, "symlink surface present");
    assert.ok(["block", "file"].includes(link.boundary_kind));
    assert.match(unitText(run, link), /new file mode 120000/);
  });

  it("rename under --no-renames: delete and add both present", async () => {
    const { repo } = await buildFixture("rename");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "rename" });
    assert.ok(unitsForPath(manifest, "old-name.txt").length >= 1, "delete side present");
    assert.ok(unitsForPath(manifest, "new-name.txt").length >= 1, "add side present");
  });

  it("no-EOL file: no-newline marker present and payload never gains a trailing 0x0a", async () => {
    const { repo } = await buildFixture("no-eol");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "no-eol" });
    const [unit] = unitsForPath(manifest, "no-eol.txt");
    assert.ok(unit, "no-eol surface present");
    assert.match(unitText(run, unit), /\\ No newline at end of file/);
    const last = manifest.units.at(-1);
    const bytes = readFileSync(path.join(run.outDir, last.file));
    assert.notEqual(bytes[bytes.length - 1], 0x0a);
  });
});

describe("hostile config/env negatives", () => {
  const hostileCases = [
    {
      name: "repo-local diff.noprefix=true",
      apply: (repo) => runGit(repo, ["config", "diff.noprefix", "true"]),
      assertBaselinePath: true,
    },
    {
      name: "repo-local diff.srcPrefix=X/ + diff.dstPrefix=Y/",
      apply: (repo) => {
        runGit(repo, ["config", "diff.srcPrefix", "X/"]);
        runGit(repo, ["config", "diff.dstPrefix", "Y/"]);
      },
      assertBaselinePath: true,
    },
    {
      name: "env GIT_DIFF_OPTS=--unified=10",
      env: { GIT_DIFF_OPTS: "--unified=10" },
    },
    {
      name: "repo-local diff.suppressBlankEmpty=true",
      apply: (repo) => runGit(repo, ["config", "diff.suppressBlankEmpty", "true"]),
    },
    {
      name: "repo-local diff.interHunkContext=10",
      apply: (repo) => runGit(repo, ["config", "diff.interHunkContext", "10"]),
    },
  ];

  for (const testCase of hostileCases) {
    it(`${testCase.name}: byte-identical to the clean baseline`, async () => {
      const repo = buildHostileRepo("hostile");
      const clean = runChunker({ repo });
      assertRunContract(clean, { label: `clean/${testCase.name}` });
      testCase.apply?.(repo);
      const hostile = runChunker({ repo, env: testCase.env ?? {} });
      assertRunContract(hostile, { label: `hostile/${testCase.name}` });
      if (testCase.assertBaselinePath) {
        const manifest = readManifest(hostile.outDir);
        assert.ok(manifest.units.every((u) => u.path === "text.txt"), `${testCase.name}: path stays exact`);
      }
      assertRunsEquivalent(clean, hostile, repo, testCase.name);
    });
  }

  it("repo-local diff.submodule=log and diff.ignoreSubmodules=all cannot hide the pointer", async () => {
    const { repo } = await buildFixture("submodule-ignore");
    const clean = runChunker({ repo });
    assertRunContract(clean, { label: "submodule clean" });
    runGit(repo, ["config", "diff.submodule", "log"]);
    const logged = runChunker({ repo });
    assertRunContract(logged, { label: "diff.submodule=log" });
    assertRunsEquivalent(clean, logged, repo, "diff.submodule=log");
    runGit(repo, ["config", "diff.ignoreSubmodules", "all"]);
    const ignored = runChunker({ repo });
    assertRunContract(ignored, { label: "diff.ignoreSubmodules=all" });
    assertRunsEquivalent(clean, ignored, repo, "diff.ignoreSubmodules=all");
  });
});

describe("external diff safety", () => {
  it("attribute-driven and GIT_EXTERNAL_DIFF drivers never run", () => {
    const repo = createFixtureRepo("extdiff");
    const scripts = tempDir("extdiff-scripts");
    const attrMarker = path.join(scripts, "attr.marker");
    const envMarker = path.join(scripts, "env.marker");
    const attrScript = path.join(scripts, "attr.sh");
    const envScript = path.join(scripts, "env.sh");
    writeFileSync(attrScript, `#!/bin/sh\ntouch "${attrMarker}"\nexit 1\n`, { mode: 0o755 });
    writeFileSync(envScript, `#!/bin/sh\ntouch "${envMarker}"\nexit 1\n`, { mode: 0o755 });
    write(repo, ".gitattributes", "*.txt diff=myext\n");
    write(repo, "doc.txt", "base doc\n");
    commitAll(repo, "base");
    branch(repo, "subject");
    write(repo, "doc.txt", "subject doc\n");
    commitAll(repo, "subject");
    runGit(repo, ["config", "diff.myext.command", attrScript]);

    const res = runChunker({ repo, env: { GIT_EXTERNAL_DIFF: envScript } });
    assert.equal(res.status, 0);
    assert.ok(!existsSync(attrMarker), "attribute diff driver must not run");
    assert.ok(!existsSync(envMarker), "GIT_EXTERNAL_DIFF must not run");
    const manifest = assertRunContract(res, { label: "extdiff" });
    assert.ok(manifest.units.some((u) => u.path === "doc.txt"), "normal units still produced");
  });
});

describe("documented-limit locks", () => {
  it(".gitattributes '*.txt binary' collapses text diffs to metadata file units", () => {
    const repo = createFixtureRepo("attr-binary");
    write(repo, ".gitattributes", "*.txt binary\n");
    write(repo, "doc.txt", "base doc\nsecond line\n");
    commitAll(repo, "base");
    branch(repo, "subject");
    write(repo, "doc.txt", "subject doc\nsecond line\n");
    commitAll(repo, "subject");
    const run = runChunker({ repo });
    const manifest = assertRunContract(run, { label: "attr-binary" });
    assert.ok(manifest.units.length > 0);
    for (const unit of manifest.units) {
      assert.equal(unit.boundary_kind, "file", `${unit.unit_id} is metadata-only`);
      assert.equal(unit.path, "doc.txt");
      const text = unitText(run, unit);
      assert.match(text, /Binary files .* differ/);
      assert.ok(!text.includes("@@"), "no hunk header for a binary-collapsed file");
    }
  });

  it("diff.orderFile may reorder units but must not change the unit set", () => {
    const repo = createFixtureRepo("order-file");
    for (const name of ["a.txt", "main.txt", "z.txt"]) write(repo, name, `base ${name}\n`);
    commitAll(repo, "base");
    branch(repo, "subject");
    for (const name of ["a.txt", "main.txt", "z.txt"]) write(repo, name, `subject ${name}\n`);
    commitAll(repo, "subject");

    const clean = runChunker({ repo });
    assertRunContract(clean, { label: "order-file clean" });
    const cleanPaths = readManifest(clean.outDir).units.map((u) => u.path);
    assert.deepStrictEqual([...cleanPaths].sort(), ["a.txt", "main.txt", "z.txt"]);

    const orderFile = path.join(tempDir("order-file-list"), "order.txt");
    writeFileSync(orderFile, "z.txt\nmain.txt\na.txt\n");
    runGit(repo, ["config", "diff.orderFile", orderFile]);
    const hostile = runChunker({ repo });
    assertRunContract(hostile, { label: "order-file hostile" });
    const hostilePaths = readManifest(hostile.outDir).units.map((u) => u.path);
    assert.deepStrictEqual([...hostilePaths].sort(), [...cleanPaths].sort(), "same unit set");
    assert.notDeepStrictEqual(hostilePaths, cleanPaths, "orderFile did reorder (limit exercised)");
  });
});

describe("goldens", () => {
  for (const name of discoverFixtures()) {
    it(`golden: ${name}`, async (t) => {
      const mod = await loadFixture(name);
      if (mod.skip) {
        t.skip("fixture unsupported on this platform");
        return;
      }
      const { repo } = await buildFixture(name);
      const run = runChunker({ repo });
      assertRunContract(run, { label: name });
      const result = assertRunMatchesGolden(name, run);
      if (!result.updated) {
        assert.ok(existsSync(path.join(FIXTURES_DIR, name, "expected", "manifest.json")), "golden manifest present");
      }
    });
  }

  it("golden fixture list is non-trivial", () => {
    const fixtures = discoverFixtures();
    assert.ok(fixtures.length >= 14, `expected extensive fixtures, found ${fixtures.length}: ${fixtures.join(", ")}`);
  });
});
