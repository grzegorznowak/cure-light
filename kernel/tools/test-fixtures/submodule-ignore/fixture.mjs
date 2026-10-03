// Golden fixture: submodule pointer change under committed `.gitmodules
// ignore = all`. Without the pinned `--ignore-submodules=none` this diff is
// silently empty; the hardening must keep the pointer unit visible.
import path from "node:path";
import {
  initGitRepo, write, commitAll, commitIndex, stageGitlink, branch, revParse, runGit,
} from "../../chunker-testkit.mjs";

export const title = "submodule pointer change survives committed ignore=all";

export function build(repo) {
  const sub = path.join(path.dirname(repo), "sub");
  initGitRepo(sub);
  write(sub, "s.txt", "sub one\n");
  commitAll(sub, "sub one");
  const oidA = revParse(sub, "main");
  write(sub, "s.txt", "sub two\n");
  commitAll(sub, "sub two");
  const oidB = revParse(sub, "main");

  write(repo, ".gitmodules", "[submodule \"sub\"]\n\tpath = sub\n\turl = ../sub\n\tignore = all\n");
  write(repo, "main.txt", "base line\n");
  runGit(repo, ["add", ".gitmodules", "main.txt"]);
  stageGitlink(repo, oidA, "sub");
  commitIndex(repo, "base");
  branch(repo, "subject");
  stageGitlink(repo, oidB, "sub");
  commitIndex(repo, "subject");
}
