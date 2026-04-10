---
title: Wiki Log
tags: [meta]
---

# Wiki Log

Reverse-chronological record of wiki activity. New entries go at the **TOP**, immediately after the hint comment below, so the newest activity is always visible first.

When this file exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. The archive is still git-tracked and search-indexable if you use an index adapter.

<!-- grep "^## \[" log.md | head -5 -->

## [YYYY-MM-DD] template | Initial setup

Replace this entry with your first real ingest, query, or lint. Format:

```
## [YYYY-MM-DD] <operation> | <one-line summary>

Domain: <domain>. <Multi-line description of what was done, which pages were touched, what was decided.>

- Bullet points for individual changes
- Cross-references via [[wikilinks]]
- Verification results
```

Operations are typically one of: `ingest`, `query`, `lint`, `refactor`, `chore`.
