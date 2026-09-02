from pathlib import Path

from conftest import page, run_script


def with_sources(text: str, sources: list[tuple[str, str]]) -> str:
    src = "sources:\n" + "".join(f"  - id: {sid}\n    page: \"[[{p}]]\"\n" for sid, p in sources)
    return text.replace("---\n\n# ", src + "---\n\n# ", 1)


def setup(vault: Path) -> None:
    (vault / "raw/Src.md").write_text("# Src\nraw stays\n", encoding="utf-8")
    (vault / "wiki/sources/Src.md").write_text(with_sources(page("source", "Src", raw="raw/Src.md", raw_sha="x", disposition="new", ingested="2026-09-01"), [("src", "Src")]), encoding="utf-8")
    (vault / "wiki/entities/Claude Code.md").write_text(with_sources(page("entity", "Claude Code", aliases=["CC"]), [("src", "Src")]), encoding="utf-8")
    (vault / "wiki/entities/Claude-Code CLI.md").write_text(with_sources(page("entity", "Claude-Code CLI", body="Duplicate of [[Claude Code]]."), [("other", "Src")]), encoding="utf-8")
    (vault / "wiki/syntheses/Overview.md").write_text(
        page("synthesis", "Overview", body="See [[Claude Code]], [[Claude Code|the CLI]], [[Claude Code#Key facts]], [[CC]] and [[Claude-Code CLI]]. Embedded: ![[Claude Code]]."),
        encoding="utf-8",
    )
    run_script("index.py", "build", "--vault", str(vault))


def test_rename_moves_file_rewrites_links_and_records_alias(vault: Path):
    setup(vault)
    raw_before = (vault / "raw/Src.md").read_bytes()
    r = run_script("rename.py", "rename", str(vault / "wiki/entities/Claude Code.md"), "Claude Code CLI", "--vault", str(vault))
    assert r.code == 0, r
    assert not (vault / "wiki/entities/Claude Code.md").exists()
    new = vault / "wiki/entities/Claude Code CLI.md"
    assert new.exists()
    data = run_script("frontmatter.py", "parse", str(new), "--json").json()["frontmatter"]
    assert data["title"] == "Claude Code CLI"
    assert data["aliases"] == ["CC", "Claude Code"]
    overview = (vault / "wiki/syntheses/Overview.md").read_text(encoding="utf-8")
    assert "[[Claude Code CLI]]" in overview
    assert "[[Claude Code CLI|the CLI]]" in overview
    assert "[[Claude Code CLI#Key facts]]" in overview
    assert "![[Claude Code CLI]]" in overview
    assert "[[CC]]" in overview  # alias links still resolve, left alone
    assert "[[Claude Code]]" not in overview.replace("[[Claude Code CLI", "")
    assert (vault / "raw/Src.md").read_bytes() == raw_before
    assert "[[Claude Code CLI]]" in (vault / "index.md").read_text(encoding="utf-8")


def test_merge_unions_sources_adds_aliases_rewrites_links_then_deletes_loser(vault: Path):
    setup(vault)
    r = run_script("rename.py", "merge", str(vault / "wiki/entities/Claude-Code CLI.md"), str(vault / "wiki/entities/Claude Code.md"), "--vault", str(vault))
    assert r.code == 0, r
    assert not (vault / "wiki/entities/Claude-Code CLI.md").exists()
    data = run_script("frontmatter.py", "parse", str(vault / "wiki/entities/Claude Code.md"), "--json").json()["frontmatter"]
    assert data["aliases"] == ["CC", "Claude-Code CLI"]
    assert data["sources"] == [{"id": "src", "page": "[[Src]]"}, {"id": "other", "page": "[[Src]]"}]
    overview = (vault / "wiki/syntheses/Overview.md").read_text(encoding="utf-8")
    assert "[[Claude-Code CLI]]" not in overview
    assert overview.count("[[Claude Code]]") >= 2
    assert (vault / "raw/Src.md").read_text(encoding="utf-8") == "# Src\nraw stays\n"


def test_rename_refuses_target_that_already_exists(vault: Path):
    setup(vault)
    r = run_script("rename.py", "rename", str(vault / "wiki/entities/Claude Code.md"), "Claude-Code CLI", "--vault", str(vault))
    assert r.code == 2
    assert (vault / "wiki/entities/Claude Code.md").exists()
