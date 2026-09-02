# Claude Code and Agentic Coding

This folder is an agent-wiki vault: `raw/` holds sources, `wiki/` holds the pages the LLM maintains, and this file is the schema. Skills: `/agent-wiki:fetch`, `/agent-wiki:ingest`, `/agent-wiki:query`, `/agent-wiki:lint`, `/agent-wiki:verify` (install: `/plugin marketplace add chrislemke/agent_wiki`, then `/plugin install agent-wiki@agent-wiki`).

<!-- agent-wiki:generic v1 -->
## How this wiki works (agent-wiki schema v1)

This folder is an LLM-maintained wiki. Three layers:

- `raw/` holds the sources. Immutable: read it, never edit it. Images live in `raw/assets/`. `raw/SOURCES.md` lists sources that are not committed and can be re-fetched.
- `wiki/` holds the pages the LLM writes: `sources/` (one page per raw file), `entities/`, `concepts/`, `syntheses/` and `analyses/` (filed answers). `wiki/syntheses/Overview.md` is the hub; its "Open questions" section is where open findings go.
- This file is the schema. `index.md` is generated from frontmatter (only the curated block at its top is written by hand). `log.md` is append-only.

### Pages
- Title Case filenames with spaces, unique across the wiki. Link with `[[Page]]`. Synonyms go in `aliases`, never in a second page. Unresolved links are "wanted pages"; leave them, they are created once two or more pages want them.
- Prose in the vault's `language` (Settings below). Quotes stay verbatim in their original language.
- Frontmatter on every page, values as plain strings, dates as `YYYY-MM-DD`:
  - all pages: `type` (source, entity, concept, synthesis, analysis), `title`, `description` (one line, it feeds the index), `tags` (from the domain vocabulary below), `aliases`, `status` (draft, stable, contested, deprecated; absent means stable), `created`, `generated` with `by` and `at` (`agent-wiki/<model-id>` or `human:<id>`; `at` moves only when the knowledge changed), `verified` as a list of `by` and `at` (set only by the owner), `stale_after`, `sources` as a list of `id` and `page` (a `"[[wikilink]]"` to a source page)
  - source pages add `raw` (path under `raw/`), `raw_sha` (SHA-256 of the raw file), `disposition` (new, update, disputed, no-material), `author`, `published`, `resource` (URL), `fidelity` (only `summary`, when the raw file is not a verbatim copy), `ingested`
  - analysis pages add `question`
- Fixed sections per type, empty ones omitted. Source: Summary, Key claims, Entities and concepts, Notable quotes, Assessment. Entity: What it is, Key facts, Timeline, Relationships, Sources. Concept: Definition, How sources treat it, Open questions. Synthesis: Thesis, Evidence, Counter-evidence, Open questions, Sources. Analysis: Question, Answer, Evidence, Caveats, Sources. Entity and concept pages may add "Not to be confused with".

### Truth
- Locate before you write, write as found: every number, date and quote comes verbatim from a raw file the page cites, in the form the source uses. If it cannot be found there, drop the precision.
- Footnote load-bearing claims (numbers, dates, quotes, anything disputed) with `[^id]`, where `id` is one of the page's `sources[].id`, and define `[^id]: <source title>` at the end of the page.
- When sources disagree, keep both claims and put directly beneath the claim:
  > **Status: Disputed**
  > [[Source A]] says claim A; [[Source B]] says claim B. Unresolved.
  and set `status: contested`. A superseded claim keeps its text and gets `> **Status: Outdated** (YYYY-MM-DD)` with what replaced it. Disputes are resolved by the owner, never by the LLM.
- A page whose whole subject is superseded becomes `status: deprecated` and links to its successor, which links back.
- Updates augment: keep every existing heading and every `sources` entry. Rewrite a page only when the owner asks for a rewrite.

### Growth
- A new entity or concept page must pass the minting gate: the topic is nameable, it is not meta content (no "overview of X" pages besides the Overview), at least one sentence on another page cites it, and two or more sources or pages want it (or the lens below names it as central). Otherwise mention it inline and leave a `[[Wanted Page]]` link.
- One link per concept mention per section.

### Bookkeeping
- Every operation ends with a log entry `## [YYYY-MM-DD] <op> | <title>` followed by `- Created:`, `- Updated:` and `- Note:` lines, and a commit `<op>: <title>`. Operations: init, fetch, ingest, ingest-failed, query, lint, verify, schema. No attribution trailers.
- Write order for an ingest: source page, then entity and concept pages, then syntheses, then index, log, commit. One source at a time, never in parallel.
- Without the agent-wiki plugin: follow these rules by hand and regenerate the index by hand. Nothing else is required to keep the wiki valid.
<!-- /agent-wiki:generic -->

<!-- agent-wiki:domain -->
## Domain

### Purpose
A working reference on Claude Code and agentic coding practice: how the tool works, how to extend it with skills, hooks and plugins, and which working patterns hold up. This vault is also the example and dogfood vault of the agent-wiki plugin.

### Entities
Tools (Claude Code, Obsidian), features (skills, hooks, plugins, MCP servers), plugins, people and repositories.

### Sources
Official Claude Code documentation pages, READMEs and skill files of relevant repositories, blog posts and talks. Fetched with /agent-wiki:fetch; public sources whose licence does not allow redistribution are listed in raw/SOURCES.md instead of committed.

### Lens
How to build reliable agentic workflows and plugins. Emphasise mechanisms, conventions and failure modes that carry over to other projects; ignore marketing and release chatter. Central concepts: Claude Code, skills, hooks, plugins, the LLM wiki pattern.

### Settings
Read by the plugin scripts and by every skill. `confidential: true` forbids web search and any publishing; `web_search` is the separate switch for filling gaps from the web; `image_cap` is the number of local images viewed per source; `tags` is the closed vocabulary; `staleness` maps a tag to the number of days after which a page carrying it is stale; `human_id` is who `verify` records.
```yaml
tags: [claude-code, skills, hooks, plugins, agents, mcp, workflow, llm-wiki, okf, docs]
language: en
image_cap: 5
human_id: chris
confidential: "false"
web_search: "true"
staleness:
  docs: 90
extra_types: []
```
<!-- /agent-wiki:domain -->
