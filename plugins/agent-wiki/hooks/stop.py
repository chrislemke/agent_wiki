#!/usr/bin/env python3
"""Stop hook: refuse to end the turn while wiki changes are unlogged or a new page is orphaned.

Blocks with {"decision": "block", "reason": ...} when session state shows wiki pages
touched but log.md unchanged since the accounting window opened, or when a page created
in the window has zero inbound links. Blocks at most once per problem set, and never
when stop_hook_active is set. Every Stop that passes opens a fresh window, so the gate
judges each turn's work rather than only the first one. Silent outside a vault.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

import frontmatter as FM  # noqa: E402  (hooklib put scripts/ on sys.path)
import links as L  # noqa: E402


def main() -> int:
    event = H.read_event()
    if event.get("stop_hook_active"):
        return 0
    root = H.find_root(event)
    if root is None:
        return 0
    session_id = str(event.get("session_id") or "default")
    if not H.state_path(session_id).is_file():
        return 0
    state = H.SessionState(session_id, root)
    problems: List[str] = []
    # A page that no longer exists is no change to account for: a create-then-delete, or a
    # revert, nets out and the message below tells the model exactly that.
    touched = [t for t in state.touched if (root / t).is_file()]
    if touched and not state.log_changed():
        plugin = os.environ.get("CLAUDE_PLUGIN_ROOT") or str(H.PLUGIN_ROOT)
        problems.append(
            "wiki pages changed since the last logged stop but log.md has no new entry: "
            + ", ".join(touched[:8])
            + (" ..." if len(touched) > 8 else "")
            + f". Append one with `python3 {plugin}/scripts/log.py append --op <op> --title <title> --created/--updated ...`, or revert the changes."
        )
    catalog = L.Catalog(root)
    orphans = []
    for rel in state.created:
        page = root / rel
        if not page.is_file():
            continue
        try:
            data, _ = FM.parse_file(page)
        except FM.FrontmatterError:
            data = None
        if (data or {}).get("type") == "source":
            continue  # provenance anchors are catalogued by the index, not linked from prose
        if not L.inbound_links(root, page.stem, catalog):
            orphans.append(f"[[{page.stem}]]")
    if orphans:
        problems.append(
            "page(s) created since the last logged stop with no inbound link: " + ", ".join(orphans)
            + ". Link each from a related page or the Overview, or delete it."
        )
    if not problems:
        state.reset_baseline()
        state.save()
        return 0
    signature = json.dumps(problems, sort_keys=True)
    if state.already_blocked_for(signature):
        # Blocked once for exactly these problems and the model stopped anyway. Let it go
        # (the gate never loops), but open a fresh window so the same pages are caught
        # again the next time they change without a log entry.
        state.reset_baseline()
        state.save()
        return 0
    state.remember_block(signature)
    state.save()
    H.block_stop("agent-wiki: " + " | ".join(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
