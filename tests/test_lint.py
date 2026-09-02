import json
import os
import subprocess
from pathlib import Path

from conftest import PLUGIN, copy_fixture, page, run_script


def findings(vault: Path, *args: str) -> tuple:
    r = run_script("lint.py", "all", "--vault", str(vault), "--json", *args)
    return r.code, r.json()


def types(group: list) -> set:
    return {f["type"] for f in group}


def by_type(data: dict, ftype: str) -> list:
    return [f for grp in ("auto_fixed", "fixable", "judgement", "informational") for f in data[grp] if f["type"] == ftype]


def test_clean_fixture_vault_has_no_judgement_or_fixable_findings(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    code, data = findings(vault)
    assert code == 0, data
    assert data["judgement"] == [] and data["fixable"] == []
    # verified entity page is not outdated, Overview is not an orphan
    assert types(data["informational"]) <= {"source-never-cited", "wanted-page"}


def defective(tmp_path: Path) -> Path:
    vault = copy_fixture("basic-vault", tmp_path / "v")
    w = vault / "wiki"
    # near-miss typo link (unique) + wanted page linked twice + orphan + unknown tag + stale + review outdated
    (w / "entities/Typo Page.md").write_text(
        page("entity", "Typo Page", tags=["tools", "madeup"], stale_after="2020-01-01", body="Links to [[Obsidan]] and [[Progressive Disclosure]].\n"),
        encoding="utf-8",
    )
    (w / "entities/Orphan.md").write_text(page("entity", "Orphan", body="Nobody links here. Passed 2,000,000 users in 2024 (ungrounded: no sources). Wants [[Progressive Disclosure]] too."), encoding="utf-8")
    # review outdated: generated after verified
    outdated = page("entity", "Reviewed", body="x").replace("generated:\n  by: agent-wiki/test-model\n  at: 2026-09-01", "generated:\n  by: agent-wiki/test-model\n  at: 2026-09-05\nverified:\n  - by: human:tester\n    at: 2026-09-02")
    (w / "entities/Reviewed.md").write_text(outdated, encoding="utf-8")
    (w / "syntheses/Overview.md").write_text((w / "syntheses/Overview.md").read_text(encoding="utf-8").replace("## Open questions", "Also [[Typo Page]] and [[Reviewed]].\n\n## Open questions"), encoding="utf-8")
    # footnote problems + duplicate title (case) + alias collision
    fn = page("concept", "wikilinks", body="Claim.[^nope]\n\n[^unused]: never referenced\n").replace("title: wikilinks", "title: wikilinks\naliases: [Obsidian]")
    (w / "concepts/Wikilinks Dup.md").write_text(fn.replace("---\n\n# ", "sources:\n  - id: guide\n    page: \"[[Note Taking Guide]]\"\n---\n\n# ", 1), encoding="utf-8")
    # raw hash mismatch + backlog + reserved name + frontmatter out of order
    (vault / "raw/Note Taking Guide.md").write_text((vault / "raw/Note Taking Guide.md").read_text(encoding="utf-8") + "\nAppended after ingest.\n", encoding="utf-8")
    (vault / "raw/Unprocessed.md").write_text("# Unprocessed\nNot ingested yet.\n", encoding="utf-8")
    (w / "concepts/log.md").write_text(page("concept", "log"), encoding="utf-8")
    (w / "concepts/Unordered.md").write_text("---\ntitle: Unordered\ntype: concept\ndescription: d\ncreated: 2026-09-01\ngenerated: { by: x, at: 2026-09-01 }\n---\n\n# Unordered\nSee [[Overview]].\n", encoding="utf-8")
    # generic block behind
    (vault / "CLAUDE.md").write_text((vault / "CLAUDE.md").read_text(encoding="utf-8").replace("agent-wiki:generic v1", "agent-wiki:generic v0"), encoding="utf-8")
    return vault


def test_each_checker_reports_its_defect(tmp_path: Path):
    vault = defective(tmp_path)
    code, data = findings(vault)
    assert code == 1
    judgement = types(data["judgement"])
    assert "near-miss-link" in types(data["fixable"])
    assert "index-drift" in types(data["fixable"])
    assert "frontmatter-order" in types(data["fixable"])
    assert {"wanted-page", "orphan", "unknown-tag", "stale", "review-outdated", "footnote-undefined", "footnote-unknown-id", "footnote-unused-definition", "duplicate-title", "alias-collision", "raw-hash-mismatch", "reserved-name", "generic-block-behind", "evidence-suspect"} <= judgement, judgement
    assert "ingest-backlog" in types(data["informational"])
    wanted = by_type(data, "wanted-page")[0]
    assert wanted["target"] == "Progressive Disclosure" and wanted["count"] == 2
    assert sorted(p.split("/")[-1] for p in wanted["pages"]) == ["Orphan.md", "Typo Page.md"]
    orphan = by_type(data, "orphan")
    assert any(o["page"].endswith("Orphan.md") for o in orphan)
    assert not any(o["page"].endswith("Overview.md") for o in orphan)
    stale = by_type(data, "stale")[0]
    assert stale["page"].endswith("Typo Page.md")


def test_fix_applies_only_the_auto_fix_policy_and_leaves_raw_untouched(tmp_path: Path):
    vault = defective(tmp_path)
    raw_before = {p: p.read_bytes() for p in (vault / "raw").rglob("*") if p.is_file()}
    code, data = findings(vault, "--fix")
    assert code == 1  # judgement findings remain
    fixed = types(data["auto_fixed"])
    assert {"index-drift", "frontmatter-order", "near-miss-link"} <= fixed
    assert data["fixable"] == []
    assert "[[Obsidian]]" in (vault / "wiki/entities/Typo Page.md").read_text(encoding="utf-8")
    assert (vault / "wiki/concepts/Unordered.md").read_text(encoding="utf-8").startswith("---\ntype: concept\ntitle: Unordered\n")
    assert run_script("index.py", "check", "--vault", str(vault)).code == 0
    assert {p: p.read_bytes() for p in (vault / "raw").rglob("*") if p.is_file()} == raw_before
    # facts are never changed: the evidence suspect and hash mismatch remain reported
    assert "evidence-suspect" in types(data["judgement"]) and "raw-hash-mismatch" in types(data["judgement"])
    # second run: nothing left to fix
    code2, data2 = findings(vault, "--fix")
    assert data2["auto_fixed"] == [] and data2["fixable"] == []


def test_near_miss_with_two_candidates_needs_judgement(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/entities/Obsidiam.md").write_text(page("entity", "Obsidiam", body="See [[Overview]]."), encoding="utf-8")
    (vault / "wiki/entities/Ambiguous.md").write_text(page("entity", "Ambiguous", body="See [[Obsidiaz]] and [[Overview]]."), encoding="utf-8")
    code, data = findings(vault, "--fix")
    nm = by_type(data, "near-miss-link")
    assert nm and nm[0]["severity"] == "judgement"
    assert "[[Obsidiaz]]" in (vault / "wiki/entities/Ambiguous.md").read_text(encoding="utf-8")


def test_created_is_added_from_git_history_and_git_freshness_is_reported(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/entities/NoCreated.md").write_text("---\ntype: entity\ntitle: NoCreated\ndescription: d\ngenerated: { by: x, at: 2026-01-01 }\n---\n\n# NoCreated\nSee [[Overview]].\n", encoding="utf-8")
    env = {"GIT_AUTHOR_DATE": "2026-03-04T10:00:00", "GIT_COMMITTER_DATE": "2026-03-04T10:00:00"}
    subprocess.run(["git", "init", "-q"], cwd=vault, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "--allow-empty", "-m", "init"], cwd=vault, check=True, env={**os.environ, **env})
    subprocess.run(["git", "add", "-A"], cwd=vault, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "commit", "-q", "-m", "add"], cwd=vault, check=True, env={**os.environ, **env})
    code, data = findings(vault, "--fix")
    created = by_type(data, "created-missing")
    assert created and created[0]["severity"] == "auto-fixed"
    assert "created: 2026-03-04" in (vault / "wiki/entities/NoCreated.md").read_text(encoding="utf-8")
    fresh = by_type(data, "git-freshness")
    assert any(f["page"].endswith("NoCreated.md") for f in fresh)  # generated 2026-01-01 < commit 2026-03-04


def test_missing_generated_is_reported_never_invented(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/entities/NoGen.md").write_text("---\ntype: entity\ntitle: NoGen\ndescription: d\ncreated: 2026-01-01\n---\n\n# NoGen\nSee [[Overview]].\n", encoding="utf-8")
    code, data = findings(vault, "--fix")
    assert by_type(data, "generated-missing")[0]["severity"] == "judgement"
    assert "generated" not in (vault / "wiki/entities/NoGen.md").read_text(encoding="utf-8")


def test_restorable_missing_raw_is_informational(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "raw/Note Taking Guide.md").unlink()
    (vault / "raw/SOURCES.md").write_text("# Sources\n\n| Title | URL | File | Licence |\n|---|---|---|---|\n| Note Taking Guide | https://example.com/note-taking-guide | Note Taking Guide.md | CC0 |\n", encoding="utf-8")
    code, data = findings(vault)
    assert code == 0, data["judgement"]
    assert "restore" in types(data["informational"])
    assert "raw-missing" not in types(data["judgement"])


def test_scope_limits_page_checks_and_single_checker_subcommands_work(tmp_path: Path):
    vault = defective(tmp_path)
    r = run_script("lint.py", "stale", "--vault", str(vault), "--json")
    assert r.code == 1 and r.json()["findings"][0]["page"].endswith("Typo Page.md")
    r = run_script("lint.py", "wanted", "--vault", str(vault), "--json")
    assert r.json()["findings"][0]["target"] == "Progressive Disclosure"
    code, data = findings(vault, "--scope", str(vault / "wiki/concepts"))
    assert not any(f["page"].endswith("Typo Page.md") for f in data["judgement"] if f.get("page"))


def test_markdown_summary_groups_findings(tmp_path: Path):
    vault = defective(tmp_path)
    r = run_script("lint.py", "all", "--vault", str(vault))
    assert r.code == 1
    assert "## Needs judgement" in r.out and "## Informational" in r.out and "## Fixable" in r.out


def test_source_pages_are_never_orphans_and_frontmatter_source_links_count_as_inbound(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/sources/Thin.md").write_text(page("source", "Thin", raw="raw/Thin.md", raw_sha="x", disposition="no-material", ingested="2026-09-02"), encoding="utf-8")
    (vault / "raw/Thin.md").write_text("nothing new\n", encoding="utf-8")
    # an entity linked only from frontmatter sources of another page
    (vault / "wiki/sources/Cited Only.md").write_text(page("source", "Cited Only", raw="raw/Cited.md", raw_sha="x", disposition="new", ingested="2026-09-02"), encoding="utf-8")
    (vault / "raw/Cited.md").write_text("cited\n", encoding="utf-8")
    text = page("entity", "Citer", body="Links to [[Overview]].").replace("---\n\n# ", 'sources:\n  - id: c\n    page: "[[Cited Only]]"\n---\n\n# ', 1)
    (vault / "wiki/entities/Citer.md").write_text(text, encoding="utf-8")
    r = run_script("lint.py", "orphans", "--vault", str(vault), "--json")
    pages = {f["page"] for f in r.json()["findings"]}
    assert not any(p.endswith(("Thin.md", "Cited Only.md")) for p in pages)
    assert any(p.endswith("Citer.md") for p in pages)  # nothing links to Citer
    inbound = run_script("links.py", "inbound", "Cited Only", "--vault", str(vault), "--json").json()
    assert inbound["count"] == 1 and inbound["inbound"][0].endswith("Citer.md")


def test_explicitly_empty_sources_suppresses_ungrounded_suspects(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/syntheses/Overview.md").write_text(page("synthesis", "Overview", sources=[], body="## Thesis\nFounded in 2024 to keep 1,000 notes.\n").replace("sources: []", "sources: []"), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/syntheses/Overview.md"), "--json")
    assert r.code == 0, r
    assert r.json()["suspects"] == []


def test_restore_findings_are_reported_once_per_source_page(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "raw/Note Taking Guide.md").unlink()
    (vault / "raw/SOURCES.md").write_text("# Sources\n\n| Title | URL | File | Licence |\n|---|---|---|---|\n| Note Taking Guide | https://example.com/note-taking-guide | Note Taking Guide.md | CC0 |\n", encoding="utf-8")
    code, data = findings(vault)
    assert code == 0, data["judgement"]
    restore = by_type(data, "restore")
    assert len(restore) == 1 and restore[0]["page"].endswith("Note Taking Guide.md")
    assert "evidence-suspect" not in types(data["judgement"])


def test_remaining_finding_types_have_a_defect_case(tmp_path: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    # duplicate-basename: same basename in two type folders
    (vault / "wiki/analyses/Obsidian.md").write_text(page("analysis", "Obsidian", question="Q?", body="See [[Overview]]."), encoding="utf-8")
    # frontmatter-invalid: unparseable yaml
    (vault / "wiki/concepts/Broken.md").write_text("---\ntype: concept\nnested:\n  a:\n    b: c\n---\n# Broken\nSee [[Overview]].\n", encoding="utf-8")
    # evidence-error: source entry pointing at a page that does not exist
    (vault / "wiki/entities/Dangling.md").write_text(page("entity", "Dangling", body="Says 12,345 things. See [[Overview]].").replace("---\n\n# ", 'sources:\n  - id: ghost\n    page: "[[Ghost Source]]"\n---\n\n# ', 1), encoding="utf-8")
    # generic-block-edited: same version, different content
    claude = vault / "CLAUDE.md"
    claude.write_text(claude.read_text(encoding="utf-8").replace("### Truth", "### Truth (edited locally)"), encoding="utf-8")
    code, data = findings(vault)
    assert code == 1
    assert {"duplicate-basename", "frontmatter-invalid", "evidence-error", "generic-block-edited"} <= types(data["judgement"])
    # generic-block-missing
    claude.write_text("# No block here\n", encoding="utf-8")
    code, data = findings(vault)
    assert "generic-block-missing" in types(data["judgement"])
