#!/usr/bin/env python3
"""Log toolkit: append and read the vault's chronological log.md.

Entry format:
  ## [YYYY-MM-DD] <op> | <title>
  - Created: [[A]], [[B]]
  - Updated: [[C]]
  - Note: free text

Operations: init, fetch, ingest, ingest-failed, query, lint, verify, schema.

Usage:
  log.py append --op OP --title T [--created P [P ...]] [--updated P [P ...]] [--note N] [--vault V]
  log.py parse [--vault V] [--json]
  log.py tail N [--vault V] [--json]
  log.py since-lint [--vault V] [--json]

Exit codes: 0 ok, 2 usage (including unknown operation).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault as V  # noqa: E402

OPERATIONS = ("init", "fetch", "ingest", "ingest-failed", "query", "lint", "verify", "schema")
HEADER_RE = re.compile(r"^## \[(\d{4}-\d{2}-\d{2})\] ([a-z-]+) \| (.*)$")
FIELD_RE = re.compile(r"^- (Created|Updated|Note): (.*)$")


def log_path(root: Path) -> Path:
    return root / "log.md"


def _wikilink(name: str) -> str:
    name = name.strip()
    if name.startswith("[[") and name.endswith("]]"):
        return name
    return f"[[{name}]]"


def format_entry(op: str, title: str, created: List[str], updated: List[str], note: Optional[str], date: Optional[str] = None) -> str:
    lines = [f"## [{date or V.today()}] {op} | {title.strip()}"]
    if created:
        lines.append("- Created: " + ", ".join(_wikilink(c) for c in created))
    if updated:
        lines.append("- Updated: " + ", ".join(_wikilink(u) for u in updated))
    if note:
        lines.append(f"- Note: {note.strip()}")
    return "\n".join(lines) + "\n"


def append(root: Path, op: str, title: str, created: List[str], updated: List[str], note: Optional[str]) -> str:
    if op not in OPERATIONS:
        raise ValueError(f"unknown operation {op!r}; expected one of {', '.join(OPERATIONS)}")
    path = log_path(root)
    existing = path.read_text(encoding="utf-8") if path.is_file() else "# Log\n"
    if not existing.endswith("\n"):
        existing += "\n"
    entry = format_entry(op, title, created, updated, note)
    path.write_text(existing + "\n" + entry, encoding="utf-8")
    return entry


def _split_links(value: str) -> List[str]:
    items = re.findall(r"\[\[([^\]]+)\]\]", value)
    if items:
        return items
    return [v.strip() for v in value.split(",") if v.strip()]


def parse(root: Path) -> List[Dict[str, Any]]:
    path = log_path(root)
    if not path.is_file():
        return []
    entries: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = HEADER_RE.match(line)
        if m:
            current = {"date": m.group(1), "op": m.group(2), "title": m.group(3).strip(), "created": [], "updated": [], "note": None}
            entries.append(current)
            continue
        if current is None:
            continue
        f = FIELD_RE.match(line)
        if f:
            key, value = f.group(1), f.group(2)
            if key == "Created":
                current["created"] = _split_links(value)
            elif key == "Updated":
                current["updated"] = _split_links(value)
            else:
                current["note"] = value.strip()
    return entries


def since_lint(root: Path) -> Dict[str, Any]:
    entries = parse(root)
    last_lint: Optional[str] = None
    count = 0
    for e in entries:
        if e["op"] == "lint":
            last_lint = e["date"]
            count = 0
        elif e["op"] == "ingest":
            count += 1
    return {"ingests_since_lint": count, "last_lint": last_lint}


def _entry_text(e: Dict[str, Any]) -> str:
    return format_entry(e["op"], e["title"], e["created"], e["updated"], e["note"], e["date"])


def _root(args: argparse.Namespace) -> Path:
    return V.require_vault(args.vault)


def _cmd_append(args: argparse.Namespace) -> int:
    try:
        root = _root(args)
        entry = append(root, args.op, args.title, args.created or [], args.updated or [], args.note)
    except (V.VaultError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    print(entry, end="")
    return V.EXIT_OK


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        root = _root(args)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    entries = parse(root)
    if args.json:
        print(json.dumps({"entries": entries}, indent=2, ensure_ascii=False))
    else:
        for e in entries:
            print(f"{e['date']} {e['op']} | {e['title']}")
    return V.EXIT_OK


def _cmd_tail(args: argparse.Namespace) -> int:
    try:
        root = _root(args)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    entries = parse(root)[-args.n :] if args.n > 0 else []
    if args.json:
        print(json.dumps({"entries": entries}, indent=2, ensure_ascii=False))
    else:
        print("\n".join(_entry_text(e) for e in entries), end="")
    return V.EXIT_OK


def _cmd_since_lint(args: argparse.Namespace) -> int:
    try:
        root = _root(args)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    data = since_lint(root)
    if args.json:
        print(json.dumps(data))
    else:
        last = data["last_lint"] or "never"
        print(f"{data['ingests_since_lint']} ingest(s) since last lint ({last})")
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="log.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("append")
    p.add_argument("--op", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--created", nargs="+", action="extend", default=[], help="page(s) created; repeatable")
    p.add_argument("--updated", nargs="+", action="extend", default=[], help="page(s) updated; repeatable")
    p.add_argument("--note", default=None)
    p.add_argument("--vault", default=None)
    p.set_defaults(func=_cmd_append)
    p = sub.add_parser("parse")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_parse)
    p = sub.add_parser("tail")
    p.add_argument("n", type=int)
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_tail)
    p = sub.add_parser("since-lint")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_since_lint)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
