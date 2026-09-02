#!/usr/bin/env python3
"""Raw file hashing: compute SHA-256 of raw files and compare with source pages.

Usage:
  rawhash.py hash FILE
  rawhash.py compare PAGE|VAULT [--json]   Compare each source page's raw_sha with its raw file

Exit codes: 0 all match, 1 mismatch or missing raw file, 2 usage. Read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_page(root: Path, page: Path) -> Optional[Dict[str, Any]]:
    try:
        data, _ = FM.parse_file(page)
    except FM.FrontmatterError:
        return None
    if not data or data.get("type") != "source":
        return None
    raw_rel = str(data.get("raw") or "")
    record: Dict[str, Any] = {"page": V.rel(root, page), "raw": raw_rel, "recorded": data.get("raw_sha")}
    if not raw_rel:
        record["status"] = "no-raw-field"
        return record
    raw_path = root / raw_rel
    if not raw_path.is_file():
        record["status"] = "missing"
        return record
    actual = sha256(raw_path)
    record["actual"] = actual
    record["status"] = "match" if actual == data.get("raw_sha") else "mismatch"
    return record


def compare(root: Path, pages: List[Path]) -> List[Dict[str, Any]]:
    out = []
    for p in pages:
        rec = compare_page(root, p)
        if rec is not None:
            out.append(rec)
    return out


def _cmd_hash(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return V.EXIT_USAGE
    print(sha256(path))
    return V.EXIT_OK


def _cmd_compare(args: argparse.Namespace) -> int:
    path = Path(args.target)
    try:
        root = V.require_vault(str(path))
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    pages = [path] if path.is_file() else list(V.iter_pages(root, None if path.resolve() == root.resolve() else path))
    results = compare(root, pages)
    bad = [r for r in results if r["status"] != "match"]
    if args.json:
        print(json.dumps({"results": results}, indent=2))
    else:
        for r in bad:
            print(f"{r['page']}: raw {r['status']}: {r['raw']}")
        print(f"{len(results) - len(bad)} match, {len(bad)} problem(s)")
    return V.EXIT_FINDINGS if bad else V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rawhash.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("hash")
    p.add_argument("file")
    p.set_defaults(func=_cmd_hash)
    p = sub.add_parser("compare")
    p.add_argument("target")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_compare)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
