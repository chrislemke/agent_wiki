#!/usr/bin/env python3
"""PreToolUse hook: raw immutability, verified and sources guards, heading snapshots.

File tools (Write, Edit, MultiEdit, NotebookEdit): deny any path inside raw/. For pages
inside wiki/, compute the post-write frontmatter and deny when `verified` differs from
disk or `sources` loses an entry. Snapshot the file's headings into session state.
Bash: deny write-like commands whose target is inside raw/ (patterns in
bash_patterns.json), unless the command invokes an allowlisted plugin script.
Exit 0 always; denials are JSON on stdout. Silent outside a vault.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

sys.path.insert(0, str(H.PLUGIN_ROOT / "scripts"))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATTERNS = Path(__file__).resolve().parent / "bash_patterns.json"


def projected_content(event: Dict[str, Any], current: Optional[str]) -> Optional[str]:
    """What the file will contain after the tool runs, or None when unknown."""
    tool = event.get("tool_name")
    ti = event.get("tool_input") or {}
    if tool == "Write":
        content = ti.get("content", ti.get("file_contents"))
        return str(content) if content is not None else None
    if current is None:
        return None
    if tool == "Edit":
        old = str(ti.get("old_string", ti.get("old_str", "")))
        new = str(ti.get("new_string", ti.get("new_str", "")))
        if old == "":
            return current
        return current.replace(old, new) if ti.get("replace_all") else current.replace(old, new, 1)
    if tool == "MultiEdit":
        text = current
        for edit in ti.get("edits") or []:
            old = str(edit.get("old_string", ""))
            new = str(edit.get("new_string", ""))
            if old:
                text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
        return text
    return None


def _normalize(value: Any) -> str:
    return json.dumps(FM.as_list(value) if value not in (None, "") else [], sort_keys=True)


def guard_page(root: Path, path: Path, event: Dict[str, Any]) -> Optional[str]:
    """Return a denial reason for a wiki page write, or None."""
    current = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    projected = projected_content(event, current)
    if projected is None:
        return None
    try:
        new_data, _ = FM.parse_text(projected)
    except FM.FrontmatterError:
        return None  # PostToolUse will warn about unparseable frontmatter
    old_data: Optional[Dict[str, Any]] = None
    if current is not None:
        try:
            old_data, _ = FM.parse_text(current)
        except FM.FrontmatterError:
            old_data = None
    old_verified = _normalize((old_data or {}).get("verified"))
    new_verified = _normalize((new_data or {}).get("verified"))
    if old_verified != new_verified:
        return (f"{V.rel(root, path)}: this write changes `verified`. Only the owner marks pages as reviewed: "
                "leave `verified` exactly as on disk, or ask the owner to run /agent-wiki:verify.")
    old_ids = [str(s.get("id")) for s in FM.as_list((old_data or {}).get("sources")) if isinstance(s, dict)]
    new_ids = [str(s.get("id")) for s in FM.as_list((new_data or {}).get("sources")) if isinstance(s, dict)]
    lost = [i for i in old_ids if i not in new_ids]
    if lost:
        return (f"{V.rel(root, path)}: this write removes source id(s) {', '.join(lost)} from `sources`. "
                "Provenance only grows: keep every existing source entry (append new ones) and augment the page instead of rewriting it.")
    return None


def guard_bash(root: Path, command: str) -> Optional[str]:
    cfg = json.loads(PATTERNS.read_text(encoding="utf-8"))
    for rule in cfg.get("allow", []):
        if re.search(rule["pattern"], command):
            return None
    raw_target = cfg["raw_target"]
    for rule in cfg.get("deny", []):
        pattern = rule["pattern"].replace("RAW", raw_target)
        if re.search(pattern, command):
            return (f"{rule['name']} targeting raw/ is blocked: raw/ is the immutable source layer. "
                    "Read it freely (cat, rg, head, sed -n). To add a source use /agent-wiki:fetch; to change one, ask the owner.")
    return None


def main() -> int:
    event = H.read_event()
    root = H.find_root(event)
    if root is None:
        return 0
    tool = event.get("tool_name")
    session_id = str(event.get("session_id") or "default")
    if tool == "Bash":
        command = str((event.get("tool_input") or {}).get("command") or "")
        reason = guard_bash(root, command)
        if reason:
            H.deny(reason)
        return 0
    if tool in FILE_TOOLS:
        path = H.tool_file_path(event)
        if path is None:
            return 0
        if V.in_raw(root, path):
            H.deny(f"{V.rel(root, path)} is inside raw/, the immutable source layer. Nothing edits raw files; "
                   "to add a source use /agent-wiki:fetch, to replace one ask the owner.")
            return 0
        if V.in_wiki(root, path) and path.suffix == ".md" and not V.is_reserved(path):
            reason = guard_page(root, path, event)
            if reason:
                H.deny(reason)
                return 0
            state = H.SessionState(session_id, root)
            state.note_pre_write(path)
            state.save()
        elif path.resolve() == (root / "log.md").resolve():
            H.SessionState(session_id, root).save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
