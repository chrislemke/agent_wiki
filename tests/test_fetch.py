import json
from pathlib import Path

from conftest import run_script

TRAFILATURA_OUTPUT = """---
title: The Unreasonable Effectiveness of RNNs
author: Karpathy
url: http://karpathy.github.io/2015/05/21/rnn-effectiveness/
hostname: github.io
date: "2015-05-21"
---
# The Unreasonable Effectiveness of RNNs

There is something magical about Recurrent Neural Networks.
"""


def test_url_stdin_writes_raw_file_with_metadata_from_extractor_header(vault: Path):
    r = run_script("fetch.py", "url", "https://karpathy.github.io/2015/05/21/rnn-effectiveness/", "--stdin", "--vault", str(vault), "--json", stdin=TRAFILATURA_OUTPUT, env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    out = r.json()
    path = vault / "raw/The Unreasonable Effectiveness of RNNs.md"
    assert out["path"] == "raw/The Unreasonable Effectiveness of RNNs.md" and path.exists()
    data = run_script("frontmatter.py", "parse", str(path), "--json").json()
    fm = data["frontmatter"]
    assert fm == {
        "title": "The Unreasonable Effectiveness of RNNs",
        "resource": "https://karpathy.github.io/2015/05/21/rnn-effectiveness/",
        "fetched": "2026-09-02",
        "author": "Karpathy",
        "published": "2015-05-21",
        "fidelity": "verbatim",
    }
    assert data["body"].strip().startswith("# The Unreasonable Effectiveness of RNNs")
    assert "There is something magical" in data["body"]


def test_url_stdin_fallback_marks_summary_fidelity_and_takes_explicit_metadata(vault: Path):
    r = run_script("fetch.py", "url", "https://example.com/post", "--stdin", "--title", "A Post: Part 1/2?", "--author", "Someone", "--published", "2026-01-02", "--fidelity", "summary", "--vault", str(vault), stdin="Summarised text.\n", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    path = vault / "raw/A Post Part 1-2.md"  # filename-safe title
    assert path.exists()
    fm = run_script("frontmatter.py", "parse", str(path), "--json").json()["frontmatter"]
    assert fm["title"] == "A Post: Part 1/2?" and fm["fidelity"] == "summary" and fm["author"] == "Someone" and fm["published"] == "2026-01-02"


def test_url_refuses_to_overwrite_an_existing_raw_file(vault: Path):
    (vault / "raw/Existing.md").write_text("original\n", encoding="utf-8")
    r = run_script("fetch.py", "url", "https://example.com/x", "--stdin", "--title", "Existing", "--vault", str(vault), stdin="new\n")
    assert r.code == 1
    assert (vault / "raw/Existing.md").read_text(encoding="utf-8") == "original\n"


def test_github_plans_readme_plus_named_files_and_downloads_them(vault: Path, tmp_path: Path):
    tree = tmp_path / "gh" / "Astro-Han" / "karpathy-llm-wiki" / "main"
    tree.mkdir(parents=True)
    (tree / "README.md").write_text("# karpathy-llm-wiki\nREADME body\n", encoding="utf-8")
    (tree / "SKILL.md").write_text("---\nname: karpathy-llm-wiki\n---\nSKILL body\n", encoding="utf-8")
    base = (tmp_path / "gh").as_uri() + "/"
    r = run_script("fetch.py", "github", "https://github.com/Astro-Han/karpathy-llm-wiki", "--files", "SKILL.md", "--dry-run", "--vault", str(vault), "--json")
    assert r.code == 0, r
    plan = r.json()["planned"]
    assert [p["file"] for p in plan] == ["README.md", "SKILL.md"]
    assert plan[0]["url"] == "https://raw.githubusercontent.com/Astro-Han/karpathy-llm-wiki/main/README.md"
    assert plan[0]["path"] == "raw/karpathy-llm-wiki README.md"
    assert plan[1]["resource"] == "https://github.com/Astro-Han/karpathy-llm-wiki/blob/main/SKILL.md"
    r = run_script("fetch.py", "github", "https://github.com/Astro-Han/karpathy-llm-wiki", "--files", "SKILL.md", "--raw-base", base, "--vault", str(vault), "--json", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    readme = run_script("frontmatter.py", "parse", str(vault / "raw/karpathy-llm-wiki README.md"), "--json").json()
    assert readme["frontmatter"]["title"] == "karpathy-llm-wiki README"
    assert readme["frontmatter"]["resource"] == "https://github.com/Astro-Han/karpathy-llm-wiki/blob/main/README.md"
    assert readme["frontmatter"]["author"] == "Astro-Han" and readme["frontmatter"]["fidelity"] == "verbatim"
    assert "README body" in readme["body"]
    skill = (vault / "raw/karpathy-llm-wiki SKILL.md").read_text(encoding="utf-8")
    assert "SKILL body" in skill and skill.startswith("---\ntitle: karpathy-llm-wiki SKILL\n")


def test_github_tree_url_sets_branch_and_subpath(vault: Path):
    r = run_script("fetch.py", "github", "https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf", "--dry-run", "--vault", str(vault), "--json")
    plan = r.json()["planned"]
    assert plan[0]["url"] == "https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/README.md"
    assert plan[0]["path"] == "raw/knowledge-catalog okf README.md"


def test_restore_downloads_only_missing_sources_listed_in_sources_md(vault: Path, tmp_path: Path):
    src = tmp_path / "remote"
    src.mkdir()
    (src / "gist.md").write_text("# LLM Wiki\n\nA pattern.\n", encoding="utf-8")
    (vault / "raw/Present.md").write_text("already here\n", encoding="utf-8")
    (vault / "raw/SOURCES.md").write_text(
        "# Sources\n\nNot committed; run fetch --restore.\n\n| Title | URL | File | Licence |\n|---|---|---|---|\n"
        f"| LLM Wiki | {(src / 'gist.md').as_uri()} | LLM Wiki.md | not stated |\n"
        f"| Present | {(src / 'gist.md').as_uri()} | Present.md | MIT |\n"
        f"| Broken | {(src / 'missing.md').as_uri()} | Broken.md | MIT |\n",
        encoding="utf-8",
    )
    r = run_script("fetch.py", "restore", "--vault", str(vault), "--json", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 1, r  # one failure
    out = r.json()
    assert out["restored"] == ["raw/LLM Wiki.md"] and out["skipped"] == ["raw/Present.md"] and out["failed"][0]["file"] == "Broken.md"
    fm = run_script("frontmatter.py", "parse", str(vault / "raw/LLM Wiki.md"), "--json").json()["frontmatter"]
    assert fm["title"] == "LLM Wiki" and fm["fidelity"] == "verbatim" and fm["resource"].startswith("file://")
    assert (vault / "raw/Present.md").read_text(encoding="utf-8") == "already here\n"


def test_gist_and_github_blob_urls_are_rewritten_to_raw_downloads(vault: Path):
    r = run_script("fetch.py", "plan-url", "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f", "--json")
    assert r.json() == {"mode": "download", "url": "https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw"}
    r = run_script("fetch.py", "plan-url", "https://github.com/o/r/blob/main/docs/x.md", "--json")
    assert r.json() == {"mode": "download", "url": "https://raw.githubusercontent.com/o/r/main/docs/x.md"}
    r = run_script("fetch.py", "plan-url", "https://example.com/article", "--json")
    assert r.json() == {"mode": "extract", "url": "https://example.com/article"}
