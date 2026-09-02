---
type: source
title: karpathy-llm-wiki README
description: README of the karpathy-llm-wiki repository, an MIT-licensed Agent Skills implementation of the LLM Wiki pattern with ingest, query and lint, usage figures from a production wiki, and a list of features deliberately not built.
tags: [llm-wiki, skills, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
raw: raw/karpathy-llm-wiki README.md
raw_sha: 4bd034168e607d766447adf3c0e000563dd0d92ca263c6091edbb8d103906c92
disposition: disputed
author: Astro-Han
resource: https://github.com/Astro-Han/karpathy-llm-wiki/blob/main/README.md
ingested: 2026-09-02
---

# karpathy-llm-wiki README

## Summary
The README of [[karpathy-llm-wiki]], which packages the [[LLM Wiki Pattern]] as one installable skill in the Agent Skills format. It states the three operations (ingest, query, lint), contrasts an LLM wiki with RAG in a table, reports usage figures from the author's own knowledge base, shows the directory layout, and closes with "Design Boundaries": a list of features deliberately not built after three months of production use, including hooks, search tooling, review dates and OKF conformance. Disposition new for the two entities it mints, update for the [[LLM Wiki Pattern]], and disputed because its stance on search tooling differs from [[LLM Wiki]].

## Key claims
- The skill packages Karpathy's LLM Wiki idea into one installable Agent Skills skill: the coding agent ingests sources into raw/, compiles durable knowledge pages into wiki/, answers questions with citations, and lints the wiki for consistency.[^kw-readme]
- Usage figures: "Based on a production knowledge base maintained daily since April 2026", with 94 wiki articles across 13 topic directories, 99 source materials ingested and 87 operation log entries in the last 7 days.[^kw-readme]
- Install is one command, `npx add-skill Astro-Han/karpathy-llm-wiki`, and works with [[Claude Code]], Cursor, Codex CLI, OpenCode and any tool that supports the Agent Skills standard.[^kw-readme]
- LLM wiki versus RAG: in RAG knowledge lives in raw chunks and embeddings and synthesis happens at query time; in the wiki it lives in curated markdown pages and synthesis happens during ingest and maintenance.[^kw-readme]
- Not built, by design: source-hash freshness tracking ("raw/ is immutable, so hashes guard against events that cannot happen"), persisted line-number citations, numeric confidence scores, per-article review dates, access-based decay, retract machinery, automatic hooks and scheduled runs ("those belong to the agent harness"), vector or graph search, typed relationship ontologies, OKF conformance, MCP servers and UIs.[^kw-readme]
- On search: "at 50K–100K tokens of curated wiki, grep and read are more reliable. Add search tooling only when recall measurably degrades."[^kw-readme]
- On OKF: "the spec is a v0.1 draft with a minimal tooling ecosystem. Tracked; will be revisited."[^kw-readme]
- The repository calls itself an unofficial community implementation and points to related projects (lucasastorian/llmwiki, atomicmemory/llm-wiki-compiler) and to Google's [[Open Knowledge Format]].[^kw-readme]

## Entities and concepts
- [[karpathy-llm-wiki]]: the repository this README describes.
- [[Andrej Karpathy]]: originator of the idea the skill implements.
- [[Claude Code]]: first entry in the tool compatibility table.
- [[LLM Wiki Pattern]]: what the skill implements; the README's RAG comparison and design boundaries extend the concept page.
- [[Agent Skills]]: the open standard (agentskills.io) the skill follows.
- [[Open Knowledge Format]]: tracked, not adopted.

## Notable quotes
> This skill is optimized for the wiki model: knowledge that improves over time instead of re-deriving relationships on every query.[^kw-readme]

## Assessment
A practitioner's document with real numbers and explicit non-goals, which makes it more useful than most READMEs. Two of its boundaries collide with other sources in this wiki: it rejects search tooling that [[LLM Wiki]] recommends, and it dismisses per-page review dates that the [[Open Knowledge Format]] makes first-class. Its OKF assessment names a v0.1 draft, which the current specification has moved past. The disputes are recorded on the [[LLM Wiki Pattern]] and [[Open Knowledge Format]] pages.

[^kw-readme]: karpathy-llm-wiki README
