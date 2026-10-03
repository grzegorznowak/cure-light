// Golden fixture: ordinary multi-file diff — two modified files (one with two
// hunks) plus one added file. Every content line carries a unique per-file
// marker so tests can assert units never mix files.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "basic multi-file diff: multiple files and hunks";

const lines = (n, tag) => Array.from({ length: n }, (_, i) => `${tag} line ${String(i + 1).padStart(2, "0")} [${tag}-marker]`);

export function build(repo) {
  write(repo, "alpha.txt", `${lines(20, "alpha").join("\n")}\n`);
  write(repo, "beta.txt", `${lines(15, "beta").join("\n")}\n`);
  commitAll(repo, "base");
  branch(repo, "subject");

  const alpha = lines(20, "alpha");
  alpha[1] = "alpha line 02 changed [alpha-marker]";
  alpha[14] = "alpha line 15 changed [alpha-marker]";
  write(repo, "alpha.txt", `${alpha.join("\n")}\n`);

  const beta = lines(15, "beta");
  beta[4] = "beta line 05 changed [beta-marker]";
  write(repo, "beta.txt", `${beta.join("\n")}\n`);

  write(repo, "gamma/new.txt", `${lines(8, "gamma").join("\n")}\n`);
  commitAll(repo, "subject");
}
