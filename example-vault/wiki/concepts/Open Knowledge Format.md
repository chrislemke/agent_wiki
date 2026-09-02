---
type: concept
title: Open Knowledge Format
description: Google Cloud's open format for agent-maintained knowledge, markdown with YAML frontmatter fields for provenance, trust, freshness and lifecycle; the vocabulary this vault's frontmatter follows.
aliases: [OKF]
tags: [okf, docs]
status: contested
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
stale_after: 2026-12-01
sources:
  - id: okf-spec
    page: "[[Open Knowledge Format Specification]]"
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
---

# Open Knowledge Format

## Definition
A format, not a workflow: a directory of markdown files with YAML frontmatter, where a small set of optional fields makes a corpus self-describing. Provenance is a sources list with per-claim footnotes keyed to source ids; trust is the pair generated and verified, from which a consumer derives unverified, machine-confirmed or human-reviewed; lifecycle is status and an absolute stale_after instant. Only the type key is required, and consumers must tolerate everything they do not understand. The vault you are reading adopts this vocabulary for its frontmatter and keeps wikilinks, plain dates and its own log format as deliberate departures.[^okf-spec]

## How sources treat it
- [[Open Knowledge Format Specification]] is the normative text at Version 0.2. It positions the format as vendor-neutral, records credibility signals rather than a credibility score, and adds Attested Computation concepts for values that must be produced the sanctioned way.[^okf-spec]
- [[karpathy-llm-wiki README]] lists OKF conformance among the features it deliberately did not build, describing the spec as a v0.1 draft with a minimal tooling ecosystem that is tracked and will be revisited.[^kw-readme]

> **Status: Outdated** (2026-09-02)
> The specification ingested on this date is Version 0.2, which supersedes v0.1 ([[Open Knowledge Format Specification]]); the README's assessment predates it.

- The two sources disagree on whether a page should carry its own expiry. [[karpathy-llm-wiki README]] rejects per-article review dates because nobody can predict at compile time how fast a domain moves and drives maintenance by whole-wiki lint instead; the specification gives every concept an optional stale_after instant so that staleness is a plain comparison.[^kw-readme]

> **Status: Disputed**
> [[karpathy-llm-wiki README]] says per-article review dates are not worth building because nobody can predict how fast a domain moves; [[Open Knowledge Format Specification]] says a concept carries an absolute stale_after instant so staleness is a plain comparison. Unresolved.

## Not to be confused with
- [[LLM Wiki Pattern]]: the pattern says how a wiki is built and maintained; OKF says how its pages describe where they came from and how much to trust them. This vault uses both.
- A data catalog: OKF grew out of one, but the format itself is domain-neutral.

## Open questions
- Who sets stale_after in practice, and from what? The spec leaves it to the producer.
- How does a consumer treat a verified page whose content changed after the verification?

[^okf-spec]: Open Knowledge Format Specification
[^kw-readme]: karpathy-llm-wiki README
