#!/usr/bin/env python3
"""Lint checkers and aggregator for a vault.

Every checker is report-first. The only mutations are the explicit auto-fix policy
(regenerate indexes, normalise frontmatter key order, add `created` when derivable
from git, fix a link whose target is a unique near-miss) and they never touch raw/.

Usage:
  lint.py all [--vault V] [--scope PATH] [--fix] [--json]
  lint.py <checker> [--vault V] [--scope PATH] [--json]

Checkers: frontmatter, index, links, wanted, stale, review, footnotes, duplicates,
orphans, tags, rawhash, backlog, generic-block, git, reserved, evidence.

Finding: {type, severity, page, detail, action, ...}. Severity is one of
auto-fixed, fixable, judgement, informational (fixable is what --fix would change).
Exit codes: 0 clean, 1 judgement or fixable findings remain, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evidence as EV  # noqa: E402
import frontmatter as FM  # noqa: E402
import index as IDX  # noqa: E402
import links as L  # noqa: E402
import rawhash as RH  # noqa: E402
import vault as V  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_GENERIC = PLUGIN_ROOT / "references" / "generic-block.md"
HUB_PAGE = "Overview"
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
FOOTNOTE_DEF_RE = re.compile(r"^\[\^([^\]]+)\]:", re.M)

Finding = Dict[str, Any]


def finding(ftype: str, severity: str, page: Optional[str], detail: str, action: str, **extra: Any) -> Finding:
    f: Finding = {"type": ftype, "severity": severity, "page": page, "detail": detail, "action": action}
    f.update(extra)
    return f


class Context:
    def __init__(self, root: Path, scope: Optional[Path], fix: bool):
        self.root = root
        self.scope = scope
        self.fix = fix
        self.catalog = L.Catalog(root)
        self.pages: List[Path] = list(V.iter_pages(root, scope)) if scope else list(self.catalog.pages)
        self.parsed: Dict[Path, Optional[Dict[str, Any]]] = {}
        self.parse_errors: Dict[Path, str] = {}
        for p in self.catalog.pages:
            try:
                data, _ = FM.parse_file(p)
                self.parsed[p] = data
            except FM.FrontmatterError as exc:
                self.parsed[p] = None
                self.parse_errors[p] = str(exc)
        self.settings = V.read_settings(root)
        self.today = V.today()
        self._git_root: Optional[Path] = self._detect_git()

    def _detect_git(self) -> Optional[Path]:
        try:
            out = subprocess.run(["git", "-C", str(self.root), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
        except OSError:
            return None
        return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None

    def git(self, *args: str) -> Optional[str]:
        if self._git_root is None:
            return None
        out = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None

    def rel(self, p: Path) -> str:
        return V.rel(self.root, p)

    def in_scope(self, p: Path) -> bool:
        if self.scope is None:
            return True
        try:
            p.resolve().relative_to(self.scope.resolve())
            return True
        except ValueError:
            return False


# ----------------------------------------------------------------------------- checkers

def check_frontmatter(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    extra_types = [str(t) for t in FM.as_list(ctx.settings.get("extra_types"))]
    for p in ctx.pages:
        rel = ctx.rel(p)
        if p in ctx.parse_errors:
            out.append(finding("frontmatter-invalid", "judgement", rel, ctx.parse_errors[p], "rewrite the frontmatter within the documented YAML subset"))
            continue
        data = ctx.parsed.get(p)
        if data is None:
            out.append(finding("frontmatter-invalid", "judgement", rel, "missing frontmatter", "add frontmatter with type, title, description, created, generated"))
            continue
        errors, _ = FM.validate_data(data, extra_types)
        missing_created = "missing required field: created" in errors
        missing_generated = "missing required field: generated" in errors
        other = [e for e in errors if e not in ("missing required field: created", "missing required field: generated")]
        if missing_created:
            date = ctx.git("log", "--diff-filter=A", "--follow", "--format=%cs", "--", str(p))
            first = date.split("\n")[-1] if date else None
            if first:
                if ctx.fix:
                    text = p.read_text(encoding="utf-8")
                    d, body = FM.parse_text(text)
                    assert d is not None
                    d["created"] = first
                    FM.write_page(p, d, body)
                    out.append(finding("created-missing", "auto-fixed", rel, f"created set to {first} from git history", "none"))
                else:
                    out.append(finding("created-missing", "fixable", rel, f"created missing; derivable from git ({first})", "run lint --fix"))
            else:
                out.append(finding("created-missing", "judgement", rel, "created missing and no git history to derive it from", "set created by hand"))
        if missing_generated:
            out.append(finding("generated-missing", "judgement", rel, "generated missing; never invented by lint", "stamp the page with frontmatter.py stamp --by <actor> after confirming who wrote it"))
        for e in other:
            out.append(finding("frontmatter-invalid", "judgement", rel, e, "fix the field"))
        text = p.read_text(encoding="utf-8")
        canonical = FM.render(data, FM.parse_text(text)[1])
        if canonical != text and not errors:
            # Normalising drops YAML comments. Report rather than silently lose them.
            lossy = FM.dropped_comments(text)
            if lossy:
                lines = ", ".join(f"line {n}" for n, _ in lossy)
                out.append(finding("frontmatter-order", "judgement", rel,
                                   f"frontmatter contains comments that normalising would drop ({lines})",
                                   "quote values or move comments into the body, then run lint --fix"))
            elif ctx.fix:
                p.write_text(canonical, encoding="utf-8")
                out.append(finding("frontmatter-order", "auto-fixed", rel, "frontmatter normalised to canonical key order", "none"))
            else:
                out.append(finding("frontmatter-order", "fixable", rel, "frontmatter keys not in canonical order", "run lint --fix"))
    return out


def check_index(ctx: Context) -> List[Finding]:
    drift = IDX.drift(ctx.root)
    if not drift:
        return []
    if ctx.fix:
        IDX.build(ctx.root)
        return [finding("index-drift", "auto-fixed", p, "index regenerated", "none") for p in drift]
    return [finding("index-drift", "fixable", p, "index does not match the pages on disk", "run lint --fix or index.py build") for p in drift]


def _rewrite_link(page: Path, old: str, new: str) -> None:
    text = page.read_text(encoding="utf-8")
    page.write_text(L.link_pattern(old).sub(lambda m: m.group(1) + new, text), encoding="utf-8")


def check_links(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    result = L.resolve_pages(ctx.root, ctx.pages, ctx.catalog)
    handled: set = set()
    for nm in result["near_miss"]:
        key = (nm["page"], nm["target"])
        if key in handled:
            continue
        handled.add(key)
        candidates = ctx.catalog.near_miss_candidates(nm["target"])
        if len(candidates) == 1:
            if ctx.fix:
                _rewrite_link(ctx.root / nm["page"], nm["target"], candidates[0])
                out.append(finding("near-miss-link", "auto-fixed", nm["page"], f"[[{nm['target']}]] -> [[{candidates[0]}]]", "none", target=nm["target"], suggestion=candidates[0]))
            else:
                out.append(finding("near-miss-link", "fixable", nm["page"], f"[[{nm['target']}]] looks like a typo of [[{candidates[0]}]]", "run lint --fix", target=nm["target"], suggestion=candidates[0]))
        else:
            out.append(finding("near-miss-link", "judgement", nm["page"], f"[[{nm['target']}]] resembles several pages: {', '.join(candidates)}", "pick the intended target", target=nm["target"], candidates=candidates))
    for d in result["duplicates"]:
        out.append(finding("duplicate-basename", "judgement", None, f"basename {d['basename']} used by {', '.join(d['paths'])}", "rename or merge one of them with rename.py", basename=d["basename"], paths=d["paths"]))
    return out


def check_wanted(ctx: Context) -> List[Finding]:
    result = L.resolve_pages(ctx.root, ctx.catalog.pages, ctx.catalog)
    counts: Dict[str, List[str]] = {}
    for u in result["unresolved"]:
        counts.setdefault(u["target"], [])
        if u["page"] not in counts[u["target"]]:
            counts[u["target"]].append(u["page"])
    out: List[Finding] = []
    for target, pages in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        severity = "judgement" if len(pages) >= 2 else "informational"
        action = "propose creating the page (minting gate applies)" if len(pages) >= 2 else "leave as wanted page"
        out.append(finding("wanted-page", severity, None, f"[[{target}]] wanted by {len(pages)} page(s)", action, target=target, count=len(pages), pages=pages))
    return out


def check_stale(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    for p in ctx.pages:
        data = ctx.parsed.get(p)
        if not data:
            continue
        stale = str(data.get("stale_after") or "")
        if stale and stale <= ctx.today:
            extra: Dict[str, Any] = {}
            if data.get("type") == "source" and data.get("resource"):
                extra["resource"] = data["resource"]
            action = "re-fetch the source and re-ingest, or re-verify and stamp" if extra else "re-verify the content and stamp the page"
            out.append(finding("stale", "judgement", ctx.rel(p), f"stale since {stale}", action, stale_after=stale, **extra))
    return out


def check_review(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    for p in ctx.pages:
        data = ctx.parsed.get(p)
        if not data:
            continue
        verified = [v for v in FM.as_list(data.get("verified")) if isinstance(v, dict) and v.get("at")]
        gen_raw = data.get("generated")
        gen: Dict[str, Any] = gen_raw if isinstance(gen_raw, dict) else {}
        gen_at = str(gen.get("at") or "")
        if verified and gen_at:
            latest = max(str(v["at"]) for v in verified)
            if gen_at > latest:
                out.append(finding("review-outdated", "judgement", ctx.rel(p), f"generated {gen_at} after last verification {latest}", "re-verify with the verify skill or accept the change", generated=gen_at, verified=latest))
    return out


def check_footnotes(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    for p in ctx.pages:
        data = ctx.parsed.get(p)
        if data is None:
            continue
        rel = ctx.rel(p)
        _, body = FM.parse_text(p.read_text(encoding="utf-8"))
        body_nocode = L.strip_code(body)
        refs = set(FOOTNOTE_REF_RE.findall(re.sub(r"^\[\^[^\]]+\]:.*$", "", body_nocode, flags=re.M)))
        defs = set(FOOTNOTE_DEF_RE.findall(body_nocode))
        ids = {str(s.get("id")) for s in FM.as_list(data.get("sources")) if isinstance(s, dict) and s.get("id")}
        for r in sorted(refs - defs):
            out.append(finding("footnote-undefined", "judgement", rel, f"[^{r}] has no definition", "add `[^{id}]: <title>` or remove the reference".replace("{id}", r), footnote=r))
        for r in sorted(refs - ids):
            out.append(finding("footnote-unknown-id", "judgement", rel, f"[^{r}] matches no sources[].id", "add the source entry or fix the label", footnote=r))
        for d in sorted(defs - refs):
            out.append(finding("footnote-unused-definition", "judgement", rel, f"[^{d}] is defined but never referenced", "remove the definition or cite it", footnote=d))
        for sid in sorted(ids - refs):
            out.append(finding("source-never-cited", "informational", rel, f"source id {sid} is never cited in a footnote", "fine unless the page carries load-bearing claims from it", source_id=sid))
    return out


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def check_duplicates(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    titles: Dict[str, List[Tuple[str, str]]] = {}
    names: Dict[str, List[Tuple[str, str]]] = {}  # exact name -> [(kind, page)]
    for p in ctx.catalog.pages:
        data = ctx.parsed.get(p)
        if not data:
            continue
        title = str(data.get("title") or p.stem)
        titles.setdefault(_norm_title(title), []).append((title, ctx.rel(p)))
        names.setdefault(title, []).append(("title", ctx.rel(p)))
        if p.stem != title:
            names.setdefault(p.stem, []).append(("title", ctx.rel(p)))
        for a in FM.as_list(data.get("aliases")):
            names.setdefault(str(a), []).append(("alias", ctx.rel(p)))
    for key, entries in titles.items():
        if len(entries) > 1:
            out.append(finding("duplicate-title", "judgement", None, "titles differ only in case or punctuation: " + ", ".join(f"{t} ({p})" for t, p in entries), "merge with rename.py merge", pages=[p for _, p in entries]))
    for name, entries in names.items():
        pages = sorted({p for _, p in entries})
        if len(pages) > 1 and any(kind == "alias" for kind, _ in entries):
            out.append(finding("alias-collision", "judgement", None, f"'{name}' is a title or alias on several pages: {', '.join(pages)}", "remove the alias or merge the pages", name=name, pages=pages))
    return out


def check_orphans(ctx: Context) -> List[Finding]:
    inbound: Dict[str, int] = {}
    alias_of: Dict[str, Path] = {}
    for p in ctx.catalog.pages:
        data = ctx.parsed.get(p) or {}
        for a in FM.as_list(data.get("aliases")):
            alias_of[str(a)] = p
    for p in ctx.catalog.pages:
        for name in L.all_targets(p.read_text(encoding="utf-8")):
            target = ctx.catalog.resolve(name)
            if target is not None and target.resolve() != p.resolve():
                inbound[str(target.resolve())] = inbound.get(str(target.resolve()), 0) + 1
    out: List[Finding] = []
    for p in ctx.pages:
        if p.stem == HUB_PAGE or V.is_reserved(p):
            continue
        if (ctx.parsed.get(p) or {}).get("type") == "source":
            continue  # source pages are provenance anchors, catalogued by the index; citations reach them via sources[]
        if inbound.get(str(p.resolve()), 0) == 0:
            out.append(finding("orphan", "judgement", ctx.rel(p), "no inbound wikilinks from other pages", "link it from a related page or the Overview, or merge it"))
    return out


def check_tags(ctx: Context) -> List[Finding]:
    vocab = [str(t) for t in FM.as_list(ctx.settings.get("tags"))]
    if not vocab:
        return []
    out: List[Finding] = []
    for p in ctx.pages:
        data = ctx.parsed.get(p) or {}
        unknown = [str(t) for t in FM.as_list(data.get("tags")) if str(t) not in vocab]
        if unknown:
            out.append(finding("unknown-tag", "judgement", ctx.rel(p), "tags outside the domain vocabulary: " + ", ".join(unknown), "use a vocabulary tag or add the tag to the domain block", tags=unknown))
    return out


def check_rawhash(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    restorable = EV.restorable_sources(ctx.root)
    for rec in RH.compare(ctx.root, ctx.pages):
        if rec["status"] == "mismatch":
            out.append(finding("raw-hash-mismatch", "judgement", rec["page"], f"raw file changed since ingest: {rec['raw']}", "re-ingest the source (ingest asks first) or restore the original raw file", raw=rec["raw"]))
        elif rec["status"] == "missing":
            key = EV.restorable_key(rec["raw"])
            if key in restorable:
                out.append(finding("restore", "informational", rec["page"], f"raw file listed in SOURCES.md but missing locally: {rec['raw']}", "run fetch --restore", raw=rec["raw"], url=restorable[key]["url"]))
            else:
                out.append(finding("raw-missing", "judgement", rec["page"], f"raw file missing: {rec['raw']}", "restore the file or deprecate the source page", raw=rec["raw"]))
        elif rec["status"] == "no-raw-field":
            out.append(finding("raw-missing", "judgement", rec["page"], "source page has no raw field", "set raw to the file in raw/", raw=None))
    return out


def check_backlog(ctx: Context) -> List[Finding]:
    referenced: set = set()
    for p in ctx.catalog.pages:
        data = ctx.parsed.get(p) or {}
        if data.get("type") == "source" and data.get("raw"):
            referenced.add((ctx.root / str(data["raw"])).resolve())
    out: List[Finding] = []
    for raw in V.iter_raw_files(ctx.root):
        if raw.resolve() not in referenced:
            out.append(finding("ingest-backlog", "informational", None, f"raw file without a source page: {ctx.rel(raw)}", "ingest it (ingest --all processes the whole backlog)", raw=ctx.rel(raw)))
    return out


def _generic_block(text: str) -> Tuple[Optional[int], Optional[str]]:
    m = V.GENERIC_OPEN_RE.search(text)
    end = text.find(V.GENERIC_CLOSE)
    if not m or end < 0 or end < m.start():
        return None, None
    return int(m.group(1)), text[m.end() : end].strip()


def check_generic_block(ctx: Context) -> List[Finding]:
    claude = ctx.root / "CLAUDE.md"
    if not claude.is_file():
        return [finding("generic-block-missing", "judgement", "CLAUDE.md", "CLAUDE.md missing", "run init to scaffold it")]
    version, content = _generic_block(claude.read_text(encoding="utf-8"))
    if version is None:
        return [finding("generic-block-missing", "judgement", "CLAUDE.md", "no agent-wiki:generic block in CLAUDE.md", "insert the canonical block from the plugin references")]
    if not CANONICAL_GENERIC.is_file():
        return []
    cversion, ccontent = _generic_block(CANONICAL_GENERIC.read_text(encoding="utf-8"))
    if cversion is not None and version < cversion:
        return [finding("generic-block-behind", "judgement", "CLAUDE.md", f"generic block is v{version}, plugin ships v{cversion}", "offer the updated block to the owner", vault_version=version, plugin_version=cversion)]
    if ccontent is not None and content != ccontent and cversion == version:
        return [finding("generic-block-edited", "judgement", "CLAUDE.md", "generic block content differs from the plugin's canonical block", "restore the canonical block or move the edits into the domain block")]
    return []


def check_git(ctx: Context) -> List[Finding]:
    if ctx._git_root is None:
        return []
    out: List[Finding] = []
    for p in ctx.pages:
        data = ctx.parsed.get(p) or {}
        gen_raw = data.get("generated")
        gen: Dict[str, Any] = gen_raw if isinstance(gen_raw, dict) else {}
        gen_at = str(gen.get("at") or "")
        if not gen_at:
            continue
        last = ctx.git("log", "-1", "--format=%cs", "--", str(p))
        if last and gen_at < last:
            out.append(finding("git-freshness", "judgement", ctx.rel(p), f"generated.at {gen_at} is older than the last commit touching the file ({last})", "stamp the page if the knowledge changed, otherwise ignore (formatting-only commits are fine)", generated=gen_at, last_commit=last))
    return out


def check_reserved(ctx: Context) -> List[Finding]:
    out: List[Finding] = []
    wiki = V.wiki_dir(ctx.root)
    type_folders = {wiki / f for f in V.TYPE_FOLDERS.values()}
    for path in sorted(wiki.rglob("*.md")):
        if path.stem not in V.RESERVED_BASENAMES:
            continue
        if path.stem == "index" and path.parent in type_folders:
            try:
                data, _ = FM.parse_file(path)
            except FM.FrontmatterError:
                data = None
            if data is None:
                continue
        out.append(finding("reserved-name", "judgement", ctx.rel(path), f"page uses the reserved basename '{path.stem}'", "rename the page with rename.py"))
    return out


def check_evidence(ctx: Context) -> List[Finding]:
    report = EV.check(ctx.root, ctx.pages)
    out: List[Finding] = []
    for s in report["suspects"]:
        fn = f" [^{s['footnote']}]" if s.get("footnote") else ""
        out.append(finding("evidence-suspect", "judgement", s["page"], f"{s['kind']} {s['value']!r}{fn}: {s['detail']}", "check the raw source; correct the page or drop the precision", kind=s["kind"], value=s["value"], footnote=s.get("footnote")))
    for e in report["errors"]:
        out.append(finding("evidence-error", "judgement", e["page"], e["detail"], "fix the sources chain (source page, raw field, raw file)"))
    # restorable-but-missing raws are reported once, by check_rawhash on the source page
    return out


CHECKERS: Dict[str, Callable[[Context], List[Finding]]] = {
    "frontmatter": check_frontmatter,
    "index": check_index,
    "links": check_links,
    "wanted": check_wanted,
    "stale": check_stale,
    "review": check_review,
    "footnotes": check_footnotes,
    "duplicates": check_duplicates,
    "orphans": check_orphans,
    "tags": check_tags,
    "rawhash": check_rawhash,
    "backlog": check_backlog,
    "generic-block": check_generic_block,
    "git": check_git,
    "reserved": check_reserved,
    "evidence": check_evidence,
}
# order matters when fixing: fix pages first, then links, then the index last
FIX_ORDER = ["frontmatter", "links", "wanted", "stale", "review", "footnotes", "duplicates", "orphans", "tags", "rawhash", "backlog", "generic-block", "git", "reserved", "evidence", "index"]


def dedupe(items: List[Finding]) -> List[Finding]:
    seen: set = set()
    out: List[Finding] = []
    for f in items:
        key = json.dumps(f, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def run_all(root: Path, scope: Optional[Path], fix: bool) -> Dict[str, Any]:
    ctx = Context(root, scope, fix)
    all_findings: List[Finding] = []
    for name in FIX_ORDER:
        fresh = Context(root, scope, fix) if (fix and name in ("links", "index")) else ctx
        all_findings.extend(CHECKERS[name](fresh))
    all_findings = dedupe(all_findings)
    groups: Dict[str, List[Finding]] = {"auto_fixed": [], "fixable": [], "judgement": [], "informational": []}
    for f in all_findings:
        groups[f["severity"].replace("-", "_")].append(f)
    summary = {k: len(v) for k, v in groups.items()}
    summary["clean"] = not groups["judgement"] and not groups["fixable"]
    return {**groups, "summary": summary, "scope": V.rel(root, scope) if scope else None}


def render_markdown(report: Dict[str, Any]) -> str:
    lines = ["# Lint report", ""]
    for title, key in (("Auto-fixed", "auto_fixed"), ("Fixable", "fixable"), ("Needs judgement", "judgement"), ("Informational", "informational")):
        items = report[key]
        lines.append(f"## {title} ({len(items)})")
        for f in items:
            where = f" `{f['page']}`" if f.get("page") else ""
            lines.append(f"- **{f['type']}**{where}: {f['detail']}. Action: {f['action']}")
        lines.append("")
    s = report["summary"]
    lines.append(f"{s['auto_fixed']} fixed, {s['fixable']} fixable, {s['judgement']} need judgement, {s['informational']} informational")
    return "\n".join(lines)


def _root_and_scope(args: argparse.Namespace) -> Tuple[Path, Optional[Path]]:
    root = V.require_vault(args.vault or (args.scope if getattr(args, "scope", None) else None))
    scope = Path(args.scope) if getattr(args, "scope", None) else None
    if scope is not None and scope.resolve() == root.resolve():
        scope = None
    return root, scope


def _cmd_all(args: argparse.Namespace) -> int:
    try:
        root, scope = _root_and_scope(args)
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    report = run_all(root, scope, args.fix)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_markdown(report))
    return V.EXIT_OK if report["summary"]["clean"] else V.EXIT_FINDINGS


def _make_checker_cmd(name: str) -> Callable[[argparse.Namespace], int]:
    def cmd(args: argparse.Namespace) -> int:
        try:
            root, scope = _root_and_scope(args)
        except V.VaultError as exc:
            print(str(exc), file=sys.stderr)
            return V.EXIT_USAGE
        results = CHECKERS[name](Context(root, scope, False))
        if args.json:
            print(json.dumps({"checker": name, "findings": results}, indent=2, ensure_ascii=False))
        else:
            for f in results:
                where = f"{f['page']}: " if f.get("page") else ""
                print(f"{where}{f['type']} ({f['severity']}): {f['detail']}")
            if not results:
                print(f"{name}: clean")
        needs = [f for f in results if f["severity"] in ("judgement", "fixable")]
        return V.EXIT_FINDINGS if needs else V.EXIT_OK

    return cmd


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lint.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("all")
    p.add_argument("--vault", default=None)
    p.add_argument("--scope", default=None)
    p.add_argument("--fix", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_all)
    for name in CHECKERS:
        p = sub.add_parser(name)
        p.add_argument("--vault", default=None)
        p.add_argument("--scope", default=None)
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=_make_checker_cmd(name))
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
