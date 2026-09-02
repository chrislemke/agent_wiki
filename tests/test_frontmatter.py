from pathlib import Path

from conftest import TODAY, make_vault, page, run_script

CANONICAL_PAGE = """---
type: source
title: LLM Wiki
description: Karpathy's pattern for an LLM-maintained knowledge base.
aliases: [Karpathy Wiki, "LLM Wiki: pattern"]
tags: [llm-wiki, docs]
status: stable
created: 2026-09-01
generated:
  by: agent-wiki/test-model
  at: 2026-09-01
verified:
  - by: human:tester
    at: 2026-09-02
stale_after: 2026-12-01
sources:
  - id: llm-wiki
    page: "[[LLM Wiki]]"
raw: raw/LLM Wiki.md
raw_sha: 0123abcd
disposition: new
author: Andrej Karpathy
published: 2026-04-02
resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
ingested: 2026-09-01
custom_field: kept as is
---

# LLM Wiki

Body text.
"""


def write(vault: Path, rel: str, text: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_parse_reads_scalars_lists_and_nested_mappings_as_strings(vault: Path):
    p = write(vault, "wiki/sources/LLM Wiki.md", CANONICAL_PAGE)
    r = run_script("frontmatter.py", "parse", str(p), "--json")
    assert r.code == 0, r
    data = r.json()["frontmatter"]
    assert data["type"] == "source"
    assert data["created"] == "2026-09-01"  # a string, never a date object
    assert data["aliases"] == ["Karpathy Wiki", "LLM Wiki: pattern"]
    assert data["generated"] == {"by": "agent-wiki/test-model", "at": "2026-09-01"}
    assert data["verified"] == [{"by": "human:tester", "at": "2026-09-02"}]
    assert data["sources"] == [{"id": "llm-wiki", "page": "[[LLM Wiki]]"}]
    assert data["custom_field"] == "kept as is"
    assert r.json()["body"].startswith("\n# LLM Wiki")


def test_parse_accepts_inline_mappings_and_bare_verified_mapping(vault: Path):
    text = """---
type: entity
title: Obsidian
description: The reader.
created: 2026-09-01
generated: { by: agent-wiki/test-model, at: 2026-09-01 }
verified: { by: human:tester, at: 2026-09-02 }
sources:
  - { id: a, page: "[[A]]" }
tags:
  - alpha
  - beta
---
Body
"""
    p = write(vault, "wiki/entities/Obsidian.md", text)
    r = run_script("frontmatter.py", "parse", str(p), "--json")
    assert r.code == 0, r
    data = r.json()["frontmatter"]
    assert data["generated"] == {"by": "agent-wiki/test-model", "at": "2026-09-01"}
    assert data["verified"] == {"by": "human:tester", "at": "2026-09-02"}
    assert data["sources"] == [{"id": "a", "page": "[[A]]"}]
    assert data["tags"] == ["alpha", "beta"]


def test_parse_reports_unparseable_yaml_instead_of_guessing(vault: Path):
    text = "---\ntype: entity\nnested:\n  deeper:\n    too: far\n---\nBody\n"
    p = write(vault, "wiki/entities/Bad.md", text)
    r = run_script("frontmatter.py", "parse", str(p), "--json")
    assert r.code == 1
    assert "unparseable" in r.err.lower() or "unparseable" in r.out.lower()


def test_parse_page_without_frontmatter_reports_missing(vault: Path):
    p = write(vault, "wiki/entities/None.md", "# No frontmatter\n")
    r = run_script("frontmatter.py", "parse", str(p), "--json")
    assert r.code == 1
    assert r.json()["frontmatter"] is None


def test_roundtrip_of_canonical_page_is_byte_identical(vault: Path):
    p = write(vault, "wiki/sources/LLM Wiki.md", CANONICAL_PAGE)
    r = run_script("frontmatter.py", "normalize", str(p))
    assert r.code == 0, r
    assert p.read_text(encoding="utf-8") == CANONICAL_PAGE


def test_normalize_reorders_keys_and_keeps_unknown_keys_after_known(vault: Path):
    text = """---
custom_field: first
title: Zed
type: entity
created: 2026-09-01
generated: { by: agent-wiki/test-model, at: 2026-09-01 }
description: Out of order.
---
Body
"""
    p = write(vault, "wiki/entities/Zed.md", text)
    r = run_script("frontmatter.py", "normalize", str(p))
    assert r.code == 0, r
    assert p.read_text(encoding="utf-8") == """---
type: entity
title: Zed
description: Out of order.
created: 2026-09-01
generated:
  by: agent-wiki/test-model
  at: 2026-09-01
custom_field: first
---
Body
"""


# ---------------------------------------------------------------- validate

def test_validate_clean_vault_exits_zero(vault: Path):
    write(vault, "wiki/entities/Obsidian.md", page("entity", "Obsidian"))
    write(vault, "wiki/sources/LLM Wiki.md", CANONICAL_PAGE)
    r = run_script("frontmatter.py", "validate", str(vault), "--json")
    assert r.code == 0, r
    assert r.json()["errors"] == 0


def test_validate_reports_missing_required_fields_per_type(vault: Path):
    text = "---\ntype: source\ntitle: Thin\ncreated: 2026-09-01\ngenerated: { by: x, at: 2026-09-01 }\n---\nBody\n"
    p = write(vault, "wiki/sources/Thin.md", text)
    r = run_script("frontmatter.py", "validate", str(p), "--json")
    assert r.code == 1
    errors = r.json()["results"][0]["errors"]
    assert "missing required field: description" in errors
    assert "missing required field for source: raw" in errors
    assert "missing required field for source: raw_sha" in errors
    assert "missing required field for source: disposition" in errors
    assert "missing required field for source: ingested" in errors


def test_validate_checks_enums_and_iso_dates(vault: Path):
    text = "---\ntype: entity\ntitle: Bad Dates\ndescription: d\ncreated: 01.09.2026\nstatus: wobbly\ngenerated: { by: x, at: 2026-09-01 }\n---\nBody\n"
    p = write(vault, "wiki/entities/Bad Dates.md", text)
    r = run_script("frontmatter.py", "validate", str(p))
    assert r.code == 1
    assert "created is not an ISO date" in r.out
    assert "invalid status: wobbly" in r.out


def test_validate_warns_but_passes_on_unknown_type_and_unknown_fields(vault: Path):
    text = "---\ntype: recipe\ntitle: Soup\ndescription: d\ncreated: 2026-09-01\ngenerated: { by: x, at: 2026-09-01 }\nspice_level: 3\n---\nBody\n"
    p = write(vault, "wiki/entities/Soup.md", text)
    r = run_script("frontmatter.py", "validate", str(p), "--json")
    assert r.code == 0, r
    result = r.json()["results"][0]
    assert result["errors"] == []
    assert "unknown type: recipe" in result["warnings"]


def test_validate_requires_id_and_page_on_every_source_entry(vault: Path):
    text = "---\ntype: concept\ntitle: C\ndescription: d\ncreated: 2026-09-01\ngenerated: { by: x, at: 2026-09-01 }\nsources:\n  - id: only-id\n---\nBody\n"
    p = write(vault, "wiki/concepts/C.md", text)
    r = run_script("frontmatter.py", "validate", str(p))
    assert r.code == 1
    assert "sources entry must carry id and page" in r.out


# ---------------------------------------------------------------- stamp

def test_stamp_sets_generated_and_created_and_stale_after_from_shortest_tag_window(vault: Path):
    text = "---\ntype: entity\ntitle: Fresh\ndescription: d\ntags: [docs, alpha]\n---\nBody\n"
    p = write(vault, "wiki/entities/Fresh.md", text)
    r = run_script("frontmatter.py", "stamp", str(p), "--by", "agent-wiki/test-model", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    data = run_script("frontmatter.py", "parse", str(p), "--json").json()["frontmatter"]
    assert data["generated"] == {"by": "agent-wiki/test-model", "at": "2026-09-02"}
    assert data["created"] == "2026-09-02"
    assert data["stale_after"] == "2026-10-02"  # alpha: 30 days beats docs: 90


def test_stamp_keeps_created_and_verified_and_drops_stale_after_without_matching_tag(vault: Path):
    text = "---\ntype: entity\ntitle: Old\ndescription: d\ntags: [beta]\ncreated: 2026-01-01\nverified:\n  - by: human:tester\n    at: 2026-02-02\nstale_after: 2026-03-03\n---\nBody\n"
    p = write(vault, "wiki/entities/Old.md", text)
    r = run_script("frontmatter.py", "stamp", str(p), "--by", "agent-wiki/test-model", env={"AGENT_WIKI_TODAY": "2026-09-02"})
    assert r.code == 0, r
    data = run_script("frontmatter.py", "parse", str(p), "--json").json()["frontmatter"]
    assert data["created"] == "2026-01-01"
    assert data["verified"] == [{"by": "human:tester", "at": "2026-02-02"}]
    assert "stale_after" not in data
    assert data["generated"]["at"] == "2026-09-02"


def test_set_refuses_verified(vault: Path):
    p = write(vault, "wiki/entities/Obsidian.md", page("entity", "Obsidian"))
    r = run_script("frontmatter.py", "set", str(p), "verified", "human:x")
    assert r.code == 2
    assert "verified" not in p.read_text(encoding="utf-8")


def test_set_updates_scalar_and_keeps_canonical_order(vault: Path):
    p = write(vault, "wiki/entities/Obsidian.md", page("entity", "Obsidian"))
    r = run_script("frontmatter.py", "set", str(p), "status", "contested")
    assert r.code == 0, r
    data = run_script("frontmatter.py", "parse", str(p), "--json").json()["frontmatter"]
    assert data["status"] == "contested"
