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
