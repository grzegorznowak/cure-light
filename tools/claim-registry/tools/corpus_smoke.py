#!/usr/bin/env python3
"""Corpus smoke test: frame every PR body in a corpus directory.

Runnable separately from the unit tests::

    python3 tools/corpus_smoke.py --corpus /tmp/prcorpus

Expects JSON files whose top-level value is a list of objects with a ``body``
field (the 918-body research corpus).  Empty bodies are explicit empty-source
records (zero units).  Exits non-zero if any body fails to frame, produces a
partition failure, or crashes.  Prints counts plus the largest observed body.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claim_registry.frame import ExtractionError, frame_source  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="/tmp/prcorpus",
                        help="directory of corpus JSON files")
    parser.add_argument("--pattern", default="*.json")
    parser.add_argument("--determinism", action="store_true",
                        help="re-frame each body and compare (2 runs)")
    args = parser.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.corpus, args.pattern)))
    if not files:
        print(f"no corpus files under {args.corpus!r}", file=sys.stderr)
        return 2

    bodies = 0
    empty = 0
    framed = 0
    blocks = 0
    separators = 0
    kinds: Counter[str] = Counter()
    errors: list[str] = []
    max_body = 0
    max_file = ""

    for path in files:
        with open(path, "rb") as fh:
            docs = json.load(fh)
        for i, doc in enumerate(docs):
            body = doc.get("body") or ""
            src = body.encode("utf-8")
            bodies += 1
            if len(src) > max_body:
                max_body, max_file = len(src), f"{os.path.basename(path)}#{i}"
            if not src:
                empty += 1
                if frame_source(b"").units:
                    errors.append(f"{path}#{i}: empty source produced units")
                else:
                    framed += 1
                continue
            try:
                frame = frame_source(src)
            except ExtractionError as exc:
                errors.append(f"{path}#{i}: extraction error: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001 - smoke test reports crashes
                errors.append(f"{path}#{i}: crash {type(exc).__name__}: {exc}")
                continue
            covered = frame.covered_bytes()
            if covered != len(src):
                errors.append(f"{path}#{i}: partition {covered} != {len(src)}")
                continue
            if args.determinism and frame_source(src).units != frame.units:
                errors.append(f"{path}#{i}: non-deterministic frame")
                continue
            framed += 1
            blocks += frame.block_count
            separators += frame.separator_count
            kinds.update(u.kind for u in frame.units)

    print(f"files={len(files)} bodies={bodies} empty={empty} framed={framed}")
    print(f"blocks={blocks} separators={separators} total_units={blocks + separators}")
    print(f"kinds={dict(sorted(kinds.items()))}")
    print(f"largest_body={max_body} bytes ({max_file})")
    print(f"errors={len(errors)}")
    for err in errors[:20]:
        print(f"  FAIL {err}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
