// Path-shape suite for kernel/tools/chunker.mjs — S1 recall corpus, unicode,
// C-quoted and non-UTF-8 documented limits. Run with:
//
//   node --test "kernel/tools/*.test.mjs"
import { after, describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import {
  assertRunContract, buildFixture, cleanupTempDirs, gitDiffRaw,
  readManifest, runChunker,
} from "./chunker-testkit.mjs";

after(cleanupTempDirs);

const pathsOf = (run) => readManifest(run.outDir).units.map((u) => u.path);

describe("S1 path corpus", () => {
  it("' b/'-shaped names and bare a/b are recalled exactly", async () => {
    const { repo } = await buildFixture("s1-adversarial-paths");
    const run = runChunker({ repo });
    assertRunContract(run, { label: "s1-adversarial-paths" });
    const expected = [
      "a",
      "a b/a b/c.txt",
      "a b/c b/d.txt",
      "b",
      "x b/x b/y.txt",
      "x b/y.txt",
    ];
    assert.deepStrictEqual([...pathsOf(run)].sort(), [...expected].sort());
    for (const name of expected) {
      assert.ok(pathsOf(run).includes(name), `path recalled exactly: ${JSON.stringify(name)}`);
    }
  });

  it("leading/trailing/embedded spaces are recalled exactly", async () => {
    const { repo } = await buildFixture("spaces-corpus");
    const run = runChunker({ repo });
    assertRunContract(run, { label: "spaces-corpus" });
    const expected = [
      " x.txt",
      "Untitled Folder/untitled.txt",
      "dir with spaces/file name.txt",
      "trail ",
      "two  spaces.txt",
    ];
    assert.deepStrictEqual([...pathsOf(run)].sort(), [...expected].sort());
    for (const name of expected) {
      assert.ok(pathsOf(run).includes(name), `path recalled exactly: ${JSON.stringify(name)}`);
    }
  });

  it("raw unicode names stay unquoted and exact", async () => {
    const { repo } = await buildFixture("unicode-paths");
    const run = runChunker({ repo });
    assertRunContract(run, { label: "unicode-paths" });
    const paths = pathsOf(run);
    assert.ok(paths.includes("caf\u00e9.txt"), "café.txt exact");
    assert.ok(paths.includes("\u30c6\u30b9\u30c8/\u65e5\u672c\u8a9e.txt"), "Japanese path exact");
    assert.ok(paths.includes("\u00fcn\u00ef\u00a9.txt"), "composed latin path exact");
    assert.ok(paths.every((p) => !p.startsWith("diff --git ")), "no header fallback for raw unicode names");
  });
});

describe("documented path limits", () => {
  it("C-quoted names store the raw header text as path", async () => {
    const { repo } = await buildFixture("quoted-paths");
    const run = runChunker({ repo });
    assertRunContract(run, { label: "quoted-paths" });
    const rawHeaders = gitDiffRaw(repo).split("\n").filter((line) => line.startsWith("diff --git "));
    assert.equal(rawHeaders.length, 4, "four quoted surfaces");
    assert.deepStrictEqual(pathsOf(run), rawHeaders, "each path equals its raw header line");
    assert.ok(pathsOf(run).every((p) => p.startsWith("diff --git \"a/")), "documented raw-header fallback");
  });

  it("non-UTF-8 name decodes lossily to U+FFFD, deterministically", { skip: process.platform !== "linux" }, async () => {
    const { repo } = await buildFixture("non-utf8-path");
    const run = runChunker({ repo });
    assertRunContract(run, { label: "non-utf8-path" });
    assert.deepStrictEqual(pathsOf(run), ["l\ufffd.txt"], "lossy replacement path");
    const rerun = runChunker({ repo });
    assertRunContract(rerun, { label: "non-utf8-path rerun" });
    assert.deepStrictEqual(pathsOf(rerun), pathsOf(run), "lossy path is deterministic");
    const unit = readManifest(run.outDir).units[0];
    assert.equal(readFileSync(path.join(run.outDir, unit.file), "utf8").includes("l\ufffd.txt"), true);
  });
});
