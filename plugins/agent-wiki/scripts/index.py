#!/usr/bin/env python3
"""Index builder: regenerate the root index and one index per type folder from frontmatter.

The root index keeps a protected curated block, delimited by
<!-- agent-wiki:curated --> ... <!-- /agent-wiki:curated -->, verbatim. It is followed by
one section per page type in a fixed order, entries alphabetical by title as
`- [[Basename]] — description`; source entries add their published date. Pages with
unparseable frontmatter are listed under "Needs attention" rather than dropped.

Usage:
  index.py build [--vault V]
  index.py check [--vault V] [--json]     Exit 1 when the indexes differ from what build would write

Exit codes: 0 clean, 1 drift, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402

CURATED_OPEN = "<!-- agent-wiki:curated -->"
CURATED_CLOSE = "<!-- /agent-wiki:curated -->"
SECTION_TITLES = {
    "synthesis": "Syntheses",
    "entity": "Entities",
    "concept": "Concepts",
    "source": "Sources",
    "analysis": "Analyses",
}


def _entry(root: Path, path: Path, data: Dict[str, Any]) -> str:
    title = str(data.get("title") or path.stem)
    link = f"[[{path.stem}]]" if title == path.stem else f"[[{path.stem}|{title}]]"
    description = str(data.get("description") or "").strip()
    line = f"- {link} — {description}" if description else f"- {link}"
    if data.get("type") == "source" and data.get("published"):
        line += f" (published {data['published']})"
    return line


def collect(root: Path) -> Tuple[Dict[str, List[Tuple[str, str]]], List[Tuple[str, str]]]:
    """Return ({type: [(sort_key, entry)]}, [(rel_path, problem)])."""
    sections: Dict[str, List[Tuple[str, str]]] = {t: [] for t in V.TYPE_ORDER}
    problems: List[Tuple[str, str]] = []
    for path in V.iter_pages(root):
        try:
            data, _ = FM.parse_file(path)
        except FM.FrontmatterError as exc:
            problems.append((V.rel(root, path), str(exc)))
            continue
        if data is None:
            problems.append((V.rel(root, path), "missing frontmatter"))
            continue
        ptype = str(data.get("type") or "")
        if ptype not in sections:
            # unknown or extra types: file them under the folder they live in, else needs attention
            folder = path.relative_to(V.wiki_dir(root)).parts[0] if V.in_wiki(root, path) and len(path.relative_to(V.wiki_dir(root)).parts) > 1 else ""
            by_folder = {v: k for k, v in V.TYPE_FOLDERS.items()}
            if folder in by_folder:
                ptype = by_folder[folder]
            else:
                problems.append((V.rel(root, path), f"unknown type: {ptype or '(none)'}"))
                continue
        title = str(data.get("title") or path.stem)
        sections[ptype].append((title.lower(), _entry(root, path, data)))
    for entries in sections.values():
        entries.sort()
    return sections, problems


def _curated_block(existing: str) -> str:
    start = existing.find(CURATED_OPEN)
    end = existing.find(CURATED_CLOSE)
    if start >= 0 and end > start:
        return existing[start : end + len(CURATED_CLOSE)]
    return f"{CURATED_OPEN}\n## Start here\n\n{CURATED_CLOSE}"


def render_root(root: Path, existing: str) -> str:
    sections, problems = collect(root)
    parts: List[str] = ["# Index", "", _curated_block(existing), ""]
    for ptype in V.TYPE_ORDER:
        entries = sections[ptype]
        if not entries:
            continue
        parts.append(f"## {SECTION_TITLES[ptype]} ({len(entries)})")
        parts.extend(e for _, e in entries)
        parts.append("")
    if problems:
        parts.append("## Needs attention")
        parts.extend(f"- {rel} — {problem}" for rel, problem in problems)
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def render_folder(root: Path, ptype: str) -> str:
    sections, _ = collect(root)
    entries = sections[ptype]
    parts = [f"# {SECTION_TITLES[ptype]} ({len(entries)})", ""]
    parts.extend(e for _, e in entries)
    if entries:
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def planned_writes(root: Path) -> Dict[Path, str]:
    writes: Dict[Path, str] = {}
    root_index = root / "index.md"
    existing = root_index.read_text(encoding="utf-8") if root_index.is_file() else ""
    writes[root_index] = render_root(root, existing)
    for ptype in V.TYPE_ORDER:
        folder = V.wiki_dir(root) / V.TYPE_FOLDERS[ptype]
        if folder.is_dir():
            writes[folder / "index.md"] = render_folder(root, ptype)
    return writes


def build(root: Path) -> List[Path]:
    changed: List[Path] = []
    for path, content in planned_writes(root).items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != content:
            path.write_text(content, encoding="utf-8")
            changed.append(path)
    return changed


def drift(root: Path) -> List[str]:
    out: List[str] = []
    for path, content in planned_writes(root).items():
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != content:
            out.append(V.rel(root, path))
    return out


def _cmd_build(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    changed = build(root)
    for p in changed:
        print(f"wrote {V.rel(root, p)}")
    if not changed:
        print("indexes already current")
    return V.EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    out = drift(root)
    if args.json:
        print(json.dumps({"drift": out}, indent=2))
    else:
        for p in out:
            print(f"index drift: {p}")
        if not out:
            print("indexes current")
    return V.EXIT_FINDINGS if out else V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="index.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("build")
    p.add_argument("--vault", default=None)
    p.set_defaults(func=_cmd_build)
    p = sub.add_parser("check")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_check)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
