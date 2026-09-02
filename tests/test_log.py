from pathlib import Path

from conftest import run_script


def test_append_writes_entry_in_fixed_format(vault: Path):
    r = run_script(
        "log.py", "append", "--op", "ingest", "--title", "LLM Wiki",
        "--created", "LLM Wiki", "--created", "[[Obsidian]]", "--updated", "Overview", "--note", "First ingest.",
        "--vault", str(vault), env={"AGENT_WIKI_TODAY": "2026-09-02"},
    )
    assert r.code == 0, r
    text = (vault / "log.md").read_text(encoding="utf-8")
    assert text.endswith(
        "\n## [2026-09-02] ingest | LLM Wiki\n- Created: [[LLM Wiki]], [[Obsidian]]\n- Updated: [[Overview]]\n- Note: First ingest.\n"
    )


def test_append_rejects_unknown_operation(vault: Path):
    r = run_script("log.py", "append", "--op", "dance", "--title", "x", "--vault", str(vault))
    assert r.code == 2
    assert "## [" not in (vault / "log.md").read_text(encoding="utf-8")


def test_parse_tail_and_since_lint(vault: Path):
    for op, title, day in [("init", "Test Vault", "2026-09-01"), ("ingest", "A", "2026-09-01"), ("lint", "2 fixed, 1 proposed", "2026-09-01"), ("ingest", "B", "2026-09-02"), ("query", "What is B?", "2026-09-02"), ("ingest", "C", "2026-09-02")]:
        assert run_script("log.py", "append", "--op", op, "--title", title, "--vault", str(vault), env={"AGENT_WIKI_TODAY": day}).code == 0
    entries = run_script("log.py", "parse", "--vault", str(vault), "--json").json()["entries"]
    assert [e["op"] for e in entries] == ["init", "ingest", "lint", "ingest", "query", "ingest"]
    assert entries[2] == {"date": "2026-09-01", "op": "lint", "title": "2 fixed, 1 proposed", "created": [], "updated": [], "note": None}
    tail = run_script("log.py", "tail", "2", "--vault", str(vault), "--json").json()["entries"]
    assert [e["title"] for e in tail] == ["What is B?", "C"]
    since = run_script("log.py", "since-lint", "--vault", str(vault), "--json").json()
    assert since == {"ingests_since_lint": 2, "last_lint": "2026-09-01"}


def test_since_lint_counts_all_ingests_when_never_linted(vault: Path):
    run_script("log.py", "append", "--op", "ingest", "--title", "A", "--vault", str(vault))
    since = run_script("log.py", "since-lint", "--vault", str(vault), "--json").json()
    assert since == {"ingests_since_lint": 1, "last_lint": None}


def test_tail_text_output_prints_entries(vault: Path):
    run_script("log.py", "append", "--op", "fetch", "--title", "Some URL", "--vault", str(vault), env={"AGENT_WIKI_TODAY": "2026-09-02"})
    r = run_script("log.py", "tail", "5", "--vault", str(vault))
    assert r.code == 0
    assert "## [2026-09-02] fetch | Some URL" in r.out
