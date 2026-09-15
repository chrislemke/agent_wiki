from pathlib import Path

from conftest import page, run_script

RAW_A = """---
title: Ghostty Update
resource: https://example.com/ghostty
fetched: 2026-09-01
---

# Ghostty Update

Ghostty reached 42K stars on GitHub in April 2026. The maintainer said "the terminal should feel invisible to users".
Daily active users reached 10,000 by 2026-03-31.
"""

RAW_B = """---
title: Other Report
resource: https://example.com/other
fetched: 2026-09-01
---

# Other Report

Forks grew to 3,020 last week. Uptime was 99.9%.
"""


def source_page(title: str, raw: str, sid: str) -> str:
    text = page("source", title, raw=f"raw/{raw}", raw_sha="x", disposition="new", ingested="2026-09-01", body="## Summary\nSee source.\n")
    return text.replace("---\n\n# ", f"sources:\n  - id: {sid}\n    page: \"[[{title}]]\"\n---\n\n# ", 1)


def setup(vault: Path) -> None:
    (vault / "raw/Ghostty Update.md").write_text(RAW_A, encoding="utf-8")
    (vault / "raw/Other Report.md").write_text(RAW_B, encoding="utf-8")
    (vault / "wiki/sources/Ghostty Update.md").write_text(source_page("Ghostty Update", "Ghostty Update.md", "ghostty"), encoding="utf-8")
    (vault / "wiki/sources/Other Report.md").write_text(source_page("Other Report", "Other Report.md", "other"), encoding="utf-8")


def entity(title: str, body: str, sources: list[tuple[str, str]]) -> str:
    src = "sources:\n" + "".join(f"  - id: {sid}\n    page: \"[[{p}]]\"\n" for sid, p in sources)
    return page("entity", title, body=body).replace("---\n\n# ", src + "---\n\n# ", 1)


def test_unfootnoted_literals_present_in_any_source_pass(vault: Path):
    setup(vault)
    body = "## Key facts\nGhostty has 42K stars and 10,000 daily users. Forks grew to 3,020 last week.\n"
    (vault / "wiki/entities/Ghostty.md").write_text(entity("Ghostty", body, [("ghostty", "Ghostty Update"), ("other", "Other Report")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Ghostty.md"), "--json")
    assert r.code == 0, r
    assert r.json()["suspects"] == []


def test_footnoted_literal_is_checked_only_against_that_source(vault: Path):
    setup(vault)
    # 3,020 lives in Other Report, but the footnote points at ghostty -> suspect
    body = "## Key facts\nForks grew to 3,020 last week.[^ghostty]\nStars: 42K.[^ghostty]\n"
    (vault / "wiki/entities/Ghostty.md").write_text(entity("Ghostty", body, [("ghostty", "Ghostty Update"), ("other", "Other Report")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Ghostty.md"), "--json")
    assert r.code == 1, r
    suspects = r.json()["suspects"]
    assert [(s["value"], s["footnote"]) for s in suspects] == [("3,020", "ghostty")]


def test_literals_in_code_and_disputed_blocks_are_ignored_but_quotes_and_dates_are_checked(vault: Path):
    setup(vault)
    body = (
        "## Notes\n"
        "Install with `--limit 9000` today.\n\n"
        "```\nexample 78K and 9,999\n```\n\n"
        "> **Status: Disputed**\n> One source says 55K stars, another 60K.\n\n"
        'The maintainer said "the terminal should feel invisible to users" on 2026-03-31.\n'
        'Someone else claimed "this quote appears in no source at all".\n'
        "The launch was on 2025-01-15.\n"
    )
    (vault / "wiki/entities/Ghostty.md").write_text(entity("Ghostty", body, [("ghostty", "Ghostty Update")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Ghostty.md"), "--json")
    assert r.code == 1
    values = sorted(s["value"] for s in r.json()["suspects"])
    assert values == ["2025-01-15", "this quote appears in no source at all"]


def test_missing_raw_listed_as_restorable_is_informational_not_error(vault: Path):
    setup(vault)
    (vault / "raw/Ghostty Update.md").unlink()
    (vault / "raw/SOURCES.md").write_text(
        "# Sources\n\n| Title | URL | File | Licence |\n|---|---|---|---|\n| Ghostty Update | https://example.com/ghostty | Ghostty Update.md | not stated |\n",
        encoding="utf-8",
    )
    body = "## Key facts\nGhostty has 42K stars.\n"
    (vault / "wiki/entities/Ghostty.md").write_text(entity("Ghostty", body, [("ghostty", "Ghostty Update")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Ghostty.md"), "--json")
    assert r.code == 0, r
    data = r.json()
    assert data["errors"] == [] and data["suspects"] == []
    assert data["restore"][0]["raw"] == "raw/Ghostty Update.md"
    assert data["restore"][0]["url"] == "https://example.com/ghostty"


def test_missing_raw_not_restorable_is_an_error(vault: Path):
    setup(vault)
    (vault / "raw/Other Report.md").unlink()
    body = "## Key facts\nUptime was 99.9%.\n"
    (vault / "wiki/entities/Uptime.md").write_text(entity("Uptime", body, [("other", "Other Report")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Uptime.md"), "--json")
    assert r.code == 1
    assert "raw/Other Report.md" in r.json()["errors"][0]["detail"]


def test_page_without_sources_reports_literals_as_ungrounded(vault: Path):
    setup(vault)
    (vault / "wiki/syntheses/Overview.md").write_text(page("synthesis", "Overview", body="## Thesis\nThere are 1,234 reasons.\n"), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault), "--json")
    assert r.code == 1
    s = [x for x in r.json()["suspects"] if x["value"] == "1,234"][0]
    assert s["checked"] == [] and "no sources" in s["detail"]


def test_text_report_and_vault_scope(vault: Path):
    setup(vault)
    r = run_script("evidence.py", "check", str(vault))
    assert r.code == 0, r
    assert "suspect" in r.out.lower()


def test_literals_that_could_live_in_a_restorable_missing_raw_are_not_suspects(vault: Path):
    setup(vault)
    (vault / "raw/Ghostty Update.md").unlink()
    (vault / "raw/SOURCES.md").write_text(
        "# Sources\n\n| Title | URL | File | Licence |\n|---|---|---|---|\n| Ghostty Update | https://example.com/ghostty | Ghostty Update.md | not stated |\n",
        encoding="utf-8",
    )
    body = "## Key facts\nStars: 42K.[^ghostty]\nForks grew to 3,020 last week.[^other]\nSomewhere it says 10,000 users.\nBut 77,777 appears nowhere.[^other]\n"
    (vault / "wiki/entities/Ghostty.md").write_text(entity("Ghostty", body, [("ghostty", "Ghostty Update"), ("other", "Other Report")]), encoding="utf-8")
    r = run_script("evidence.py", "check", str(vault / "wiki/entities/Ghostty.md"), "--json")
    data = r.json()
    # 42K (footnoted to the missing source) and 10,000 (unfootnoted, could be in it) are skipped;
    # 77,777 is footnoted to a present source and is a real suspect
    assert [s["value"] for s in data["suspects"]] == ["77,777"]
    assert data["restore"] and data["errors"] == []


# ------------------------------------------------------------------ publisher typography

RAW_TYPO = """---
title: Typography Report
resource: https://example.com/typo
fetched: 2026-09-01
---

# Typography Report

The roaster said “We don’t chase the 18–22% window any more.”
She called it a «careful, slow process» that runs 40–50 minutes—no shortcuts…
The café in München roasts on site.
Some long words are soft­hyphenated across a line.
"""


def typo_setup(vault: Path) -> None:
    (vault / "raw/Typography Report.md").write_text(RAW_TYPO, encoding="utf-8")
    (vault / "wiki/sources/Typography Report.md").write_text(source_page("Typography Report", "Typography Report.md", "typo"), encoding="utf-8")


def typo_page(vault: Path, body: str) -> Path:
    path = vault / "wiki/entities/Roasting.md"
    path.write_text(entity("Roasting", body, [("typo", "Typography Report")]), encoding="utf-8")
    return path


TYPOGRAPHY_CASES = [
    ("curly double quotes", '"We don\'t chase the 18-22% window any more."[^typo]'),
    ("curly apostrophe", '"We don’t chase the 18-22% window any more."[^typo]'),
    ("en dash as hyphen", '"We don\'t chase the 18-22% window any more."[^typo]'),
    ("em dash as hyphen", '"that runs 40-50 minutes-no shortcuts"[^typo] is what she said.'),
    ("ellipsis spelled out", '"runs 40-50 minutes-no shortcuts..."[^typo]'),
    ("guillemets as quotes", '"careful, slow process"[^typo] is how she put it, over 15 characters.'),
    ("decomposed accent", '"The café in München roasts on site."[^typo]'),
    ("soft hyphen dropped", '"Some long words are softhyphenated across a line."[^typo]'),
]


def test_publisher_typography_is_not_reported_as_fabrication(vault: Path):
    """A page that retypes a quote with an ASCII keyboard is quoting, not inventing."""
    typo_setup(vault)
    for name, line in TYPOGRAPHY_CASES:
        page_path = typo_page(vault, f"## Quotes\n{line}\n\n[^typo]: Typography Report\n")
        r = run_script("evidence.py", "check", str(page_path), "--json")
        assert r.json()["suspects"] == [], (name, r.out)


def test_a_folded_comparison_still_catches_a_doctored_quote(vault: Path):
    typo_setup(vault)
    body = (
        "## Quotes\n"
        '"We do chase the 18-22% window any more."[^typo]\n'
        '"We don\'t chase the 25-30% window any more."[^typo]\n\n'
        "[^typo]: Typography Report\n"
    )
    page_path = typo_page(vault, body)
    r = run_script("evidence.py", "check", str(page_path), "--json")
    values = [s["value"] for s in r.json()["suspects"]]
    assert "We do chase the 18-22% window any more" in values, r.out
    assert "We don't chase the 25-30% window any more" in values, r.out
    assert "30%" in values  # the invented number is caught on its own too
