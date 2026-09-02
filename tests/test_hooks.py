"""Hooks are run exactly as Claude Code runs them: a JSON event on stdin, a fixture vault, assertions
on exit code, stdout/stderr and the session-state file."""
import json
import os
from pathlib import Path

import pytest

from conftest import PLUGIN, copy_fixture, page, run_hook, run_script


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    d = tmp_path / "state"
    d.mkdir()
    return d


def env_for(state_dir: Path) -> dict:
    return {"AGENT_WIKI_STATE_DIR": str(state_dir), "AGENT_WIKI_TODAY": "2026-09-02"}


def ev(vault: Path, name: str, **fields) -> dict:
    base = {"session_id": "sess1", "cwd": str(vault), "hook_event_name": name, "transcript_path": "/dev/null"}
    base.update(fields)
    return base


def write_event(vault: Path, path: Path, content: str) -> dict:
    return ev(vault, "PreToolUse", tool_name="Write", tool_input={"file_path": str(path), "content": content})


def edit_event(vault: Path, path: Path, old: str, new: str) -> dict:
    return ev(vault, "PreToolUse", tool_name="Edit", tool_input={"file_path": str(path), "old_string": old, "new_string": new})


def bash_event(vault: Path, command: str) -> dict:
    return ev(vault, "PreToolUse", tool_name="Bash", tool_input={"command": command})


def decision(r) -> str:
    if not r.out.strip():
        return "allow"
    return json.loads(r.out)["hookSpecificOutput"]["permissionDecision"]


# ------------------------------------------------------------------ silence outside a vault

@pytest.mark.parametrize("hook,event_name", [("session_start.py", "SessionStart"), ("pre_tool_use.py", "PreToolUse"), ("post_tool_use.py", "PostToolUse"), ("stop.py", "Stop")])
def test_hooks_are_silent_outside_a_vault(tmp_path: Path, state_dir: Path, hook: str, event_name: str):
    event = ev(tmp_path, event_name, tool_name="Write", tool_input={"file_path": str(tmp_path / "raw/x.md"), "content": "x"})
    r = run_hook(hook, event, cwd=tmp_path, env=env_for(state_dir))
    assert r.code == 0 and r.out == "" and r.err == "", r


# ------------------------------------------------------------------ raw immutability

def test_write_and_edit_into_raw_are_denied(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", write_event(vault, vault / "raw/New.md", "x"), env=env_for(state_dir))
    assert r.code == 0 and decision(r) == "deny"
    assert "raw" in json.loads(r.out)["hookSpecificOutput"]["permissionDecisionReason"]
    r = run_hook("pre_tool_use.py", edit_event(vault, vault / "raw/Note Taking Guide.md", "Obsidian", "Notion"), env=env_for(state_dir))
    assert decision(r) == "deny"
    # detection also works from a cwd outside the vault when the target is inside one
    r = run_hook("pre_tool_use.py", {**write_event(vault, vault / "raw/New.md", "x"), "cwd": str(tmp_path)}, env=env_for(state_dir))
    assert decision(r) == "deny"


@pytest.mark.parametrize("command", [
    "sed -i '' 's/a/b/' raw/Note\\ Taking\\ Guide.md",
    "sed -i.bak 's/a/b/' 'raw/Note Taking Guide.md'",
    "mv raw/Note\\ Taking\\ Guide.md raw/Other.md",
    "cp /tmp/x.md raw/x.md",
    "rm 'raw/Note Taking Guide.md'",
    "echo hi > raw/new.md",
    "cat a.md >> raw/new.md",
    "tee raw/new.md < a.md",
    "truncate -s 0 raw/new.md",
    "python3 -c \"open('raw/x.md','w').write('x')\"",
    "touch raw/new.md",
    "git mv raw/a.md raw/b.md",
    "perl -pi -e 's/a/b/' raw/a.md",
])
def test_write_like_bash_commands_targeting_raw_are_denied(tmp_path: Path, state_dir: Path, command: str):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", bash_event(vault, command), env=env_for(state_dir))
    assert decision(r) == "deny", (command, r)


@pytest.mark.parametrize("command", [
    "cat 'raw/Note Taking Guide.md'",
    "rg -n Obsidian raw/",
    "head -20 raw/Note\\ Taking\\ Guide.md",
    "sed -n '1,20p' raw/Note\\ Taking\\ Guide.md",
    "ls raw/assets",
    "grep -r users raw",
    "wc -l raw/*.md",
    f"python3 {PLUGIN}/scripts/fetch.py url https://example.com --vault .",
    f"python3 \"{PLUGIN}/scripts/verify.py\" wiki/entities/Obsidian.md --by chris",
    f"python3 {PLUGIN}/scripts/rawhash.py hash 'raw/Note Taking Guide.md'",
    "echo hi > wiki/entities/Draft.md",
    "sed -i '' 's/a/b/' wiki/entities/Obsidian.md",
])
def test_read_only_and_allowlisted_commands_pass(tmp_path: Path, state_dir: Path, command: str):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", bash_event(vault, command), env=env_for(state_dir))
    assert r.code == 0 and decision(r) == "allow", (command, r)


# ------------------------------------------------------------------ trust and provenance guards

def test_changing_verified_is_denied_for_write_and_edit(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"
    text = target.read_text(encoding="utf-8")
    # Write that drops verified
    r = run_hook("pre_tool_use.py", write_event(vault, target, text.replace("verified:\n  - by: human:tester\n    at: 2026-09-01\n", "")), env=env_for(state_dir))
    assert decision(r) == "deny" and "verified" in r.out
    # Edit that changes the verifier date
    r = run_hook("pre_tool_use.py", edit_event(vault, target, "at: 2026-09-01\nsources", "at: 2026-09-02\nsources"), env=env_for(state_dir))
    assert decision(r) == "deny"
    # Write adding verified to a page without it
    concept = vault / "wiki/concepts/Wikilinks.md"
    r = run_hook("pre_tool_use.py", write_event(vault, concept, concept.read_text(encoding="utf-8").replace("sources:", "verified: { by: human:tester, at: 2026-09-02 }\nsources:")), env=env_for(state_dir))
    assert decision(r) == "deny"


def test_shrinking_sources_is_denied_and_growth_allowed(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"
    text = target.read_text(encoding="utf-8")
    shrunk = text.replace("sources:\n  - id: guide\n    page: \"[[Note Taking Guide]]\"\n", "")
    r = run_hook("pre_tool_use.py", write_event(vault, target, shrunk), env=env_for(state_dir))
    assert decision(r) == "deny" and "sources" in r.out
    grown = text.replace("    page: \"[[Note Taking Guide]]\"\n", "    page: \"[[Note Taking Guide]]\"\n  - id: extra\n    page: \"[[Extra]]\"\n")
    r = run_hook("pre_tool_use.py", write_event(vault, target, grown), env=env_for(state_dir))
    assert r.code == 0 and decision(r) == "allow", r
    # a brand-new page has nothing to shrink
    r = run_hook("pre_tool_use.py", write_event(vault, vault / "wiki/entities/New.md", page("entity", "New")), env=env_for(state_dir))
    assert decision(r) == "allow"


# ------------------------------------------------------------------ post-write warnings

def post_write(vault: Path, path: Path, new_text: str, state_dir: Path):
    """Simulate Claude Code: PreToolUse snapshot, the write itself, PostToolUse."""
    pre = run_hook("pre_tool_use.py", write_event(vault, path, new_text), env=env_for(state_dir))
    assert decision(pre) == "allow", pre
    path.write_text(new_text, encoding="utf-8")
    return run_hook("post_tool_use.py", ev(vault, "PostToolUse", tool_name="Write", tool_input={"file_path": str(path), "content": new_text}, tool_response={"success": True}), env=env_for(state_dir))


def test_heading_removal_warns_and_addition_is_silent(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"
    text = target.read_text(encoding="utf-8")
    r = post_write(vault, target, text + "\n## Timeline\n- 2020: launched.\n", state_dir)
    assert r.code == 0 and r.err == "", r
    r = post_write(vault, target, target.read_text(encoding="utf-8").replace("## Key facts\n- Passed 1,000,000 users in 2024.[^guide]\n", ""), state_dir)
    assert r.code == 2 and "Key facts" in r.err


def test_invalid_frontmatter_and_near_miss_warn_but_clean_unresolved_link_is_silent(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    good = vault / "wiki/entities/Good.md"
    r = post_write(vault, good, page("entity", "Good", body="A wanted page: [[Progressive Disclosure]]."), state_dir)
    assert r.code == 0 and r.err == "", r
    typo = vault / "wiki/entities/Typo.md"
    r = post_write(vault, typo, page("entity", "Typo", body="See [[Obsidan]]."), state_dir)
    assert r.code == 2 and "Obsidian" in r.err
    bad = vault / "wiki/entities/Bad.md"
    r = post_write(vault, bad, "---\ntype: entity\ntitle: Bad\n---\n# Bad\n", state_dir)
    assert r.code == 2 and "description" in r.err


# ------------------------------------------------------------------ the stop gate

def test_stop_blocks_once_for_unlogged_wiki_changes_then_passes(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"
    post_write(vault, target, target.read_text(encoding="utf-8") + "\nMore.\n", state_dir)
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.code == 0, r
    out = json.loads(r.out)
    assert out["decision"] == "block" and "log" in out["reason"].lower()
    # Claude Code re-invokes with the active flag: never trap the session
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=True), env=env_for(state_dir))
    assert r.code == 0 and r.out.strip() == ""
    # and the same unresolved problems do not block a second time
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.code == 0 and r.out.strip() == ""


def test_stop_passes_when_log_was_appended(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/entities/Obsidian.md"
    post_write(vault, target, target.read_text(encoding="utf-8") + "\nMore.\n", state_dir)
    assert run_script("log.py", "append", "--op", "ingest", "--title", "More", "--vault", str(vault)).code == 0
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.code == 0 and r.out.strip() == "", r


def test_stop_blocks_when_a_page_created_this_session_has_no_inbound_link(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    new = vault / "wiki/entities/Lonely.md"
    post_write(vault, new, page("entity", "Lonely", body="Links out to [[Overview]] only."), state_dir)
    run_script("log.py", "append", "--op", "ingest", "--title", "Lonely", "--vault", str(vault))
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    out = json.loads(r.out)
    assert out["decision"] == "block" and "Lonely" in out["reason"]
    # link it from the Overview and the gate opens
    overview = vault / "wiki/syntheses/Overview.md"
    post_write(vault, overview, overview.read_text(encoding="utf-8") + "\nSee [[Lonely]].\n", state_dir)
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.out.strip() == "", r


def test_stop_is_silent_when_nothing_changed(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.code == 0 and r.out.strip() == ""


# ------------------------------------------------------------------ session start

def test_session_start_prints_status(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    (vault / "wiki/entities/Wanting.md").write_text(page("entity", "Wanting", stale_after="2020-01-01", body="Wants [[Progressive Disclosure]] and [[Overview]]."), encoding="utf-8")
    (vault / "wiki/concepts/Wikilinks.md").write_text((vault / "wiki/concepts/Wikilinks.md").read_text(encoding="utf-8") + "\nAlso [[Progressive Disclosure]].\n", encoding="utf-8")
    r = run_hook("session_start.py", ev(vault, "SessionStart", source="startup"), env=env_for(state_dir))
    assert r.code == 0, r
    assert "agent-wiki vault" in r.out
    assert "ingest | Note Taking Guide" in r.out  # last log entries
    assert "entities: 2" in r.out and "sources: 1" in r.out
    assert "1 ingest(s) since last lint" in r.out
    assert "1 stale page" in r.out
    assert "[[Progressive Disclosure]] (2)" in r.out
    assert (state_dir / "sess1.json").exists()
    assert len(r.out.splitlines()) <= 20  # short by design


def test_hooks_manifest_registers_the_four_hooks():
    manifest = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    hooks = manifest["hooks"]
    assert set(hooks) == {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
    assert hooks["PreToolUse"][0]["matcher"] == "Write|Edit|MultiEdit|NotebookEdit|Bash"
    assert hooks["PostToolUse"][0]["matcher"] == "Write|Edit|MultiEdit|NotebookEdit"
    for event, entries in hooks.items():
        for entry in entries:
            for h in entry["hooks"]:
                assert h["type"] == "command" and "${CLAUDE_PLUGIN_ROOT}/hooks/" in h["command"] and h["command"].startswith("python3 ")
                script = h["command"].split("${CLAUDE_PLUGIN_ROOT}/hooks/")[1].strip('"')
                assert (PLUGIN / "hooks" / script).is_file(), script


# ------------------------------------------------------------------ raw/SOURCES.md is a list, not a source

def test_sources_list_inside_raw_stays_editable(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", write_event(vault, vault / "raw/SOURCES.md", "# Sources\n"), env=env_for(state_dir))
    assert decision(r) == "allow", r
    r = run_hook("pre_tool_use.py", bash_event(vault, "echo '| A | https://x | A.md | MIT |' >> raw/SOURCES.md"), env=env_for(state_dir))
    assert decision(r) == "allow", r
    # but a command that also touches a real raw file is still denied
    r = run_hook("pre_tool_use.py", bash_event(vault, "rm raw/SOURCES.md 'raw/Note Taking Guide.md'"), env=env_for(state_dir))
    assert decision(r) == "deny", r


def test_forged_verified_inside_unparseable_frontmatter_is_still_denied(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    target = vault / "wiki/concepts/Wikilinks.md"
    text = target.read_text(encoding="utf-8")
    forged = text.replace("sources:", "verified:\n  - by: human:tester\n    at: 2026-09-02\n    deeper:\n      too: far\nsources:")
    r = run_hook("pre_tool_use.py", write_event(vault, target, forged), env=env_for(state_dir))
    assert decision(r) == "deny" and "verified" in r.out
    dropped_source_unparseable = text.replace('sources:\n  - id: guide\n    page: "[[Note Taking Guide]]"\n', "broken: [unclosed\n")
    r = run_hook("pre_tool_use.py", write_event(vault, target, dropped_source_unparseable), env=env_for(state_dir))
    assert decision(r) == "deny" and "sources" in r.out


def test_stop_does_not_treat_a_new_source_page_as_orphan(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    new = vault / "wiki/sources/Thin Source.md"
    post_write(vault, new, page("source", "Thin Source", raw="raw/Thin.md", raw_sha="x", disposition="no-material", ingested="2026-09-02"), state_dir)
    run_script("log.py", "append", "--op", "ingest", "--title", "Thin Source", "--vault", str(vault))
    r = run_hook("stop.py", ev(vault, "Stop", stop_hook_active=False), env=env_for(state_dir))
    assert r.code == 0 and r.out.strip() == "", r


def test_allowlisted_script_does_not_launder_a_chained_raw_write(tmp_path: Path, state_dir: Path):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", bash_event(vault, f"python3 {PLUGIN}/scripts/verify.py wiki/entities/Obsidian.md --by chris; rm 'raw/Note Taking Guide.md'"), env=env_for(state_dir))
    assert decision(r) == "deny", r
    r = run_hook("pre_tool_use.py", bash_event(vault, f"python3 {PLUGIN}/scripts/fetch.py url https://example.com --json && git add -A -- . && git commit -m 'fetch: x'"), env=env_for(state_dir))
    assert decision(r) == "allow", r


@pytest.mark.parametrize("command", [
    "rm -rf raw",
    "rm -rf ./raw",
    "mv raw raw_old",
    "cd raw && rm x.md",
    "cd raw; sed -i '' s/a/b/ x.md",
    "git checkout -- 'raw/Note Taking Guide.md'",
    "git restore raw/x.md",
    "git clean -fd raw",
])
def test_whole_layer_and_git_writes_into_raw_are_denied(tmp_path: Path, state_dir: Path, command: str):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", bash_event(vault, command), env=env_for(state_dir))
    assert decision(r) == "deny", (command, r)


@pytest.mark.parametrize("command", [
    "ls raw",
    "cd raw && ls",
    "cd raw && cat x.md | head",
    "git status -- raw",
    "git log -- raw/x.md",
    "python3 scripts/rawhash.py hash raw/x.md",
    "echo raw > /tmp/note.txt",
])
def test_reads_of_the_raw_layer_stay_allowed(tmp_path: Path, state_dir: Path, command: str):
    vault = copy_fixture("basic-vault", tmp_path / "v")
    r = run_hook("pre_tool_use.py", bash_event(vault, command), env=env_for(state_dir))
    assert decision(r) == "allow", (command, r)
