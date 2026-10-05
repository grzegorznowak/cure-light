// Golden fixture: binary content change. Git emits a no-hunk
// "Binary files ... differ" block, which must surface as one `file` unit with
// no code payload.
import { write, commitAll, branch } from "../../chunker-testkit.mjs";

export const title = "binary no-hunk surface: file unit";

const binary = (tail) => Buffer.concat([Buffer.from([0x00, 0x01, 0x02, 0x7f, 0xff]), Buffer.from(tail), Buffer.from([0x00])]);

export function build(repo) {
  write(repo, "blob.bin", binary("base"));
  write(repo, "plain.txt", "plain base\n");
  commitAll(repo, "base");
  branch(repo, "subject");
  write(repo, "blob.bin", binary("subject"));
  write(repo, "plain.txt", "plain subject\n");
  commitAll(repo, "subject");
}
