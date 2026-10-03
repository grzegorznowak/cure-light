// Golden fixture: raw UTF-8 path bytes (core.quotepath=false is passed by the
// chunker, so these headers stay unquoted).
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "path corpus: unicode names stay raw";

export const expectedPaths = ["caf\u00e9.txt", "\u30c6\u30b9\u30c8/\u65e5\u672c\u8a9e.txt", "\u00fcn\u00ef\u00a9.txt"].sort();

export function build(repo) {
  const files = ["caf\u00e9.txt", "\u30c6\u30b9\u30c8/\u65e5\u672c\u8a9e.txt", "\u00fcn\u00ef\u00a9.txt"];
  for (const file of files) write(repo, file, `base content of ${file}\nsecond base line\n`);
  commitAll(repo, "base");
  branch(repo, "subject");
  for (const file of files) write(repo, file, `subject content of ${file}\nsecond base line\n`);
  commitAll(repo, "subject");
}
