import hashlib
from pathlib import Path

from conftest import page, run_script


def test_hash_prints_sha256_of_file(vault: Path):
    f = vault / "raw/Note.md"
    f.write_text("hello\n", encoding="utf-8")
    r = run_script("rawhash.py", "hash", str(f))
    assert r.code == 0
    assert r.out.strip() == hashlib.sha256(b"hello\n").hexdigest()


def test_compare_reports_match_mismatch_and_missing(vault: Path):
    (vault / "raw/Good.md").write_text("good\n", encoding="utf-8")
    (vault / "raw/Changed.md").write_text("changed later\n", encoding="utf-8")
    good_sha = hashlib.sha256(b"good\n").hexdigest()
    (vault / "wiki/sources/Good.md").write_text(page("source", "Good", raw="raw/Good.md", raw_sha=good_sha, disposition="new", ingested="2026-09-01"), encoding="utf-8")
    (vault / "wiki/sources/Changed.md").write_text(page("source", "Changed", raw="raw/Changed.md", raw_sha="deadbeef", disposition="new", ingested="2026-09-01"), encoding="utf-8")
    (vault / "wiki/sources/Missing.md").write_text(page("source", "Missing", raw="raw/Missing.md", raw_sha="deadbeef", disposition="new", ingested="2026-09-01"), encoding="utf-8")
    r = run_script("rawhash.py", "compare", str(vault), "--json")
    assert r.code == 1
    by_page = {x["page"].split("/")[-1]: x["status"] for x in r.json()["results"]}
    assert by_page == {"Good.md": "match", "Changed.md": "mismatch", "Missing.md": "missing"}
    r = run_script("rawhash.py", "compare", str(vault / "wiki/sources/Good.md"))
    assert r.code == 0
