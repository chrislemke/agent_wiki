---
name: init
description: Turn a folder into an agent-wiki vault by interview, then scaffold and commit it. On a folder that is already a vault, fill the gaps.
disable-model-invocation: true
argument-hint: "[folder]"
---

# Init a vault

Turn one folder into a wiki vault: look, interview, scaffold, commit. The folder is `$ARGUMENTS` when given, else the working directory. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` (two directories above this skill's base directory when the variable is unset); their flags are listed in `${CLAUDE_PLUGIN_ROOT}/references/bookkeeping.md`.

## Steps

1. **Look before asking.** List the folder. Read an existing `README.md` or `CLAUDE.md`. Note whether `raw/` already holds files. Run `git -C <folder> rev-parse --show-toplevel` to learn whether an enclosing repository exists. If `.agent-wiki.json` is already there, this is a gap-filling run: read the domain block of `CLAUDE.md` and `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py settings --vault <folder> --json`, write `answers.json` (step 3) from them, ask only about sections that are missing, and continue with step 4. Done when you can propose an answer to every interview question.

2. **Interview.** Ask the six questions in `${CLAUDE_PLUGIN_ROOT}/references/interview.md` in one message, each with the answer you propose from step 1, and wait. Done when every answer is confirmed or explicitly defaulted. The owner's own id (question 6) defaults to their git user name, lower-cased with dashes.

3. **Write `answers.json`** in the shape given in `interview.md`, into a temporary directory outside the vault (never inside it, or the first commit picks it up). Tags are kebab-case; the staleness map is tag to days.

4. **Scaffold.** Run:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.py init --vault <folder> --answers <answers.json> --by agent-wiki/<model-id> --json
   ```

   It never overwrites a file, and it writes the `init` log entry itself. Read `created`, `skipped`, `warnings`, `enclosing_git_repo`. When a warning says `CLAUDE.md` lacks the generic or domain block, run `scaffold.py render-claude-md --answers <answers.json>`, take the block between its `<!-- agent-wiki:... -->` markers, and append it to the existing `CLAUDE.md`. Done when `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py all --vault <folder> --json` reports `"clean": true`.

5. **Commit.** If `enclosing_git_repo` is `null` and the folder has no `.git`, run `git -C <folder> init`. Then:

   ```
   git -C <folder> add -A -- . && git -C <folder> commit -m "init: <title>"
   ```

   Done when `git -C <folder> status --short -- .` prints nothing. Nested repositories are never created inside an enclosing one; the commit then lands in the enclosing repository.

6. **Hand over.** Tell the owner, in a few lines: the layout (`raw/` for sources, `wiki/` for pages, `CLAUDE.md` as schema); that the folder opens directly as an Obsidian vault with links and the attachment folder preconfigured; that anyone cloning it is prompted to install this plugin; and the next move: `/agent-wiki:fetch <url>` or drop files into `raw/` and run `/agent-wiki:ingest --all`. The write guards are live as soon as the marker file exists; the session status line appears from the next Claude Code session on.
