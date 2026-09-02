---
name: query
description: Answer a question from the wiki with page citations and a trust count, falling back to raw sources with an explicit gap flag, and offer to file the answer as an analysis page. Use when the owner asks what the wiki knows, asks a question about the domain, says "query the wiki", "what do I know about", "compare A and B from my notes", or asks to file an answer.
argument-hint: "<question>"
---

# Query the wiki

Answer `$ARGUMENTS` from the wiki, cite pages, say how much of it is human-reviewed, and offer to file the answer so it compounds. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`; citation rules are in `${CLAUDE_PLUGIN_ROOT}/references/rules.md`, the analysis skeleton in `references/skeletons.md`.

## Steps

1. **Vault check and settings.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`, then `vault.py settings --json` for `confidential` and `web_search`.

2. **Find candidate pages.** Read `index.md`. Then `rg -il` across `wiki/` for the question's terms, their synonyms and the aliases you know, to catch what the index misses. Read the candidates. The wiki "has nothing" only after both the index and the search came back empty, and the answer then says that both were tried.

3. **Answer from the wiki** when the pages cover the question. Cite every page used as `[[Page]]`. Count cited pages whose frontmatter lacks `verified` and state it in one line: "N of M cited pages are unverified." Load-bearing numbers, dates and quotes are copied from the pages as written.

4. **Fall back when the wiki is thin.** Search `raw/` (`rg -il`) for the terms, read the raw files that plausibly answer, answer from them, and flag the gap in one line: "Gap: [[Page]] is too thin on X; this answer read raw/<file> directly." That flag is the lint finding that improves the wiki. Web search only when `web_search` is true and `confidential` is false; claims from the web are marked as such and are not wiki knowledge. When search is not allowed, say so in one line and stop there.

5. **Offer filing** in one line at the end: "File this as an analysis page? (yes / no)". Wait.

6. **File** when the owner says yes. Write `wiki/analyses/<Short Title>.md` from the analysis skeleton with `question`, `sources` as the union of the cited pages' `sources` entries you relied on, the Evidence section naming each cited page and whether it is verified, and Caveats naming any raw files read directly. Then:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/frontmatter.py stamp <page> --by agent-wiki/<model-id>
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/frontmatter.py validate <page> --json
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/links.py resolve <page>
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/index.py build
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op query --title "<question>" --created "<Short Title>"
   git add -A -- . && git commit -m "query: <question>"
   ```

   Link the new page from the Overview or the most related synthesis page (one line under Evidence or Open questions), so it is not an orphan. Done when validate reports zero errors and the commit exists.

7. **Log an unfiled query too**, without a commit; the entry rides along with the next operation:

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op query --title "<question>" --note "not filed"
   ```

Answers are markdown in the conversation. Slides, charts or other formats are a domain decision and belong in the domain block when a vault wants them.
