# agent-wiki

A Claude Code plugin that turns a folder of sources into a wiki that Claude writes and maintains, and that you read in Obsidian.

## What is this?

You collect sources: articles, papers, README files, meeting notes. Claude reads each one, works out what it adds, and writes or updates the wiki pages it touches. Pages link to each other, every number and quote points back to the source it came from, and disagreements between sources are marked on the page instead of being smoothed over. You browse the result in Obsidian and ask Claude questions against it. Good answers get filed back into the wiki, so it grows with every source and every question.

The plugin gives Claude six commands and four guard rails. The guard rails matter as much as the commands. Claude cannot edit a source file, cannot mark a page as reviewed by you, cannot drop a source from a page, and cannot end a turn with changes it did not log. Those are the mistakes an LLM makes when nobody is watching, and a hook catches each one.

## Two ideas combined

The workflow comes from Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea. Instead of searching raw documents every time you ask something, the LLM keeps a persistent wiki between you and the sources: it ingests, it answers with citations, and it periodically checks the wiki for contradictions and gaps. The wiki compounds. That gist is the first source in the example wiki.

The metadata comes from Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format) (OKF). Every page records who wrote it, who verified it, which sources it rests on, and when it goes stale, in a small set of frontmatter fields. Karpathy's pattern has no way to tell a page Claude wrote from a page you checked; OKF has no immutable source layer and no notion of two sources disagreeing. Each fills the other's gap, so this plugin uses both.

## How it works

A wiki is one folder, called a vault.

- `raw/` holds your sources, exactly as fetched. Nothing edits them.
- `wiki/` holds the pages Claude writes: one page per source, plus entities, concepts, syntheses and filed answers.
- `CLAUDE.md` is the schema. It tells Claude the conventions, and it carries the answers you gave when the vault was created: what the wiki is about, which things deserve a page, whether web search is allowed.
- `index.md` is generated from the pages. `log.md` records every operation, and every operation is also one git commit with the same words.

Small Python scripts do the deterministic work (parsing frontmatter, resolving links, rebuilding the index, checking that a quoted number really appears in the source). Claude does the reading, the writing and the judgement.

## Install

In Claude Code:

```
/plugin marketplace add chrislemke/agent_wiki
/plugin install agent-wiki@agent-wiki
```

Optional: install [Obsidian](https://obsidian.md) and open your vault folder in it. The vault ships an Obsidian configuration, so links and the attachment folder work without setup.

You install this repository; you do not copy it. A new wiki starts with `/agent-wiki:init` in its own empty folder, and that folder is what you commit and share. Anyone who clones your wiki is prompted to install the plugin.

## Your first wiki

1. `/agent-wiki:init` in an empty folder. Six questions, then the vault exists and is committed.
2. `/agent-wiki:fetch <url>` saves a web page or a GitHub README into `raw/` as markdown. Or drop your own files into `raw/`.
3. `/agent-wiki:ingest raw/<file>` reads the source, shows you what it takes away and which pages it will create or update, waits for your go, then writes. `--all` works through everything in `raw/` without a page.
4. `/agent-wiki:query <question>` answers from the wiki with links to the pages it used and says how many of them you have verified. It offers to file the answer as a page.
5. `/agent-wiki:lint` fixes what a script can fix, lists what needs your judgement, and files the open points on the Overview page.
6. `/agent-wiki:verify <page>` records that you read a page against its sources. Nothing else can set that field.

## How to use it

Open Claude Code in your vault folder. Think of `raw/` as the inbox for source material and `wiki/` as the notebook agent-wiki builds from it. You add a source, Claude turns it into linked pages, and you browse those pages in Obsidian or ask questions about them in Claude Code.

A typical run looks like this:

```
/agent-wiki:fetch <url>
/agent-wiki:ingest raw/<file>
/agent-wiki:query <question>
```

Replace `<url>`, `<file>` and `<question>` with your own values. You can also put files into `raw/` yourself instead of fetching them. When you ingest a source, Claude first shows what it found and which pages it plans to change. After a query, it asks whether you want to save the answer as a new page; answer `yes` if the result should become part of the wiki.

You do not always need to type the query command. If you ask a question that is clearly about your wiki, Claude can choose the `query` skill automatically. Use `/agent-wiki:query <question>` when you want to make sure Claude searches the wiki; the explicit command is more reliable.

For day-to-day use:

- Add new material with `/agent-wiki:fetch <url>` or by placing files in `raw/`, then ingest it. Use `/agent-wiki:ingest --all` to work through everything waiting in the inbox.
- Ask questions naturally and let Claude choose the `query` skill, or use `/agent-wiki:query <question>` for the most reliable wiki lookup. File useful answers so the wiki grows with your work.
- Open the vault in Obsidian whenever you want to browse the linked pages directly.
- After checking an important page against its sources, record that review with `/agent-wiki:verify <page>`.
- Run `/agent-wiki:lint` occasionally to repair simple problems and collect anything that needs your judgement.

## What's in the box

| Kind | Name | What it does |
|---|---|---|
| Skill | `init` | Interview, then scaffold and commit a vault |
| Skill | `fetch` | Save a URL, a GitHub repository's files, or restore listed sources into `raw/` |
| Skill | `ingest` | Compile one source into the wiki, one at a time, with a gate you approve |
| Skill | `query` | Answer from the wiki with citations and a trust count; file the answer |
| Skill | `lint` | Structural fixes by script, semantic findings by Claude, filed as open questions |
| Skill | `verify` | Record your review of a page |
| Hook | SessionStart | Shows recent log entries, page counts, stale pages and most-wanted pages |
| Hook | PreToolUse | Blocks writes into `raw/`, changes to `verified`, and shrinking a page's sources |
| Hook | PostToolUse | Warns about invalid frontmatter, removed headings and links that look like typos |
| Hook | Stop | Refuses to end a turn with unlogged wiki changes or a new page nobody links to |

## The example wiki

`example-vault/` is a real vault about Claude Code and agentic coding, built with this plugin. It contains the karpathy-llm-wiki README and SKILL file as sources (MIT licensed), pages for the entities and concepts they introduce, one filed answer, one disputed claim and one verified page. Two sources are not committed for licence reasons, Karpathy's gist and the OKF specification. To get them:

```
cd example-vault
/agent-wiki:fetch --restore
```

The example vault also serves as the maintainer's own wiki, so it keeps receiving sources.

## Credits and licence

MIT licence, see [LICENSE](LICENSE). The workflow is Andrej Karpathy's LLM Wiki idea; the operating rules borrow from Astro-Han's [karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) (MIT), in particular the grounding check; the frontmatter follows Google's Open Knowledge Format v0.2. The skills use the Agent Skills format and could be copied into other tools, but without the hooks, which exist only in Claude Code, the guard rails are gone.

The reasoning behind every convention is in [DESIGN.md](DESIGN.md).
