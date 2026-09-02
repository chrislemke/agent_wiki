#!/usr/bin/env python3
"""Evidence checker: verify load-bearing literals against the raw sources a page cites.

Candidates are quotes of fifteen or more characters (double-quoted spans and
blockquotes), ISO dates (YYYY-MM-DD, YYYY-MM) and specific numbers
(thousands-grouped, dotted versions, K/M/B/% suffixed, or four or more digits).
Frontmatter, fenced and inline code, Status blocks and footnote definitions are
excluded. Resolution is two hops: sources[].page names a source page whose raw
field names the file. A sentence ending in [^id] is checked only against that
source; other sentences against all of the page's raws. Report-only.

Usage:
  evidence.py check PAGE|VAULT [--json]

Exit codes: 0 no suspects or errors, 1 findings, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import links as L  # noqa: E402
import vault as V  # noqa: E402

NUMBER_TOKEN_RE = re.compile(
    r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)*(?:\s*[KMB%](?![A-Za-z]))?"
    r"|\d+(?:\.\d+)*(?:\s*[KMB%](?![A-Za-z]))?)(?![A-Za-z])"
)
SUFFIX_RE = re.compile(r"[KMB%]$")
DATE_RE = re.compile(r"\d{4}-\d{2}(?:-\d{2})?")
QUOTE_RES = [re.compile(r'"([^"\n]*)"'), re.compile(r"“([^”\n]*)”")]
STATUS_LINE_RE = re.compile(r"^>\s*\**Status:", re.IGNORECASE)
FOOTNOTE_DEF_RE = re.compile(r"^\[\^[^\]]+\]:")
FOOTNOTE_REF_RE = re.compile(r"\[\^([^\]]+)\]")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
WIKILINK_RE = re.compile(r"!?\[\[[^\]]+\]\]")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(\[])")
WS_RE = re.compile(r"\s+")
MIN_QUOTE = 15


def normalize(text: str) -> str:
    return WS_RE.sub(" ", text).strip()


def strip_noise(text: str) -> str:
    text = INLINE_CODE_RE.sub(" ", text)
    text = WIKILINK_RE.sub(" ", text)
    text = MD_LINK_RE.sub(r"\1", text)
    return text


def keep_number(token: str) -> bool:
    token = token.strip()
    if SUFFIX_RE.search(token) or "," in token or "." in token:
        return True
    return len(token) >= 4


def numeric_date_candidates(text: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    date_matches = list(DATE_RE.finditer(text))
    out.extend(("date", m.group(0)) for m in date_matches)
    chars = list(text)
    for m in date_matches:
        chars[m.start() : m.end()] = " " * (m.end() - m.start())
    masked = "".join(chars)
    out.extend(("number", m.group(0).strip()) for m in NUMBER_TOKEN_RE.finditer(masked) if keep_number(m.group(0)))
    return out


def quote_candidates(text: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for qre in QUOTE_RES:
        for m in qre.finditer(text):
            value = normalize(m.group(1))
            if len(value) >= MIN_QUOTE:
                out.append(("quote", value))
    return out


class Candidate:
    __slots__ = ("kind", "value", "footnotes")

    def __init__(self, kind: str, value: str, footnotes: Tuple[str, ...]):
        self.kind = kind
        self.value = value.strip().strip(".,;:()[]")
        self.footnotes = footnotes

    def key(self) -> Tuple[str, str, Tuple[str, ...]]:
        return (self.kind, self.value, self.footnotes)


def extract_candidates(body: str) -> List[Candidate]:
    """Walk the body line by line, honouring fences, status blocks and footnote defs."""
    text = L.strip_code(body)
    lines = text.split("\n")
    candidates: List[Candidate] = []
    seen: Set[Tuple[str, str, Tuple[str, ...]]] = set()

    def add(kind: str, value: str, refs: Tuple[str, ...]) -> None:
        c = Candidate(kind, value, refs)
        if c.value and c.key() not in seen:
            seen.add(c.key())
            candidates.append(c)

    def handle_sentence(sentence: str) -> None:
        refs = tuple(FOOTNOTE_REF_RE.findall(sentence))
        cleaned = strip_noise(FOOTNOTE_REF_RE.sub("", sentence))
        for kind, value in numeric_date_candidates(cleaned):
            add(kind, value, refs)
        for kind, value in quote_candidates(cleaned):
            add(kind, value, refs)

    in_status = False
    blockquote: List[str] = []
    bq_refs: Set[str] = set()

    def flush_blockquote() -> None:
        nonlocal blockquote, bq_refs
        if blockquote:
            joined = normalize(" ".join(blockquote))
            refs = tuple(sorted(bq_refs))
            if len(joined) >= MIN_QUOTE:
                add("quote", joined, refs)
            blockquote = []
            bq_refs = set()

    for line in lines:
        stripped = line.strip()
        if STATUS_LINE_RE.match(stripped):
            flush_blockquote()
            in_status = True
            continue
        if in_status:
            if stripped.startswith(">"):
                continue
            in_status = False
        if FOOTNOTE_DEF_RE.match(stripped):
            flush_blockquote()
            continue
        if stripped.startswith(">"):
            content = stripped.lstrip(">").strip()
            bq_refs.update(FOOTNOTE_REF_RE.findall(content))
            content = strip_noise(FOOTNOTE_REF_RE.sub("", content))
            blockquote.append(content)
            for kind, value in numeric_date_candidates(content):
                add(kind, value, tuple(sorted(bq_refs)))
            continue
        flush_blockquote()
        if not stripped:
            continue
        for sentence in SENTENCE_SPLIT_RE.split(stripped):
            handle_sentence(sentence)
    flush_blockquote()
    return candidates


def contains(haystack: str, kind: str, value: str) -> bool:
    if kind == "quote":
        return value in haystack
    right = r"(?!-\d{2})" if kind == "date" and len(value) == 7 else ""
    pattern = r"(?<![\d.,])" + re.escape(value) + right + r"(?![A-Za-z0-9]|[.,]\d|%)"
    return re.search(pattern, haystack) is not None


def raw_body(path: Path) -> str:
    try:
        _, body = FM.parse_text(path.read_text(encoding="utf-8", errors="replace"))
    except FM.FrontmatterError:
        body = path.read_text(encoding="utf-8", errors="replace")
    return normalize(body)


def restorable_sources(root: Path) -> Dict[str, Dict[str, str]]:
    """Parse raw/SOURCES.md: a table with Title, URL, File, Licence columns. Keyed by file."""
    path = V.raw_dir(root) / V.SOURCES_LIST
    out: Dict[str, Dict[str, str]] = {}
    if not path.is_file():
        return out
    header: Optional[List[str]] = None
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = [c.lower() for c in cells]
            continue
        if all(set(c) <= set("-: ") for c in cells):
            continue
        row = dict(zip(header, cells))
        file = row.get("file", "")
        if file:
            out[file] = {"title": row.get("title", ""), "url": row.get("url", ""), "file": file, "license": row.get("licence", row.get("license", ""))}
    return out


def _wikilink_target(value: str) -> str:
    m = re.match(r"^\[\[([^\]|#]+)", value.strip())
    return m.group(1).strip() if m else value.strip()


def check_page(root: Path, page: Path, catalog: L.Catalog, restorable: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {"page": V.rel(root, page), "suspects": [], "errors": [], "restore": []}
    try:
        data, body = FM.parse_file(page)
    except FM.FrontmatterError as exc:
        result["errors"].append({"page": result["page"], "detail": f"unparseable frontmatter: {exc}"})
        return result
    if data is None:
        result["errors"].append({"page": result["page"], "detail": "missing frontmatter"})
        return result
    raws_by_id: Dict[str, Tuple[str, str]] = {}  # id -> (rel raw path, content)
    for entry in FM.as_list(data.get("sources")):
        if not isinstance(entry, dict):
            continue
        sid = str(entry.get("id", ""))
        target = _wikilink_target(str(entry.get("page", "")))
        source_page = catalog.resolve(target)
        if source_page is None:
            result["errors"].append({"page": result["page"], "detail": f"source page not found: [[{target}]] (id {sid})"})
            continue
        try:
            sdata, _ = FM.parse_file(source_page)
        except FM.FrontmatterError:
            sdata = None
        raw_rel = str((sdata or {}).get("raw") or "")
        if not raw_rel:
            result["errors"].append({"page": result["page"], "detail": f"source page [[{target}]] has no raw field"})
            continue
        raw_path = root / raw_rel
        if not raw_path.is_file():
            file_key = raw_rel.split("/", 1)[1] if raw_rel.startswith("raw/") else raw_rel
            if file_key in restorable:
                result["restore"].append({"page": result["page"], "raw": raw_rel, "url": restorable[file_key]["url"], "detail": "raw file listed in SOURCES.md but missing locally; run fetch --restore"})
            else:
                result["errors"].append({"page": result["page"], "detail": f"raw file missing: {raw_rel} (cited via [[{target}]])"})
            continue
        raws_by_id[sid] = (raw_rel, raw_body(raw_path))
    candidates = extract_candidates(body)
    if not raws_by_id:
        if "sources" not in data:
            # no sources at all: every literal is ungrounded. An explicit `sources: []`
            # declares that the page grounds nothing (a hub page's editorial text) and is skipped.
            for c in candidates:
                result["suspects"].append({"page": result["page"], "kind": c.kind, "value": c.value, "footnote": None, "checked": [], "detail": "page has no sources; literal cannot be grounded"})
        return result
    all_raws = list(raws_by_id.values())
    for c in candidates:
        if c.footnotes:
            targets = [raws_by_id[f] for f in c.footnotes if f in raws_by_id]
            footnote: Optional[str] = ",".join(c.footnotes)
            if not targets:
                targets = all_raws
                footnote = None
        else:
            targets, footnote = all_raws, None
        if not any(contains(content, c.kind, c.value) for _, content in targets):
            result["suspects"].append({"page": result["page"], "kind": c.kind, "value": c.value, "footnote": footnote, "checked": [rel for rel, _ in targets], "detail": "literal not found verbatim in the cited source(s)"})
    return result


def check(root: Path, pages: List[Path]) -> Dict[str, Any]:
    catalog = L.Catalog(root)
    restorable = restorable_sources(root)
    report: Dict[str, Any] = {"suspects": [], "errors": [], "restore": [], "checked_pages": 0}
    for p in pages:
        r = check_page(root, p, catalog, restorable)
        report["checked_pages"] += 1
        report["suspects"].extend(r["suspects"])
        report["errors"].extend(r["errors"])
        report["restore"].extend(r["restore"])
    return report


def render_text(report: Dict[str, Any]) -> str:
    lines = ["# Evidence check", "", "## Fidelity suspects"]
    if report["suspects"]:
        for s in report["suspects"]:
            fn = f" [^{s['footnote']}]" if s.get("footnote") else ""
            lines.append(f"- {s['page']}: {s['kind']} {s['value']!r}{fn}: {s['detail']}")
    else:
        lines.append("(none)")
    lines += ["", "## Evidence errors"]
    lines += [f"- {e['page']}: {e['detail']}" for e in report["errors"]] or ["(none)"]
    lines += ["", "## Restorable raw files missing locally"]
    lines += [f"- {r['page']}: {r['raw']} <{r['url']}>" for r in report["restore"]] or ["(none)"]
    lines += ["", f"## Summary", f"{len(report['suspects'])} suspect(s), {len(report['errors'])} error(s), {len(report['restore'])} restorable, {report['checked_pages']} page(s) checked"]
    return "\n".join(lines)


def _cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.target)
    try:
        root = V.require_vault(str(path))
    except V.VaultError as exc:
        print(str(exc), file=sys.stderr)
        return V.EXIT_USAGE
    pages = [path] if path.is_file() else list(V.iter_pages(root, None if path.resolve() == root.resolve() else path))
    report = check(root, pages)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render_text(report))
    return V.EXIT_FINDINGS if (report["suspects"] or report["errors"]) else V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evidence.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("check")
    p.add_argument("target")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_check)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
