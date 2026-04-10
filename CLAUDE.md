# LLM Wiki - Agent Operating Notes

You maintain a personal knowledge wiki built on the LLM Wiki pattern. Your job: summarize, cross-reference, file, maintain. The human curates sources, asks questions, and decides ambiguous classification or domain splits.

This file is harness-agnostic despite its compatibility filename. Some agent harnesses auto-load `CLAUDE.md`; if yours uses `AGENTS.md`, `.cursor/rules`, a system prompt, a skill file, or another native rules file, mirror this content there. The portable contract is `PROGRAM.md`. `SPEC.md` documents architecture and invariants. `README.md` is the human introduction.

**Privacy notice**: this vault is git-versioned. Anything written into `wiki/` enters git history and remains recoverable even after deletion. If you push to a public remote, your wiki and its deleted versions are public. Keep `raw/` gitignored, think before pushing, and decide whether a topic belongs here before ingesting. History rewrites are messy; read GitHub's guidance on removing sensitive data before attempting one.

## Directory Structure

The wiki is physically partitioned by domain. Each domain owns its pages, manifest, and optional scoped search collection.

```text
Vault/
├── PROGRAM.md              # Portable build-and-operate contract
├── CLAUDE.md               # Harness-agnostic agent notes (compatibility filename)
├── SPEC.md                 # Architecture and numeric invariants
├── README.md               # Human intro
├── raw/                    # Sources (human-managed, gitignored)
│   ├── assets/             # Inbox: unprocessed
│   ├── attachments/        # Local images or extracted attachments
│   └── archived/           # Processed or skipped sources
├── scripts/                # Canonical verification and generation tools
├── .claude/skills/         # Optional adapter examples
├── .mcp.json               # Optional MCP adapter config
└── wiki/
    ├── index.md            # Thin pointer to domain manifests
    ├── overview.md         # One-line description per domain
    ├── log.md              # Reverse-chronological activity log
    ├── xrefs.json          # Auto-generated cross-reference map
    └── <domain>/
        ├── _manifest.md    # Prose + auto-generated registry
        ├── sources/
        ├── entities/
        ├── concepts/
        └── analyses/
```

The template ships with two placeholder domains, `research` and `projects`. Rename freely. Scripts auto-discover domains from immediate children of `wiki/`.

## Domain Rules

- Default to single-domain operations.
- Cross-domain reads or filings require explicit human opt-in.
- During routing/classification, read only each manifest's `summary:` line.
- After choosing a domain, read that domain's full `_manifest.md`.
- Cross-domain wikilinks are cheap; cross-domain page reads are not.
- Keep one canonical page per topic. Never duplicate across domains.
- Every page's `domain:` frontmatter must match its parent domain directory.
- Do not create `_meta`; cross-cutting topics live in their primary domain and are linked from anywhere.

## Page Rules

Required frontmatter on every wiki page:

- `title`
- `updated`
- `tags`
- `summary`
- `domain`

Source pages also need exactly one of:

- `source_file`
- `source_url`

Other page rules:

- filenames: lowercase, hyphenated
- wikilinks: slug-only `[[some-topic]]`, never path-form links
- keep `summary:` current; manifests and search workflows rely on it
- every page should have at least one inbound link from another page, manifest, or log
- unresolved future topics: use plain text or code span, not speculative `[[wikilink]]`

## Source Rules

- `raw/` is gitignored and human-managed.
- Do not edit source content during normal wiki maintenance.
- Allowed moves: `raw/assets/` to `raw/archived/` after processing or skipping.
- Allowed URL ingest exception: save a fetched URL as `raw/assets/YYYY-MM-DD-slug.md`, then ingest the local copy.
- For attachments, run `bash scripts/find-attachments.sh '<source-title-without-.md>'`; use single quotes.
- For PDFs, run `pdfinfo <file>` first; read at most 20 pages per chunk.

## Read Protocol

Manifest-first. Progressive disclosure. Token budget matters.

1. Discovery:
   - manifest registry
   - frontmatter summaries
   - scoped mechanical search such as `rg -n "<terms>" wiki/<domain>`
   - optional scoped index search such as `qmd search "<terms>" -c vault-<domain>`
   - `wiki/xrefs.json`
2. Structure:
   - headings
   - first lines of relevant sections
   - enough to choose an edit target
3. Full content:
   - only pages or sections being actively edited

Rules:

- read only manifest `summary:` lines to classify
- full-read only pages you are editing or directly citing
- prefer `wiki/xrefs.json` over brute-force grep for inbound/outbound checks
- for returning sessions, inspect recent git history before re-reading broad content
- keep `wiki/log.md` reverse-chronological; newest entries at the top

## Operation: Ingest

Use this for a new source in `raw/assets/` or for a URL the human asks you to file.

1. Locate source, or fetch URL into `raw/assets/YYYY-MM-DD-slug.md`.
2. Read source and relevant local attachments.
3. Classify via manifest `summary:` lines only.
4. Ask if ambiguous. Cross-domain only with explicit opt-in.
5. Load the chosen domain manifest.
6. Search overlap inside the chosen domain. Default to `rg`; use an optional scoped index only if configured.
7. Discuss durable takeaways with the human before filing when the source is substantial or ambiguous.
8. Create or update source/entity/concept/analysis pages in one primary domain.
9. Update manifest prose if new load-bearing facts entered the wiki; never hand-edit the registry block.
10. Run `bash scripts/build-registry.sh <domain>`.
11. Run `python3 scripts/build-xrefs.py`.
12. Prepend an entry to `wiki/log.md`.
13. Flag contradictions on both affected pages.
14. Verify touched pages: frontmatter, domain alignment, wikilinks, math, manifest budget.
15. If an index adapter is enabled, refresh it in the foreground. Never run embedding or reranking jobs in the background.
16. Archive processed or skipped sources from `raw/assets/` to `raw/archived/`.
17. Commit reviewable changes when the human asks or when the repo workflow expects ingest commits.

Skip and archive, with a log note, when the source is duplicate, derivative, SEO spam, too thin to support reusable facts, or too broad to connect cleanly to wiki themes. Multiple thin sources on the same event can merge into one source page.

## Operation: Query

Use this when the human asks a question that should be answered from wiki knowledge.

1. Route via manifest `summary:` lines only.
2. Load the chosen domain manifest.
3. Search with scoped mechanical search by default; use optional semantic search only if explicitly enabled.
4. Read via progressive disclosure.
5. Answer with `[[wikilink]]` citations.
6. Offer to file substantial reusable answers as `wiki/<domain>/analyses/<slug>.md`.
7. If filed, update manifest registry and prepend `wiki/log.md`.

## Operation: Health

Modes:

- `health <domain>`: deep per-domain contradictions, math, gaps, and research checks
- `health --structural`: cheap global lint and manifest pressure checks
- `health --domain-scan`: divergence scan only

There is no `health --all`. Full coverage means structural health plus one deep domain run per domain, separated to keep context and compute bounded.

Error propagation rule: after fixing a wrong value, grep the wiki for the old value. Expect propagation into source page, concept page, manifest, log, and related analyses.

## Verification Rules

- never do mental math; use Python or shell
- verify fetched claims; web summaries can drift
- X/Twitter/forum claims are low trust by default
- README claims are not code reality; verify important repository claims against source files or API shape
- after any page add/move/update that changes summaries, run `bash scripts/build-registry.sh <domain>`
- after broader content changes, run:
  - `python3 scripts/build-xrefs.py`
  - `python3 scripts/check-wikilinks.py`
  - `python3 scripts/check-frontmatter-domain.py`
  - `python3 scripts/detect-domain-divergence.py`
- if a search adapter is enabled, refresh it in the foreground
- never run embedding, reranking, or model-heavy jobs in the background

Use verification-level notes on source pages when relevant:

- `*Verified against PDF*`
- `*Verified against source code*`
- `*Unverified - synthesized from README/discussions*`

## Manifest Rules

Each domain `_manifest.md` is the load-bearing compression artifact.

Keep current:

- scope
- key facts
- open questions
- cross-domain links

Do not hand-edit:

- `<!-- REGISTRY:START ... REGISTRY:END -->`

Prose budget:

- warning around 2.5k tokens
- split candidate around 3k
- hard fail around 3.5k

Do not auto-split domains. Flag; the human decides.

## Contradictions and Canonicality

- if two pages cover the same primary artifact, merge or differentiate
- cross-domain near-duplicates are a hard smell
- update referring pages to match the canonical page; do not fork facts
- if a page cites a number whose primary topic belongs elsewhere, that primary page is authoritative

## Optional Search Adapter

Always scope search/query to one domain.

Reference commands when `qmd` is configured:

```bash
qmd search "query" -c vault-<domain>
qmd query "question" -c vault-<domain>
qmd update
qmd embed
```

Treat hybrid/vector/LLM-reranked search as opt-in. Warn first: it can load local models, use significant RAM, run slowly on CPU-only machines, and use GPU/VRAM if available.

## Git

- only the wiki layer is tracked; `raw/` is gitignored
- keep commits reviewable
- common messages:
  - `ingest: Source Title`
  - `query: Question summary`
  - `lint: Description`
- do not delete or rename unexpected files without human consent

## Batch Ingest

When ingesting multiple sources:

- group by domain first
- default to separate per-domain batches
- if multiple agents are explicitly in play, do not let them edit the same manifest or log file in parallel

Parallel-compatible work:

- create source/concept/entity pages
- keep write ownership disjoint

Serial consolidation:

1. update domain manifest prose if needed
2. run `bash scripts/build-registry.sh <domain>`
3. run `python3 scripts/build-xrefs.py`
4. prepend `wiki/log.md`
5. deduplicate overlapping concept/entity pages
6. archive processed sources
7. verify page counts against manifest `page_count`
8. refresh optional search adapter if enabled

## Customizing This File

After forking, extend with vault-specific rules in clearly marked sections at the bottom so this file stays diff-able against the upstream template.

Good local additions:

- routing rules for overlapping page roles
- project references to connected code repos, notebooks, or dashboards
- domain-specific verification rules
- cost rules for token, model, or compute budgets
