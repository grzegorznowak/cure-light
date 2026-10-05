// Golden fixture: S3 labeling — an oversized hunk that line-splits, followed
// by (a) a small block in the same hunk and (b) a later whole hunk in the same
// file. Both must be labeled `block`, never line-split.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "S3: line-split labels do not leak past their buffer";

const baseLines = (tag) => Array.from({ length: 600 }, (_, i) => `${tag} base ${String(i).padStart(3, "0")} ${"p".repeat(40)}`);

export function build(repo) {
  write(repo, "same-hunk.txt", `${baseLines("same").join("\n")}\n`);
  write(repo, "cross-hunk.txt", `${baseLines("cross").join("\n")}\n`);
  commitAll(repo, "base");
  branch(repo, "subject");

  // A giant added run (~6.5KB) forces line splits; a blank separator followed
  // by a small added block keeps the small block in the same hunk.
  const giant = (tag) => Array.from({ length: 105 }, (_, i) => `${tag} giant ${String(i).padStart(3, "0")} ${"G".repeat(40)}`);
  const same = baseLines("same").slice(0, 5);
  same.push(...giant("same"), "", "small-marker-same-hunk");
  same.push(...baseLines("same").slice(15));
  write(repo, "same-hunk.txt", `${same.join("\n")}\n`);

  // The later isolated change is a separate whole hunk after the oversized
  // hunk; it must flush as `block`.
  const cross = baseLines("cross").slice(0, 5);
  cross.push(...giant("cross"));
  cross.push(...baseLines("cross").slice(15, 400));
  cross.push("small-marker-cross-hunk");
  cross.push(...baseLines("cross").slice(400));
  write(repo, "cross-hunk.txt", `${cross.join("\n")}\n`);
  commitAll(repo, "subject");
}
