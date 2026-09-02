"""Whole-toolkit checks against the checked-in fixture vault."""
from pathlib import Path

from conftest import FIXTURES, copy_fixture, run_script


def test_fixture_pages_round_trip_byte_identical(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    pages = sorted(p for p in (vault / "wiki").rglob("*.md") if p.stem not in {"index", "log"})
    before = {p: p.read_text(encoding="utf-8") for p in pages}
    r = run_script("frontmatter.py", "normalize", *[str(p) for p in pages])
    assert r.code == 0, r
    assert r.out == ""  # nothing needed normalizing
    assert {p: p.read_text(encoding="utf-8") for p in pages} == before


def test_fixture_vault_is_clean_for_every_spec1_tool(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    assert run_script("frontmatter.py", "validate", str(vault)).code == 0
    assert run_script("links.py", "resolve", str(vault)).code == 0
    assert run_script("index.py", "check", "--vault", str(vault)).code == 0
    assert run_script("rawhash.py", "compare", str(vault)).code == 0
    since = run_script("log.py", "since-lint", "--vault", str(vault), "--json").json()
    assert since == {"ingests_since_lint": 1, "last_lint": None}


def test_toolkit_never_writes_inside_raw(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    raw_before = {p: p.read_bytes() for p in (vault / "raw").rglob("*") if p.is_file()}
    run_script("index.py", "build", "--vault", str(vault))
    run_script("frontmatter.py", "stamp", str(vault / "wiki/entities/Obsidian.md"), "--by", "agent-wiki/t")
    run_script("frontmatter.py", "normalize", *[str(p) for p in (vault / "wiki").rglob("*.md")])
    run_script("log.py", "append", "--op", "lint", "--title", "0 fixed", "--vault", str(vault))
    assert {p: p.read_bytes() for p in (vault / "raw").rglob("*") if p.is_file()} == raw_before
