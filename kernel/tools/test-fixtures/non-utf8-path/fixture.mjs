// Golden fixture: non-UTF-8 path byte. Documented limit: the diff stream is
// decoded as UTF-8, so the name becomes lossy U+FFFD; the golden locks the
// exact lossy path and payload. Linux-only: other filesystems reject or
// normalize raw non-UTF-8 names.
import { writeFileSync } from "node:fs";
import path from "node:path";
import { commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "path corpus: non-UTF-8 name lossy decode lock";
export const skip = process.platform !== "linux";

// "l" 0xE9 ".txt": 0xE9 alone is an invalid UTF-8 sequence.
const rawName = () => Buffer.concat([Buffer.from("l"), Buffer.from([0xe9]), Buffer.from(".txt")]);

export function build(repo) {
  const abs = () => Buffer.concat([Buffer.from(`${repo}${path.sep}`), rawName()]);
  writeFileSync(abs(), "base non-utf8\n");
  commitAll(repo, "base");
  branch(repo, "subject");
  writeFileSync(abs(), "subject non-utf8\n");
  commitAll(repo, "subject");
}
