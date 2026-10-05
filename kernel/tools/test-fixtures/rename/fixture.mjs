// Golden fixture: rename. `--no-renames` is pinned, so a rename is a delete
// plus an add: two file surfaces, both present in diff order.
import { write, commitAll, branch, runGit } from "../../chunker-testkit.mjs";

export const title = "rename: delete + add under --no-renames";

export function build(repo) {
  write(repo, "old-name.txt", "renamed content line one\nrenamed content line two\n");
  commitAll(repo, "base");
  branch(repo, "subject");
  runGit(repo, ["mv", "old-name.txt", "new-name.txt"]);
  commitAll(repo, "subject");
}
