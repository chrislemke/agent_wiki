"""The skills are instructions to a model, so almost nothing about them is testable here.

One thing is: every script command line a SKILL.md quotes has to be a command line the
script's own argparse parser accepts. Placeholders (`<page>`, optional `[--flag V]`) are
substituted, then the parser is asked to parse the result in a subprocess, which imports
the script but never runs it.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import List, Tuple

import pytest

from conftest import PLUGIN, PYTHON, SCRIPTS

SKILLS = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
INVOCATION_RE = re.compile(r"scripts/([a-z_]+)\.py([^\n`]*)")
PLACEHOLDER_RE = re.compile(r"<[^<>]*>")
# a command line ends where the shell takes over
TAIL_RE = re.compile(r"\s(?:<<|&&|\|\||\||;|>>?)")

PARSE_ONLY = """
import importlib.util, json, sys
path, argv = sys.argv[1], json.loads(sys.argv[2])
spec = importlib.util.spec_from_file_location("under_test", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod.build_parser().parse_args(argv)
"""


def _placeholder(match: re.Match) -> str:
    inner = match.group(0)[1:-1]
    return "3" if re.fullmatch(r"[Nn]|number|count", inner.strip()) else "X"


def _tokens(args: str) -> List[str]:
    cut = TAIL_RE.search(args)
    if cut:
        args = args[: cut.start()]
    args = PLACEHOLDER_RE.sub(_placeholder, args).replace("[", "").replace("]", "")
    return [t for t in shlex.split(args) if t not in ("...", "…")]


def _invocations() -> List[Tuple[str, str, str, List[str]]]:
    out: List[Tuple[str, str, str, List[str]]] = []
    for skill in SKILLS:
        for m in INVOCATION_RE.finditer(skill.read_text(encoding="utf-8")):
            out.append((skill.parent.name, m.group(1), m.group(0), _tokens(m.group(2))))
    return out


INVOCATIONS = _invocations()


def test_the_skills_quote_some_script_commands():
    assert len(INVOCATIONS) > 20  # the discovery regex still finds them


@pytest.mark.parametrize("skill,script,quoted,argv", INVOCATIONS, ids=[f"{s}:{q[:60]}" for s, _, q, _ in INVOCATIONS])
def test_every_script_command_quoted_in_a_skill_parses(skill: str, script: str, quoted: str, argv: List[str]):
    path = SCRIPTS / f"{script}.py"
    assert path.is_file(), f"{skill} names a script that does not exist: {script}.py"
    proc = subprocess.run(
        [PYTHON, "-c", PARSE_ONLY, str(path), json.dumps(argv)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"{skill} quotes `{quoted.strip()}`, which {script}.py rejects:\n{proc.stderr}"
