---
type: source
title: Open Knowledge Format Specification
description: Version 0.2 of OKF, Google Cloud's format for agent-maintained knowledge as markdown with YAML frontmatter that makes provenance, trust, freshness, lifecycle and attestation first-class fields.
tags: [okf, docs]
created: 2026-09-02
generated:
  by: agent-wiki/claude-fable-5-1
  at: 2026-09-02
stale_after: 2026-12-01
sources:
  - id: okf-spec
    page: "[[Open Knowledge Format Specification]]"
raw: raw/Open Knowledge Format Specification.md
raw_sha: a928e2d362dc3b5d8e4d9e2c834f672aa7a289015428d776a3ebe149f9db6c6d
disposition: disputed
author: GoogleCloudPlatform
resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
ingested: 2026-09-02
---

# Open Knowledge Format Specification

## Summary
The self-contained specification of the [[Open Knowledge Format]], Version 0.2. A knowledge bundle is "a directory of markdown files with YAML frontmatter", distributed as a git repository, archive or subdirectory, with no schema registry and no required tooling. The spec's motivation is that knowledge corpora are increasingly written and maintained by agents, so a consumer needs first-class answers to five questions: provenance, trust, freshness, lifecycle and attestation. It standardises a small frontmatter vocabulary for those, keeps everything else to the producer, and closes with a worked income-statement example. It grew out of data catalogs, which shows in the attested-computation section. Disposition new for the concept page it mints, update for the [[Grounding Invariant]], and disputed because it clashes with [[karpathy-llm-wiki README]] on freshness dates and on its own maturity.

## Key claims
- Only one frontmatter key is required: type "is the only always-required key", and a concept carrying nothing else is fully conformant. Consumers must tolerate unknown types, unknown keys, missing optional fields and broken links.[^okf-spec]
- Provenance lives in a sources list whose entries carry a resource plus optional credibility signals (author, usage_count, last_modified). A per-claim attribution is a markdown footnote whose label is a source id, keyed rather than positional because "a positional index misattributes silently the moment the list is reordered".[^okf-spec]
- Trust separates generated (who wrote the content, with an at timestamp for the last meaningful change) from verified (who confirmed it, a list of by and at). Consumers derive a trust tier: unverified, machine-confirmed, or human-reviewed when a human: actor verified.[^okf-spec]
- Lifecycle is status (draft, stable, deprecated; absent means stable) and stale_after, an absolute instant that "keeps the staleness decision a plain comparison".[^okf-spec]
- Actors follow one convention: producer/version for agents and tools, human:id for people, process:id for automated processes.[^okf-spec]
- Broken links are not malformed: a link to a missing concept "may simply represent not-yet-written knowledge".[^okf-spec]
- index.md and log.md are reserved filenames at any level; index files list a directory for progressive disclosure, log files hold date-grouped entries newest first.[^okf-spec]
- An Attested Computation concept carries a sanctioned way to compute a value plus an executor and a deterministic attester; OKF records the computation and the means to check it, "it does not execute anything itself".[^okf-spec]
- Non-goals include "Defining a fixed taxonomy of concept types." and prescribing storage or query infrastructure.[^okf-spec]
- Version 0.2 supersedes v0.1 with two breaking changes, generated.at replacing timestamp and a sources list replacing a body citations section; everything else is additive.[^okf-spec]

## Entities and concepts
- [[Open Knowledge Format]]: the format this document specifies.
- [[Grounding Invariant]]: complemented by OKF's per-claim footnotes keyed to source ids.
- [[LLM Wiki Pattern]]: a workflow OKF could describe the pages of, but does not itself define.
- Mentioned without a page: Google Cloud, BigQuery, dbt, Looker, the reference agent and its bundles.

## Notable quotes
> a positional index misattributes silently the moment the list is reordered[^okf-spec]

## Assessment
A careful format specification that supplies exactly what the LLM wiki sources lack: who verified a page, when it expires, and how a single claim points at its source. It has no raw layer, so grounding cannot be checked against a preserved copy once a linked resource changes, and it has no model for two sources that disagree. Its verified field is self-declared by whoever writes the file, and it treats verification as independent of later edits, which is a hazard for agent-maintained pages. A third of the text covers attested SQL computations, which do not apply to a reading wiki.

[^okf-spec]: Open Knowledge Format Specification
