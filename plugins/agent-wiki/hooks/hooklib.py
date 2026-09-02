"""Shared helpers for the agent-wiki hooks: event input, vault detection, session state.

Session state is one JSON file per session id, kept outside the vault in the system
temporary directory (override with AGENT_WIKI_STATE_DIR). It records pages created and
touched this session, pre-write heading snapshots, the log hash when the session was
first seen, and the signature of the last Stop block so the gate never loops.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402

HEADING_RE = re.compile(r"^(#{1,2})\s+(.+?)\s*$", re.M)


def read_event() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read()
    except OSError:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def tool_file_path(event: Dict[str, Any]) -> Optional[Path]:
    tool_input = event.get("tool_input") or {}
    fp = tool_input.get("file_path") or tool_input.get("path") or tool_input.get("notebook_path")
    if not fp:
        return None
    path = Path(str(fp))
    if not path.is_absolute():
        path = Path(str(event.get("cwd") or os.getcwd())) / path
    return path


def find_root(event: Dict[str, Any]) -> Optional[Path]:
    """Vault enclosing the event's cwd, else the one enclosing the tool's target file."""
    cwd = Path(str(event.get("cwd") or os.getcwd()))
    root = V.find_vault(cwd)
    if root is None:
        target = tool_file_path(event)
        if target is not None:
            root = V.find_vault(target.parent if not target.exists() else target)
    return root


def state_dir() -> Path:
    override = os.environ.get("AGENT_WIKI_STATE_DIR")
    d = Path(override) if override else Path(tempfile.gettempdir()) / "agent-wiki"
    d.mkdir(parents=True, exist_ok=True)
    return d


def state_path(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default")
    return state_dir() / f"{safe}.json"


def file_hash(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SessionState:
    def __init__(self, session_id: str, root: Path):
        self.path = state_path(session_id)
        self.root = root
        self.data: Dict[str, Any] = {
            "vault": str(root),
            "created": [],
            "touched": [],
            "existed": {},
            "headings": {},
            "log_hash_at_start": None,
            "last_block_signature": None,
        }
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict) and loaded.get("vault") == str(root):
                    self.data.update(loaded)
            except (OSError, ValueError):
                pass
        if self.data.get("log_hash_at_start") is None:
            self.data["log_hash_at_start"] = file_hash(root / "log.md") or ""

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def rel(self, path: Path) -> str:
        return V.rel(self.root, path)

    def note_pre_write(self, path: Path) -> None:
        rel = self.rel(path)
        if rel not in self.data["existed"]:
            self.data["existed"][rel] = path.is_file()
        if path.is_file():
            self.data["headings"][rel] = headings_of(path.read_text(encoding="utf-8", errors="replace"))
        else:
            self.data["headings"][rel] = []

    def note_post_write(self, path: Path) -> None:
        rel = self.rel(path)
        if rel not in self.data["touched"]:
            self.data["touched"].append(rel)
        existed_before = self.data["existed"].get(rel, True)
        if not existed_before and rel not in self.data["created"]:
            self.data["created"].append(rel)

    def log_changed(self) -> bool:
        return (file_hash(self.root / "log.md") or "") != (self.data.get("log_hash_at_start") or "")

    @property
    def touched(self) -> List[str]:
        return list(self.data.get("touched", []))

    @property
    def created(self) -> List[str]:
        return list(self.data.get("created", []))

    def headings_before(self, rel: str) -> List[str]:
        return list(self.data.get("headings", {}).get(rel, []))

    def already_blocked_for(self, signature: str) -> bool:
        return self.data.get("last_block_signature") == signature

    def remember_block(self, signature: str) -> None:
        self.data["last_block_signature"] = signature


def headings_of(text: str) -> List[str]:
    try:
        _, body = FM.split_frontmatter(text)
    except FM.FrontmatterError:
        body = text
    return [m.group(2).strip() for m in HEADING_RE.finditer(body)]


def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}))


def block_stop(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))
