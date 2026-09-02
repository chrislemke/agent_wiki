---
type: synthesis
title: Overview
description: "Hub page of Claude Code and Agentic Coding: what this wiki covers and what is still open."
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources: []
---

# Overview

## Thesis
A working reference on Claude Code and agentic coding practice: how the tool works, how to extend it with skills, hooks and plugins, and which working patterns hold up. This vault is also the example and dogfood vault of the agent-wiki plugin.

The agent-wiki plugin behind this vault combines two of the ingested sources: the [[LLM Wiki Pattern]] for the workflow and the [[Open Knowledge Format]] for the frontmatter vocabulary.

## Evidence
- [[LLM Wiki]] is the founding text: the LLM compiles immutable raw sources into a wiki and keeps it current, the human curates and asks. Summarised as the [[LLM Wiki Pattern]].
- [[karpathy-llm-wiki README]] shows the pattern in production as an Agent Skills skill and lists what its author chose not to build; it disagrees with the founding text on search tooling. Entities: [[Andrej Karpathy]], [[Claude Code]].
- [[karpathy-llm-wiki SKILL]] supplies the operating rules, above all the [[Grounding Invariant]]; the repository has its own page, [[karpathy-llm-wiki]].
- [[Open Knowledge Format Specification]] supplies the frontmatter vocabulary this vault uses for provenance, trust and freshness, summarised as the [[Open Knowledge Format]]. It disagrees with the karpathy-llm-wiki README on per-page expiry dates.
- Filed answer: [[LLM Wiki Versus RAG]] contrasts the wiki with retrieval and states what OKF adds.

## Open questions
- Which Claude Code documentation pages to ingest first: skills, hooks, or plugins?
