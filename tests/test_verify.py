from pathlib import Path

from conftest import copy_fixture, page, run_script


def test_verify_appends_human_entry_and_changes_nothing_else(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/concepts/Wikilinks.md"
    before = target.read_text(encoding="utf-8")
    r = run_script("verify.py", str(target), "--by", "chris", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    after = target.read_text(encoding="utf-8")
    added = "verified:\n  - by: human:chris\n    at: 2026-09-02\n"
    assert after.replace(added, "") == before
    assert after.index("generated:") < after.index("verified:") < after.index("sources:")


def test_verify_appends_to_existing_list_and_keeps_prefix(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"  # already verified by human:tester on 2026-09-01
    r = run_script("verify.py", str(target), "--by", "human:chris", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    data = run_script("frontmatter.py", "parse", str(target), "--json").json()["frontmatter"]
    assert data["verified"] == [{"by": "human:tester", "at": "2026-09-01"}, {"by": "human:chris", "at": "2026-09-02"}]


def test_verify_refuses_raw_files_and_pages_without_frontmatter(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_script("verify.py", str(vault / "raw/Note Taking Guide.md"), "--by", "chris")
    assert r.code == 2
    (vault / "wiki/entities/Bare.md").write_text("# Bare\n", encoding="utf-8")
    r = run_script("verify.py", str(vault / "wiki/entities/Bare.md"), "--by", "chris")
    assert r.code == 1


def test_verify_and_rename_offer_json_output(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_script("verify.py", str(vault / "wiki/concepts/Wikilinks.md"), "--by", "chris", "--json", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0 and r.json()["verified"] == {"by": "human:chris", "at": "2026-09-02"}
    r = run_script("rename.py", "rename", str(vault / "wiki/concepts/Wikilinks.md"), "Wiki Links", "--vault", str(vault), "--json")
    assert r.code == 0 and r.json()["new"] == "wiki/concepts/Wiki Links.md"
