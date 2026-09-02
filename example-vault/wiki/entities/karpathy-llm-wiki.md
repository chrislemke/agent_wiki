---
type: entity
title: karpathy-llm-wiki
description: An MIT-licensed Agent Skills skill by Astro-Han that implements the LLM Wiki pattern with ingest, query and lint, backed by a production wiki since April 2026.
aliases: [Astro-Han/karpathy-llm-wiki]
tags: [llm-wiki, skills]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
  - id: kw-skill
    page: "[[karpathy-llm-wiki SKILL]]"
---

# karpathy-llm-wiki

## What it is
A GitHub repository that packages the [[LLM Wiki Pattern]] as one installable skill in the Agent Skills format. Its two central files are the README, which explains the idea, the usage figures and the design boundaries, and SKILL.md, the schema the agent follows. This vault ingested both.

## Key facts
- Calls itself an unofficial community implementation of the workflow from Karpathy's LLM Wiki idea, and is MIT licensed.[^kw-readme]
- Installs with `npx add-skill Astro-Han/karpathy-llm-wiki` into [[Claude Code]], Cursor and OpenCode, or by copying the skill directory for Codex CLI and other Agent Skills tools.[^kw-readme]
- Reports a production knowledge base of 94 wiki articles across 13 topic directories, 99 source materials and 87 operation log entries in the last 7 days, maintained daily since April 2026.[^kw-readme]
- Ships a mechanical evidence check, check_evidence.py, that reports fidelity suspects, evidence errors and unreferenced raw files without fixing anything.[^kw-skill]
- Lays out raw/ and wiki/ by topic directory, one level deep, with index.md and log.md inside wiki/.[^kw-skill]

## Relationships
- [[Andrej Karpathy]]: originator of the idea the skill implements.
- [[LLM Wiki Pattern]]: what it implements.
- [[Grounding Invariant]]: the rule it introduces to the pattern.
- [[Agent Skills]]: the format it ships in.
- [[Open Knowledge Format]]: tracked in its README, not adopted.

## Not to be confused with
- [[LLM Wiki]]: Karpathy's idea file. The repository is a third-party implementation, not his.

## Sources
- [[karpathy-llm-wiki README]]
- [[karpathy-llm-wiki SKILL]]

[^kw-readme]: karpathy-llm-wiki README
[^kw-skill]: karpathy-llm-wiki SKILL
