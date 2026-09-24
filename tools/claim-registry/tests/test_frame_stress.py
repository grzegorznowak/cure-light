"""Ported adversarial stress corpus (32 docs) from the chunkhound reuse research.

The cases originate from /tmp/frame_stress.py and /tmp/frame_stress2.py (research
scratch), ported here so the acceptance gate is reproducible.
"""

CASES = {
    'adjacent-list-blocks': b'- a\n\n* b\n\n+ c\n',
    'alerts-footnotes': b'> [!IMPORTANT]\n> Check this.\n\nA claim with a footnote[^1].\n\n[^1]: the footnote text\n',
    'big-log-fence': b"Log:\n\n```text\n" + b"x" * 120000 + b"\n```\n",
    'big-table': b"| a | b |\n|---|---|\n" + b"".join(b"| r%d | v |\n" % i for i in range(200)),
    'blockquote-fence': b'> note:\n>\n> ```sh\n> run tests\n> ```\n\nafter\n',
    'consecutive-headings': b'# A\n## B\ntext\n',
    'crlf': b'# Title\r\n\r\n- bullet one\r\n- bullet two\r\n\r\npara\r\n',
    'emoji-heading': b'## \xf0\x9f\x9a\x80 Launch plan\n\nbody\n',
    'fence-in-list': b'- item:\n\n  ```py\n  x = 1\n  ```\n\n- next\n',
    'frontmatter': b'---\ntitle: thing\nowner: x\n---\n\n# Real heading\n\nBody text.\n',
    'hard-breaks-inline': b'First line with hard break  \nsecond line \\\nthird with **bold** and ~~strike~~ and <em>html</em>.\n',
    'html-comment-checklist': b'<!-- - [ ] do not forget X -->\n\nReal text.\n',
    'html-details': b'<details>\n<summary>Full log</summary>\n\nThe *promise* is inside details, in markdown.\n\n</details>\n\n<!-- reviewer note: keep this -->\n\n<table><tr><td>html table</td></tr></table>\n\nline<br>break\n',
    'indented-code': b'Para.\n\n    indented code\n    line two\n\nAfter.\n',
    'list-with-table': b'- item with table\n\n  | a | b |\n  |---|---|\n  | 1 | 2 |\n\n- next\n',
    'lone-cr': b'line one\rline two\r',
    'math-display': b'Claim with display math:\n\n$$\nrate = 5/60\n$$\n\ndone.\n',
    'mdx-ish': b'<Callout type="info">\n\nThis is docs copied into a PR body.\n\n</Callout>\n\nDone.\n',
    'nested-fence-outer-list': b'1. step\n\n   ```md\n   - [ ] inner checklist\n   ```\n\n2. step two\n',
    'nested-lists': b'1. outer\n   - inner a\n   - inner b\n\n   continued paragraph\n2. next\n\n   > quote inside list\n   > more quote\n',
    'no-trailing-newline': b'# Title\n\nbody without newline',
    'pasted-diff-unfenced': b'Fix the thing.\n\n--- a/auth/login.py\n+++ b/auth/login.py\n@@ -1,3 +1,4 @@\n+import limits\n\ndone.\n',
    'quirk-endash': b'1. first item\n2\xe2\x80\x934. continuation line\n',
    'rtl-mixed': b'# \xd8\xb9\xd9\x86\xd9\x88\xd8\xa7\xd9\x86 123\n\n\xd9\x85\xd8\xb1\xd8\xad\xd8\xa8\xd8\xa7 mixed English.\n',
    'script-block': b'<script>\nvar x = 1;\n</script>\n\ntext\n',
    'setext-bom-unicode': b'\xef\xbb\xbfTitle\n=====\n\nSubtitle\n--------\n\n\xf0\x9f\x9a\x80 \xe6\x97\xa5\xe6\x9c\xac\xe8\xaa\x9e \xd8\xb9\xd8\xb1\xd8\xa8\xd9\x8a caf\xc3\xa9 e\xcc\x81\n',
    'setext-then-list': b'Title\n-----\n\n- a\n- b\n',
    'table-escaped': b'| expr | note |\n|------|------|\n| `a\\|b` | escaped pipe |\n| plain | x \\| y |\n',
    'tabs': b'\t- tab item\n  - space item\n\tstray tab line\n',
    'tilde-fence': b'~~~\ncode\n~~~\n\ntext\n',
    'typical': b'# Rate-limit login\n\nCloses #123. This PR hardens login.\n\n- [x] cap failed logins at 5/min per client\n- [ ] return 429 with `Retry-After`\n\n| field | value |\n|-------|-------|\n| window | 60s |\n\n> [!NOTE]\n> see docs: <https://example.com/guide>\n\n![diagram](https://example.com/x.png)\n',
    'unclosed-fence': b'Before fence.\n\n```\ndef login():\n    ...\n',
}

import hashlib

import pytest

from claim_registry.frame import frame_source


@pytest.mark.parametrize("name", sorted(CASES))
def test_stress_doc_frames(name):
    src = CASES[name]
    frame = frame_source(src)
    units = list(frame.units)

    # STRICT partition: gapless, ordered, full coverage
    pos = 0
    for u in units:
        assert u.start == pos, f"{name}: gap/overlap at {pos} -> {u.start}"
        pos = u.end
    assert pos == len(src), f"{name}: partition ends at {pos}, len {len(src)}"
    assert frame.covered_bytes() == len(src)

    # separators are whitespace-only
    for u in units:
        if u.kind == "separator":
            assert not src[u.start:u.end].strip(b" \t\r\n"), (name, u)

    # spans line-aligned; hashes exact
    for u in units:
        assert u.start == 0 or src[u.start - 1:u.start] == b"\n", (name, u)
        assert u.end == len(src) or src[u.end - 1:u.end] == b"\n", (name, u)
        assert u.sha256 == hashlib.sha256(src[u.start:u.end]).hexdigest(), (name, u)

    # determinism over three runs
    assert frame_source(src).units == frame_source(src).units == frame.units
