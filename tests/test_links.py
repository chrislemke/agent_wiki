from pathlib import Path

from conftest import page, run_script


def setup(vault: Path) -> None:
    (vault / "wiki/entities/Obsidian.md").write_text(page("entity", "Obsidian", aliases=["The Reader"]), encoding="utf-8")
    (vault / "wiki/concepts/Grounding Invariant.md").write_text(page("concept", "Grounding Invariant"), encoding="utf-8")
    (vault / "wiki/syntheses/Overview.md").write_text(
        page(
            "synthesis",
            "Overview",
            body=(
                "See [[Obsidian]] and [[Obsidian|the reader]] and [[The Reader]].\n"
                "Also [[Grounding Invariant#Definition]] and ![[diagram.png]].\n"
                "Typo: [[Obsidan]] and a wanted page: [[Progressive Disclosure]].\n"
                "In code `[[Not A Link]]` and\n\n```\n[[Also Not A Link]]\n```\n"
            ),
        ),
        encoding="utf-8",
    )
    (vault / "raw/assets/diagram.png").write_bytes(b"png")


def test_resolve_classifies_resolved_unresolved_and_near_miss(vault: Path):
    setup(vault)
    r = run_script("links.py", "resolve", str(vault / "wiki/syntheses/Overview.md"), "--json")
    assert r.code == 1, r  # findings present
    data = r.json()
    resolved = {(l["target"], l["path"].split("/")[-1]) for l in data["resolved"]}
    assert ("Obsidian", "Obsidian.md") in resolved
    assert ("The Reader", "Obsidian.md") in resolved  # alias
    assert ("Grounding Invariant", "Grounding Invariant.md") in resolved  # heading stripped
    assert ("diagram.png", "diagram.png") in resolved  # embed of an asset
    assert [l["target"] for l in data["unresolved"]] == ["Progressive Disclosure"]
    assert data["near_miss"][0]["target"] == "Obsidan"
    assert data["near_miss"][0]["suggestion"] == "Obsidian"
    targets = {l["target"] for group in ("resolved", "unresolved", "near_miss") for l in data[group]}
    assert "Not A Link" not in targets and "Also Not A Link" not in targets


def test_resolve_whole_vault_reports_duplicates_and_inbound_counts(vault: Path):
    setup(vault)
    (vault / "wiki/analyses/Obsidian.md").write_text(page("analysis", "Obsidian", question="Q?"), encoding="utf-8")
    r = run_script("links.py", "resolve", str(vault), "--json")
    assert r.code == 1
    data = r.json()
    assert data["duplicates"][0]["basename"] == "Obsidian"
    assert len(data["duplicates"][0]["paths"]) == 2


def test_resolve_clean_page_exits_zero(vault: Path):
    setup(vault)
    (vault / "wiki/entities/Clean.md").write_text(page("entity", "Clean", body="Links to [[Obsidian]] only."), encoding="utf-8")
    r = run_script("links.py", "resolve", str(vault / "wiki/entities/Clean.md"))
    assert r.code == 0, r


def test_inbound_lists_pages_linking_to_a_target(vault: Path):
    setup(vault)
    r = run_script("links.py", "inbound", "Obsidian", "--vault", str(vault), "--json")
    assert r.code == 0, r
    assert [p.split("/")[-1] for p in r.json()["inbound"]] == ["Overview.md"]
    r = run_script("links.py", "inbound", "Grounding Invariant", "--vault", str(vault), "--json")
    assert r.json()["count"] == 1
