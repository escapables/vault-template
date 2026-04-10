---
title: "Example Source — Demonstrates the Frontmatter Contract"
updated: 2026-01-01
tags: [example, template, source]
summary: "A placeholder source page showing the required frontmatter fields and the structure agents should follow when filing new sources. Delete this file once you've ingested your first real source."
domain: research
source_url: "https://example.com/template-placeholder"
---

# Example Source — Demonstrates the Frontmatter Contract

This file exists to show the structure of a wiki page in the LLM Wiki template. It is safe to delete after your first real ingest.

*Unverified — placeholder content with no real source.*

## Why this file exists

Every source page in the wiki follows the same conventions:

1. **YAML frontmatter** with `title`, `updated`, `tags`, `summary`, `domain`, and exactly one of `source_file:` or `source_url:`
2. **`domain:` matches the parent directory** — this file lives in `wiki/research/sources/`, so `domain: research`. `scripts/check-frontmatter-domain.py` enforces this
3. **A `summary:` field** that's 1-2 sentences and gives an agent enough context to decide whether to read the body. This summary feeds the auto-generated registry block in `wiki/research/_manifest.md`
4. **Verification tier** in italics near the top — one of `*Verified against PDF*`, `*Verified against source code*`, or `*Unverified — fetched via web tool*`. The tier tells future-you and future-agents how much to trust the page's claims
5. **Wikilinks via slug only** — never include the path. Use the bare-slug form (e.g. the slug `other-page` wrapped in double brackets) instead of including the directory path. Renderers and search adapters should resolve by slug across the whole vault. Anti-pattern: prefixing the wikilink with `research/sources/` is wrong.
6. **Standard markdown** for everything else

## Sections you'll typically see

- **Summary of key points** — what the source actually says, in your words
- **Notable claims, data, quotes** — the pull-out quotes and numbers worth surfacing
- **Connections** — wikilinks to related entity, concept, and analysis pages

## Connections

When you create real entities and concepts, link to them here using bare-slug wikilinks (the slug wrapped in double brackets). Until then, this section is intentionally empty — `check-wikilinks.py` fails on speculative wikilinks even when written in code-spans, because the regex matches anywhere in a line.

The domain manifest is at `wiki/research/_manifest.md`.

## What to do next

1. Delete this file once you've ingested your first real source
2. Remove the placeholder example wikilinks above so `check-wikilinks.py` passes
3. Update `wiki/research/_manifest.md` with the actual scope, key facts, and open questions for your domain
4. Run `bash scripts/build-registry.sh research` to regenerate the manifest's auto-registry block
5. Refresh your configured search adapter if you enabled one; if using `qmd`, run `qmd update`, and run `qmd embed` only when vector search is explicitly enabled
