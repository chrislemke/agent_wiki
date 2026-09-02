# The init interview

Six questions, asked in one message, with the defaults shown. The answers become the domain block of the vault's `CLAUDE.md` and the `answers.json` handed to `scaffold.py`. Propose answers when you can infer them from the folder (its name, an existing README, files in `raw/`), so the owner mostly confirms.

1. **Purpose.** What is this wiki about, in one paragraph? Also the vault's title (default: the folder name in Title Case). Writes `title` and `purpose`.
2. **Entities.** What kinds of things deserve their own page? (people, companies, tools, papers, characters, places) Writes `entities`.
3. **Sources.** What does a typical source look like and where does it come from? (articles, papers, docs, meeting notes, book chapters) Writes `sources`.
4. **Lens.** What thesis or angle are you pursuing; what should ingest emphasise and what should it ignore? Names the concepts that count as central (they pass the minting gate on first mention). Writes `lens`.
5. **Sensitivity.** Is the content confidential (default: no)? May the LLM use web search to fill gaps (default: yes)? The confidential flag disables web search and any publishing in every skill. Writes `confidential` and `web_search`.
6. **Overrides.** Language of the wiki pages (default: English, `en`); image cap per source (default: 5); the tag vocabulary (propose eight to twelve kebab-case tags from the purpose); the staleness map, tag to days, for content that expires (default: empty; `docs: 90` is typical for product documentation); extra page types (default: none); the owner's id for `verify` (default: the git user name, lower-cased, spaces to dashes). Writes `language`, `image_cap`, `tags`, `staleness`, `extra_types`, `human_id`.

`answers.json` shape:

```json
{
  "title": "Claude Code Notes",
  "purpose": "...",
  "entities": "...",
  "sources": "...",
  "lens": "...",
  "confidential": false,
  "web_search": true,
  "language": "en",
  "image_cap": 5,
  "human_id": "chris",
  "tags": ["claude-code", "skills", "hooks"],
  "staleness": {"docs": 90},
  "extra_types": []
}
```
