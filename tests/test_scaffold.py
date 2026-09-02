import json
import subprocess
from pathlib import Path

from conftest import PLUGIN, run_script

ANSWERS = {
    "title": "Claude Code Notes",
    "purpose": "A working reference on Claude Code and agentic coding practice.",
    "entities": "Tools, features, plugins, people and repositories.",
    "sources": "Official docs, READMEs, blog posts and talks.",
    "lens": "How to build reliable agentic workflows and plugins.",
    "confidential": False,
    "web_search": True,
    "language": "en",
    "image_cap": 5,
    "human_id": "chris",
    "tags": ["claude-code", "skills", "docs"],
    "staleness": {"docs": 90},
    "extra_types": [],
}


def scaffold(target: Path, answers: dict = ANSWERS, *extra: str):
    (target.parent / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    return run_script("scaffold.py", "init", "--vault", str(target), "--answers", str(target.parent / "answers.json"), "--by", "agent-wiki/test-model", "--json", *extra, env={"AGENT_WIKI_TODAY": "2026-09-02"})


def test_scaffold_creates_a_complete_vault(tmp_path: Path):
    target = tmp_path / "wiki-home"
    r = scaffold(target)
    assert r.code == 0, r
    for rel in [".agent-wiki.json", "CLAUDE.md", "index.md", "log.md", ".gitignore", ".obsidian/app.json", ".claude/settings.json",
                "raw/assets/.gitkeep", "raw/SOURCES.md", "wiki/sources/.gitkeep", "wiki/entities/.gitkeep", "wiki/concepts/.gitkeep", "wiki/analyses/.gitkeep", "wiki/syntheses/Overview.md"]:
        assert (target / rel).exists(), rel
    marker = json.loads((target / ".agent-wiki.json").read_text(encoding="utf-8"))
    assert marker == {"schema_version": 1, "plugin_version": "0.1.0", "created": "2026-09-02"}
    claude = (target / "CLAUDE.md").read_text(encoding="utf-8")
    canonical = (PLUGIN / "references/generic-block.md").read_text(encoding="utf-8").strip()
    assert claude.startswith("# Claude Code Notes\n")
    assert canonical in claude
    assert "### Purpose\nA working reference on Claude Code and agentic coding practice." in claude
    settings = run_script("vault.py", "settings", "--vault", str(target), "--json").json()
    assert settings["tags"] == ["claude-code", "skills", "docs"]
    assert settings["staleness"] == {"docs": "90"}
    assert settings["confidential"] == "false" and settings["web_search"] == "true"
    assert settings["human_id"] == "chris" and settings["image_cap"] == "5"
    overview = run_script("frontmatter.py", "parse", str(target / "wiki/syntheses/Overview.md"), "--json").json()
    assert overview["frontmatter"]["type"] == "synthesis"
    assert overview["frontmatter"]["generated"] == {"by": "agent-wiki/test-model", "at": "2026-09-02"}
    assert "## Open questions" in overview["body"]
    index = (target / "index.md").read_text(encoding="utf-8")
    assert "<!-- agent-wiki:curated -->" in index and "[[Overview]]" in index
    assert "## [2026-09-02] init | Claude Code Notes" in (target / "log.md").read_text(encoding="utf-8")
    settings_json = json.loads((target / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings_json["extraKnownMarketplaces"]["agent-wiki"]["source"] == {"source": "github", "repo": "chrislemke/agent_wiki"}
    assert settings_json["enabledPlugins"] == {"agent-wiki@agent-wiki": True}
    app = json.loads((target / ".obsidian/app.json").read_text(encoding="utf-8"))
    assert app["attachmentFolderPath"] == "raw/assets" and app["useMarkdownLinks"] is False and app["newLinkFormat"] == "shortest"
    assert ".obsidian/workspace.json" in (target / ".gitignore").read_text(encoding="utf-8")
    # the new vault passes every checker except the informational ones
    lint = run_script("lint.py", "all", "--vault", str(target), "--json")
    assert lint.code == 0, lint.out
    out = r.json()
    assert "CLAUDE.md" in out["created"] and out["skipped"] == [] and out["enclosing_git_repo"] is None


def test_scaffold_fills_gaps_without_overwriting(tmp_path: Path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "CLAUDE.md").write_text("# Mine\nHand-written, keep me.\n", encoding="utf-8")
    (target / "raw").mkdir()
    (target / "raw/Old.md").write_text("raw stays\n", encoding="utf-8")
    r = scaffold(target)
    assert r.code == 0, r
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\nHand-written, keep me.\n"
    assert (target / "raw/Old.md").read_text(encoding="utf-8") == "raw stays\n"
    assert (target / "wiki/syntheses/Overview.md").exists()
    out = r.json()
    assert "CLAUDE.md" in out["skipped"]
    assert any("generic block" in w for w in out["warnings"])  # CLAUDE.md lacks the block; init skill must add it


def test_scaffold_reports_enclosing_git_repo(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    target = tmp_path / "nested"
    r = scaffold(target)
    assert r.code == 0, r
    assert r.json()["enclosing_git_repo"] == str(tmp_path.resolve())


def test_scaffold_render_claude_md_prints_the_blocks_for_manual_insertion(tmp_path: Path):
    (tmp_path / "answers.json").write_text(json.dumps(ANSWERS), encoding="utf-8")
    r = run_script("scaffold.py", "render-claude-md", "--answers", str(tmp_path / "answers.json"))
    assert r.code == 0
    assert "<!-- agent-wiki:generic v1 -->" in r.out and "<!-- agent-wiki:domain -->" in r.out and "tags: [claude-code, skills, docs]" in r.out
