#!/usr/bin/env python3
"""Stop hook: refuse to end the turn while wiki changes are unlogged or a new page is orphaned.

Blocks with {"decision": "block", "reason": ...} when session state shows wiki pages
touched but log.md unchanged since the session was first seen, or when a page created
this session has zero inbound links. Blocks at most once per problem set, and never
when stop_hook_active is set. Silent outside a vault.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

sys.path.insert(0, str(H.PLUGIN_ROOT / "scripts"))
import links as L  # noqa: E402


def main() -> int:
    event = H.read_event()
    if event.get("stop_hook_active"):
        return 0
    root = H.find_root(event)
    if root is None:
        return 0
    session_id = str(event.get("session_id") or "default")
    state_path = H._state_path(session_id)
    if not state_path.is_file():
        return 0
    state = H.SessionState(session_id, root)
    problems: List[str] = []
    touched = [t for t in state.data.get("touched", []) if (root / t).is_file() or t in state.data.get("created", [])]
    if touched and not state.log_changed():
        problems.append(
            "wiki pages changed this session but log.md has no new entry: "
            + ", ".join(touched[:8])
            + (" ..." if len(touched) > 8 else "")
            + ". Append one with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op <op> --title <title> --created/--updated ...`, or revert the changes."
        )
    catalog = L.Catalog(root)
    orphans = []
    for rel in state.data.get("created", []):
        page = root / rel
        if not page.is_file():
            continue
        if not L.inbound_links(root, page.stem, catalog):
            orphans.append(f"[[{page.stem}]]")
    if orphans:
        problems.append(
            "page(s) created this session with no inbound link: " + ", ".join(orphans)
            + ". Link each from a related page or the Overview, or delete it."
        )
    if not problems:
        return 0
    signature = json.dumps(problems, sort_keys=True)
    if state.data.get("last_block_signature") == signature:
        return 0
    state.data["last_block_signature"] = signature
    state.save()
    H.block_stop("agent-wiki: " + " | ".join(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
