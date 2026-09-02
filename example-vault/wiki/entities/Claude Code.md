---
type: entity
title: Claude Code
description: Anthropic's terminal coding agent; the host this vault is built for, whose schema document is CLAUDE.md and which supports Agent Skills.
aliases: [claude-code]
tags: [claude-code, agents]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: llm-wiki
    page: "[[LLM Wiki]]"
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
---

# Claude Code

## What it is
Anthropic's coding agent that runs in the terminal, reads and edits files, runs commands, and is configured through a project file named CLAUDE.md plus skills, hooks and plugins. In this wiki it is both a subject and the host: the agent-wiki plugin runs inside it.

## Key facts
- [[LLM Wiki]] names CLAUDE.md as the schema document when the pattern runs on Claude Code, the counterpart of AGENTS.md for Codex.[^llm-wiki]
- [[karpathy-llm-wiki README]] lists Claude Code first among the tools that install the skill with `npx add-skill Astro-Han/karpathy-llm-wiki`, alongside Cursor, Codex CLI and OpenCode, all through the Agent Skills standard.[^kw-readme]
- The same README keeps automatic hooks and scheduled runs out of a tool-agnostic skill because "those belong to the agent harness", which is exactly what a Claude Code plugin can add.[^kw-readme]

## Relationships
- [[LLM Wiki Pattern]]: the pattern this vault runs on Claude Code.
- [[Agent Skills]]: the skill format Claude Code shares with other tools.
- [[karpathy-llm-wiki]]: a skill installable into Claude Code.

## Not to be confused with
- Claude, the model family: Claude Code is the agent product that drives a Claude model with tools.

## Sources
- [[LLM Wiki]]
- [[karpathy-llm-wiki README]]

[^llm-wiki]: LLM Wiki
[^kw-readme]: karpathy-llm-wiki README
