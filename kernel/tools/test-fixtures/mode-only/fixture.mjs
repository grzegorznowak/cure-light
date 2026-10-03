// Golden fixture: mode-only change (chmod +x) — a no-hunk surface that must
// stay visible as one `file` unit with no ranges, exempt from the ceiling.
import { write, commitAll, branch, setMode } from "../../chunker-testkit.mjs";

export const title = "mode-only change: single file unit";

export function build(repo) {
  write(repo, "mode.txt", "base mode line\n");
  commitAll(repo, "base");
  branch(repo, "subject");
  setMode(repo, "mode.txt", 0o755);
  commitAll(repo, "subject");
}
