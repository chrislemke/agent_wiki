#!/usr/bin/env python3
"""Scaffold a vault from the init interview answers. Idempotent: never overwrites a file.

Usage:
  scaffold.py init --vault DIR --answers answers.json --by ACTOR [--json]
  scaffold.py render-claude-md --answers answers.json

answers.json keys: title, purpose, entities, sources, lens, confidential, web_search,
language, image_cap, human_id, tags (list), staleness (tag -> days), extra_types (list).
Creates the marker, CLAUDE.md (generic + domain block), the folders, the Overview hub,
index and log, the Obsidian config, .gitignore, .claude/settings.json and raw/SOURCES.md.
Does not run git; reports the enclosing git repository so the caller can decide.
Exit 0 done, 2 usage.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frontmatter as FM  # noqa: E402
import index as IDX  # noqa: E402
import log as LOG  # noqa: E402
import vault as V  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
GENERIC = PLUGIN_ROOT / "references" / "generic-block.md"
DOMAIN_TEMPLATE = PLUGIN_ROOT / "references" / "domain-block-template.md"
MARKETPLACE_REPO = "chrislemke/agent_wiki"

OBSIDIAN_APP = {
    "useMarkdownLinks": False,
    "newLinkFormat": "shortest",
    "attachmentFolderPath": "raw/assets",
    "alwaysUpdateLinks": True,
    "showUnsupportedFiles": True,
}
GITIGNORE = """# Obsidian per-user state
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/cache
.trash/

# OS
.DS_Store
"""
SOURCES_MD = """# Sources

Sources listed here are not committed to this vault (licence or size). Run `/agent-wiki:fetch --restore` to download them into `raw/`.

| Title | URL | File | Licence |
|---|---|---|---|
"""


def load_answers(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("answers must be a JSON object")
    data.setdefault("title", "Wiki")
    data.setdefault("language", "en")
    data.setdefault("image_cap", 5)
    data.setdefault("confidential", False)
    data.setdefault("web_search", True)
    data.setdefault("tags", [])
    data.setdefault("staleness", {})
    data.setdefault("extra_types", [])
    return data


def settings_yaml(a: Dict[str, Any]) -> str:
    def yes_no(v: Any) -> str:
        return "true" if V.truthy(v) or v is True else "false"

    mapping: Dict[str, Any] = {
        "language": str(a.get("language", "en")),
        "image_cap": str(a.get("image_cap", 5)),
        "human_id": str(a.get("human_id", "owner")),
        "confidential": yes_no(a.get("confidential", False)),
        "web_search": yes_no(a.get("web_search", True)),
        "tags": [str(t) for t in a.get("tags", [])],
        "staleness": {str(k): str(v) for k, v in dict(a.get("staleness") or {}).items()},
        "extra_types": [str(t) for t in a.get("extra_types", [])],
    }
    return "\n".join(FM.serialize_mapping(mapping))


def render_domain_block(a: Dict[str, Any]) -> str:
    template = DOMAIN_TEMPLATE.read_text(encoding="utf-8")
    fields = {
        "purpose": str(a.get("purpose", "")).strip(),
        "entities": str(a.get("entities", "")).strip(),
        "sources": str(a.get("sources", "")).strip(),
        "lens": str(a.get("lens", "")).strip(),
        "settings": settings_yaml(a),
    }
    for key, value in fields.items():
        template = template.replace("{{" + key + "}}", value or "(not stated)")
    return template.strip() + "\n"


def render_claude_md(a: Dict[str, Any]) -> str:
    generic = GENERIC.read_text(encoding="utf-8").strip()
    return (
        f"# {a['title']}\n\n"
        "This folder is an agent-wiki vault: `raw/` holds sources, `wiki/` holds the pages the LLM maintains, "
        "and this file is the schema. Skills: `/agent-wiki:fetch`, `/agent-wiki:ingest`, `/agent-wiki:query`, "
        "`/agent-wiki:lint`, `/agent-wiki:verify` (install: `/plugin marketplace add " + MARKETPLACE_REPO + "`, then `/plugin install agent-wiki@agent-wiki`).\n\n"
        + generic + "\n\n" + render_domain_block(a)
    )


def overview_page(a: Dict[str, Any], actor: str) -> str:
    today = V.today()
    data: Dict[str, Any] = {
        "type": "synthesis",
        "title": "Overview",
        "description": f"Hub page of {a['title']}: what this wiki covers and what is still open.",
        "created": today,
        "generated": {"by": actor, "at": today},
    }
    body = (
        "\n# Overview\n\n"
        "## Thesis\n"
        f"{str(a.get('purpose', '')).strip() or 'What this wiki is about.'}\n\n"
        "## Evidence\n- No sources ingested yet.\n\n"
        "## Open questions\n- Which sources to ingest first?\n"
    )
    return FM.render(data, body)


def enclosing_git_repo(target: Path) -> Optional[str]:
    probe = target if target.is_dir() else target.parent
    while not probe.exists():
        probe = probe.parent
    try:
        out = subprocess.run(["git", "-C", str(probe), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    except OSError:
        return None
    if out.returncode != 0:
        return None
    top = Path(out.stdout.strip()).resolve()
    return str(top) if top != target.resolve() else None


def scaffold(target: Path, a: Dict[str, Any], actor: str) -> Dict[str, Any]:
    created: List[str] = []
    skipped: List[str] = []
    warnings: List[str] = []

    def write(rel: str, content: str) -> None:
        path = target / rel
        if path.exists():
            skipped.append(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(rel)

    target.mkdir(parents=True, exist_ok=True)
    today = V.today()
    write(V.MARKER, json.dumps({"schema_version": V.SCHEMA_VERSION, "plugin_version": V.PLUGIN_VERSION, "created": today}, indent=2) + "\n")
    write("CLAUDE.md", render_claude_md(a))
    if "CLAUDE.md" in skipped:
        text = (target / "CLAUDE.md").read_text(encoding="utf-8")
        if not V.GENERIC_OPEN_RE.search(text):
            warnings.append("CLAUDE.md exists but has no agent-wiki generic block; append the output of `scaffold.py render-claude-md` by hand")
        elif V.DOMAIN_OPEN not in text:
            warnings.append("CLAUDE.md exists but has no domain block; append the domain block from `scaffold.py render-claude-md`")
    for folder in ("raw/assets", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses", "wiki/analyses"):
        (target / folder).mkdir(parents=True, exist_ok=True)
        if folder != "wiki/syntheses" and not any((target / folder).iterdir()):
            write(f"{folder}/.gitkeep", "")
    write("raw/SOURCES.md", SOURCES_MD)
    write("wiki/syntheses/Overview.md", overview_page(a, actor))
    write("index.md", "# Index\n\n<!-- agent-wiki:curated -->\n## Start here\n- [[Overview]] is the hub. Ask questions with `/agent-wiki:query`.\n<!-- /agent-wiki:curated -->\n")
    if not (target / "log.md").exists():
        (target / "log.md").write_text("# Log\n", encoding="utf-8")
        created.append("log.md")
        LOG.append(target, "init", str(a["title"]), ["Overview"], [], "Vault scaffolded by agent-wiki init.")
    else:
        skipped.append("log.md")
    write(".gitignore", GITIGNORE)
    write(".obsidian/app.json", json.dumps(OBSIDIAN_APP, indent=2) + "\n")
    write(".claude/settings.json", json.dumps({
        "extraKnownMarketplaces": {"agent-wiki": {"source": {"source": "github", "repo": MARKETPLACE_REPO}}},
        "enabledPlugins": {"agent-wiki@agent-wiki": True},
    }, indent=2) + "\n")
    IDX.build(target)
    return {"vault": str(target), "created": created, "skipped": skipped, "warnings": warnings, "enclosing_git_repo": enclosing_git_repo(target)}


def _cmd_init(args: argparse.Namespace) -> int:
    try:
        answers = load_answers(Path(args.answers))
    except (OSError, ValueError) as exc:
        print(f"cannot read answers: {exc}", file=sys.stderr)
        return V.EXIT_USAGE
    result = scaffold(Path(args.vault), answers, args.by)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for rel in result["created"]:
            print(f"created {rel}")
        for rel in result["skipped"]:
            print(f"kept    {rel}")
        for w in result["warnings"]:
            print(f"warning: {w}")
        if result["enclosing_git_repo"]:
            print(f"enclosing git repository: {result['enclosing_git_repo']} (do not git init here)")
    return V.EXIT_OK


def _cmd_render(args: argparse.Namespace) -> int:
    try:
        answers = load_answers(Path(args.answers))
    except (OSError, ValueError) as exc:
        print(f"cannot read answers: {exc}", file=sys.stderr)
        return V.EXIT_USAGE
    print(render_claude_md(answers), end="")
    return V.EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scaffold.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("--vault", required=True)
    p.add_argument("--answers", required=True)
    p.add_argument("--by", required=True, help="actor for the Overview page, e.g. agent-wiki/<model-id>")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_init)
    p = sub.add_parser("render-claude-md")
    p.add_argument("--answers", required=True)
    p.set_defaults(func=_cmd_render)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
