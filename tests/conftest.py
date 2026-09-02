"""Shared fixtures: build small vaults on disk and run plugin scripts as subprocesses.

Every test goes through one seam: a vault directory plus the script command line.
Nothing imports script internals.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "agent-wiki"
SCRIPTS = PLUGIN / "scripts"
HOOKS = PLUGIN / "hooks"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

TODAY = __import__("datetime").date.today().isoformat()

MARKER = {"schema_version": 1, "plugin_version": "0.1.0", "created": "2026-09-01"}

GENERIC_BLOCK = (PLUGIN / "references" / "generic-block.md").read_text(encoding="utf-8").strip()

CLAUDE_MD = """# Test Vault

""" + GENERIC_BLOCK + """

<!-- agent-wiki:domain -->
## Domain

### Purpose
A vault used by the test suite.

### Settings
```yaml
language: en
image_cap: 5
human_id: tester
confidential: false
web_search: true
tags: [alpha, beta, docs]
staleness:
  docs: 90
  alpha: 30
```
<!-- /agent-wiki:domain -->
"""


def page(type_: str, title: str, description: str = "A page.", **extra: object) -> str:
    """Render a minimal canonical page of the given type."""
    lines = [
        "---",
        f"type: {type_}",
        f"title: {title}",
        f"description: {description}",
        "created: 2026-09-01",
        "generated:",
        "  by: agent-wiki/test-model",
        "  at: 2026-09-01",
    ]
    body = extra.pop("body", None)
    for key, value in extra.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(value)}]")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(str(body) if body is not None else f"Body of {title}.")
    lines.append("")
    return "\n".join(lines)


def make_vault(root: Path, files: dict[str, str] | None = None, marker: dict | None = None) -> Path:
    """Create a vault at root with the standard layout plus the given files."""
    root.mkdir(parents=True, exist_ok=True)
    for folder in ("raw/assets", "wiki/sources", "wiki/entities", "wiki/concepts", "wiki/syntheses", "wiki/analyses"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / ".agent-wiki.json").write_text(json.dumps(marker or MARKER, indent=2) + "\n", encoding="utf-8")
    if not (root / "CLAUDE.md").exists():
        (root / "CLAUDE.md").write_text(CLAUDE_MD, encoding="utf-8")
    if not (root / "index.md").exists():
        (root / "index.md").write_text("# Index\n", encoding="utf-8")
    if not (root / "log.md").exists():
        (root / "log.md").write_text("# Log\n", encoding="utf-8")
    for rel, content in (files or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def sync_generic_block(vault: Path) -> None:
    """Replace the generic block in a vault's CLAUDE.md with the plugin's current canonical block."""
    import re

    claude = vault / "CLAUDE.md"
    text = claude.read_text(encoding="utf-8")
    pattern = re.compile(r"<!--\s*agent-wiki:generic\s+v\d+\s*-->.*?<!-- /agent-wiki:generic -->", re.S)
    claude.write_text(pattern.sub(lambda m: GENERIC_BLOCK, text, count=1), encoding="utf-8")


def copy_fixture(name: str, dest: Path) -> Path:
    shutil.copytree(FIXTURES / name, dest)
    if (dest / "CLAUDE.md").exists():
        sync_generic_block(dest)
    return dest


class Result:
    def __init__(self, proc: subprocess.CompletedProcess[str]):
        self.code = proc.returncode
        self.out = proc.stdout
        self.err = proc.stderr

    def json(self):
        return json.loads(self.out)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Result(code={self.code}, out={self.out!r}, err={self.err!r})"


def run_script(name: str, *args: str, cwd: Path | None = None, stdin: str | None = None, env: dict | None = None) -> Result:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, input=stdin, capture_output=True, text=True, env=full_env)
    return Result(proc)


def run_hook(name: str, event: dict, cwd: Path | None = None, env: dict | None = None) -> Result:
    cmd = [sys.executable, str(HOOKS / name)]
    full_env = dict(os.environ)
    full_env.setdefault("CLAUDE_PLUGIN_ROOT", str(PLUGIN))
    if env:
        full_env.update(env)
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None, input=json.dumps(event), capture_output=True, text=True, env=full_env)
    return Result(proc)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    return make_vault(tmp_path / "vault")
