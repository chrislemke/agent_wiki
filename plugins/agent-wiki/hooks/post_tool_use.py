#!/usr/bin/env python3
"""PostToolUse hook: warn about invalid frontmatter, vanished headings and near-miss links.

Runs after Write, Edit, MultiEdit or NotebookEdit on a page inside wiki/. Records the
page as touched (and as created when it did not exist before) in session state.
Warnings go to stderr with exit code 2 so the model sees and answers them; the write
itself is never undone. Silent outside a vault.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

import frontmatter as FM  # noqa: E402  (hooklib put scripts/ on sys.path)
import links as L  # noqa: E402
import vault as V  # noqa: E402


def main() -> int:
    event = H.read_event()
    root = H.find_root(event)
    if root is None:
        return 0
    path = H.tool_file_path(event)
    if path is None or not path.is_file():
        return 0
    if not (V.in_wiki(root, path) and path.suffix == ".md" and not V.is_reserved(path)):
        return 0
    session_id = str(event.get("session_id") or "default")
    state = H.SessionState(session_id, root)
    rel = V.rel(root, path)
    before = state.headings_before(rel)
    state.note_post_write(path)
    state.save()

    warnings: List[str] = []
    result = FM.validate_page(path, [str(t) for t in FM.as_list(V.read_settings(root).get("extra_types"))])
    for e in result["errors"]:
        warnings.append(f"{rel}: frontmatter: {e}")
    text = path.read_text(encoding="utf-8", errors="replace")
    after = H.headings_of(text)
    for heading in before:
        if heading not in after:
            warnings.append(f"{rel}: heading removed: '{heading}'. Updates augment pages; restore the section unless the owner asked for a rewrite.")
    links = L.resolve_pages(root, [path])
    for nm in links["near_miss"]:
        warnings.append(f"{rel}:{nm['line']}: [[{nm['target']}]] looks like a typo of [[{nm['suggestion']}]]; fix the link or confirm it is a new wanted page.")
    if warnings:
        print("\n".join(warnings), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
