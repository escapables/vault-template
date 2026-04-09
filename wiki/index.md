---
title: Wiki Index
tags: [meta, navigation]
---

# Wiki Index

This is the thin pointer index for the vault. It lists the domain manifests and global navigation files. It does NOT enumerate per-domain pages — the domain manifests own that.

## Domains

- **research** — see `wiki/research/_manifest.md`
- **projects** — see `wiki/projects/_manifest.md`

## Global navigation

- `wiki/overview.md` — top-level navigator with a one-sentence description per domain
- `wiki/log.md` — append-only chronological activity log
- `wiki/xrefs.json` — auto-generated wikilink graph (read with `python3` or grep)

## Adding a domain

1. Create `wiki/<name>/` with the four standard subdirectories: `sources/`, `entities/`, `concepts/`, `analyses/`
2. Write `wiki/<name>/_manifest.md` per [`SPEC.md` §4](../SPEC.md)
3. Add the qmd collection: `qmd collection add wiki/<name> --name vault-<name> --mask "**/*.md"`
4. Add the new domain to this index and to `overview.md`
