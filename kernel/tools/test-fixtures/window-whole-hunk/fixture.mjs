// Golden fixture: small whole hunks fit inside one unit per file; multi.txt
// carries two separate hunks inside the same unit (hunk_count 2, blocks 2).
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "window grouping: whole hunks fit";

const lines = (n, tag) => Array.from({ length: n }, (_, i) => `${tag} line ${String(i + 1).padStart(2, "0")} [${tag}-marker]`);

export function build(repo) {
  write(repo, "one.txt", `${lines(12, "one").join("\n")}\n`);
  write(repo, "two.txt", `${lines(12, "two").join("\n")}\n`);
  write(repo, "multi.txt", `${lines(24, "multi").join("\n")}\n`);
  commitAll(repo, "base");
  branch(repo, "subject");

  const one = lines(12, "one");
  one[4] = "one line 05 changed [one-marker]";
  write(repo, "one.txt", `${one.join("\n")}\n`);

  const two = lines(12, "two");
  two[6] = "two line 07 changed [two-marker]";
  write(repo, "two.txt", `${two.join("\n")}\n`);

  const multi = lines(24, "multi");
  multi[1] = "multi line 02 changed [multi-marker]";
  multi[20] = "multi line 21 changed [multi-marker]";
  write(repo, "multi.txt", `${multi.join("\n")}\n`);
  commitAll(repo, "subject");
}
