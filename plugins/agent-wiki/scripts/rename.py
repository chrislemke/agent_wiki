#!/usr/bin/env python3
"""Rename or merge a wiki page and rewrite every wikilink to it.

rename: moves the page file within its folder, sets the title, adds the old title
to aliases, rewrites [[Old]], [[Old|alias]], [[Old#heading]] and ![[Old]] across the
wiki (body and frontmatter), and rebuilds the indexes.
merge: unions the loser's sources into the winner, adds the loser's title and
aliases to the winner's aliases, rewrites links from loser to winner, and deletes
the loser only after every link is rewritten. Content merging is the caller's job.
Neither command touches the raw folder.

Usage:
  rename.py rename PAGE NEW_TITLE [--vault V] [--json]
  rename.py merge LOSER WINNER [--vault V] [--json]

Exit codes: 0 done, 2 usage (missing page, target exists, reserved name).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import index as IDX  # noqa: E402
import links as L  # noqa: E402
import vault as V  # noqa: E402


def rewrite_links(root: Path, old: str, new: str, skip: Optional[Path] = None) -> List[Path]:
    """Rewrite wikilinks targeting `old` to `new` in every wiki page. Returns touched pages."""
    pattern = L.link_pattern(old)
    touched: List[Path] = []
    for page in V.iter_pages(root):
        if skip is not None and page.resolve() == skip.resolve():
            continue
        text = page.read_text(encoding="utf-8")
        new_text = pattern.sub(lambda m: m.group(1) + new, text)
        if new_text != text:
            page.write_text(new_text, encoding="utf-8")
            touched.append(page)
    return touched


def _resolve_page(root: Path, ref: str) -> Path:
    path = Path(ref)
    if path.is_file():
        return path
    for p in V.iter_pages(root):
        if p.stem == ref:
            return p
    raise FileNotFoundError(ref)


def _guard(root: Path, path: Path, label: str) -> None:
    if V.in_raw(root, path):
        raise ValueError(f"{label} is inside the raw folder; rename.py never touches raw")
    if not V.in_wiki(root, path):
        raise ValueError(f"{label} is not inside the wiki folder: {path}")


def _add_aliases(data: Dict[str, Any], names: List[str]) -> None:
    aliases = [str(a) for a in FM.as_list(data.get("aliases"))]
    title = str(data.get("title", ""))
    for name in names:
        if name and name not in aliases and name != title:
            aliases.append(name)
    if aliases:
        data["aliases"] = aliases


def rename(root: Path, page: Path, new_title: str) -> Dict[str, Any]:
    _guard(root, page, "page")
    if new_title.strip() in V.RESERVED_BASENAMES or "/" in new_title:
        raise ValueError(f"invalid new title: {new_title!r}")
    target = page.with_name(new_title.strip() + ".md")
    if target.exists():
        raise ValueError(f"target already exists: {V.rel(root, target)}")
    data, body = FM.parse_file(page)
    if data is None:
        raise ValueError("page has no frontmatter")
    old_stem = page.stem
    old_title = str(data.get("title") or old_stem)
    data["title"] = new_title.strip()
    _add_aliases(data, [old_title, old_stem])
    FM.write_page(page, data, body)
    page.rename(target)
    touched = rewrite_links(root, old_stem, target.stem)
    # the page's own self-references, if any
    self_text = target.read_text(encoding="utf-8")
    new_self = L.link_pattern(old_stem).sub(lambda m: m.group(1) + target.stem, self_text)
    if new_self != self_text:
        target.write_text(new_self, encoding="utf-8")
    IDX.build(root)
    return {"old": V.rel(root, page), "new": V.rel(root, target), "links_rewritten_in": [V.rel(root, p) for p in touched]}


def merge(root: Path, loser: Path, winner: Path) -> Dict[str, Any]:
    _guard(root, loser, "loser")
    _guard(root, winner, "winner")
    if loser.resolve() == winner.resolve():
        raise ValueError("loser and winner are the same page")
    ldata, _ = FM.parse_file(loser)
    wdata, wbody = FM.parse_file(winner)
    if ldata is None or wdata is None:
        raise ValueError("both pages need frontmatter")
    # union sources by id
    wsources = [s for s in FM.as_list(wdata.get("sources")) if isinstance(s, dict)]
    have = {str(s.get("id")) for s in wsources}
    for s in FM.as_list(ldata.get("sources")):
        if isinstance(s, dict) and str(s.get("id")) not in have:
            wsources.append(s)
            have.add(str(s.get("id")))
    if wsources:
        wdata["sources"] = wsources
    _add_aliases(wdata, [str(ldata.get("title") or loser.stem), loser.stem] + [str(a) for a in FM.as_list(ldata.get("aliases"))])
    FM.write_page(winner, wdata, wbody)
    touched = rewrite_links(root, loser.stem, winner.stem, skip=loser)
    for alias in FM.as_list(ldata.get("aliases")):
        touched += rewrite_links(root, str(alias), winner.stem, skip=loser)
    loser.unlink()
    IDX.build(root)
    return {"loser": V.rel(root, loser), "winner": V.rel(root, winner), "links_rewritten_in": sorted({V.rel(root, p) for p in touched})}


def _cmd_rename(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault or args.page)
        page = _resolve_page(root, args.page)
        result = rename(root, page, args.new_title)
    except (V.VaultError, FileNotFoundError, ValueError, FM.FrontmatterError) as exc:
        print(f"rename failed: {exc}", file=sys.stderr)
        return V.EXIT_USAGE
    print(json.dumps(result) if args.json else f"renamed {result['old']} -> {result['new']}; links rewritten in {len(result['links_rewritten_in'])} page(s)")
    return V.EXIT_OK


def _cmd_merge(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault or args.loser)
        loser = _resolve_page(root, args.loser)
        winner = _resolve_page(root, args.winner)
        result = merge(root, loser, winner)
    except (V.VaultError, FileNotFoundError, ValueError, FM.FrontmatterError) as exc:
        print(f"merge failed: {exc}", file=sys.stderr)
        return V.EXIT_USAGE
    print(json.dumps(result) if args.json else f"merged {result['loser']} into {result['winner']}; links rewritten in {len(result['links_rewritten_in'])} page(s)")
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rename.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("rename")
    p.add_argument("page")
    p.add_argument("new_title")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_rename)
    p = sub.add_parser("merge")
    p.add_argument("loser")
    p.add_argument("winner")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_merge)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
