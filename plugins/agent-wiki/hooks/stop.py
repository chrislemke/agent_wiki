#!/usr/bin/env python3
"""Stop hook: refuse to end the turn while wiki changes are unlogged or a new page is orphaned.

Blocks with {"decision": "block", "reason": ...} when session state shows wiki pages
touched but log.md unchanged since the session was first seen, when a touched page is
named by no log entry added this session, or when a page created this session has zero
inbound links. Blocks at most once per problem set (the anti-loop rule: a model that
changes nothing and ends the turn again goes through), and never when stop_hook_active
is set. Silent outside a vault.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

import frontmatter as FM  # noqa: E402  (hooklib put scripts/ on sys.path)
import links as L  # noqa: E402


def _listed(items: List[str]) -> str:
    return ", ".join(items[:8]) + (" ..." if len(items) > 8 else "")


def _is_logged(root: Path, rel: str, logged: Set[str]) -> bool:
    """A page counts as logged when a new entry names its basename or its title."""
    page = root / rel
    names = {page.stem}
    try:
        data, _ = FM.parse_file(page)
    except FM.FrontmatterError:
        data = None
    title = str((data or {}).get("title") or "").strip()
    if title:
        names.add(title)
    return any(n.casefold() in logged for n in names)


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
    touched = [t for t in state.touched if (root / t).is_file() or t in state.created]
    if touched and not state.log_changed():
        problems.append(
            "wiki pages changed this session but log.md has no new entry: "
            + _listed(touched)
            + ". Append one with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op <op> --title <title> --created/--updated ...`, or revert the changes."
        )
    elif touched:
        logged = state.logged_names()
        unlogged = [t for t in touched if not _is_logged(root, t, logged)]
        if unlogged:
            problems.append(
                "wiki pages changed this session that no new log entry names: "
                + _listed(unlogged)
                + ". An entry about another page does not cover them: name each one in "
                "`--created` or `--updated`, or revert the changes."
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
            "page(s) created this session with no inbound link: " + ", ".join(orphans)
            + ". Link each from a related page or the Overview, or delete it."
        )
    if not problems:
        return 0
    signature = json.dumps(problems, sort_keys=True)
    if state.already_blocked_for(signature):
        return 0
    state.remember_block(signature)
    state.save()
    H.block_stop("agent-wiki: " + " | ".join(problems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
