from pathlib import Path

from conftest import page, run_script

CURATED = """# Index

<!-- agent-wiki:curated -->
## Start here
Read [[Overview]] first. Hand-written, never regenerated.
<!-- /agent-wiki:curated -->

## Stale listing that must be replaced
- [[Gone]] — no longer exists
"""


def setup(vault: Path) -> None:
    (vault / "index.md").write_text(CURATED, encoding="utf-8")
    (vault / "wiki/syntheses/Overview.md").write_text(page("synthesis", "Overview", "The hub page."), encoding="utf-8")
    (vault / "wiki/entities/Obsidian.md").write_text(page("entity", "Obsidian", "Markdown reader with a graph view."), encoding="utf-8")
    (vault / "wiki/entities/Claude Code.md").write_text(page("entity", "Claude Code", "Anthropic's coding agent."), encoding="utf-8")
    (vault / "wiki/sources/LLM Wiki.md").write_text(
        page("source", "LLM Wiki", "Karpathy's idea file.", raw="raw/LLM Wiki.md", raw_sha="abc", disposition="new", ingested="2026-09-01", published="2026-04-02"),
        encoding="utf-8",
    )
    (vault / "wiki/concepts/Broken.md").write_text("---\ntype: concept\nnested:\n  a:\n    b: c\n---\nBody\n", encoding="utf-8")


def test_build_regenerates_root_index_preserving_curated_block(vault: Path):
    setup(vault)
    r = run_script("index.py", "build", "--vault", str(vault))
    assert r.code == 0, r
    text = (vault / "index.md").read_text(encoding="utf-8")
    assert "Read [[Overview]] first. Hand-written, never regenerated." in text
    assert "[[Gone]]" not in text
    assert "## Syntheses (1)\n- [[Overview]] — The hub page.\n" in text
    # alphabetical within a type
    assert text.index("[[Claude Code]]") < text.index("[[Obsidian]]")
    assert "## Entities (2)" in text
    assert "- [[LLM Wiki]] — Karpathy's idea file. (published 2026-04-02)" in text
    assert "## Needs attention" in text and "wiki/concepts/Broken.md" in text
    # fixed section order
    assert text.index("## Syntheses") < text.index("## Entities") < text.index("## Sources")


def test_build_writes_an_index_per_type_folder(vault: Path):
    setup(vault)
    run_script("index.py", "build", "--vault", str(vault))
    entities = (vault / "wiki/entities/index.md").read_text(encoding="utf-8")
    assert entities.startswith("# Entities")
    assert "- [[Claude Code]] — Anthropic's coding agent." in entities
    assert "[[Overview]]" not in entities
    assert (vault / "wiki/analyses/index.md").exists()


def test_build_inserts_empty_curated_block_when_missing(vault: Path):
    (vault / "wiki/syntheses/Overview.md").write_text(page("synthesis", "Overview"), encoding="utf-8")
    run_script("index.py", "build", "--vault", str(vault))
    text = (vault / "index.md").read_text(encoding="utf-8")
    assert "<!-- agent-wiki:curated -->" in text and "<!-- /agent-wiki:curated -->" in text


def test_check_reports_drift_and_is_clean_after_build(vault: Path):
    setup(vault)
    r = run_script("index.py", "check", "--vault", str(vault))
    assert r.code == 1
    run_script("index.py", "build", "--vault", str(vault))
    r = run_script("index.py", "check", "--vault", str(vault), "--json")
    assert r.code == 0, r
    assert r.json()["drift"] == []


def test_build_links_by_basename_when_title_differs(vault: Path):
    (vault / "wiki/entities/Claude Code.md").write_text(page("entity", "Claude Code (CLI)", "Tool."), encoding="utf-8")
    run_script("index.py", "build", "--vault", str(vault))
    assert "- [[Claude Code|Claude Code (CLI)]] — Tool." in (vault / "index.md").read_text(encoding="utf-8")
