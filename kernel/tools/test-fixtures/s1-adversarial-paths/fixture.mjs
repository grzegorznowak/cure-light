// Golden fixture: S1 path recall — names that contain " b/" (the separator the
// header parser must not confuse) plus the bare names `a` and `b`.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "S1 path corpus: b/-shaped names, bare a/b";

export const expectedPaths = [
  "x b/y.txt",
  "a b/c b/d.txt",
  "a b/a b/c.txt",
  "x b/x b/y.txt",
  "a",
  "b",
].sort();

export function build(repo) {
  const files = ["x b/y.txt", "a b/c b/d.txt", "a b/a b/c.txt", "x b/x b/y.txt", "a", "b"];
  for (const file of files) write(repo, file, `base content of ${file}\nsecond base line\n`);
  commitAll(repo, "base");
  branch(repo, "subject");
  for (const file of files) write(repo, file, `subject content of ${file}\nsecond base line\n`);
  commitAll(repo, "subject");
}
