# Page skeletons

One skeleton per page type. Keep the section names exactly; omit a section that would be empty. Frontmatter values are plain strings; dates are `YYYY-MM-DD`. `generated.by` is `agent-wiki/<model-id>`. Stamp every page you write with `frontmatter.py stamp` instead of computing dates yourself.

Footnotes: a load-bearing claim ends with `[^id]` where `id` is a `sources[].id`; definitions `[^id]: <source title>` go at the very end of the page.

## Source (`wiki/sources/<Title>.md`, one per raw file)

```markdown
---
type: source
title: <Title, same as the raw file's title>
description: <one line: what the source is and its main point>
tags: [<vocabulary tags>]
created: <date>
generated:
  by: agent-wiki/<model-id>
  at: <date>
sources:
  - id: <short-id>
    page: "[[<Title>]]"
raw: raw/<Title>.md
raw_sha: <sha256 from rawhash.py hash>
disposition: new | update | disputed | no-material
author: <from the raw frontmatter, if known>
published: <YYYY-MM-DD, if known>
resource: <URL from the raw frontmatter>
ingested: <date>
---

# <Title>

## Summary
<Three to eight sentences. What the source says and why it matters for this wiki's lens.>

## Key claims
- <Claim, written as found.>[^<short-id>]
- <Claim with a number or date exactly as in the raw file.>[^<short-id>]

## Entities and concepts
- [[<Entity>]]: <how the source treats it>
- [[<Wanted Page>]]: <mentioned, no page yet>

## Notable quotes
> <Verbatim quote of fifteen or more characters, original language.>[^<short-id>]

## Assessment
<Credibility, gaps, what it contradicts or updates. Name disputed pages.>

[^<short-id>]: <Title>
```

A `no-material` source keeps Summary and Assessment (one line each) and nothing else.

## Entity (`wiki/entities/<Name>.md`)

```markdown
---
type: entity
title: <Name>
description: <one line>
aliases: [<synonyms, other spellings>]
tags: [<vocabulary tags>]
created: <date>
generated:
  by: agent-wiki/<model-id>
  at: <date>
sources:
  - id: <short-id>
    page: "[[<Source Title>]]"
---

# <Name>

## What it is
<Two to five sentences.>

## Key facts
- <Fact, as found.>[^<short-id>]

## Timeline
- <YYYY-MM-DD or YYYY-MM>: <event>[^<short-id>]

## Relationships
- [[<Other Entity>]]: <relation in one clause>

## Not to be confused with
- [[<Similar Thing>]]: <the difference in one sentence>

## Sources
- [[<Source Title>]]

[^<short-id>]: <Source Title>
```

## Concept (`wiki/concepts/<Name>.md`)

```markdown
---
type: concept
title: <Name>
description: <one line>
aliases: []
tags: [<vocabulary tags>]
created: <date>
generated:
  by: agent-wiki/<model-id>
  at: <date>
sources:
  - id: <short-id>
    page: "[[<Source Title>]]"
---

# <Name>

## Definition
<One paragraph. The wiki's working definition, attributed.>

## How sources treat it
- [[<Source Title>]]: <its take>[^<short-id>]

## Not to be confused with
- [[<Neighbour Concept>]]: <the difference>

## Open questions
- <What the sources leave unanswered.>

[^<short-id>]: <Source Title>
```

## Synthesis (`wiki/syntheses/<Topic>.md`; `Overview.md` is the hub)

```markdown
---
type: synthesis
title: <Topic>
description: <one line>
tags: [<vocabulary tags>]
created: <date>
generated:
  by: agent-wiki/<model-id>
  at: <date>
sources:
  - id: <short-id>
    page: "[[<Source Title>]]"
---

# <Topic>

## Thesis
<The current position, in a paragraph.>

## Evidence
- <Point, with links to pages and footnotes to sources.>

## Counter-evidence
- <Where sources push back.>

## Open questions
- <Open findings from lint and from queries land here.>

## Sources
- [[<Source Title>]]
```

## Analysis (`wiki/analyses/<Question as Title>.md`, a filed query answer)

```markdown
---
type: analysis
title: <Short title for the question>
description: <one line>
tags: [<vocabulary tags>]
created: <date>
generated:
  by: agent-wiki/<model-id>
  at: <date>
sources:
  - id: <short-id>
    page: "[[<Source Title>]]"
question: <The question as asked>
---

# <Short title>

## Question
<The question as asked.>

## Answer
<The answer, citing pages as [[Page]] and load-bearing claims with footnotes.>

## Evidence
- [[<Page>]]: <what it contributed> (<verified | unverified>)

## Caveats
- <Thin pages, gaps, or raw files consulted directly.>

## Sources
- [[<Source Title>]]
```

## Status blocks (any page, directly beneath the affected claim)

```markdown
> **Status: Disputed**
> [[Source A]] says <claim A>; [[Source B]] says <claim B>. Unresolved.

> **Status: Outdated** (YYYY-MM-DD)
> Superseded by [[Source C]]: <what replaced it>.
```

A page with a Disputed block sets `status: contested`. A page whose whole subject is superseded sets `status: deprecated` and adds a line `Superseded by [[Successor]].` under its first heading; the successor links back.
