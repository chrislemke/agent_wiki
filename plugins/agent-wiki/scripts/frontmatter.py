#!/usr/bin/env python3
"""Frontmatter toolkit: parse, normalize, validate and stamp wiki pages.

The parser understands a deliberate YAML subset and keeps every value a string:
  - scalars, double- and single-quoted strings
  - inline lists [a, b] and block lists (- item)
  - one-level nested mappings, inline { k: v } or block form
  - lists of mappings, inline or block form
Anything else is reported as unparseable, never guessed at.

Usage:
  frontmatter.py parse PAGE [--json]
  frontmatter.py normalize PAGE...             Rewrite frontmatter in canonical key order
  frontmatter.py validate PAGE|VAULT [--json]  Required fields per type, enums, ISO dates
  frontmatter.py stamp PAGE --by ACTOR [--vault V]   Sets generated, created and stale_after (and ingested on source pages)
  frontmatter.py set PAGE KEY VALUE            Set a scalar key (never verified)

Exit codes: 0 clean, 1 findings or errors, 2 usage. Python 3 stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault as V  # noqa: E402

KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:\s+(.*))?$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CANONICAL_ORDER = [
    "type",
    "title",
    "description",
    "aliases",
    "tags",
    "status",
    "created",
    "generated",
    "verified",
    "stale_after",
    "sources",
    "question",
    "raw",
    "raw_sha",
    "disposition",
    "author",
    "published",
    "resource",
    "fidelity",
    "ingested",
]

STATUS_VALUES = ("draft", "stable", "contested", "deprecated")
DISPOSITION_VALUES = ("new", "update", "disputed", "no-material")
REQUIRED_ALL = ("type", "title", "description", "created", "generated")
REQUIRED_BY_TYPE = {
    "source": ("raw", "raw_sha", "disposition", "ingested"),
    "analysis": ("question",),
}
DATE_FIELDS = ("created", "stale_after", "published", "ingested")


class FrontmatterError(Exception):
    pass


# ----------------------------------------------------------------------------
# Parsing
# ----------------------------------------------------------------------------

def split_frontmatter(text: str) -> Tuple[Optional[List[str]], str]:
    """Return (frontmatter lines or None, body). Body keeps its leading newline."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            body = "\n".join(lines[i + 1 :])
            return lines[1:i], body
    raise FrontmatterError("unparseable frontmatter: opening --- without closing ---")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _split_top(text: str, sep: str = ",") -> List[str]:
    """Split on sep outside quotes and nested brackets."""
    parts: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(text):
                buf.append(text[i + 1])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "":
        return ""
    if s[0] == '"':
        out: List[str] = []
        i = 1
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                nxt = s[i + 1]
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, "\\" + nxt))
                i += 2
                continue
            if ch == '"':
                rest = s[i + 1 :].strip()
                if rest and not rest.startswith("#"):
                    raise FrontmatterError(f"unparseable scalar: {raw!r}")
                return "".join(out)
            out.append(ch)
            i += 1
        raise FrontmatterError(f"unparseable scalar: unterminated quote in {raw!r}")
    if s[0] == "'":
        i = 1
        out = []
        while i < len(s):
            if s[i] == "'":
                if i + 1 < len(s) and s[i + 1] == "'":
                    out.append("'")
                    i += 2
                    continue
                rest = s[i + 1 :].strip()
                if rest and not rest.startswith("#"):
                    raise FrontmatterError(f"unparseable scalar: {raw!r}")
                return "".join(out)
            out.append(s[i])
            i += 1
        raise FrontmatterError(f"unparseable scalar: unterminated quote in {raw!r}")
    if s[0] == "[":
        if not s.endswith("]"):
            raise FrontmatterError(f"unparseable inline list: {raw!r}")
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part) for part in _split_top(inner)]
    if s[0] == "{":
        if not s.endswith("}"):
            raise FrontmatterError(f"unparseable inline mapping: {raw!r}")
        inner = s[1:-1].strip()
        result: Dict[str, Any] = {}
        if not inner:
            return result
        for part in _split_top(inner):
            key, _, value = part.partition(":")
            if not _ or not key.strip():
                raise FrontmatterError(f"unparseable inline mapping entry: {part!r}")
            val = parse_scalar(value)
            if isinstance(val, (list, dict)):
                raise FrontmatterError(f"unparseable: nesting deeper than one level in {raw!r}")
            result[key.strip()] = val
        return result
    # plain scalar; strip trailing comment
    idx = s.find(" #")
    if idx >= 0:
        s = s[:idx].rstrip()
    return s


def _parse_block_mapping(lines: List[str], start: int, indent: int) -> Tuple[Dict[str, Any], int]:
    """Parse `key: scalar` lines at exactly `indent` until indentation drops. One level only."""
    result: Dict[str, Any] = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if _indent(line) < indent:
            break
        if _indent(line) > indent:
            raise FrontmatterError(f"unparseable: nesting deeper than one level at line {i + 1}: {line!r}")
        m = KEY_RE.match(line.strip())
        if not m:
            raise FrontmatterError(f"unparseable mapping line {i + 1}: {line!r}")
        key, value = m.group(1), m.group(2)
        if value is None or value.strip() == "":
            raise FrontmatterError(f"unparseable: nested key {key!r} without a scalar value at line {i + 1}")
        val = parse_scalar(value)
        if isinstance(val, (list, dict)):
            raise FrontmatterError(f"unparseable: nesting deeper than one level at line {i + 1}")
        result[key] = val
        i += 1
    return result, i


def _parse_block_list(lines: List[str], start: int, indent: int) -> Tuple[List[Any], int]:
    items: List[Any] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if _indent(line) != indent or not line.strip().startswith("-"):
            break
        content = line.strip()[1:]
        if content and not content.startswith(" "):
            raise FrontmatterError(f"unparseable list item at line {i + 1}: {line!r}")
        content = content.strip()
        m = KEY_RE.match(content) if content else None
        if m and not content.startswith(("[", "{", '"', "'")):
            # block mapping item: `- key: value` with continuation lines at indent+2
            item_indent = indent + 2
            first_key, first_value = m.group(1), m.group(2)
            if first_value is None or first_value.strip() == "":
                raise FrontmatterError(f"unparseable list mapping at line {i + 1}: {line!r}")
            first_val = parse_scalar(first_value)
            if isinstance(first_val, (list, dict)):
                raise FrontmatterError(f"unparseable: nesting deeper than one level at line {i + 1}")
            mapping: Dict[str, Any] = {first_key: first_val}
            rest, j = _parse_block_mapping(lines, i + 1, item_indent)
            mapping.update(rest)
            items.append(mapping)
            i = j
            continue
        val = parse_scalar(content)
        if isinstance(val, list):
            raise FrontmatterError(f"unparseable: list inside list at line {i + 1}")
        items.append(val)
        i += 1
    return items, i


def parse_mapping(lines: List[str]) -> Dict[str, Any]:
    """Parse a top-level mapping from frontmatter lines."""
    result: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        if _indent(line) != 0:
            raise FrontmatterError(f"unparseable frontmatter line {i + 1}: unexpected indentation {line!r}")
        m = KEY_RE.match(line.rstrip())
        if not m:
            raise FrontmatterError(f"unparseable frontmatter line {i + 1}: {line!r}")
        key, value = m.group(1), m.group(2)
        if value is not None and value.strip() != "":
            result[key] = parse_scalar(value)
            i += 1
            continue
        # empty value: look ahead
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("#")):
            j += 1
        if j >= len(lines) or (_indent(lines[j]) == 0 and not lines[j].lstrip().startswith("- ")):
            result[key] = ""
            i = j
            continue
        nxt = lines[j]
        if nxt.lstrip().startswith("- ") or nxt.strip() == "-":
            items, i = _parse_block_list(lines, j, _indent(nxt))
            result[key] = items
        else:
            mapping, i = _parse_block_mapping(lines, j, _indent(nxt))
            result[key] = mapping
    return result


def parse_text(text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    fm_lines, body = split_frontmatter(text)
    if fm_lines is None:
        return None, body
    return parse_mapping(fm_lines), body


def parse_file(path: Path) -> Tuple[Optional[Dict[str, Any]], str]:
    return parse_text(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# Serializing
# ----------------------------------------------------------------------------

_PLAIN_UNSAFE_START = set("[]{}\"'#&*!|>%@`,?-:")


def needs_quotes(value: str) -> bool:
    if value == "":
        return True
    if value != value.strip():
        return True
    if value[0] in _PLAIN_UNSAFE_START and not (value[0] == "-" and len(value) > 1 and value[1] not in " -"):
        return True
    if ": " in value or " #" in value or value.endswith(":"):
        return True
    if "\n" in value or "\t" in value:
        return True
    if value.lower() in {"true", "false", "null", "~", "yes", "no", "on", "off"}:
        return True
    return False


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t") + '"'


def scalar_out(value: Any) -> str:
    s = str(value)
    return quote(s) if needs_quotes(s) else s


def serialize_mapping(data: Dict[str, Any]) -> List[str]:
    """Serialize a mapping in canonical key order; unknown keys follow in original order."""
    ordered = [k for k in CANONICAL_ORDER if k in data] + [k for k in data if k not in CANONICAL_ORDER]
    lines: List[str] = []
    for key in ordered:
        value = data[key]
        if isinstance(value, dict):
            if not value:
                lines.append(f"{key}: {{}}")
                continue
            lines.append(f"{key}:")
            for k, v in value.items():
                lines.append(f"  {k}: {scalar_out(v)}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            elif any(isinstance(v, dict) for v in value):
                lines.append(f"{key}:")
                for item in value:
                    if isinstance(item, dict):
                        first = True
                        for k, v in item.items():
                            prefix = "  - " if first else "    "
                            lines.append(f"{prefix}{k}: {scalar_out(v)}")
                            first = False
                        if first:
                            lines.append("  - {}")
                    else:
                        lines.append(f"  - {scalar_out(item)}")
            else:
                lines.append(f"{key}: [{', '.join(scalar_out(v) for v in value)}]")
        else:
            lines.append(f"{key}: {scalar_out(value)}")
    return lines


def render(data: Dict[str, Any], body: str) -> str:
    return "---\n" + "\n".join(serialize_mapping(data)) + "\n---\n" + body


def write_page(path: Path, data: Dict[str, Any], body: str) -> None:
    path.write_text(render(data, body), encoding="utf-8")


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

def as_list(value: Any) -> List[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def validate_data(data: Optional[Dict[str, Any]], extra_types: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
    """Return (errors, warnings) for one page's frontmatter."""
    errors: List[str] = []
    warnings: List[str] = []
    if data is None:
        return ["missing frontmatter"], warnings
    known_types = list(V.PAGE_TYPES) + list(extra_types or [])
    for key in REQUIRED_ALL:
        if key not in data or data[key] in ("", [], {}):
            errors.append(f"missing required field: {key}")
    ptype = str(data.get("type", ""))
    if ptype and ptype not in known_types:
        warnings.append(f"unknown type: {ptype}")
    for key in REQUIRED_BY_TYPE.get(ptype, ()):
        if key not in data or data[key] in ("", [], {}):
            errors.append(f"missing required field for {ptype}: {key}")
    status = data.get("status")
    if status not in (None, "") and status not in STATUS_VALUES:
        errors.append(f"invalid status: {status} (expected one of {', '.join(STATUS_VALUES)})")
    disposition = data.get("disposition")
    if disposition not in (None, "") and disposition not in DISPOSITION_VALUES:
        errors.append(f"invalid disposition: {disposition} (expected one of {', '.join(DISPOSITION_VALUES)})")
    for key in DATE_FIELDS:
        value = data.get(key)
        if value not in (None, "") and not (isinstance(value, str) and ISO_DATE_RE.match(value)):
            errors.append(f"{key} is not an ISO date (YYYY-MM-DD): {value}")
    generated = data.get("generated")
    if generated not in (None, ""):
        if not isinstance(generated, dict):
            errors.append("generated must be a mapping of by and at")
        else:
            if not generated.get("by"):
                errors.append("generated.by is missing")
            at = generated.get("at")
            if not at or not ISO_DATE_RE.match(str(at)):
                errors.append(f"generated.at is not an ISO date: {at}")
    verified = data.get("verified")
    if verified not in (None, "", []):
        for entry in as_list(verified):
            if not isinstance(entry, dict) or not entry.get("by") or not entry.get("at"):
                errors.append(f"verified entry must have by and at: {entry}")
            elif not ISO_DATE_RE.match(str(entry.get("at"))):
                errors.append(f"verified.at is not an ISO date: {entry.get('at')}")
    sources = data.get("sources")
    if sources not in (None, "", []):
        if not isinstance(sources, list):
            errors.append("sources must be a list of id and page entries")
        else:
            for entry in sources:
                if not isinstance(entry, dict) or not entry.get("id") or not entry.get("page"):
                    errors.append(f"sources entry must carry id and page: {entry}")
    for key in ("tags", "aliases"):
        value = data.get(key)
        if value not in (None, "") and not isinstance(value, list):
            errors.append(f"{key} must be a list")
    return errors, warnings


def validate_page(path: Path, extra_types: Optional[List[str]] = None) -> Dict[str, Any]:
    try:
        data, _ = parse_file(path)
    except FrontmatterError as exc:
        return {"page": str(path), "errors": [str(exc)], "warnings": []}
    errors, warnings = validate_data(data, extra_types)
    return {"page": str(path), "errors": errors, "warnings": warnings}


# ----------------------------------------------------------------------------
# Stamping
# ----------------------------------------------------------------------------

def compute_stale_after(tags: List[str], staleness: Dict[str, Any], base: str) -> Optional[str]:
    import datetime as dt

    windows: List[int] = []
    for tag in tags:
        days = staleness.get(str(tag))
        if days is None:
            continue
        try:
            windows.append(int(str(days)))
        except ValueError:
            continue
    if not windows:
        return None
    start = dt.date.fromisoformat(base)
    return (start + dt.timedelta(days=min(windows))).isoformat()


def stamp(path: Path, actor: str, root: Optional[Path]) -> Dict[str, Any]:
    data, body = parse_file(path)
    if data is None:
        raise FrontmatterError("missing frontmatter")
    now = V.today()
    data["generated"] = {"by": actor, "at": now}
    if not data.get("created"):
        data["created"] = now
    if data.get("type") == "source" and not data.get("ingested"):
        data["ingested"] = now
    staleness: Dict[str, Any] = {}
    if root is not None:
        settings = V.read_settings(root)
        raw_map = settings.get("staleness")
        if isinstance(raw_map, dict):
            staleness = raw_map
    stale = compute_stale_after([str(t) for t in as_list(data.get("tags"))], staleness, now)
    if stale:
        data["stale_after"] = stale
    else:
        data.pop("stale_after", None)
    write_page(path, data, body)
    return data


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _cmd_parse(args: argparse.Namespace) -> int:
    path = Path(args.page)
    try:
        data, body = parse_file(path)
    except FrontmatterError as exc:
        payload = {"page": str(path), "frontmatter": None, "body": None, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"{path}: {exc}", file=sys.stderr)
        return V.EXIT_FINDINGS
    payload = {"page": str(path), "frontmatter": data, "body": body}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif data is not None:
        print("\n".join(serialize_mapping(data)))
    if data is None:
        print(f"{path}: missing frontmatter", file=sys.stderr)
        return V.EXIT_FINDINGS
    return V.EXIT_OK


def _cmd_normalize(args: argparse.Namespace) -> int:
    code = V.EXIT_OK
    for page in args.pages:
        path = Path(page)
        try:
            data, body = parse_file(path)
        except FrontmatterError as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            code = V.EXIT_FINDINGS
            continue
        if data is None:
            print(f"{path}: missing frontmatter", file=sys.stderr)
            code = V.EXIT_FINDINGS
            continue
        new_text = render(data, body)
        if new_text != path.read_text(encoding="utf-8"):
            path.write_text(new_text, encoding="utf-8")
            print(f"normalized {path}")
    return code


def _collect_pages(target: str) -> Tuple[Optional[Path], List[Path]]:
    path = Path(target)
    root = V.find_vault(path)
    if path.is_file():
        return root, [path]
    if root is not None and path.resolve() == root.resolve():
        return root, list(V.iter_pages(root))
    return root, list(V.iter_pages(root or path, path))


def _cmd_validate(args: argparse.Namespace) -> int:
    root, pages = _collect_pages(args.target)
    extra: List[str] = []
    if root is not None:
        extra_types = V.read_settings(root).get("extra_types")
        if isinstance(extra_types, list):
            extra = [str(t) for t in extra_types]
    results = [validate_page(p, extra) for p in pages]
    has_errors = any(r["errors"] for r in results)
    if args.json:
        print(json.dumps({"results": results, "errors": sum(len(r["errors"]) for r in results), "warnings": sum(len(r["warnings"]) for r in results)}, indent=2, ensure_ascii=False))
    else:
        for r in results:
            for e in r["errors"]:
                print(f"{r['page']}: error: {e}")
            for w in r["warnings"]:
                print(f"{r['page']}: warning: {w}")
        if not has_errors and not any(r["warnings"] for r in results):
            print(f"ok: {len(results)} page(s) valid")
    return V.EXIT_FINDINGS if has_errors else V.EXIT_OK


def _cmd_stamp(args: argparse.Namespace) -> int:
    path = Path(args.page)
    root = V.find_vault(Path(args.vault)) if args.vault else V.find_vault(path)
    try:
        data = stamp(path, args.by, root)
    except FrontmatterError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return V.EXIT_FINDINGS
    print(f"stamped {path}: generated.at={data['generated']['at']} stale_after={data.get('stale_after', '-')}")
    return V.EXIT_OK


def _cmd_set(args: argparse.Namespace) -> int:
    path = Path(args.page)
    if args.key in ("verified",):
        print("refusing to set verified: use verify.py", file=sys.stderr)
        return V.EXIT_USAGE
    try:
        data, body = parse_file(path)
    except FrontmatterError as exc:
        print(f"{path}: {exc}", file=sys.stderr)
        return V.EXIT_FINDINGS
    if data is None:
        print(f"{path}: missing frontmatter", file=sys.stderr)
        return V.EXIT_FINDINGS
    value: Any = args.value
    if value.startswith("[") or value.startswith("{"):
        value = parse_scalar(value)
    data[args.key] = value
    write_page(path, data, body)
    print(f"set {args.key} on {path}")
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="frontmatter.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse")
    p.add_argument("page")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_parse)
    p = sub.add_parser("normalize")
    p.add_argument("pages", nargs="+")
    p.set_defaults(func=_cmd_normalize)
    p = sub.add_parser("validate")
    p.add_argument("target")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_validate)
    p = sub.add_parser("stamp")
    p.add_argument("page")
    p.add_argument("--by", required=True, help="actor, e.g. agent-wiki/<model-id>")
    p.add_argument("--vault", default=None)
    p.set_defaults(func=_cmd_stamp)
    p = sub.add_parser("set")
    p.add_argument("page")
    p.add_argument("key")
    p.add_argument("value")
    p.set_defaults(func=_cmd_set)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
