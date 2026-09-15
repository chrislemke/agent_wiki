#!/usr/bin/env python3
"""PreToolUse hook: raw immutability, verified and sources guards, heading snapshots.

File tools (Write, Edit, MultiEdit, NotebookEdit): deny any path inside raw/. For pages
inside wiki/, compute the post-write frontmatter and deny when `verified` differs from
disk or `sources` loses an entry. Snapshot the file's headings into session state.
Bash: deny write-like commands whose target is inside raw/ or inside wiki/ (patterns in
bash_patterns.json), unless the command invokes an allowlisted plugin script. The wiki
layer skips rm, mv and the git write verbs: deleting or moving a whole page is legitimate
and visible in git, while an in-place edit would slip past the verified and sources guards.
Exit 0 always; denials are JSON on stdout. Silent outside a vault.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hooklib as H  # noqa: E402

import frontmatter as FM  # noqa: E402  (hooklib put scripts/ on sys.path)
import vault as V  # noqa: E402

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
PATTERNS = Path(__file__).resolve().parent / "bash_patterns.json"


def projected_content(event: Dict[str, Any], current: Optional[str]) -> Optional[str]:
    """What the file will contain after the tool runs, or None when unknown."""
    tool = event.get("tool_name")
    tool_input = event.get("tool_input") or {}
    # Claude Code names the fields content / old_string / new_string; the alternate spellings
    # appear in some published examples and cost nothing to accept.
    if tool == "Write":
        content = tool_input.get("content", tool_input.get("file_contents"))
        return str(content) if content is not None else None
    if current is None:
        return None
    if tool == "Edit":
        old = str(tool_input.get("old_string", tool_input.get("old_str", "")))
        new = str(tool_input.get("new_string", tool_input.get("new_str", "")))
        if old == "":
            return current
        return current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)
    if tool == "MultiEdit":
        text = current
        for edit in tool_input.get("edits") or []:
            old = str(edit.get("old_string", ""))
            new = str(edit.get("new_string", ""))
            if old:
                text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
        return text
    return None


def _normalize(value: Any) -> str:
    return json.dumps(FM.as_list(value) if value not in (None, "") else [], sort_keys=True)


VERIFIED_BLOCK_RE = re.compile(r"^verified:.*(?:\n[ \t-].*)*", re.M)
SOURCE_ID_RE = re.compile(r"^\s*-\s*id:\s*(.+?)\s*$", re.M)


def _frontmatter_text(text: str) -> str:
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    return text[3:end] if end >= 0 else text[3:]


def _textual_guard(root: Path, path: Path, current: str, projected: str) -> Optional[str]:
    """When the projected frontmatter cannot be parsed, compare the guarded fields as text.

    Fails closed: a `verified` block that differs, or a source id that disappears, is denied
    even though the YAML is broken. PostToolUse will still warn about the parse error.
    """
    old_fm, new_fm = _frontmatter_text(current), _frontmatter_text(projected)
    old_verified = VERIFIED_BLOCK_RE.findall(old_fm)
    new_verified = VERIFIED_BLOCK_RE.findall(new_fm)
    if old_verified != new_verified:
        return (f"{V.rel(root, path)}: this write changes `verified` (and its frontmatter does not parse). "
                "Leave `verified` exactly as on disk; only /agent-wiki:verify records reviews.")
    lost = [i for i in SOURCE_ID_RE.findall(old_fm) if i not in SOURCE_ID_RE.findall(new_fm)]
    if lost:
        return (f"{V.rel(root, path)}: this write removes source id(s) {', '.join(lost)} from `sources` "
                "(and its frontmatter does not parse). Provenance only grows; keep every existing source entry.")
    return None


def guard_page(root: Path, path: Path, event: Dict[str, Any]) -> Optional[str]:
    """Return a denial reason for a wiki page write, or None."""
    current = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
    projected = projected_content(event, current)
    if projected is None:
        return None
    try:
        new_data, _ = FM.parse_text(projected)
    except FM.FrontmatterError:
        return _textual_guard(root, path, current or "", projected)
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


HEREDOC_INTERPRETER_RE = re.compile(r"\b(?:python3?|node|ruby|perl)\s+(?:-\s+)?<<")
CD_RE = re.compile(r"(?:^|\s)cd(?:\s|$)")


def split_segments(command: str) -> List[str]:
    """Split a command line into pipeline segments, ignoring separators inside quotes.

    A quoted `;` or `|` is an argument, not a separator. Splitting on one tears a command
    away from its target and both halves then look harmless, which is how a sed script such
    as `sed -i '' '/^verified:/,/^sources:/{...;}' page.md` used to slip past every rule.
    """
    segments: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    i = 0
    while i < len(command):
        ch = command[i]
        if quote is not None:
            buf.append(ch)
            quote = None if ch == quote else quote
            i += 1
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch == "\\" and i + 1 < len(command):
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        elif command.startswith("&&", i) or command.startswith("||", i):
            segments.append("".join(buf))
            buf = []
            i += 2
            continue
        elif ch in ";|\n":
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def _guard_layer(cfg: Dict[str, Any], layer: Dict[str, Any], command: str, cwd_inside: bool, exempt_file: Optional[str]) -> Optional[str]:
    """Deny write-like operations on one layer. Each pipeline segment is judged on its own, so an
    allowlisted plugin script never launders a chained command."""
    target = layer["target"]
    cd_into = re.compile(cfg["cd_into"].replace("TARGET", target))
    deny = [r for r in cfg["deny"] if r["name"] not in layer.get("skip_rules", [])]
    xargs_writer = re.compile(layer["xargs"])
    # A script fed on stdin is one program: judge the whole command, not its lines.
    if HEREDOC_INTERPRETER_RE.search(command) and re.search(target, command):
        return layer["reason"].format(rule="inline interpreter")
    inside = cwd_inside  # the shell's cwd persists between Bash calls
    upstream_mentions_target = False
    for segment in split_segments(command):
        if any(re.search(rule["pattern"], segment) for rule in layer.get("allow", [])):
            continue
        # raw/SOURCES.md is the list of restorable sources, not a source: a segment whose only
        # raw/ mentions are that file passes.
        if exempt_file:
            mentions = re.findall(layer["mention"], segment)
            if mentions and all(m.endswith(exempt_file) for m in mentions):
                continue
        if upstream_mentions_target and xargs_writer.search(segment):
            return layer["reason"].format(rule="xargs")
        effective = "" if inside else target
        for rule in deny:
            if re.search(rule["pattern"].replace("TARGET", effective), segment):
                return layer["reason"].format(rule=rule["name"])
        if re.search(target, segment):
            upstream_mentions_target = True
        if cd_into.search(segment):
            inside = True
        elif CD_RE.search(segment):
            inside = False  # cd anywhere else leaves the layer (approximation)
    return None


def guard_bash(root: Path, command: str, cwd: Path) -> Optional[str]:
    """Deny write-like operations on raw/ and on wiki/, in that order."""
    cfg = json.loads(PATTERNS.read_text(encoding="utf-8"))
    reason = _guard_layer(cfg, cfg["layers"]["raw"], command, V.in_raw(root, cwd), V.SOURCES_LIST)
    if reason:
        return reason
    return _guard_layer(cfg, cfg["layers"]["wiki"], command, V.in_wiki(root, cwd), None)


def main() -> int:
    event = H.read_event()
    root = H.find_root(event)
    if root is None:
        return 0
    tool = event.get("tool_name")
    session_id = str(event.get("session_id") or "default")
    if tool == "Bash":
        command = str((event.get("tool_input") or {}).get("command") or "")
        cwd = Path(str(event.get("cwd") or os.getcwd()))
        reason = guard_bash(root, command, cwd)
        if reason:
            H.deny(reason)
        return 0
    if tool in FILE_TOOLS:
        path = H.tool_file_path(event)
        if path is None:
            return 0
        if V.in_raw(root, path) and path.name != V.SOURCES_LIST:
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
