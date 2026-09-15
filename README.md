# agent-wiki

A Claude Code plugin that turns a folder of sources into a wiki that Claude writes and maintains, and that you read in Obsidian.

## What is this?

You have a folder of documents. You read them once, and now you remember the gist and none of the detail. Every question you ask sends Claude back into the same files to read them again, and the answer that comes back is new each time. Nothing you worked out last week is there this week, and nothing tells you which sentence in which file the answer rests on.

agent-wiki puts a wiki in between. You collect sources: articles, papers, README files, meeting notes. Claude reads each one, works out what it adds, and writes or updates the wiki pages it touches. Pages link to each other, every number and quote points back to the source it came from, and disagreements between sources are marked on the page instead of being smoothed over. You browse the result in Obsidian and ask Claude questions against it. Good answers get filed back into the wiki, so it grows with every source and every question.

You could point Claude at the folder instead, and for a handful of files that is the better choice. The difference shows up later. A search gives you an answer. A wiki page gives you the answer, the sources under it, a note where a second source disagrees, a mark saying whether you have read it yourself, and a date after which nobody should trust it. None of that survives in a chat window.

Reading a source in is the slow part: Claude reads the whole file, searches the whole wiki for what it touches, and waits for you to approve a plan. Asking is the cheap part. So this is worth the trouble when you will put many questions to the same material over months, and it is not worth it when you have five files and one question.

The plugin gives Claude six commands and four guard rails. The guard rails matter as much as the commands. Claude cannot edit a source file, cannot mark a page as reviewed by you, cannot drop a source from a page, and is stopped at the end of a turn when it leaves changed pages out of the log. Those are the mistakes an LLM makes when nobody is watching, and a hook catches each one. What you get for that is a page you can still trust in six months without opening the sources again.

## How it works

A wiki is one folder, called a vault.

- `raw/` holds your sources, exactly as fetched. Nothing edits them.
- `wiki/` holds the pages Claude writes: one page per source, plus entities, concepts, syntheses and filed answers.
- `CLAUDE.md` is the schema. It tells Claude the conventions, and it carries the answers you gave when the vault was created: what the wiki is about, which things deserve a page, whether web search is allowed.
- `index.md` is generated from the pages. `log.md` records every operation, and every operation is also one git commit with the same words.

Small Python scripts do the deterministic work (parsing frontmatter, resolving links, rebuilding the index, checking that a quoted number really appears in the source). Claude does the reading, the writing and the judgement.

## What it is good for

It fits when sources pile up over time, when they disagree with each other, when they go out of date, and when you will ask about them again and again. That is what the machinery is for.

- **A field that moves fast.** Model releases, framework documentation, vendor APIs. Half of what you save is wrong within a quarter, so pages carry a date after which they should be checked, and two sources disagreeing is the normal case rather than an exception.
- **Watching a market or a competitor.** Nothing is authoritative and everything is second-hand, so who said it, and when, matters as much as what was said.
- **A decision with many inputs.** Build or buy, which vendor, which architecture. Thirty documents over a few weeks, and at the end you have to explain the choice with the evidence still attached.
- **Rules, standards and contracts.** Every number and every quote has to appear word for word in the file it came from, and a script checks that it does.
- **The memory of a team or a system.** Design documents, meeting notes, postmortems. "Why did we decide this" is an answer spread across forty files that nobody will ever put back together by hand.
- **A long piece of research.** Papers that contradict each other, and citations you need anyway.
- **Something personal and serious.** An illness, a legal matter, buying a house. A closed subject, sources that conflict, and a year of questions ahead of you.

It does not fit everywhere:

- **Your own code.** The code is the truth and it changes faster than you can read it in. A `CLAUDE.md` and a search tool do the job better.
- **A few files and one question.** Reading them in costs more than asking Claude to read them.
- **News.** You want the latest thing, not the accumulated picture.
- **A subject with no edges.** One vault holds one subject. A wiki about "AI" becomes a pile.
- **Files that keep changing.** A page records a fingerprint of the file it came from, and a living document sets that off every time.

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

Replace `<url>`, `<file>` and `<question>` with your own values.

You do not always need to type the query command. If you ask a question that is clearly about your wiki, Claude can choose the `query` skill automatically. Use `/agent-wiki:query <question>` when you want to make sure Claude searches the wiki; the explicit command is more reliable.

Day to day, the work is a loop: collect, ingest, read, ask, tidy, review. Most days you only do the first four.

**Collect sources.** When you find something worth keeping, get it into `raw/`. Give Claude a link and it saves the page as a markdown file with title, author and date. For a GitHub repository it saves the README, plus any files you name with `--files`. You can also copy files in yourself: notes from a meeting, an exported chapter, a paper you converted to markdown. Images are not fetched; the Obsidian Web Clipper with "download attachments" switched on puts them into `raw/assets/`. Once a file is in `raw/`, Claude never edits it. It is the evidence every page points back to.

**Ingest one source.** Point Claude at a file in `raw/`. It reads the whole thing, searches the wiki for everything the source touches, and shows you a plan before it writes anything: the key takeaways, which pages it will create, which it will add to, and where the source disagrees with what the wiki already says. You say go, or change the plan. Then it writes. If you trust the source, `--batch` skips the question. `--all` works through every file in `raw/` that has no page yet, one after another. Each source becomes one page under `wiki/sources/`, and its facts flow into the pages about the people, tools and ideas it mentions. Every ingest is one entry in `log.md` and one git commit, so you can see what a source changed and roll it back.

**Read in Obsidian.** Open the vault folder as an Obsidian vault. `index.md` lists every page, and the Overview page is the front door. The block at the top of each page says who wrote it, which sources it rests on and when it goes stale. Numbers and quotes carry footnotes to the source they came from. Where two sources disagree, the page keeps both claims under a Status block instead of picking one. Links to pages that do not exist yet are normal. Claude leaves them where a page would help but no source justifies one so far. When several pages want the same missing page, lint offers to create it.

**Ask questions.** Ask anything the sources might answer. Claude answers from the wiki pages, links every page it used, and tells you how many of those pages you have checked yourself. If the pages are thin, it reads the raw sources directly and says so. At the end it offers to file the answer. Say yes when the answer is worth keeping. It becomes a page under `wiki/analyses/`, and the next question can build on it.

**Tidy up.** Every so often, run lint. The scripts fix what has one correct answer: the index, link typos, field order. Claude then reads the pages and lists what needs your judgement, such as two pages that contradict each other, a claim a newer source has overtaken, or a topic mentioned without a link to its page. What it cannot settle it writes as a dated bullet into the Open questions section of the Overview page. Each Claude Code session in the vault starts with a short status: recent log entries, page counts, how many ingests since the last lint, stale pages and the most wanted pages. When the ingest count is high, lint.

**Review a page.** When you have read a page against its sources and it holds, verify it. Your name and the date go into the page. Only you can do this. Every way Claude could write that block is refused, including the small script that writes it, so Claude checks the page over with you, then hands you one line to run yourself. That is what makes "verified" mean a person looked. Query then counts that page as checked. If a later source changes the page, lint flags the review as outdated and you look again.

**When Claude gets stopped.** Now and then Claude will report that the plugin refused an action. That is the guard rails working. Claude cannot write into `raw/`, cannot touch the verified block, cannot remove a source from a page's list, cannot run the verify script, and cannot end a turn while wiki changes sit unlogged. The same applies through the shell: an in-place edit of a page with `sed`, a redirection into one, an inline `python3 -c` are all refused, so every page write goes through a path the guards can read. Deleting or moving a whole page is not refused, because that is a legitimate act and git records it. If a source file really needs changing, edit it yourself in Obsidian or your editor. The guard only stops Claude.

The log guard is softer than the write guards. At the end of a turn, Claude is stopped when it changed pages that no new log entry names, and it is stopped once per problem: if it ends the turn again having changed nothing, the turn ends. It also keeps its notes for the session in a scratch folder outside the vault, so that git only ever holds your wiki; if your machine clears that folder mid-session, the reminder goes quiet until the next one. It is a reminder, not a lock. The write guards work by refusing the tools Claude writes with, which covers the ways a model actually goes wrong, but a model determined to get around them could still write a little program of its own and run it. What the guards buy you is that the honest path is the easy one, and that anything else would show up in the log and the diff.

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
| Hook | PreToolUse | Blocks writes into `raw/`, in-place shell edits of pages, changes to `verified`, the verify script, and shrinking a page's sources |
| Hook | PostToolUse | Warns about invalid frontmatter, removed headings and links that look like typos |
| Hook | Stop | Refuses to end a turn with unlogged wiki changes or a new page nobody links to, every turn |

## The example wiki

`example-vault/` is a real vault about Claude Code and agentic coding, built with this plugin. It contains the karpathy-llm-wiki README and SKILL file as sources (MIT licensed), pages for the entities and concepts they introduce, one filed answer, one disputed claim and one verified page. Two sources are not committed for licence reasons, Karpathy's gist and the OKF specification. To get them:

```
cd example-vault
/agent-wiki:fetch --restore
```

The example vault also serves as the maintainer's own wiki, so it keeps receiving sources.

## Two ideas combined

The workflow comes from Andrej Karpathy's [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) idea: keep a wiki between the reader and the sources, ingest into it, answer from it with citations, and check it now and then for contradictions and gaps. That gist is the first source in the example wiki.

The metadata comes from Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format) (OKF). Every page records who wrote it, who verified it, which sources it rests on, and when it goes stale, in a small set of frontmatter fields. Karpathy's pattern has no way to tell a page Claude wrote from a page you checked; OKF has no immutable source layer and no notion of two sources disagreeing. Each fills the other's gap, so this plugin uses both.

## Credits and licence

MIT licence, see [LICENSE](LICENSE). The workflow is Andrej Karpathy's LLM Wiki idea; the operating rules borrow from Astro-Han's [karpathy-llm-wiki](https://github.com/Astro-Han/karpathy-llm-wiki) (MIT), in particular the grounding check; the frontmatter follows Google's Open Knowledge Format v0.2. The skills use the Agent Skills format and could be copied into other tools, but without the hooks, which exist only in Claude Code, the guard rails are gone.

The reasoning behind every convention is in [DESIGN.md](DESIGN.md).
