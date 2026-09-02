#!/usr/bin/env python3
"""Vault detection and shared helpers for the agent-wiki toolkit.

Usage:
  vault.py detect [PATH] [--json]     Print the vault root enclosing PATH (default: cwd)
  vault.py settings [--vault V] [--json]  Print the domain settings block from CLAUDE.md

Exit codes: 0 found/clean, 1 not found, 2 usage error.
Python 3 standard library only. Never writes inside the raw folder.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

MARKER = ".agent-wiki.json"
SCHEMA_VERSION = 1
PLUGIN_VERSION = "0.1.0"
RAW = "raw"
WIKI = "wiki"
ASSETS = "assets"
SOURCES_LIST = "SOURCES.md"
RESERVED_BASENAMES = {"index", "log"}
PAGE_TYPES = ("source", "entity", "concept", "synthesis", "analysis")
TYPE_FOLDERS = {
    "source": "sources",
    "entity": "entities",
    "concept": "concepts",
    "synthesis": "syntheses",
    "analysis": "analyses",
}
# Fixed order for index sections.
TYPE_ORDER = ("synthesis", "entity", "concept", "source", "analysis")
GENERIC_OPEN_RE = re.compile(r"<!--\s*agent-wiki:generic\s+v(\d+)\s*-->")
GENERIC_CLOSE = "<!-- /agent-wiki:generic -->"
DOMAIN_OPEN = "<!-- agent-wiki:domain -->"
DOMAIN_CLOSE = "<!-- /agent-wiki:domain -->"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_USAGE = 2


class VaultError(Exception):
    """Raised when no vault can be found or a path is outside one."""


def today() -> str:
    override = os.environ.get("AGENT_WIKI_TODAY")
    return override or _dt.date.today().isoformat()


def find_vault(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from start (default cwd) to the nearest directory holding the marker."""
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        if (candidate / MARKER).is_file():
            return candidate
    return None


def require_vault(explicit: Optional[str] = None, start: Optional[Path] = None) -> Path:
    if explicit:
        root = find_vault(Path(explicit))
        if root is None:
            raise VaultError(f"no vault found at or above {explicit}")
        return root
    root = find_vault(start)
    if root is None:
        raise VaultError("no vault found: no .agent-wiki.json in this directory or any parent")
    return root


def read_marker(root: Path) -> Dict[str, object]:
    try:
        return json.loads((root / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wiki_dir(root: Path) -> Path:
    return root / WIKI


def raw_dir(root: Path) -> Path:
    return root / RAW


def is_reserved(path: Path) -> bool:
    return path.stem in RESERVED_BASENAMES


def iter_pages(root: Path, scope: Optional[Path] = None) -> Iterable[Path]:
    """Yield every markdown page under wiki/ (or under scope), skipping index and log files."""
    base = scope if scope is not None else wiki_dir(root)
    if base.is_file():
        if base.suffix == ".md" and not is_reserved(base):
            yield base
        return
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*.md")):
        if is_reserved(path):
            continue
        yield path


def iter_raw_files(root: Path) -> Iterable[Path]:
    """Yield raw source files, excluding the assets folder and the restorable sources list."""
    base = raw_dir(root)
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if rel.parts and rel.parts[0] == ASSETS:
            continue
        if rel.as_posix() == SOURCES_LIST:
            continue
        if path.name.startswith("."):
            continue
        yield path


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def in_raw(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(raw_dir(root).resolve())
        return True
    except ValueError:
        return False


def in_wiki(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(wiki_dir(root).resolve())
        return True
    except ValueError:
        return False


def domain_block(root: Path) -> Optional[str]:
    text = (root / "CLAUDE.md").read_text(encoding="utf-8") if (root / "CLAUDE.md").is_file() else ""
    start = text.find(DOMAIN_OPEN)
    end = text.find(DOMAIN_CLOSE)
    if start < 0 or end < 0 or end < start:
        return None
    return text[start + len(DOMAIN_OPEN) : end]


def read_settings(root: Path) -> Dict[str, object]:
    """Return the settings mapping from the fenced yaml block inside the domain block.

    Missing block or unparseable yaml yields defaults, never an exception: a vault
    must stay usable without settings.
    """
    defaults: Dict[str, object] = {
        "language": "en",
        "image_cap": "5",
        "confidential": "false",
        "web_search": "true",
        "tags": [],
        "staleness": {},
        "extra_types": [],
    }
    block = domain_block(root)
    if block is None:
        return defaults
    match = re.search(r"```ya?ml\n(.*?)\n```", block, re.S)
    if not match:
        return defaults
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from frontmatter import FrontmatterError, parse_mapping  # noqa: E402

    try:
        parsed = parse_mapping(match.group(1).splitlines())
    except FrontmatterError:
        return defaults
    merged = dict(defaults)
    merged.update(parsed)
    return merged


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "on", "allowed"}


def pages_for(target: str) -> Tuple[Path, List[Path]]:
    """Resolve a page, a folder or a vault root to (vault root, pages to work on)."""
    path = Path(target)
    root = require_vault(str(path))
    if path.is_file():
        return root, [path]
    if path.resolve() == root.resolve():
        return root, list(iter_pages(root))
    return root, list(iter_pages(root, path))


def _cmd_detect(args: argparse.Namespace) -> int:
    try:
        root = require_vault(args.path)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FINDINGS
    marker = read_marker(root)
    data = {
        "root": str(root),
        "schema_version": marker.get("schema_version"),
        "plugin_version": marker.get("plugin_version"),
        "created": marker.get("created"),
    }
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(str(root))
    return EXIT_OK


def _cmd_settings(args: argparse.Namespace) -> int:
    try:
        root = require_vault(args.vault)
    except VaultError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FINDINGS
    settings = read_settings(root)
    if args.json:
        print(json.dumps(settings, indent=2, ensure_ascii=False))
    else:
        for key, value in settings.items():
            print(f"{key}: {value}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vault.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("detect", help="print the vault root enclosing PATH or the working directory")
    p.add_argument("path", nargs="?", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_detect)
    p = sub.add_parser("settings", help="print the domain settings from CLAUDE.md")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_settings)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
