// Golden fixture: one oversized diff file forced through logical block
// grouping (blank-line paragraphs and column-0 def starts), no line splits.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "window grouping: oversized hunks split at block boundaries";

export function build(repo) {
  write(repo, "paragraphs.txt", "para base 1\npara base 2\npara base 3\npara base 4\npara base 5\n");
  write(repo, "defs.py", "# defs base 1\n# defs base 2\n# defs base 3\n");
  commitAll(repo, "base");
  branch(repo, "subject");

  const paragraphs = ["para base 1\npara base 2\npara base 3\npara base 4\npara base 5\n"];
  for (let i = 0; i < 40; i += 1) {
    const para = Array.from({ length: 5 }, (_, j) => `paragraph ${String(i).padStart(2, "0")} line ${j} ${"p".repeat(24)} [para-marker]`);
    paragraphs.push(`${para.join("\n")}\n\n`);
  }
  write(repo, "paragraphs.txt", paragraphs.join(""));

  const defs = ["# defs base 1\n# defs base 2\n# defs base 3\n"];
  for (let i = 0; i < 40; i += 1) {
    const body = Array.from({ length: 3 }, (_, j) => `    body ${j} of def ${String(i).padStart(2, "0")} ${"d".repeat(20)} [defs-marker]`);
    defs.push(`def fn_${String(i).padStart(2, "0")}():\n${body.join("\n")}\n`);
  }
  write(repo, "defs.py", defs.join(""));
  commitAll(repo, "subject");
}
