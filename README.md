# Vault — A Domain-Atomized LLM Wiki

A reference implementation of [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/3ae50c94fe5c72884137a38d5b81d5ff), extended with domain atomization, token-cost optimizations, and structural lint. The human curates sources; the LLM maintainer summarizes, cross-references, files, and lints.

This repo is a working **example layout**. The portable specification lives in [`PROGRAM.md`](PROGRAM.md) — a self-contained LLM prompt spec you can drop into any harness. Use this repo to see the structure in practice; use `PROGRAM.md` to actually adopt it. For the agent-facing schema, see [`CLAUDE.md`](CLAUDE.md). For architectural rationale, see [`SPEC.md`](SPEC.md).

## Why

Canonical LLM Wiki works at ~30-60 pages. Past that, per-session read cost grows roughly linearly with total page count — a 6-source ingest on a flat ~130-page wiki spends ~60% of its tokens reading existing state before writing anything. This layout drops per-ingest read cost by **~65-71%** at that scale by shifting cost from "scales with total wiki size" to "scales with the touched domain's size." Savings compound as the wiki grows.

## The Core Pattern

- **Domain partitioning.** `wiki/` is physically split by domain. Each domain owns its `_manifest.md`, its `{sources,entities,concepts,analyses}/` subdirs, and its qmd search collection. Cross-domain wikilinks resolve by slug and are cheap; cross-domain *ingests/queries* require explicit opt-in.
- **Manifest-first reading.** Each `_manifest.md` holds scope, key facts, open questions, cross-domain links, and an auto-generated registry of every page's one-sentence summary. The prose region is budgeted at ≤3,000 tokens. Classification reads only the `summary:` YAML line — full manifests load *after* a domain is chosen.
- **Progressive disclosure.** Three tiers: search results + registry summaries (discovery), section headings (structure), specific section (edit). Full-page reads happen only for pages being actively edited.
- **Precomputed `xrefs.json`.** Auto-generated map of inbound/outbound links, tags, and update dates. Look up connections here instead of grepping.
- **Page-level summaries.** Every page carries a mandatory `summary:` frontmatter field that feeds the manifest registry.
- **Log compaction.** `log.md` is reverse-chronological; entries older than 30 days move to `log-archive-YYYY.md` once the file exceeds ~300 lines.
- **Source verification tiers.** Every source page declares `*Verified against PDF*`, `*Verified against source code*`, or `*Unverified — fetched via WebFetch*`. WebFetch and social media fabricate.
- **No mental math.** Any number that enters the wiki is computed by Python/bash first, never by the LLM.
- **Phased batch ingest.** Parallel agents create source pages; a single serial pass updates shared files (manifest, log, registries).
- **Skip criteria.** Duplicate / derivative / SEO spam / too thin / too broad sources get archived with a log entry, not a wiki page.

The three operations — `/ingest`, `/query`, `/health` — all default to single-domain routing. See [`CLAUDE.md`](CLAUDE.md) and [`SPEC.md`](SPEC.md) for the full contracts.

## Directory Layout

```
Vault/
├── raw/                   # Immutable sources (gitignored)
│   ├── assets/            # Inbox — unprocessed
│   ├── attachments/       # Obsidian-extracted images
│   └── archived/          # Processed sources
├── wiki/                  # LLM-maintained markdown
│   ├── index.md           # Thin pointer → per-domain manifests
│   ├── overview.md        # One-sentence navigator per domain
│   ├── log.md             # Reverse-chronological activity log
│   ├── xrefs.json         # Precomputed cross-reference map
│   └── <domain>/
│       ├── _manifest.md   # Prose + auto-generated registry
│       ├── sources/
│       ├── entities/
│       ├── concepts/
│       └── analyses/
├── scripts/               # Lint + automation helpers
├── .claude/skills/        # ingest / query / health
├── .mcp.json              # MCP config (qmd search)
├── CLAUDE.md              # Agent-facing schema
├── SPEC.md                # Architecture source of truth
└── README.md              # This file
```

## Quickstart

1. Clone or fork this repo.
2. Read [`PROGRAM.md`](PROGRAM.md) for the portable spec, or [`CLAUDE.md`](CLAUDE.md) if you're using Claude Code.
3. Replace the example domains in `wiki/` with your own. Each domain needs a `_manifest.md` and the four standard subdirectories.
4. Drop sources into `raw/assets/` and invoke `/ingest` (or your harness's equivalent).
5. Keep the lint green:
   ```bash
   python3 scripts/check-wikilinks.py             # all [[slug]] refs resolve
   python3 scripts/check-frontmatter-domain.py    # domain: matches parent dir
   python3 scripts/detect-domain-divergence.py    # manifest budget + community detection
   bash   scripts/build-registry.sh <domain>      # regenerate manifest registry
   ```

## Portability

`PROGRAM.md`, `CLAUDE.md`, `SPEC.md`, `scripts/`, and the `wiki/` skeleton are harness-agnostic. The `.claude/skills/` directory uses the [agentskills.io](https://agentskills.io) open `SKILL.md` format, but its content references Claude Code tool names (`Read`, `Edit`, `Bash`, ...) — swap those for your harness's equivalents. Start from `PROGRAM.md` if you're adopting from a different harness.

## Files at the repo root

| File | Purpose |
|---|---|
| [`PROGRAM.md`](PROGRAM.md) | Portable, harness-agnostic spec. **Start here to adopt the pattern.** |
| [`CLAUDE.md`](CLAUDE.md) | Agent-facing operational schema for this layout (Claude Code specifics). |
| [`SPEC.md`](SPEC.md) | Architectural rationale and acceptance criteria. |
| [`README.md`](README.md) | This file. |
| `LICENSE` | MIT. |

## A Note on Privacy

This is a git-versioned vault. **Anything committed to `wiki/` enters git history and is recoverable even after deletion.** A public remote means public content *and* public history.

- `raw/` is gitignored — source documents stay local. Only `wiki/` is tracked.
- `.claude/settings.local.json` is gitignored too; it accumulates machine paths and personal project references. Generate your own.
- Think before pushing to a public remote. Research notes are often personal in ways that aren't obvious until they're indexed.
- Force-pushing to rewrite history is rarely clean: GitHub caches forks and PRs for days, mirrors may exist, pre-rewrite clones keep the old history. See [GitHub's docs on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) before attempting one.
- The split between a private working vault and a public template is intentional. Run your personal vault in a private repo; copy the schema and scripts out into a public repo (or fork this template) rather than sanitizing the private one retroactively.

## License

MIT — see [`LICENSE`](LICENSE). The schema, scripts, and structural patterns are published in case they're useful for other wikis hitting the same scaling wall. Content in a personal vault is personal research notes; this template ships with none.
