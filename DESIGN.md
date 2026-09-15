# Design record

This file records the decisions behind `agent-wiki` and why they were made, so
that nobody has to re-litigate them. It was distilled from an eight-round
planning session on 2026-09-02 and from the five specs that came out of it
(GitHub issues #1 to #5 on `chrislemke/agent_wiki`). Decisions are grouped by
topic. Each one states what was chosen and the reason.

The README explains the project for a general reader. This document is for
contributors and for future maintainers of a vault who want to know why the
conventions are what they are.

## 1. What this is

**D1. A plugin, not a template to copy.** The repository is a Claude Code
directory marketplace serving one plugin, `agent-wiki`. People install the
plugin and run `init` in an empty folder to start a wiki. Nobody forks this
repository to make a wiki: their wiki repository then contains only their
content, and plugin fixes reach every wiki through a plugin update.

**D2. Two ideas combined.** The workflow is Karpathy's LLM Wiki pattern
(immutable raw sources, an LLM-maintained wiki, a schema document, ingest /
query / lint). The metadata is the Open Knowledge Format's (OKF v0.2)
provenance, trust and freshness vocabulary. OKF has no raw layer and no model
for disagreeing sources; the Karpathy pattern has no trust signal and no
freshness. Each fills the other's gap.

**D3. One vault, one domain.** The graph view, the index size, the privacy
boundary and the domain block of `CLAUDE.md` all assume a single subject.
Someone with three topics runs `init` three times.

**D4. Obsidian is the reader.** Pages use Title Case filenames with spaces and
`[[wikilinks]]`, the Obsidian defaults, because the LLM reads and writes links
thousands of times and the shortest form is the one it will not drop under
pressure. Basenames are unique across the wiki so shortest-path links never
collide; synonyms live in `aliases`.

**D5. The vault must survive its plugin.** The vault's `CLAUDE.md` carries a
compact copy of the generic conventions, so a human, Codex, or any other tool
can maintain the wiki without these skills. The skills are the disciplined fast
path, not the only path.

## 2. Vault layout

```
<vault>/
  CLAUDE.md            generic block (versioned) + domain block (from the init interview)
  index.md             generated; one protected curated block at the top
  log.md               append-only, chronological
  .agent-wiki.json     marker: schema version, plugin version, creation date
  .obsidian/           minimal committed config (wikilinks, attachment folder)
  .claude/settings.json  names this marketplace and plugin, so clones prompt to install
  raw/                 immutable sources; raw/assets/ for images; raw/SOURCES.md lists restorable sources
  wiki/sources/  wiki/entities/  wiki/concepts/  wiki/syntheses/  wiki/analyses/
```

**D6. Folders per type.** `ls wiki/entities` answers "what entities exist"
without parsing frontmatter, and moving a page between types is rare. Domain
subtypes (people versus companies) are tags, not folders.

**D7. Special files at the vault root.** `index.md` and `log.md` are reserved
basenames and never pages. Each type folder also gets a generated `index.md`
for progressive disclosure once the root index outgrows a context window.

**D8. The marker file.** `.agent-wiki.json` lets hooks detect a vault from any
subdirectory and read the schema version without parsing markdown. Every
script also accepts an explicit vault path.

**D9. Settings live in `CLAUDE.md`.** The domain block holds a fenced `yaml`
settings block (language, image cap, human id, confidentiality, web search,
tag vocabulary, staleness map, extra types). Scripts parse it with the same
frontmatter parser; the model reads the same text. One source of truth, no
side file that drifts.

## 3. Frontmatter

**D10. OKF vocabulary, Obsidian idiom.** Field names follow OKF v0.2 where the
concept exists: `description` (not `summary`), `resource` (not `url`),
`generated: {by, at}` (not `updated`), `verified` as a list of `{by, at}`,
`sources` as a list of `{id, page}`, `status` with `deprecated`, and
`stale_after`. Departures are deliberate: wikilinks instead of markdown paths,
plain `YYYY-MM-DD` dates instead of datetimes with offsets, and our own log
format. An export to strict OKF is a documented extension.

**D11. Every value stays a string.** PyYAML rewrites ISO dates on round trip.
Our stdlib parser handles a documented YAML subset (scalars, quoted strings,
inline and block lists, one-level nested mappings, lists of mappings) and
reports anything else as unparseable rather than guessing. Round-tripping a
canonical page is byte-identical.

**D12. Required fields per type; unknown fields allowed.** Every page needs
`type`, `title`, `description`, `created`, `generated`. Source pages add
`raw`, `raw_sha`, `disposition`, `ingested`; `author`, `published` and
`resource` are recorded when the raw file knows them and are optional because
many sources have no known author or date. Analysis pages add `question`.
Unknown fields and unknown types produce warnings, never rejections, so a vault
from a newer plugin still works with an older one, and a domain can extend the
schema.

**D13. Actors.** `generated.by` is `agent-wiki/<model-id>`; people are
`human:<id>`. The `human:` prefix is what trust tiers key off.

**D14. `generated.at` means the knowledge changed.** A typo or formatting fix
does not refresh it. Lint compares it with git history to keep "last changed"
truthful.

## 4. Truth, trust and freshness

**D15. Grounding invariant.** Every load-bearing literal (numbers, ISO dates,
quotes of fifteen or more characters) must appear verbatim in the raw files the
page cites. Ingest establishes it: locate before you write, write as found (if
the source says 42K, write 42K). Lint verifies it with a deterministic checker
that reports suspects and never edits facts. The resolution chain is two hops:
page `sources[].page` names a source page, whose `raw` names the file.

**D16. Per-claim attribution for load-bearing claims only.** Footnotes `[^id]`
whose label matches a `sources[].id` attribute numbers, dates, quotes and any
disputed claim. Keys beat positions because agents reorder lists. Unfootnoted
literals are checked against all of the page's sources. Lint checks that every
footnote resolves and every definition is used.

**D17. Verification is a control, not a convention.** `verified` is set only by
a plugin script the owner runs themselves, or by a human editing the file. The
`verify` skill is user-invoked and prepares the review, but the Bash guard
denies `verify.py` to the model, so the model can neither decide on its own that
the owner reviewed a page nor stamp one on their behalf. A hook denies any write
from the LLM that changes `verified`, falling back to a textual comparison when
the written frontmatter does not even parse. That covers the file tools and,
because in-place Bash writes into `wiki/` are denied outright, the shell as
well: every page write reaches a path the guard can read. Approving an ingest plan
is not reading the page, so it does not verify anything. Lint flags a page
whose `generated.at` is later than its last `verified.at` as "review outdated";
OKF treats the two as independent, which is precisely the hazard.

**D18. Freshness is derived, not guessed.** The domain block maps tags to days
(for example `docs: 90`). The stamp script computes `stale_after` from the
page's tags, taking the shortest window, and removes it when no tag matches.
Lint lists stale pages and suggests re-fetching sources. A domain with no
fast-moving content leaves the map empty.

**D19. Disputes stay visible and are never resolved by the LLM.** A
contradiction is recorded in place, as a blockquote directly beneath the claim
(`Status: Disputed` with both claims and their sources, or `Status: Outdated`
with a date and what replaced it), plus `status: contested` in frontmatter. The
in-place block is where the reader already is; a separate section would drift.
Resolution is the human's job. Whole-page supersession uses
`status: deprecated` with links both ways.

**D20. Updates augment, never rewrite.** Cascade updates during ingest are
where an LLM most often trims a page it did not fully read. A hook denies any
write that shrinks a page's `sources` and warns when a top-level heading
disappears. A rewrite happens only when the owner asks for one.

## 5. Pages and the graph

**D21. Fixed skeletons per type, empty sections may be omitted.** Source:
Summary, Key claims, Entities and concepts, Notable quotes, Assessment. Entity:
What it is, Key facts, Timeline, Relationships, Sources. Concept: Definition,
How sources treat it, Open questions. Synthesis: Thesis, Evidence,
Counter-evidence, Open questions, Sources. Analysis: Question, Answer,
Evidence, Caveats, Sources. Entity and concept pages may add "Not to be
confused with". Consistent sections are what make a 200-page wiki skimmable.

**D22. The minting gate.** A new entity or concept page is created only if the
topic is nameable, not meta content, citable from another page, and wanted by
two or more sources or pages (or named as central by the domain lens).
Otherwise the concept is mentioned inline and may be promoted later. Pages are
earned by reuse, not created on first mention.

**D23. Wanted pages.** Unresolved wikilinks are allowed. Inbound links count
body wikilinks and `sources[].page` citations alike; source pages are never
orphans, since the index catalogues them and citations reach them through
frontmatter. Hub pages that ground nothing declare `sources: []` so the evidence
checker leaves their editorial text alone. They are the Obsidian
"ghost node" idiom and a deterministic signal: a script counts inbound
unresolved links and lint proposes creating any target with two or more. The
typo risk is handled by a near-miss check (case-insensitive match or edit
distance of two or less against basenames and aliases), which hooks warn about
immediately.

**D24. Controlled tags, English pages.** Tags come from the vocabulary in the
domain block; lint flags others. All pages are in English regardless of source
language, with verbatim quotes in their original language. The wiki only
compounds when the same thing has the same name.

**D25. The index is generated.** A script rebuilds `index.md` from
frontmatter: sections per type in a fixed order, alphabetical within a type,
source entries showing their publication date. One protected block at the top
holds hand-written "start here" guidance. A hand-maintained catalog is the
first thing to rot.

**D26. The Overview hub.** `init` creates `wiki/syntheses/Overview.md` with an
Open questions section, so no page is ever without a home and lint has a
default place to file findings.

## 6. Operations

**D27. Six skills.** `init`, `fetch`, `ingest`, `query`, `lint`, `verify`.
`status` was dropped because the SessionStart hook does it; `file` was dropped
because filing is the last step of `query`. `init` and `verify` are user-invoked
(no model triggering): creating a vault and recording a human review are the
owner's calls. The other four carry trigger phrases so the model reaches them
from ordinary requests inside a vault.

**D28. One interactive gate in ingest.** After reading a source and searching
the whole wiki for its entities and synonyms, the LLM states a disposition
(new, update, disputed, no-material), then shows takeaways and a page plan
together and waits. Two gates double the round trips for the common "go".
`--all` implies batch; `--batch` on one path skips the gate for a trusted
source.

**D29. Every raw file gets a source page.** Even a no-material source gets a
short one, because the source page is the provenance anchor and the single
mechanism for "is this ingested". Its `raw_sha` lets lint detect a replaced raw
file.

**D30. One source at a time, never in parallel.** Index, log and cascade
updates are shared state. This binds batch mode and any future subagent use.

**D31. One commit and one log entry per operation.** Log header
`## [YYYY-MM-DD] <op> | <title>`, commit message `<op>: <title>`, no
attribution trailer. The log and git history then describe the same events in
the same words and either can verify the other. In batch mode this holds per
source, so a bad ingest is one revert away. Failed sources are logged as
`ingest-failed` and skipped.

**D32. Query falls back honestly.** Index first, then pages, then ripgrep. If
the wiki cannot answer, read raw and say which page was too thin; that flag is
a lint finding for free. Web search only when the domain block allows it.
Answers cite pages as wikilinks and state how many cited pages are unverified.
Every query is offered for filing as an analysis page and logged either way;
an unfiled query is committed with only its log entry, so the rule "every
operation ends with a log entry and a commit" has no exception (the spec's
"commit only when filed" was dropped for that consistency).

**D33. Lint fixes structure, proposes semantics.** Deterministic problems
(index drift, key order, unique near-miss links, missing `created` derivable
from git) are fixed automatically. Everything needing judgement is reported;
open semantic findings are filed into the relevant synthesis page's Open
questions rather than a report nobody reopens. Duplicate pages are merged
through a rename helper that rewrites every link and adds the old title as an
alias.

**D34. Fetch keeps the article, not a summary.** `uvx trafilatura` extracts
verbatim markdown. Only when that fails does WebFetch run, and the raw file is
stamped `fidelity: summary`. GitHub repository URLs fetch the README plus named
files as separate raw files. `fetch --restore` re-downloads everything listed
in `raw/SOURCES.md`.

**D35. Confidentiality has teeth.** `confidential: true` disables web search
and Artifact publishing in every skill. `web_search` is a separate switch.
Fetch stays allowed since it only sends the URL outbound.

## 7. Hooks

**D36. Only the harness can enforce what the model forgets.** Four hooks, all
silent outside a vault:

- SessionStart shows the last log entries, page counts, ingests since the last
  lint, stale pages and the most wanted pages.
- PreToolUse denies writes into `raw/` from Write, Edit, MultiEdit and from
  write-like Bash commands (in-place sed, mv, cp, rm, tee, redirections, inline
  interpreters, downloaders, `find -delete`, directory and mode changes), with
  the plugin's fetch and scaffold scripts allowlisted and `raw/SOURCES.md`
  exempt, since it is a list of sources rather than a source. Every rule is
  written against the TARGET token, so it still fires after a `cd` into the
  layer. The same pattern list guards `wiki/`, minus `rm`, `mv`, the git write
  verbs and the directory and mode changes: an in-place shell edit would slip
  past the `verified` and `sources` guards, while deleting or moving a whole
  page is legitimate and visible in git, and a directory or a mode can forge
  neither a review nor a source. A shell already sitting inside a layer is
  judged by the event's `cwd`, not only by a `cd` in the command, because the
  Bash tool's working directory persists between calls. It also denies writes
  that change `verified` or shrink `sources`, and denies `verify.py` itself
  wherever it runs: stamping a human review is the owner's own act.
- PostToolUse warns on invalid frontmatter, frontmatter comments that
  normalising would drop, removed top-level headings and near-miss link
  targets. It never undoes a write.
- Stop blocks once per turn's problem set when wiki files changed without a log
  entry, when a changed page is named by no new entry, or when a page created
  in the turn has no inbound link. Every Stop that passes opens a fresh
  accounting window, so the gate judges each turn rather than only the first
  one.

**D37. Graded strictness.** Raw immutability, `verified` and `sources`
shrinkage are hard denials. Everything else is a warning the model must answer.
Blocking every intermediate write would fight the natural order of an ingest.

**D38. Hook state lives outside the vault.** One JSON file per session in the
system temporary directory, so git history contains only wiki content. Human
edits made in Obsidian bypass hooks by design.

## 8. Tooling and testing

**D39. Python 3 standard library only.** Scripts and hooks run with the
system `python3` (3.9 or newer) so a vault works on a machine without `uv`.
Each script is one entry point per concern with subcommands, a `--json` flag,
and exit codes 0 clean, 1 findings, 2 usage (`vault.py detect` exits 1 when no
vault encloses the path, since "not found" is its finding). No script writes
inside `raw/` except the two designated ones: `fetch.py`, which creates raw
files and never overwrites, and `scaffold.py`, which creates the empty layout
(`raw/assets/.gitkeep`, the `raw/SOURCES.md` header).

**D40. One test seam.** A fixture vault on disk plus the script command line
(and for hooks, a JSON event on stdin). Tests assert only on exit code, output
and resulting files. Nothing imports script internals. Skills are prose the
model executes and are validated by running them on the example vault.

**D41. Public-repo hygiene.** The example vault commits only raw files whose
licence allows redistribution. Everything else is listed in `raw/SOURCES.md`
and restored with `fetch --restore`; lint reports a listed-but-missing raw file
as "run restore", not as an error. MIT licence. No attribution trailers in
history.

## 9. Additions beyond the specs

Small things the implementation added that the specs did not name, kept
because they cost little and remove a failure: the hook matchers include
`NotebookEdit`; `stamp` also sets `ingested` on source pages; lint reports a
fourth group, `fixable`, for what `--fix` would change; extra subcommands
(`frontmatter.py set`, `links.py inbound`, `fetch.py plan-url`,
`scaffold.py render-claude-md`, one `lint.py <checker>` per checker); extra
Bash deny patterns (`touch`, `install`, `dd`, `rsync`, `ln`, `find -delete`,
`sort -o`, `shred`, `sponge`, `xargs`, heredoc interpreters, git write verbs,
whole-layer `rm`/`mv` and `cd raw && ...`); footnotes anywhere in a sentence,
not only at its end, bind that sentence's literals; the index links
`[[Basename|Title]]` when the two differ; and the OKF specification joined the
example vault as a third, restorable seed source because the plugin builds on it.

## 10. Documented extensions, not built

Office formats via `markitdown`; directory sources; `fetch --crawl` with a host
restriction; a git remote allowlist for confidential vaults; subagent-parallel
lint; slides and charts as query output; OKF export; attested computations; a
one-click template repository; search tooling such as `qmd` once the index
stops being enough.

## 11. Prior art

- Karpathy, *LLM Wiki* (gist 442a6bf555914893e9891c11519de94f): the three
  layers and the operations.
- Astro-Han, *karpathy-llm-wiki* (MIT): the grounding invariant and its
  candidate definition, triage dispositions, in-place status blocks, and the
  rules "search the whole wiki before triage", "compile one source at a
  time", "updated means knowledge changed".
- Google Cloud, *Open Knowledge Format v0.2*: the frontmatter vocabulary,
  trust tiers, `stale_after`, footnotes keyed to source ids, augmentation
  rules, the minting gate, per-directory indexes and "one link per concept
  mention per section".
