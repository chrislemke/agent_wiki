# Rules the skills share

Reference for ingest, query and lint. Read the section you need.

## Dispositions

State one before writing anything. `new`, `update` and `disputed` may combine; `no-material` is exclusive.

- **new**: the source introduces entities, concepts or claims the wiki lacks. Creates pages (through the minting gate) and a source page.
- **update**: the source adds to pages that exist. Augments them and adds itself to their `sources`.
- **disputed**: the source contradicts a claim the wiki holds. Adds Status blocks and sets `status: contested` on the affected pages.
- **no-material**: the source adds nothing beyond what the wiki already holds. Still gets a short source page (Summary and Assessment, one line each) so provenance and the backlog stay simple; nothing else changes. Source pages are catalogued by the index and are never counted as orphans.

## The minting gate

Create a new entity or concept page only when all four hold:

1. **Nameable**: the topic has a name people use, fit for a Title Case filename.
2. **Not meta**: it is a thing in the domain, not "overview of X", "notes on Y", a changelog or a list.
3. **Citable**: you can write at least one sentence on another page that links to it.
4. **Wanted**: two or more sources or pages want it, or the lens in the domain block names it as central.

Otherwise mention it inline and leave a `[[Wanted Page]]` link. Lint counts wanted links and proposes the page when the count reaches two. Domain subtypes (people versus companies) are tags, not folders or types.

## Augmentation

Existing pages are augmented, never rewritten, unless the owner asks for a rewrite in so many words.

- Keep every existing heading, in its order. Add bullets, sentences and new sections; do not delete or reword what is there.
- `sources` only grows. Append `{id, page}` entries; never remove one.
- `verified` stays exactly as it is on disk. Only the owner, through `/agent-wiki:verify` or their own editor, changes it; the write guard denies every edit to it, and the Bash guard denies `verify.py` to you, so the owner runs that line themselves.
- A changed claim gets a Status block beneath it; the old text stays.
- Refresh `generated.at` (with `frontmatter.py stamp`) only when the knowledge changed, not for formatting.
- One link per concept mention per section: link the first mention in a section, write the plain name afterwards.

## Disputes

The LLM records disagreements and never resolves them.

- Contradiction between sources: keep both claims, add directly beneath the claim
  `> **Status: Disputed**` and a second blockquote line `> [[Source A]] says <claim A>; [[Source B]] says <claim B>. Unresolved.`, and set `status: contested`.
- Newer source explicitly updates an older claim (a version change, a retraction, a correction): keep the old text, add `> **Status: Outdated** (YYYY-MM-DD)` with what replaced it and its source page.
- Whole subject superseded: `status: deprecated`, a `Superseded by [[Successor]].` line under the first heading, and a back-link from the successor.
- In an interactive ingest you may ask the owner which reading they favour; in batch mode you only record. Resolution is the owner's edit or answer.

## Footnotes and citations

- Load-bearing claims carry a footnote: numbers, dates, quotes, and any claim marked disputed. Plain prose needs none.
- The label is a `sources[].id`: short, kebab-case, stable (`llm-wiki`, `hooks-docs`). Reordering `sources` never changes a footnote.
- Every referenced label has a definition `[^id]: <source title>` at the end of the page; every definition is referenced.
- Locate before you write: grep the raw file for the exact number, date or quote before writing it, and write it as found (`42K` stays `42K`). Derived values show their components. A value you cannot find is stated without precision or left out.
- Answers in a query cite wiki pages as `[[Page]]`. Raw files are cited only when the wiki could not answer, and the answer says so.

## Wiki-wide search before triage

Before stating a disposition, search the whole wiki with `rg -il` for the source's key entities, their synonyms and aliases, and the specific claims it makes. The index alone misses cascade updates. Include `aliases` values and obvious spelling variants in the search.
