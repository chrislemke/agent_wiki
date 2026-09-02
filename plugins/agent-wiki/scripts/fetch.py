#!/usr/bin/env python3
"""Fetch sources into raw/ as markdown with source metadata. The designated writer into raw/.

Usage:
  fetch.py url URL [--vault V] [--stdin] [--title T] [--author A] [--published D] [--fidelity verbatim|summary] [--json]
      Extract the article with `uvx trafilatura` (verbatim markdown). With --stdin the
      content comes from stdin instead (the WebFetch fallback; pass --fidelity summary).
      An extractor header (title/author/url/date) in the content supplies metadata.
  fetch.py github REPO_URL [--files A,B] [--branch B] [--dry-run] [--raw-base URL] [--vault V] [--json]
      Fetch the README plus named files, one raw file each, as verbatim copies.
  fetch.py restore [--vault V] [--json]
      Download every entry of raw/SOURCES.md whose file is missing.
  fetch.py plan-url URL [--json]
      Show how a URL would be fetched (direct download or article extraction).

Raw frontmatter: title, resource, fetched, author, published, fidelity. Refuses to
overwrite an existing raw file. Exit 0 done, 1 problem (exists, download failed), 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as EV  # noqa: E402
import frontmatter as FM  # noqa: E402
import vault as V  # noqa: E402

USER_AGENT = "agent-wiki/0.1 (+https://github.com/chrislemke/agent_wiki)"
RAW_GITHUB = "https://raw.githubusercontent.com/"


class FetchError(Exception):
    pass


# ----------------------------------------------------------------------------- helpers

def safe_filename(title: str) -> str:
    """Title Case filename: drop characters that are illegal in filenames, slashes become dashes."""
    name = re.sub(r'[:*?"<>|]+', "", title)
    name = re.sub(r"[\\/]+", "-", name)
    name = re.sub(r"\s+", " ", name).strip(" .-")
    return name[:120] or "Untitled"


def plan_url(url: str) -> Dict[str, str]:
    """Direct download for markdown-ish resources (gists, GitHub blobs, raw files, file://); extraction otherwise."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if parsed.scheme == "file":
        return {"mode": "download", "url": url}
    if host == "gist.github.com":
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            return {"mode": "download", "url": f"https://gist.githubusercontent.com/{parts[0]}/{parts[1]}/raw"}
    if host == "github.com":
        m = re.match(r"^/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", path)
        if m:
            return {"mode": "download", "url": f"{RAW_GITHUB}{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}"}
    if host in ("raw.githubusercontent.com", "gist.githubusercontent.com") or path.lower().endswith((".md", ".txt", ".markdown")):
        return {"mode": "download", "url": url}
    return {"mode": "extract", "url": url}


def download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 - URLs come from the owner
            data = resp.read()
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise FetchError(f"download failed for {url}: {exc}") from exc
    return data.decode("utf-8", errors="replace")


def extract_article(url: str) -> str:
    cmd = ["uvx", "trafilatura", "-u", url, "--markdown", "--with-metadata", "--formatting", "--links"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FetchError(f"trafilatura failed: {exc}") from exc
    if out.returncode != 0 or not out.stdout.strip():
        raise FetchError(f"trafilatura returned nothing for {url}: {out.stderr.strip()[:300]}")
    return out.stdout


def split_extractor_header(content: str) -> Tuple[Dict[str, Any], str]:
    """Take title/author/url/date from a leading YAML header (trafilatura style), if any."""
    try:
        data, body = FM.parse_text(content)
    except FM.FrontmatterError:
        return {}, content
    if data is None:
        return {}, content
    meta: Dict[str, Any] = {}
    if data.get("title"):
        meta["title"] = str(data["title"])
    if data.get("author"):
        meta["author"] = str(data["author"])
    if data.get("date"):
        meta["published"] = str(data["date"])[:10]
    if data.get("url"):
        meta["resource"] = str(data["url"])
    return meta, body.lstrip("\n")


def write_raw(root: Path, body: str, meta: Dict[str, Any], filename: Optional[str] = None) -> Path:
    """Write raw/<file> with frontmatter title, resource, fetched, author, published, fidelity.

    meta carries title and resource (required), author and published (optional) and fidelity
    (default verbatim). Refuses to overwrite: raw is immutable.
    """
    title = str(meta["title"])
    name = filename or (safe_filename(title) + ".md")
    path = V.raw_dir(root) / name
    if path.exists():
        raise FetchError(f"raw file already exists: {V.rel(root, path)} (raw is immutable; delete it by hand to refetch)")
    data: Dict[str, Any] = {"title": title, "resource": meta["resource"], "fetched": V.today()}
    if meta.get("author"):
        data["author"] = meta["author"]
    if meta.get("published"):
        data["published"] = meta["published"]
    data["fidelity"] = meta.get("fidelity") or "verbatim"
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = [f"{k}: {FM.scalar_out(v)}" for k, v in data.items()]
    path.write_text("---\n" + "\n".join(fm_lines) + "\n---\n\n" + body.strip("\n") + "\n", encoding="utf-8")
    return path


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


# ----------------------------------------------------------------------------- commands

def _cmd_url(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    try:
        if args.stdin:
            content = sys.stdin.read()
            fidelity = args.fidelity or "verbatim"
        else:
            plan = plan_url(args.url)
            content = download(plan["url"]) if plan["mode"] == "download" else extract_article(args.url)
            fidelity = args.fidelity or "verbatim"
        meta, body = split_extractor_header(content)
        title = args.title or meta.get("title") or _title_from_body(body, urllib.parse.urlparse(args.url).path.rstrip("/").split("/")[-1] or args.url)
        path = write_raw(root, body, {"title": title, "resource": args.url, "author": args.author or meta.get("author"), "published": args.published or meta.get("published"), "fidelity": fidelity})
    except FetchError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_FINDINGS
    result = {"path": V.rel(root, path), "title": title, "resource": args.url, "fidelity": fidelity}
    print(json.dumps(result) if args.json else f"fetched {result['path']} ({fidelity})")
    return V.EXIT_OK


def parse_github_url(url: str) -> Tuple[str, str, Optional[str], str]:
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if parsed.netloc.lower() != "github.com" or len(parts) < 2:
        raise FetchError(f"not a GitHub repository URL: {url}")
    owner, repo = parts[0], parts[1].removesuffix(".git")
    branch: Optional[str] = None
    subpath = ""
    if len(parts) >= 4 and parts[2] == "tree":
        branch = parts[3]
        subpath = "/".join(parts[4:])
    return owner, repo, branch, subpath


def github_plan(url: str, files: List[str], branch: Optional[str], raw_base: str) -> List[Dict[str, str]]:
    owner, repo, url_branch, subpath = parse_github_url(url)
    branch = branch or url_branch or "main"
    wanted = ["README.md"] + [f for f in files if f and f != "README.md"]
    plan: List[Dict[str, str]] = []
    for f in wanted:
        rel = f"{subpath}/{f}".strip("/") if subpath else f
        label = " ".join(p for p in [repo, subpath.replace("/", " ") if subpath else "", Path(f).stem] if p)
        plan.append({
            "file": f,
            "url": f"{raw_base}{owner}/{repo}/{branch}/{rel}",
            "resource": f"https://github.com/{owner}/{repo}/blob/{branch}/{rel}",
            "title": label,
            "path": f"raw/{safe_filename(label)}.md",
            "author": owner,
            "branch": branch,
        })
    return plan


def _cmd_github(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
        files = [f.strip() for f in (args.files or "").split(",") if f.strip()]
        plan = github_plan(args.url, files, args.branch, args.raw_base)
    except (V.VaultError, FetchError) as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    if args.dry_run:
        print(json.dumps({"planned": plan}, indent=2) if args.json else "\n".join(f"{p['url']} -> {p['path']}" for p in plan))
        return V.EXIT_OK
    fetched: List[str] = []
    failed: List[Dict[str, str]] = []
    for item in plan:
        try:
            try:
                content = download(item["url"])
            except FetchError:
                if args.branch is None and item["branch"] == "main":
                    alt = item["url"].replace("/main/", "/master/", 1)
                    content = download(alt)
                    item["resource"] = item["resource"].replace("/blob/main/", "/blob/master/", 1)
                else:
                    raise
            path = write_raw(root, content, {"title": item["title"], "resource": item["resource"], "author": item["author"]}, filename=Path(item["path"]).name)
            fetched.append(V.rel(root, path))
        except FetchError as exc:
            failed.append({"file": item["file"], "error": str(exc)})
    result = {"fetched": fetched, "failed": failed}
    print(json.dumps(result, indent=2) if args.json else "\n".join([f"fetched {p}" for p in fetched] + [f"failed {f['file']}: {f['error']}" for f in failed]))
    return V.EXIT_FINDINGS if failed else V.EXIT_OK


def _cmd_restore(args: argparse.Namespace) -> int:
    try:
        root = V.require_vault(args.vault)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    entries = EV.restorable_sources(root)
    restored: List[str] = []
    skipped: List[str] = []
    failed: List[Dict[str, str]] = []
    for file, row in entries.items():
        target = V.raw_dir(root) / file
        if target.exists():
            skipped.append(V.rel(root, target))
            continue
        try:
            plan = plan_url(row["url"])
            content = download(plan["url"]) if plan["mode"] == "download" else extract_article(row["url"])
            meta, body = split_extractor_header(content)
            path = write_raw(root, body, {"title": row["title"] or meta.get("title") or Path(file).stem, "resource": row["url"], "author": meta.get("author"), "published": meta.get("published")}, filename=file)
            restored.append(V.rel(root, path))
        except FetchError as exc:
            failed.append({"file": file, "url": row["url"], "error": str(exc)})
    result = {"restored": restored, "skipped": skipped, "failed": failed}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for p in restored:
            print(f"restored {p}")
        for p in skipped:
            print(f"present  {p}")
        for f in failed:
            print(f"failed   {f['file']}: {f['error']}")
    return V.EXIT_FINDINGS if failed else V.EXIT_OK


def _cmd_plan_url(args: argparse.Namespace) -> int:
    plan = plan_url(args.url)
    print(json.dumps(plan) if args.json else f"{plan['mode']}: {plan['url']}")
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fetch.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("url")
    p.add_argument("url")
    p.add_argument("--vault", default=None)
    p.add_argument("--stdin", action="store_true", help="read the content from stdin instead of fetching")
    p.add_argument("--title", default=None)
    p.add_argument("--author", default=None)
    p.add_argument("--published", default=None)
    p.add_argument("--fidelity", choices=["verbatim", "summary"], default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_url)
    p = sub.add_parser("github")
    p.add_argument("url")
    p.add_argument("--files", default="", help="comma-separated files besides README.md")
    p.add_argument("--branch", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--raw-base", default=RAW_GITHUB)
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_github)
    p = sub.add_parser("restore")
    p.add_argument("--vault", default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_restore)
    p = sub.add_parser("plan-url")
    p.add_argument("url")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_plan_url)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
