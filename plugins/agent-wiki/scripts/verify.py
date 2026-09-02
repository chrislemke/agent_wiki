#!/usr/bin/env python3
"""Record a human review on a page: append a `verified` entry and touch nothing else.

Usage:
  verify.py PAGE --by HUMAN_ID [--vault V] [--json]

HUMAN_ID is recorded as `human:<id>` (a `human:` prefix is kept as given). The date is
today. The rest of the file stays byte-identical. Exit 0 done, 1 page problem, 2 usage.
This is the only plugin script the PreToolUse guard lets change `verified`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402


def _block_end(lines: List[str], start: int) -> int:
    """Index after a top-level key's block (its indented or dash-led continuation lines)."""
    i = start + 1
    while i < len(lines) and (lines[i].startswith((" ", "\t")) or lines[i].startswith("- ") or not lines[i].strip()):
        if not lines[i].strip():
            # blank lines inside frontmatter are unusual; stop the block here
            break
        i += 1
    return i


def add_verified(text: str, actor: str, date: str) -> str:
    fm_lines, body = FM.split_frontmatter(text)
    if fm_lines is None:
        raise FM.FrontmatterError("missing frontmatter")
    data = FM.parse_mapping(fm_lines)
    if data is None:
        raise FM.FrontmatterError("missing frontmatter")
    existing = [v for v in FM.as_list(data.get("verified")) if isinstance(v, dict)]
    existing.append({"by": actor, "at": date})
    new_block = ["verified:"] + [f"  - by: {FM.scalar_out(v.get('by', ''))}\n    at: {FM.scalar_out(v.get('at', ''))}" for v in existing]
    new_block_lines: List[str] = []
    for item in new_block:
        new_block_lines.extend(item.split("\n"))
    lines = list(fm_lines)
    # drop the old verified block
    for i, line in enumerate(lines):
        if line.startswith("verified:"):
            end = _block_end(lines, i)
            del lines[i:end]
            insert_at = i
            break
    else:
        insert_at = None
    if insert_at is None:
        insert_at = len(lines)
        for i, line in enumerate(lines):
            if line.startswith("generated:"):
                insert_at = _block_end(lines, i)
                break
        else:
            for i, line in enumerate(lines):
                if line.split(":", 1)[0] in ("stale_after", "sources", "question", "raw"):
                    insert_at = i
                    break
    lines[insert_at:insert_at] = new_block_lines
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="verify.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("page")
    parser.add_argument("--by", required=True, help="human id, e.g. chris or human:chris")
    parser.add_argument("--vault", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.page)
    try:
        root = V.require_vault(args.vault or str(path))
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return V.EXIT_USAGE
    if V.in_raw(root, path) or not V.in_wiki(root, path) or path.suffix != ".md" or V.is_reserved(path):
        print(f"refusing: {V.rel(root, path)} is not a wiki page", file=sys.stderr)
        return V.EXIT_USAGE
    actor = args.by if args.by.startswith("human:") else f"human:{args.by}"
    try:
        new_text = add_verified(path.read_text(encoding="utf-8"), actor, V.today())
    except FM.FrontmatterError as exc:
        print(f"{V.rel(root, path)}: {exc}", file=sys.stderr)
        return V.EXIT_FINDINGS
    path.write_text(new_text, encoding="utf-8")
    if args.json:
        print(json.dumps({"page": V.rel(root, path), "verified": {"by": actor, "at": V.today()}}))
    else:
        print(f"verified {V.rel(root, path)} by {actor} on {V.today()}")
    return V.EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
