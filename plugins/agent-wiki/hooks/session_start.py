#!/usr/bin/env python3
"""SessionStart hook: print where the vault stands.

Shows the last five log entries, page counts per type, ingests since the last lint,
the number of stale pages and the three most wanted pages. Plain text on stdout, which
Claude Code adds to the session context. Silent outside a vault.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

import lint as LINT  # noqa: E402  (hooklib put scripts/ on sys.path)
import log as LOG  # noqa: E402
import vault as V  # noqa: E402


def main() -> int:
    event = H.read_event()
    root = H.find_root(event)
    if root is None:
        return 0
    session_id = str(event.get("session_id") or "default")
    H.SessionState(session_id, root).save()

    lines = [f"agent-wiki vault: {root}"]
    entries = LOG.parse(root)[-5:]
    if entries:
        lines.append("Recent log entries:")
        lines.extend(f"  [{e['date']}] {e['op']} | {e['title']}" for e in entries)
    else:
        lines.append("Log is empty.")
    counts = []
    for ptype in V.TYPE_ORDER:
        folder = V.wiki_dir(root) / V.TYPE_FOLDERS[ptype]
        n = len([p for p in folder.glob("*.md") if not V.is_reserved(p)]) if folder.is_dir() else 0
        counts.append(f"{V.TYPE_FOLDERS[ptype]}: {n}")
    lines.append("Pages: " + ", ".join(counts))
    since = LOG.since_lint(root)
    last = since["last_lint"] or "never"
    lines.append(f"{since['ingests_since_lint']} ingest(s) since last lint ({last}).")
    try:
        ctx = LINT.Context(root, None, False)
        stale = LINT.check_stale(ctx)
        wanted = [w for w in LINT.check_wanted(ctx)][:3]
    except Exception as exc:  # noqa: BLE001 - status must never break a session
        stale, wanted = [], []
        lines.append(f"(status checks skipped: {exc})")
    lines.append(f"{len(stale)} stale page(s).")
    if wanted:
        lines.append("Most wanted pages: " + ", ".join(f"[[{w['target']}]] ({w['count']})" for w in wanted))
    lines.append("Skills: /agent-wiki:fetch, /agent-wiki:ingest, /agent-wiki:query, /agent-wiki:lint, /agent-wiki:verify.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
