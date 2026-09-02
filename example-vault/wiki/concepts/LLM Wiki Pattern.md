---
type: concept
title: LLM Wiki Pattern
description: A knowledge base that an LLM compiles and maintains as an interlinked markdown wiki from immutable raw sources, guided by a schema document, with ingest, query and lint as its operations.
aliases: [LLM Wiki pattern, Karpathy wiki]
tags: [llm-wiki, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: llm-wiki
    page: "[[LLM Wiki]]"
---

# LLM Wiki Pattern

## Definition
A personal or team knowledge base in which the LLM, not the human, writes and maintains the pages. Raw sources stay immutable; the LLM compiles them into summaries, entity pages, concept pages and syntheses, keeps the cross-references current and flags where new material contradicts old claims. A schema document tells the LLM the structure and the workflows. The human curates sources, steers the analysis and asks questions. The pattern positions itself against RAG, where retrieval happens at query time and nothing accumulates between questions.[^llm-wiki]

## How sources treat it
- [[LLM Wiki]] introduces the pattern with three layers (raw sources, wiki, schema), three operations (ingest, query, lint) and two navigation files (index.md read first on every query, log.md appended on every operation). It recommends ingesting one source at a time while staying involved, filing good query answers back as pages, and periodic lint for contradictions, stale claims, orphans and missing pages.[^llm-wiki]
- On search tooling, [[LLM Wiki]] says the index carries a wiki to moderate scale and names qmd, a local hybrid search engine with a CLI and an MCP server, as the tool to add "as the wiki grows".[^llm-wiki]

## Not to be confused with
- Retrieval-augmented generation (RAG): documents are chunked and retrieved at query time; synthesis is redone for every question and nothing is written back.
- A personal wiki maintained by hand: the pattern's point is that the LLM does the maintenance, which is why hand-maintained wikis are abandoned.

## Open questions
- How large can the index-first approach grow before search tooling is needed? The source gives an order of magnitude, not a threshold.
- What does the interactive ingest gate look like in practice, and how much supervision does batch ingest lose?

[^llm-wiki]: LLM Wiki
