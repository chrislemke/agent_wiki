#!/usr/bin/env python3
"""Wikilink resolver for a vault.

Recognises [[Target]], [[Target|Alias]], [[Target#Heading]] and ![[embeds]]; ignores
links inside fenced and inline code. Resolves by basename, then by frontmatter
aliases. Reports resolved, unresolved, near-miss (probable typo) targets and
duplicate basenames across the wiki.

Usage:
  links.py resolve PAGE|VAULT [--json]
  links.py inbound TARGET --vault V [--json]
  links.py extract PAGE [--json]

Exit codes: 0 clean, 1 findings (near-miss, duplicates, or unresolved), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402

LINK_RE = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def strip_code(text: str) -> str:
    """Blank out fenced blocks and inline code while preserving line structure."""
    out: List[str] = []
    fence: Optional[str] = None
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if fence:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append("")
            continue
        if m:
            fence = m.group(1)
            out.append("")
            continue
        out.append(INLINE_CODE_RE.sub(lambda mm: " " * len(mm.group(0)), line))
    return "\n".join(out)


def body_of(text: str) -> str:
    try:
        _, body = FM.split_frontmatter(text)
    except FM.FrontmatterError:
        return text
    return body


def extract_links(text: str, include_frontmatter_sources: bool = False) -> List[Dict[str, Any]]:
    """Return link records: target, alias, heading, embed, line."""
    body = body_of(text)
    cleaned = strip_code(body)
    links: List[Dict[str, Any]] = []
    for lineno, line in enumerate(cleaned.split("\n"), start=1):
        for m in LINK_RE.finditer(line):
            embed = m.group(1) == "!"
            inner = m.group(2)
            target, alias = inner, None
            if "|" in inner:
                target, alias = inner.split("|", 1)
            heading = None
            if "#" in target:
                target, heading = target.split("#", 1)
            target = target.strip()
            if not target:
                continue
            links.append({"target": target, "alias": alias, "heading": heading, "embed": embed, "line": lineno, "raw": m.group(0)})
    return links


def _levenshtein(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
        if min(prev) > cap:
            return cap + 1
    return prev[-1]


class Catalog:
    """Every resolvable name in a vault: page basenames, aliases and non-markdown files."""

    def __init__(self, root: Path):
        self.root = root
        self.pages: List[Path] = list(V.iter_pages(root))
        self.by_basename: Dict[str, List[Path]] = {}
        self.by_alias: Dict[str, List[Path]] = {}
        self.files: Dict[str, List[Path]] = {}
        for p in self.pages:
            self.by_basename.setdefault(p.stem, []).append(p)
            try:
                data, _ = FM.parse_file(p)
            except FM.FrontmatterError:
                data = None
            if data:
                for alias in FM.as_list(data.get("aliases")):
                    self.by_alias.setdefault(str(alias), []).append(p)
        for f in sorted(root.rglob("*")):
            if f.is_file() and f.suffix != ".md" and not any(part.startswith(".") for part in f.relative_to(root).parts):
                self.files.setdefault(f.name, []).append(f)
        self.names_lower: Dict[str, str] = {}
        for name in list(self.by_basename) + list(self.by_alias):
            self.names_lower.setdefault(name.lower(), name)

    def resolve(self, target: str) -> Optional[Path]:
        t = target
        if t.endswith(".md"):
            t = t[:-3]
        # a path-like target resolves by its last component
        t = t.split("/")[-1]
        if t in self.by_basename:
            return self.by_basename[t][0]
        if t in self.by_alias:
            return self.by_alias[t][0]
        if target.split("/")[-1] in self.files:
            return self.files[target.split("/")[-1]][0]
        return None

    def near_miss_candidates(self, target: str) -> List[str]:
        """Existing names that look like typos of target: case-insensitive match or edit distance <= 2."""
        t = target.split("/")[-1]
        scored: List[Tuple[int, str]] = []
        for name in list(self.by_basename) + list(self.by_alias):
            if name == t:
                return []
            if name.lower() == t.lower():
                scored.append((0, name))
                continue
            d = _levenshtein(t, name)
            if d <= 2:
                scored.append((d, name))
        scored.sort()
        out: List[str] = []
        for _, name in scored:
            if name not in out:
                out.append(name)
        return out

    def near_miss(self, target: str) -> Optional[str]:
        candidates = self.near_miss_candidates(target)
        return candidates[0] if candidates else None

    def duplicates(self) -> List[Dict[str, Any]]:
        out = []
        for name, paths in sorted(self.by_basename.items()):
            if len(paths) > 1:
                out.append({"basename": name, "paths": [V.rel(self.root, p) for p in paths]})
        return out


def resolve_pages(root: Path, pages: List[Path], catalog: Optional[Catalog] = None) -> Dict[str, Any]:
    cat = catalog or Catalog(root)
    result: Dict[str, Any] = {"resolved": [], "unresolved": [], "near_miss": [], "duplicates": cat.duplicates()}
    for p in pages:
        text = p.read_text(encoding="utf-8")
        for link in extract_links(text):
            record = {"page": V.rel(root, p), "target": link["target"], "line": link["line"], "raw": link["raw"]}
            hit = cat.resolve(link["target"])
            if hit is not None:
                record["path"] = V.rel(root, hit)
                result["resolved"].append(record)
                continue
            suggestion = cat.near_miss(link["target"])
            if suggestion:
                record["suggestion"] = suggestion
                result["near_miss"].append(record)
            else:
                result["unresolved"].append(record)
    return result


def source_links(text: str) -> List[str]:
    """Targets named in frontmatter sources[].page (a citation is an inbound reference too)."""
    try:
        data, _ = FM.parse_text(text)
    except FM.FrontmatterError:
        return []
    out: List[str] = []
    for entry in FM.as_list((data or {}).get("sources")):
        if isinstance(entry, dict):
            m = re.match(r"^\[\[([^\]|#]+)", str(entry.get("page", "")).strip())
            if m:
                out.append(m.group(1).strip())
    return out


def all_targets(text: str) -> List[str]:
    return [l["target"].split("/")[-1] for l in extract_links(text)] + source_links(text)


def inbound_links(root: Path, target: str, catalog: Optional[Catalog] = None) -> List[Path]:
    """Pages (other than the target itself) that link to target by basename or alias, in the body or in sources[].page."""
    cat = catalog or Catalog(root)
    target_path = cat.resolve(target)
    names = {target}
    if target_path is not None:
        names.add(target_path.stem)
        try:
            data, _ = FM.parse_file(target_path)
        except FM.FrontmatterError:
            data = None
        if data:
            names.update(str(a) for a in FM.as_list(data.get("aliases")))
    hits: List[Path] = []
    for p in cat.pages:
        if target_path is not None and p.resolve() == target_path.resolve():
            continue
        if any(t in names for t in all_targets(p.read_text(encoding="utf-8"))):
            hits.append(p)
    return hits


def _pages_for(target: str) -> Tuple[Path, List[Path]]:
    path = Path(target)
    root = V.require_vault(str(path))
    if path.is_file():
        return root, [path]
    if path.resolve() == root.resolve():
        return root, list(V.iter_pages(root))
    return root, list(V.iter_pages(root, path))


def _cmd_resolve(args: argparse.Namespace) -> int:
    try:
        root, pages = _pages_for(args.target)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    result = resolve_pages(root, pages)
    findings = bool(result["unresolved"] or result["near_miss"] or result["duplicates"])
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for r in result["near_miss"]:
            print(f"{r['page']}:{r['line']}: near-miss [[{r['target']}]] -> did you mean [[{r['suggestion']}]]?")
        for r in result["unresolved"]:
            print(f"{r['page']}:{r['line']}: unresolved [[{r['target']}]] (wanted page)")
        for d in result["duplicates"]:
            print(f"duplicate basename {d['basename']}: {', '.join(d['paths'])}")
        print(f"{len(result['resolved'])} resolved, {len(result['unresolved'])} unresolved, {len(result['near_miss'])} near-miss, {len(result['duplicates'])} duplicate basename(s)")
    return V.EXIT_FINDINGS if findings else V.EXIT_OK


def _cmd_inbound(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    hits = inbound_links(root, args.target)
    payload = {"target": args.target, "count": len(hits), "inbound": [V.rel(root, p) for p in hits]}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for p in payload["inbound"]:
            print(p)
        print(f"{len(hits)} inbound link(s) to [[{args.target}]]")
    return V.EXIT_OK


def _cmd_extract(args: argparse.Namespace) -> int:
    path = Path(args.page)
    links = extract_links(path.read_text(encoding="utf-8"))
    if args.json:
        print(json.dumps(links, indent=2, ensure_ascii=False))
    else:
        for l in links:
            print(l["target"])
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="links.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("resolve")
    p.add_argument("target")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_resolve)
    p = sub.add_parser("inbound")
    p.add_argument("target")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_inbound)
    p = sub.add_parser("extract")
    p.add_argument("page")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_extract)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
