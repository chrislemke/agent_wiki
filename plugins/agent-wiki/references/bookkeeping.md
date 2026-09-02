# Bookkeeping: scripts, actor, write order, log and commit

## Scripts

All scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/` and run with `python3`. `${CLAUDE_PLUGIN_ROOT}` is the plugin root; when the variable is not set, it is two directories above the skill's base directory. Exit codes: 0 clean, 1 findings, 2 usage. The flags below are exact; `--help` on any script prints the rest.

| Task | Command |
|---|---|
| Find the vault | `vault.py detect [PATH] [--json]` (prints the root; `root` in JSON; exit 1 when no vault encloses the path) |
| Read the domain settings | `vault.py settings [--vault V] --json` (booleans are the strings `"true"`/`"false"`) |
| Stamp a page after writing it | `frontmatter.py stamp <page> --by agent-wiki/<model-id> [--vault V]` (sets `generated`, `created` and `stale_after`; `ingested` on source pages) |
| Validate frontmatter | `frontmatter.py validate <page or vault> [--json]` |
| Set one scalar field | `frontmatter.py set <page> <key> <value>` (refuses `verified`) |
| Canonical key order | `frontmatter.py normalize <page>...` |
| Resolve links | `links.py resolve <page or vault> [--json]` (exit 1 on wanted pages too) |
| Inbound links to a page | `links.py inbound "<Title>" [--vault V] [--json]` (body links and `sources[].page`) |
| Hash a raw file | `rawhash.py hash <raw file>` |
| Compare raw hashes | `rawhash.py compare <page or vault> [--json]` |
| Regenerate indexes | `index.py build [--vault V]`; drift: `index.py check [--vault V] [--json]` |
| Append a log entry | `log.py append --op <op> --title "<title>" [--created "<Page>" ...] [--updated "<Page>" ...] [--note "<text>"] [--vault V]` |
| Read the log | `log.py tail <N> [--json]`, `log.py since-lint [--json]`, `log.py parse [--json]` |
| Rename or merge pages | `rename.py rename <page> "<New Title>" [--vault V]`, `rename.py merge <loser> <winner> [--vault V]` |
| Grounding check | `evidence.py check <page or vault> [--json]` |
| All lint checks | `lint.py all [--vault V] [--scope <path>] [--fix] [--json]`; one checker: `lint.py <checker> [--vault V] [--json]` |
| Fetch into raw | `fetch.py url <URL> [--stdin --fidelity summary --title T] [--json]`, `fetch.py github <repo URL> [--files A,B] [--json]`, `fetch.py restore [--json]`, `fetch.py plan-url <URL>` |
| Record a human review | `verify.py <page> --by <human id> [--vault V]` |
| Scaffold a vault | `scaffold.py init --vault <dir> --answers answers.json --by agent-wiki/<model-id> [--json]`; `scaffold.py render-claude-md --answers answers.json` |

`--created` and `--updated` take one or more page titles after the flag and may be repeated. Titles are written bare or as `[[Title]]`; the log gets `[[Title]]`.

## Actor

`generated.by` is `agent-wiki/<model-id>`, with the exact model id you are running as (for example `agent-wiki/claude-fable-5-1`). Use `agent-wiki/claude` only when the id is unknown. Humans are `human:<id>` and are written only by `verify.py` or by the owner's own editor.

## Write order for an ingest

1. Source page (`wiki/sources/<Title>.md`).
2. Entity and concept pages, new ones through the minting gate, existing ones augmented.
3. Syntheses (at least the Overview, if the source changes the picture).
4. Stamp every page written; validate; resolve links; run the evidence check on the written pages.
5. `index.py build`.
6. `log.py append`.
7. `git commit` with the matching message.

One source at a time. Never compile two sources in parallel: index, log and cascade updates are shared state.

## Log and commit

Log header `## [YYYY-MM-DD] <op> | <title>`, then `- Created:`, `- Updated:`, `- Note:` lines as needed. Operations: `init`, `fetch`, `ingest`, `ingest-failed`, `query`, `lint`, `verify`, `schema`. Titles: the source title for ingest; for fetch the source title, `<repo> README[ and <files>]` for a repository, or `restore: <N> sources`; the question for query; `<N> fixed, <M> proposed` for lint (a check-only run may use a short description such as `fresh clone acceptance`); the page title for verify; `generic block v<N>` for schema.

The commit message is `<op>: <title>`, the same words as the log header, no body needed, no attribution trailer. Every operation ends with both, an unfiled query included (its commit holds only the log entry). Run git against the vault root reported by `vault.py detect`, whatever the working directory:

```
git -C <root> add -A -- . && git -C <root> commit -m "<op>: <title>"
```

When the vault sits inside a larger repository, the commit lands in the enclosing repository with paths relative to it.

## Confidentiality

Every skill reads `vault.py settings --json` before any outward action. `confidential: "true"` forbids web search and publishing (Artifacts, gists, anything that leaves the machine) and is explained in one line when it blocks something. `web_search: "false"` forbids web search alone. Fetching a URL the owner gave is always allowed.
