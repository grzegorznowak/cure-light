// Golden fixture: C-quoted paths (embedded quote, backslash, TAB, LF).
// Documented limit: the chunker stores the raw `diff --git` header text as
// `path` rather than a decoded name; the golden locks that exact behavior.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "path corpus: C-quoted names lock the documented limit";
export const skip = process.platform === "win32";

export const quotedNames = ["quote\"q.txt", "back\\slash.txt", "tab\tname.txt", "line\nname.txt"];

export function build(repo) {
  for (const file of quotedNames) write(repo, file, `base content\nsecond base line\n`);
  commitAll(repo, "base");
  branch(repo, "subject");
  for (const file of quotedNames) write(repo, file, `subject content\nsecond base line\n`);
  commitAll(repo, "subject");
}
