---
type: analysis
title: LLM Wiki Versus RAG
description: Filed answer on how an LLM-maintained wiki differs from retrieval-augmented generation and what the Open Knowledge Format adds to the wiki's pages.
tags: [llm-wiki, okf, workflow]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
sources:
  - id: llm-wiki
    page: "[[LLM Wiki]]"
  - id: kw-readme
    page: "[[karpathy-llm-wiki README]]"
  - id: okf-spec
    page: "[[Open Knowledge Format Specification]]"
question: How does an LLM wiki differ from RAG, and what does the Open Knowledge Format add on top?
---

# LLM Wiki Versus RAG

## Question
How does an LLM wiki differ from RAG, and what does the Open Knowledge Format add on top?

## Answer
RAG and an LLM wiki put the work in different places. In RAG the knowledge stays in raw chunks and embeddings and the model re-synthesises an answer on every question, so nothing accumulates between questions. In the [[LLM Wiki Pattern]] the LLM does the synthesis once, when a source is ingested, and writes it into pages that link to each other; later questions read those pages. [[LLM Wiki]] puts it as "the wiki is a persistent, compounding artifact", and [[karpathy-llm-wiki README]] tabulates the trade: RAG suits broad retrieval across large corpora, the wiki suits knowledge that compounds, summaries and durable cross-links.[^llm-wiki][^kw-readme]

The wiki also changes who is accountable for a fact. A RAG answer is only as traceable as its retrieved chunks; a wiki page carries its sources, and with the [[Grounding Invariant]] every number, date and quote on it can be checked against a raw file that never changes. That is the part RAG cannot offer, because it keeps no curated intermediate layer.

The [[Open Knowledge Format]] does not change the workflow; it changes what a page says about itself. Each page records who generated it and when, who verified it, which sources it rests on with per-claim footnotes keyed to source ids, its lifecycle status, and an absolute stale_after instant. From those fields a reader derives a trust tier: unverified, machine-confirmed or human-reviewed.[^okf-spec] The wiki pattern on its own treats every page as equally trustworthy and has no expiry, so OKF supplies exactly the two signals a reader of an LLM-written wiki needs most: whether a human checked this, and whether it is still current.

The two ideas also disagree in places. The founding text recommends adding search tooling as the wiki grows; the karpathy-llm-wiki README builds none and prefers grep at the sizes it has seen. The README rejects per-page review dates; OKF makes stale_after first-class. Both disputes are recorded on the pages that hold the claims.

## Evidence
- [[LLM Wiki Pattern]]: the definition of the pattern and its contrast with RAG (unverified).
- [[LLM Wiki]]: the founding text, "persistent, compounding artifact" (unverified).
- [[karpathy-llm-wiki README]]: the RAG comparison table and the design boundaries (unverified).
- [[Open Knowledge Format]] and [[Open Knowledge Format Specification]]: the trust, provenance and lifecycle fields (unverified).
- [[Grounding Invariant]]: why wiki facts are checkable (unverified).

## Caveats
- Answered from wiki pages only; no raw file was read directly.
- Five of five cited pages are unverified at the time of filing.

## Sources
- [[LLM Wiki]]
- [[karpathy-llm-wiki README]]
- [[Open Knowledge Format Specification]]

[^llm-wiki]: LLM Wiki
[^kw-readme]: karpathy-llm-wiki README
[^okf-spec]: Open Knowledge Format Specification
