# Bookkeeping: stamping, log, commit, write order

## Scripts

All scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` and run with `python3`. `${CLAUDE_PLUGIN_ROOT}` is the plugin root; when the variable is not set, it is two directories above the skill's base directory. Every script accepts `--vault <path>` and `--json`. Exit codes: 0 clean, 1 findings, 2 usage.

| Task | Command |
|---|---|
| Find the vault | `vault.py detect [--json]` |
| Read the domain settings | `vault.py settings --json` |
| Stamp a page after writing it | `frontmatter.py stamp <page> --by agent-wiki/<model-id>` |
| Validate frontmatter | `frontmatter.py validate <page or vault> --json` |
| Set one scalar field | `frontmatter.py set <page> status contested` |
| Resolve links on a page | `links.py resolve <page or vault> --json` |
| Inbound links to a page | `links.py inbound "<Title>" --json` |
| Hash a raw file | `rawhash.py hash <raw file>` |
| Regenerate indexes | `index.py build` |
| Append a log entry | `log.py append --op <op> --title "<title>" --created "<Page>" --updated "<Page>" --note "<text>"` |
| Rename or merge pages | `rename.py rename <page> "<New Title>"`, `rename.py merge <loser> <winner>` |
| Grounding check | `evidence.py check <page or vault> --json` |
| All lint checks | `lint.py all [--fix] [--scope <path>] --json` |
| Fetch into raw | `fetch.py url <URL>`, `fetch.py github <repo URL> --files A,B`, `fetch.py restore` |
| Record a human review | `verify.py <page> --by <human id>` |
| Scaffold a vault | `scaffold.py init --vault <dir> --answers answers.json --by agent-wiki/<model-id>` |

## Actor

`generated.by` is `agent-wiki/<model-id>`, with the exact model id you are running as (for example `agent-wiki/claude-fable-5-1`). Use `agent-wiki/claude` only when the id is unknown. Humans are `human:<id>` and are written only by `verify.py` or by the owner's own editor.

## Write order for an ingest

1. Source page (`wiki/sources/<Title>.md`).
2. Entity and concept pages, new ones through the minting gate, existing ones augmented.
3. Syntheses (at least the Overview, if the source changes the picture).
4. Stamp every page written; validate; resolve links.
5. `index.py build`.
6. `log.py append`.
7. `git commit` with the matching message.

One source at a time. Never compile two sources in parallel: index, log and cascade updates are shared state.

## Log and commit

Log header `## [YYYY-MM-DD] <op> | <title>`, then `- Created:`, `- Updated:`, `- Note:` lines as needed. Operations: `init`, `fetch`, `ingest`, `ingest-failed`, `query`, `lint`, `verify`, `schema`. Titles: the source title for fetch and ingest; the question for query; `N fixed, M proposed` for lint; the page title for verify.

The commit message is `<op>: <title>`, the same words as the log header, no body needed, no attribution trailer. Stage everything under the vault except what `.gitignore` excludes:

```
git add -A -- . && git commit -m "<op>: <title>"
```

When the vault sits inside a larger repository, run git from the vault directory anyway; the commit lands in the enclosing repository with paths relative to it.

## Confidentiality

Read `vault.py settings --json` before any outward action. `confidential: true` forbids web search and publishing (Artifacts, gists, anything that leaves the machine) and is explained in one line when it blocks something. `web_search: false` forbids web search alone. Fetching a URL the owner gave is always allowed.
