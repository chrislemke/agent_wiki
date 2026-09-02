---
type: concept
title: Agent Skills
description: The open standard (agentskills.io) for packaging an agent's instructions as a SKILL.md file with supporting references and scripts, shared by Claude Code, Cursor, Codex CLI and OpenCode.
aliases: [SKILL.md format, agentskills.io]
tags: [skills, claude-code]
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

# Agent Skills

## Definition
A convention for shipping reusable behaviour to a coding agent as a folder: a SKILL.md file whose frontmatter carries a name and a description that says when to use it, and whose body holds the instructions, plus optional references and scripts beside it. Because several tools read the same layout, one skill can be installed into any of them. This vault's own plugin ships six skills in this format.

## How sources treat it
- [[karpathy-llm-wiki README]] packages the whole LLM wiki workflow as one skill in this format, installs it with `npx add-skill Astro-Han/karpathy-llm-wiki` into [[Claude Code]], Cursor and OpenCode, copies it into a skills directory for Codex CLI, and tells other tools to copy SKILL.md, references and scripts into their own skill directory.[^kw-readme]
- [[karpathy-llm-wiki SKILL]] is an instance: its frontmatter names the skill and lists the phrases that trigger it, and the body is the schema the agent follows, with templates in a references folder read on demand.[^kw-skill]

## Not to be confused with
- A Claude Code plugin: a plugin bundles skills together with hooks and other components and is installed from a marketplace; a skill is one folder that other tools can read too.

## Open questions
- Which parts of a skill carry over between tools unchanged, and which (hooks, permissions) do not?

[^kw-readme]: karpathy-llm-wiki README
[^kw-skill]: karpathy-llm-wiki SKILL
