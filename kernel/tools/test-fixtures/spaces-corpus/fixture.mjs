// Golden fixture: spaces in path shapes — trailing space, leading space,
// directory with spaces, double space.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "path corpus: leading/trailing/embedded spaces";

export const expectedPaths = [
  "trail ",
  " x.txt",
  "Untitled Folder/untitled.txt",
  "dir with spaces/file name.txt",
  "two  spaces.txt",
].sort();

export function build(repo) {
  const files = ["trail ", " x.txt", "Untitled Folder/untitled.txt", "dir with spaces/file name.txt", "two  spaces.txt"];
  for (const file of files) write(repo, file, `base content of ${file}\nsecond base line\n`);
  commitAll(repo, "base");
  branch(repo, "subject");
  for (const file of files) write(repo, file, `subject content of ${file}\nsecond base line\n`);
  commitAll(repo, "subject");
}
