// Golden fixture: file without a trailing newline; the diff carries
// "\ No newline at end of file" and the unit payload still must not end 0x0a.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "no-EOL file: payload byte length and terminal newline";

export function build(repo) {
  write(repo, "no-eol.txt", "first line\nsecond line\nno newline at end");
  commitAll(repo, "base");
  branch(repo, "subject");
  write(repo, "no-eol.txt", "first line changed\nsecond line\nno newline at end");
  commitAll(repo, "subject");
}
