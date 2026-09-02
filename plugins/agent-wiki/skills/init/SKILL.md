---
name: init
description: Turn a folder into an agent-wiki vault by interview, then scaffold and commit it.
disable-model-invocation: true
argument-hint: "[folder]"
---

# Init a vault

Turn one folder into a wiki vault: look, interview, scaffold, commit. The folder is `$ARGUMENTS` when given, else the working directory. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` (two directories above this skill's base directory when the variable is unset).

## Steps

1. **Look before asking.** List the folder. Read an existing `README.md` or `CLAUDE.md`. Note whether `raw/` already holds files. Run `git -C <folder> rev-parse --show-toplevel` to learn whether an enclosing repository exists. If `.agent-wiki.json` is already there, this is a gap-filling run: skip to step 4 with the existing domain block and say so. Done when you can propose an answer to every interview question.

2. **Interview.** Ask the six questions in `${CLAUDE_PLUGIN_ROOT}/references/interview.md` in one message, each with the answer you propose from step 1, and wait. Done when every answer is confirmed or explicitly defaulted. The owner's own id (question 6) defaults to their git user name, lower-cased with dashes.

3. **Write `answers.json`** in the shape given in `interview.md`, into your scratchpad directory. Tags are kebab-case; the staleness map is tag to days.

4. **Scaffold.** Run:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py init --vault <folder> --answers <answers.json> --by agent-wiki/<model-id> --json
   ```

   It never overwrites a file. Read `created`, `skipped`, `warnings`, `enclosing_git_repo`. When a warning says `CLAUDE.md` lacks the generic or domain block, run `scaffold.py render-claude-md --answers <answers.json>` and append the missing block(s) to the existing `CLAUDE.md`. Done when `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py all --vault <folder> --json` reports `"clean": true`.

5. **Commit.** If `enclosing_git_repo` is `null` and the folder has no `.git`, run `git init` in it. Then, from the folder:

   ```
   git add -A -- . && git commit -m "init: <title>"
   ```

   Done when `git status --short -- .` prints nothing. Nested repositories are never created inside an enclosing one.

6. **Hand over.** Tell the owner, in a few lines: the layout (`raw/` for sources, `wiki/` for pages, `CLAUDE.md` as schema); that the folder opens directly as an Obsidian vault with links and the attachment folder preconfigured; that anyone cloning it is prompted to install this plugin; and the next move: `/agent-wiki:fetch <url>` or drop files into `raw/` and run `/agent-wiki:ingest --all`. Hooks load at session start, so a restart of Claude Code turns the guards on for this vault.
