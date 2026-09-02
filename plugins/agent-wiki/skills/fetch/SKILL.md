---
name: fetch
description: Fetch a URL into the vault's raw/ folder as a verbatim markdown source, or restore the sources listed in raw/SOURCES.md. Use when the owner gives a URL to add as a source ("fetch", "clip", "add this source", "save this article"), names a GitHub repository to bring in, or asks to restore missing raw files.
argument-hint: "<url> [--files A,B] | --restore"
---

# Fetch a source

Put a verbatim copy of a web resource into `raw/`, the immutable source layer, with its metadata. `fetch.py` is the only permitted writer into `raw/`; the raw guard allowlists it. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## Steps

1. **Vault check.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`. On failure stop: this folder is not a vault; suggest `/agent-wiki:init`.

2. **Route `$ARGUMENTS`.**
   - `--restore` → step 5.
   - A GitHub repository URL (`github.com/<owner>/<repo>`, optionally `/tree/<branch>/<path>`) → step 4.
   - Anything else → step 3.

3. **Article.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py url <URL> --json`. It extracts the article verbatim with `uvx trafilatura` and writes `raw/<Title>.md` with `title`, `resource`, `fetched`, `author`, `published`, `fidelity: verbatim`. If it fails (paywall, script-rendered page, non-HTML), fall back: WebFetch the URL with the prompt "Return the complete article text as markdown, verbatim, keeping headings, lists and quotes. No summary, no commentary." and pipe the result in:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py url <URL> --stdin --fidelity summary --title "<title>" [--author "<a>"] [--published YYYY-MM-DD] <<'EOF'
   <text>
   EOF
   ```

   `fidelity: summary` is recorded in the raw file so the loss stays visible. An existing raw file is never overwritten; the script exits 1 and you report it. Done when the raw path is printed.

4. **GitHub repository.** README first, named files as separate raw files:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py github <URL> [--files SKILL.md,docs/x.md] --json
   ```

   Use the files the owner named; with none named, fetch the README and mention that files can be added with `--files`. Each raw file records the blob URL as `resource`. Done when every planned file is fetched or its failure is reported.

5. **Restore.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch.py restore --json` downloads every row of `raw/SOURCES.md` whose file is missing and skips the rest. Done when the script reports `restored`, `skipped` and `failed`.

6. **Log and commit.** One entry and one commit per fetch (restore counts as one):

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op fetch --title "<title>" --note "<resource>; fidelity <verbatim|summary>"
   git add -A -- . && git commit -m "fetch: <title>"
   ```

7. **Report** the raw path(s) in one line and offer `/agent-wiki:ingest raw/<file>`.

Images are not downloaded in this version; the Obsidian Web Clipper with "download attachments" is the way to get local images into `raw/assets/`. Fetching a URL the owner gave is allowed in confidential vaults, since only the URL leaves the machine.
