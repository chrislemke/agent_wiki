---
type: source
title: LLM Wiki
description: Karpathy's idea file for a personal knowledge base that an LLM builds and maintains as an interlinked markdown wiki instead of re-retrieving from raw documents on every question.
tags: [llm-wiki, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
verified:
  - by: human:chris
    at: 2026-09-02
sources:
  - id: llm-wiki
    page: "[[LLM Wiki]]"
raw: raw/LLM Wiki.md
raw_sha: 55b2360538338a5dff0d5f45a8e1f55e6d72853b85734e922689522ab0b18e15
disposition: new
author: Andrej Karpathy
resource: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
ingested: 2026-09-02
---

# LLM Wiki

## Summary
An idea file meant to be pasted into a coding agent so that the agent and its user build a version that fits them. The core move is to replace per-query retrieval (RAG) with a wiki the LLM writes and keeps current: when a source arrives, the LLM reads it, extracts what matters and integrates it into existing pages, so cross-references and contradictions are already in place when a question comes. The human curates sources and asks questions; the LLM does the bookkeeping. The document describes three layers, three operations, two navigation files and a set of practical tips, and it stays deliberately abstract about directory structure and tooling. It is the pattern this vault implements through the [[LLM Wiki Pattern]].

## Key claims
- RAG rediscovers knowledge from scratch on every question; nothing accumulates. The wiki is compiled once and then kept current: "the wiki is a persistent, compounding artifact".[^llm-wiki]
- Division of labour: "The human's job is to curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job is everything else."[^llm-wiki]
- Three layers: raw sources (immutable, the LLM reads but never modifies them), the wiki (LLM-owned markdown), and the schema, a document such as CLAUDE.md or AGENTS.md that turns the LLM into a disciplined maintainer.[^llm-wiki]
- Ingest reads a source, discusses takeaways, writes a summary page, updates the index and the affected entity and concept pages, and appends to the log. "A single source might touch 10-15 wiki pages."[^llm-wiki]
- Query answers come with citations, and "good answers can be filed back into the wiki as new pages" so explorations compound like sources do.[^llm-wiki]
- Lint looks for contradictions, stale claims, orphan pages, concepts without a page, missing cross-references and data gaps.[^llm-wiki]
- A content index (index.md) read first on every query works "at moderate scale (~100 sources, ~hundreds of pages)" without embedding-based retrieval; a chronological log (log.md) with a fixed prefix per entry becomes parseable with plain unix tools.[^llm-wiki]
- Search tooling such as qmd, a local hybrid BM25 and vector search with an MCP server, is presented as the natural first CLI tool once the index is not enough.[^llm-wiki]
- Practical tips: Obsidian Web Clipper for turning articles into markdown, downloading images into a fixed attachment folder such as raw/assets/ so the LLM can view them, the Obsidian graph view for spotting hubs and orphans, Marp for slides, Dataview for frontmatter queries, and git for history.[^llm-wiki]
- The lineage is Vannevar Bush's Memex of 1945: a private, curated store with associative trails, whose unsolved problem was who does the maintenance.[^llm-wiki]

## Entities and concepts
- [[LLM Wiki Pattern]]: the pattern itself, as this wiki names it.
- [[Obsidian]]: the reader the author sits beside the agent; "Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."[^llm-wiki]
- [[Claude Code]]: named as one of the agents the file is written for, with CLAUDE.md as its schema document.
- [[Andrej Karpathy]]: the author.
- Mentioned without a page: OpenAI Codex, OpenCode, qmd, Marp, Dataview, Obsidian Web Clipper, Tolkien Gateway, the Memex.

## Notable quotes
> Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.[^llm-wiki]

> The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping.[^llm-wiki]

## Assessment
A pattern description, not an implementation: it names the layers and operations and leaves structure, page formats and tooling to each domain. It has no notion of who verified a page, of pages that expire, or of per-claim attribution, and it treats every page as equally trustworthy. Its contradiction handling is a lint concern rather than a page convention. Those gaps are what later sources in this wiki address.

[^llm-wiki]: LLM Wiki
