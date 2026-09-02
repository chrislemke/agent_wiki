---
type: source
title: karpathy-llm-wiki SKILL
description: The SKILL.md of karpathy-llm-wiki, the operating rules of an Agent Skills implementation of the LLM Wiki pattern, including the grounding invariant, triage dispositions, cascade updates, status blocks and a three-level lint.
tags: [llm-wiki, skills, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: kw-skill
    page: "[[karpathy-llm-wiki SKILL]]"
raw: raw/karpathy-llm-wiki SKILL.md
raw_sha: 6d1276b79a5ea84a8f72d3afc04663b3bf4774a5cb715a32dd659bd696455bbd
disposition: update
author: Astro-Han
resource: https://github.com/Astro-Han/karpathy-llm-wiki/blob/main/SKILL.md
ingested: 2026-09-02
---

# karpathy-llm-wiki SKILL

## Summary
The schema layer of [[karpathy-llm-wiki]], written for the agent that runs it. It fixes a two-directory layout (raw/ by topic, wiki/ by topic with index.md and log.md inside wiki/), then specifies the three operations of the [[LLM Wiki Pattern]] in detail: ingest as fetch, triage, compile, cascade updates and post-ingest bookkeeping; query with citations and an explicit archive step; lint with three authority levels. Its distinctive contribution is the [[Grounding Invariant]], a rule that every load-bearing literal must exist verbatim in the linked raw files, established at compile time and verified by a script. Disposition new for the two pages it mints and update for the pattern and the people and repository pages it extends.

## Key claims
- "Every load-bearing fact in wiki/ — numbers, dates, direct quotes — exists verbatim in the raw/ files linked by that article's Raw field." Compile establishes the invariant by locating before writing; lint verifies it with a script that greps the high-signal literals.[^kw-skill]
- Source fidelity means writing the value exactly as found: "if the source says 42K, write 42K, not 42,000". Derived values show their components; an unlocatable value is dropped or stated without precision.[^kw-skill]
- Triage before compiling: search the wiki for the source's key entities and synonyms, then state one of four dispositions, New, Update, Disputed or No material. "Do not force an article out of a thin source."[^kw-skill]
- Cascade updates search the full wiki, not only the index, and refresh every affected article; a contradicted or superseded claim keeps its text and gets a Status block. "Never silently rewrite history."[^kw-skill]
- Parallel search is fine, parallel compilation is not: "compile one source at a time, because index.md, log.md, and cascade updates are shared state".[^kw-skill]
- Query never writes files unless asked; an archived answer is always a new page. "Always create a new page. Never merge into existing articles".[^kw-skill]
- Lint has three authority levels: safe fixes applied automatically (index consistency, internal links, raw references, See Also), mechanical reports from the evidence script (source fidelity suspects, evidence errors, unreferenced raw files), and judgment reports (contradictions, outdated claims, orphans, concepts without a page).[^kw-skill]
- Raw files are named `raw/<topic>/YYYY-MM-DD-descriptive-slug.md` with a metadata header of source, collected and published dates; wiki articles carry Sources, Raw and Updated fields, and "Updated dates reflect when the article's knowledge content last changed".[^kw-skill]

## Entities and concepts
- [[karpathy-llm-wiki]]: the repository whose behaviour this file defines.
- [[LLM Wiki Pattern]]: the pattern, made operational.
- [[Grounding Invariant]]: the file's central rule.
- [[Andrej Karpathy]]: quoted at the top as the origin of the core ideas.
- [[Cascade Updates]]: the ripple pass after the primary article; no page yet.
- [[Status Blocks]]: the Disputed and Outdated annotations beneath a claim; no page yet.
- Mentioned without a page: the check_evidence.py script, See Also sections, archive pages.

## Notable quotes
> compile one source at a time, because index.md, log.md, and cascade updates are shared state[^kw-skill]

## Assessment
The most operational of the sources so far: it turns the pattern's prose into rules an agent can follow and a script can check. Its layout choices (topic folders, index and log inside wiki/, standard markdown links) differ from this vault's, which does not matter for the rules. It has no notion of who verified an article and no expiry, which the [[Open Knowledge Format]] adds.

[^kw-skill]: karpathy-llm-wiki SKILL
