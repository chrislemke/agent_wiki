---
type: concept
title: Grounding Invariant
description: The rule that every load-bearing number, date and quote in a wiki page exists verbatim in a raw source the page links, established when writing and verified by a script.
aliases: [Source fidelity, Locate before you write]
tags: [llm-wiki, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: kw-skill
    page: "[[karpathy-llm-wiki SKILL]]"
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
---

# Grounding Invariant

## Definition
A wiki page may state a specific number, date or direct quote only if that literal appears, in exactly that form, in a raw source the page links. The rule has two halves: the writer locates the literal in the raw file before writing it and writes it as found, and a lint script later greps every high-signal literal in the linked raws and reports the misses as suspects. Because raw files never change, a page that passed once keeps passing, and the whole wiki can be re-checked in seconds.[^kw-skill]

## How sources treat it
- [[karpathy-llm-wiki SKILL]] defines it: "Every load-bearing fact in wiki/ — numbers, dates, direct quotes — exists verbatim in the raw/ files linked by that article's Raw field." Compile establishes it, lint verifies it. Values are written as found ("if the source says 42K, write 42K, not 42,000"), derived values show their components, and a value that cannot be located is dropped or stated without precision.[^kw-skill]
- The same file treats the script's output as candidates, not verdicts: derived values and product names show up as suspects and are judged against the raw context by the reader.[^kw-skill]
- [[karpathy-llm-wiki README]] explains why the project stopped at whole-file grep and did not persist line-number citations: every fidelity error it observed was a value absent from the source, which a whole-file grep catches, and the annotation friction would make agents skip the rule.[^kw-readme]

## Not to be confused with
- Verification by a human: the invariant is mechanical and says a literal exists in the source, not that the page is right or that anyone reviewed it.
- Retrieval grounding in RAG: there the model sees retrieved chunks at answer time; here the check runs on the written page against immutable files.

## Open questions
- Where is the line between a derived value that should show its components and a paraphrase that should not be checked at all?
- Does the rule hold for images and tables, or only for prose?

[^kw-skill]: karpathy-llm-wiki SKILL
[^kw-readme]: karpathy-llm-wiki README
