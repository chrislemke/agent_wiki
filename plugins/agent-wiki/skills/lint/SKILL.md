---
name: lint
description: Health-check the wiki - fix structural problems automatically, then review the semantic ones (contradictions, superseded claims, missing cross-references, thin pages, wanted pages) and file open findings. Use when the owner asks to lint, health-check, clean up or maintain the wiki, or when the session status shows many ingests since the last lint.
argument-hint: "[folder or page]"
---

# Lint the wiki

Two passes. The deterministic pass runs the checkers and applies the auto-fix policy. The semantic pass is your judgement over the scope. Open findings are filed where the owner will read them: the Open questions section of the relevant synthesis page. Scope is `$ARGUMENTS` (a folder or a page) or the whole wiki. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`; merge and dispute rules are in `${CLAUDE_PLUGIN_ROOT}/references/rules.md`.

## Steps

1. **Vault check.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`.

2. **Structural pass.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py all --fix [--scope <path>] --json
   ```

   `auto_fixed` lists what changed (index regenerated, key order normalised, `created` derived from git, unique near-miss links corrected). Each finding in `judgement` carries an `action`; handle them by type:
   - `wanted-page` with count two or more: propose creating the page. It still passes the minting gate (`rules.md`). On the owner's go, write it from what the wanting pages say about it, with their sources, following `references/skeletons.md`, stamp it, and link nothing extra: the wanting pages already link to it.
   - `duplicate-title`, `alias-collision`, `duplicate-basename`: propose which page survives. On confirmation, move the loser's unique content into the winner (augment; every winner heading stays), then `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/rename.py merge <loser> <winner>`, which unions sources, adds aliases, rewrites links and deletes the loser.
   - `near-miss-link` with several candidates: ask which target was meant, then fix the link.
   - `evidence-suspect`: open the raw file; correct the literal to what the source says or remove the precision. Facts are never invented and never "fixed" to match the page.
   - `review-outdated`, `stale`: report; the owner re-verifies or re-fetches (`resource` is given for source pages).
   - `generic-block-behind`, `generic-block-edited`: show the owner what changed between the vault's block and `${CLAUDE_PLUGIN_ROOT}/references/generic-block.md`; on confirmation replace the block in `CLAUDE.md` with the canonical one and log it as `schema: generic block v<N>`.
   - everything else (`orphan`, `unknown-tag`, `footnote-*`, `raw-hash-mismatch`, `raw-missing`, `git-freshness`, `reserved-name`, `frontmatter-invalid`, `generated-missing`): fix what has one obvious fix (link an orphan from a related page, complete a footnote definition, replace a stray tag with the vocabulary term), report the rest with the script's action.
   `informational` (backlog, restore, never-cited sources) is reported, not acted on, except that a `restore` finding suggests `/agent-wiki:fetch --restore`.

3. **Semantic pass** over the scope. Read the pages and look for: two pages stating incompatible claims without a Status block; a claim a newer source supersedes, still standing without `Status: Outdated`; a page mentioning a topic that has a page without linking it; thin pages (a source page nothing cites, an entity with a definition and nothing else); questions a web search could settle (only when `web_search` is true and `confidential` is false, from `vault.py settings --json`). Add the Status blocks and cross-references that are unambiguous; the rest become findings.

4. **File open findings.** Append each unresolved finding as a bullet under `## Open questions` of the most relevant synthesis page, defaulting to `wiki/syntheses/Overview.md`, in the form `- [lint YYYY-MM-DD] <finding> ([[Page A]], [[Page B]])`. Stamp each synthesis page you touched. Done when every judgement finding is either fixed, confirmed by the owner, or filed.

5. **Index, log, commit.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/index.py build
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op lint --title "<N> fixed, <M> proposed" --updated "<pages touched>" --note "<one line>"
   git add -A -- . && git commit -m "lint: <N> fixed, <M> proposed"
   ```

6. **Report** three short lists: fixed, proposed (with where each was filed), informational.

Work one scope at a time; for a wiki too large for one context, run the semantic pass per folder over several invocations. Subagents are not used for the semantic pass in this version.
