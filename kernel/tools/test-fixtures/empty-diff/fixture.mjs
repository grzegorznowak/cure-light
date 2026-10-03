// Golden fixture: base and subject resolve to the same commit — a valid but
// empty inventory (0 units, 0 files) that must still publish a manifest.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "empty diff: valid 0-unit manifest";

export function build(repo) {
  write(repo, "only.txt", "content that never changes\n");
  commitAll(repo, "base");
  branch(repo, "subject");
}
