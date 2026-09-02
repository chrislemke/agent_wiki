---
type: concept
title: Cascade Updates
description: The pass after a source's primary page is written in which every other page the source affects is found by searching the whole wiki and updated, with contradicted claims marked instead of rewritten.
aliases: [Ripple updates]
tags: [llm-wiki, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: kw-skill
    page: "[[karpathy-llm-wiki SKILL]]"
  - id: llm-wiki
    page: "[[LLM Wiki]]"
---

# Cascade Updates

## Definition
Writing the page for a new source is the smaller half of an ingest. The larger half is finding every existing page whose content the source touches and updating each one: adding the new fact or perspective, adding the source to the page's provenance, and marking any claim the source contradicts or supersedes instead of overwriting it. The search runs over the whole wiki, not only the index, because the index does not show which pages mention an entity in passing.

## How sources treat it
- [[LLM Wiki]] describes the effect: an ingest "updates relevant entity and concept pages across the wiki", so that a single source may touch many pages.[^llm-wiki]
- [[karpathy-llm-wiki SKILL]] names the pass and gives its rules: check for ripple effects after the primary article; search the full wiki for the source's key entities, aliases and the claims it touches; update every non-archive article whose content is materially affected; keep a superseded or contradicted claim and mark it with a Status block; leave archive pages alone because they are point-in-time snapshots.[^kw-skill]
- The same file is why cascade updates forbid parallel compilation: "compile one source at a time, because index.md, log.md, and cascade updates are shared state".[^kw-skill]

## Not to be confused with
- Rewriting a page: a cascade update augments and marks; the old text stays visible.
- Regenerating the index: that is bookkeeping done by a script after the cascade, not part of it.

## Open questions
- How does the pass scale when a source touches dozens of pages? The sources describe the rule, not a budget.

[^llm-wiki]: LLM Wiki
[^kw-skill]: karpathy-llm-wiki SKILL
