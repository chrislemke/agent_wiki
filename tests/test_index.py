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


def test_a_lost_curated_block_is_recovered_not_discarded(vault: Path):
    """Deleting the two marker lines used to drop everything a person had typed."""
    setup(vault)
    stripped = CURATED.replace("<!-- agent-wiki:curated -->\n", "").replace("<!-- /agent-wiki:curated -->\n", "")
    (vault / "index.md").write_text(stripped, encoding="utf-8")
    r = run_script("index.py", "build", "--vault", str(vault))
    assert r.code == 0, r
    text = (vault / "index.md").read_text(encoding="utf-8")
    assert "Read [[Overview]] first. Hand-written, never regenerated." in text
    assert "## Start here" in text
    # the markers are restored, so the next build protects the block again
    assert "<!-- agent-wiki:curated -->" in text and "<!-- /agent-wiki:curated -->" in text
    # without markers nothing distinguishes a person's section from a stale one, so everything
    # above the first generated section is kept; keeping too much beats deleting in silence
    head, _, rest = text.partition("<!-- /agent-wiki:curated -->")
    assert "[[Gone]]" in head and "## Syntheses (1)" in rest
    before = text
    assert run_script("index.py", "build", "--vault", str(vault)).code == 0
    assert (vault / "index.md").read_text(encoding="utf-8") == before


def test_half_a_marker_pair_also_recovers(vault: Path):
    setup(vault)
    (vault / "index.md").write_text(CURATED.replace("<!-- /agent-wiki:curated -->\n", ""), encoding="utf-8")
    assert run_script("index.py", "build", "--vault", str(vault)).code == 0
    text = (vault / "index.md").read_text(encoding="utf-8")
    assert "Read [[Overview]] first. Hand-written, never regenerated." in text
    assert text.count("<!-- agent-wiki:curated -->") == 1 and text.count("<!-- /agent-wiki:curated -->") == 1


def test_an_index_with_no_curated_content_gets_the_default_block(vault: Path):
    setup(vault)
    (vault / "index.md").write_text("# Index\n", encoding="utf-8")
    assert run_script("index.py", "build", "--vault", str(vault)).code == 0
    text = (vault / "index.md").read_text(encoding="utf-8")
    assert "<!-- agent-wiki:curated -->\n## Start here\n\n<!-- /agent-wiki:curated -->" in text
