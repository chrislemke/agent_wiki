---
name: ingest
description: Compile a raw source into the wiki, updating every affected page, one source at a time. Use when the owner asks to ingest, process, compile or "add to the wiki" a file in raw/, or to work through the backlog (--all).
argument-hint: "<raw file> [--batch] | --all"
---

# Ingest a source

Read one source fully, decide what it changes, write the pages in a fixed order, then index, log and commit. Interactive by default: takeaways and page plan wait for a go. `--batch` skips the gate for one trusted source; `--all` ingests every raw file without a source page, in batch, one after another. Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`; the shared rules are in `${CLAUDE_PLUGIN_ROOT}/references/rules.md`, the page shapes in `references/skeletons.md`, the write order and commands in `references/bookkeeping.md`.

## Steps

1. **Vault check and settings.** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vault.py detect --json`, then `vault.py settings --json` for `image_cap`, `tags`, `language`, `confidential`. Read `CLAUDE.md`'s domain block for the lens.

2. **Pick the work.**
   - `--all`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/lint.py backlog --json` lists raw files without a source page. Process them in that order, each in batch mode, and keep a result line per file for the final summary.
   - One path: if a source page already points at it (`rg -l "^raw: <path>" wiki/sources`), ask before re-ingesting, in every mode. Re-ingesting replaces the source page and augments the rest.

3. **Read the source completely.** Read the raw file to its last line (in chunks for long files). Then find its local image references (`![[...]]`, `![](...)` under `raw/assets/`) and view up to `image_cap` of them, preferring figures over decoration. Done when no unread text remains.

4. **Search the whole wiki** for the source's key entities, their synonyms and aliases, and the specific claims it makes (`rg -il`), and read `index.md`. Collect every page the source could touch. The index alone misses cascade updates.

5. **State the disposition**: new, update, disputed, no-material (definitions in `rules.md`).

6. **Gate** (interactive only). Post one message: five to ten key takeaways; the disposition; the page plan as "create X (gate: nameable, not meta, citable, wanted by A and B)", "update Y: add ...", "dispute Z on claim ..."; then wait for go or adjustments. Batch mode skips this step.

7. **Write, in order.** Source page, then entity and concept pages, then syntheses. Follow `skeletons.md`. Rules that bind every write:
   - Locate before you write, write as found. Grep the raw file for each number, date and quote before writing it.
   - Footnote load-bearing claims with `[^id]`, `id` from `sources[].id`, definitions at the end of the page.
   - New entity or concept pages only through the minting gate; otherwise mention inline with a `[[Wanted Page]]` link.
   - Existing pages are augmented: every heading and every `sources` entry stays; add, do not reword.
   - Disagreement gets a Status block beneath the claim and `status: contested`; you never resolve it.
   - The source page gets `raw`, `raw_sha` from `rawhash.py hash <raw file>`, `disposition`, `ingested` (today), and `author`, `published`, `resource` from the raw frontmatter. A no-material source gets a two-line source page and nothing else.
   - After writing each page: `frontmatter.py stamp <page> --by agent-wiki/<model-id>`.

8. **Check.** `frontmatter.py validate <vault> --json` (zero errors), `links.py resolve <each written page>` (fix near-misses; unresolved links are wanted pages and stay), `evidence.py check <each written page> --json` (zero suspects: correct the literal from the raw file or drop the precision). Done when all three are clean for the pages you wrote.

9. **Index, log, commit.**

   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/index.py build
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op ingest --title "<Source Title>" --created "<Page>" ... --updated "<Page>" ... --note "disposition: <d>; <one line>"
   git add -A -- . && git commit -m "ingest: <Source Title>"
   ```

   One entry and one commit per source, also inside `--all`.

10. **Failures in a batch.** An unreadable, empty or non-text file is logged and skipped, and the batch continues:

    ```
    python3 ${CLAUDE_PLUGIN_ROOT}/scripts/log.py append --op ingest-failed --title "<raw file>" --note "<reason>"
    git add -A -- . && git commit -m "ingest-failed: <raw file>"
    ```

11. **Report.** For one source: pages created and updated, disputes recorded, wanted pages left behind. For a batch: one line per source with its disposition, then the failures.

Never compile two sources at the same time, and never dispatch subagents to compile in parallel: index, log and cascade updates are shared state.
