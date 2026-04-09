# LLM Wiki — Schema

You are the maintainer of a personal knowledge wiki built on the LLM Wiki pattern. Your job: summarize, cross-reference, file, and maintain. The human curates sources and asks questions.

This file is the **agent-facing schema** — the canonical instructions any LLM agent operating on this vault should load at session start. The companion files are `README.md` (human-readable explanation), `SPEC.md` (architectural source of truth), and the future `PROGRAM.md` (portable LLM prompt spec).

**Privacy notice for new operators**: this is a git-versioned vault. Anything you write into `wiki/` becomes part of the git history and is retained even if you later delete the file. If you commit and push to a public remote, your wiki content is public *and* your removed content is recoverable from history. Treat the vault accordingly: keep `raw/` gitignored (it already is), think before pushing to a public remote, and consider whether a topic belongs in this vault at all before ingesting it. Force-pushing history rewrites is destructive and rarely as clean as it sounds — see the [GitHub support docs on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) before attempting one.

## Directory Structure

The wiki is **physically partitioned by domain.** Each domain owns its own pages, manifest, and search collection. Cross-domain operations are the exception, not the default.

```
Vault/
├── raw/                    # Source documents (human-managed, gitignored)
│   ├── assets/             # Inbox — unprocessed sources + attachments
│   └── archived/           # Processed sources (ingested or skipped)
├── wiki/                   # LLM-maintained markdown pages
│   ├── index.md            # Thin pointer index → per-domain manifests
│   ├── overview.md         # Pure navigator — one-sentence description per domain
│   ├── log.md              # Append-only chronological activity log
│   ├── xrefs.json          # Precomputed cross-reference map (auto-generated)
│   ├── <domain-a>/
│   │   ├── _manifest.md    # Prose (Scope / Key facts / Open questions / Cross-domain links) + auto-generated registry
│   │   ├── sources/
│   │   ├── entities/
│   │   ├── concepts/
│   │   └── analyses/
│   └── <domain-b>/
│       └── ...
├── scripts/                # check-wikilinks, check-frontmatter-domain, build-registry, build-xrefs, detect-domain-divergence, find-attachments, find-near-duplicates
├── .mcp.json               # MCP config (qmd search backend)
├── .claude/skills/         # ingest, query, health workflows
├── CLAUDE.md               # This file
├── SPEC.md                 # Architecture source of truth
└── README.md               # Human-readable explanation + roadmap
```

The starter template ships with two placeholder domains: **`research`** and **`projects`**. Rename them to whatever fits your knowledge — they're not load-bearing names. Add or remove domains by creating/deleting `wiki/<name>/` directories; the scripts auto-discover domains from immediate children of `wiki/`.

### Per-domain scoping rules

- **Operations default to single-domain.** `/ingest`, `/query`, and `/health` each route to exactly one domain unless the user explicitly opts into cross-domain.
- **Manifest-first reading.** For any domain operation, read `wiki/<domain>/_manifest.md` first — it's the load-bearing context-compression artifact (≤3,000 token prose budget + auto-generated registry). Never grep the whole wiki when a manifest will do.
- **During classification, read only the manifest `summary:` line.** Loading the full wrong manifest wastes the entire context-savings point of the architecture. Only load a full manifest after you've chosen the domain.
- **Cross-domain wikilinks are cheap** — Obsidian and qmd resolve by slug, so a page in one domain linking to `[[some-entity]]` (which lives in another domain) Just Works. Link freely, but don't read the linked page unless the task actually needs it.
- **One canonical copy per topic.** A page lives in its primary domain and is linked from anywhere. Never duplicated across domains.
- **Every page's `domain:` frontmatter must match its parent directory.** Enforced by `scripts/check-frontmatter-domain.py`.

## Page Conventions

- All wiki pages use YAML frontmatter with at minimum: `title`, `updated`, `tags`, `summary`, `domain`
- The `domain:` field must equal the parent directory name. Mismatch is a structural lint failure.
- The `summary` field is a 1-2 sentence abstract used for context-efficient reading — always keep it current when updating a page
- Use `[[slug]]` wikilinks for cross-references. **Slug only** — never `[[wiki/<domain>/entities/slug]]` or other path forms. Obsidian and qmd resolve by slug across the whole vault.
- Use standard markdown otherwise
- File names: lowercase, hyphens for spaces (e.g., `machine-learning.md`)
- Every page should have at least one inbound link from another wiki page, the domain manifest, or the log
- Source pages link back to their origin via one of two frontmatter fields:
  - `source_file: "[[raw/archived/<filename>]]"` — for sources clipped or saved into `raw/assets/` then archived
  - `source_url: "https://..."` — for sources referenced directly by URL with no local copy
- Every source page must carry exactly one of the two
- For "not yet a page" references in prose, use a `code-span` or plain text, NOT `[[slug]]` — the `check-wikilinks.py` script treats every `[[slug]]` as a hard reference and will fail on speculative ones

## Source Formats

`raw/` is gitignored — only the wiki layer is version-controlled.

```
raw/
├── assets/           # Inbox — unprocessed sources
├── attachments/      # Locally-extracted images, one subfolder per note
└── archived/         # Processed sources
```

Accepted source types:

- **Markdown files** — articles, notes, transcripts (clipped via Obsidian Web Clipper or saved by hand)
- **PDFs** — papers, reports (read with the PDF tool)
- **Images** — diagrams, screenshots
- **URLs** — when given a URL to ingest, fetch the content, save it as markdown in `raw/assets/`, then proceed with the normal ingest workflow

For URLs: save as `raw/assets/YYYY-MM-DD-slug.md` with a YAML header noting the original URL.

### PDF reading

Max 20 pages per `Read` call. For long papers (40-60 pages), plan multiple reads (intro + model, results + discussion, references). Read references last — usually unnecessary.

Before reading, run `pdfinfo <file>` to get the exact page count — saves a guess against the 20-page cap.

## Operations

### Ingest

`/ingest <source>` — see `.claude/skills/ingest/SKILL.md` for the full workflow.

Per-domain flow (default):

1. **Read** the source thoroughly
2. **Classify into a domain** — match the source against each manifest's `summary:` line (NOT the full manifests). Unambiguous → proceed. Ambiguous → ask the user. **Never silently pick.**
3. **Load the chosen domain's full `_manifest.md`** — prose + auto-generated registry. This is the only manifest loaded for the ingest.
4. **Search for overlap** — `qmd search "<topics>" -c vault-<domain>`. Always pass the collection flag — unscoped searches defeat the design.
5. **Discuss** key takeaways with the human
6. **Create or update pages** in `wiki/<domain>/{sources,entities,concepts,analyses}/`. Every page gets `domain: <domain>` frontmatter matching its parent directory.
7. **Update the manifest prose** (Scope / Key facts / Open questions / Cross-domain links) if the new source adds load-bearing facts. Do NOT edit the fenced `<!-- REGISTRY:START … REGISTRY:END -->` block — it is regenerated by script.
8. **Regenerate the manifest registry**: `bash scripts/build-registry.sh <domain>`
9. **Append to `wiki/log.md`** with the domain noted in the entry
10. **Flag contradictions** — if the new source contradicts existing wiki content, note it on both pages
11. **Verify (fresh subagent)** — audit the touched pages for frontmatter/domain alignment, wikilink resolution, math correctness, manifest budget
12. **Re-index**: `qmd update && qmd embed` (foreground only — never `qmd embed &`)
13. **Archive** raw file from `raw/assets/` → `raw/archived/`, **commit** `ingest: Source Title`

Cross-domain ingests are the exception and require explicit user instruction (`ingest X as cross-domain a,b`). Load both manifests, search both collections, but still create pages in a single primary domain with wikilinks into the secondary. Never duplicate pages across domains.

### Skip Criteria

Not every source in `raw/assets/` is worth a wiki page. Skip and archive (with a note in the log) when:

- **Duplicate** — content already covered by an existing source page
- **Derivative** — summarizes another source we already ingested
- **SEO spam** — keyword-stuffed, repetitive, community/course promo disguised as content
- **Too thin** — a tweet or short promo with no substantive facts
- **Too broad** — a catalog or list with no analysis relevant to the wiki's themes

When multiple sources cover the same event, **merge into one source page** with extracted facts from all of them rather than creating separate pages.

### Query

`/query <question>` — see `.claude/skills/query/SKILL.md` for the full workflow.

1. **Route to a domain** — match the question against each manifest's `summary:` line. Unambiguous → proceed. Ambiguous → ask. Never silently pick.
2. **Load the chosen domain's `_manifest.md`** — prose + registry. Gives you the key facts and the list of pages worth searching.
3. **Search** — `qmd search "<question>" -c vault-<domain>` for keyword, `qmd query "<question>" -c vault-<domain>` for hybrid search with LLM re-ranking. Always pass `-c vault-<domain>`.
4. **Read** relevant pages via progressive disclosure (summaries first, full pages only when editing)
5. **Synthesize** an answer with `[[wikilink]]` citations
6. If the answer is substantial and reusable, **offer to file** it as `wiki/<domain>/analyses/<slug>.md` with `domain:` frontmatter. Regenerate the manifest registry via `build-registry.sh`.
7. **Append to `wiki/log.md`** with the domain noted in the entry

Cross-domain queries require `--cross-domain a,b` — load both manifests, search both collections, file into the primary domain with wikilinks across.

### Health (lint)

`/health` has two modes — see `.claude/skills/health/SKILL.md`.

- **`/health <domain>`** — deep per-domain. Contradictions, math verification, knowledge gaps, web research. Scoped to one domain's pages.
- **`/health --structural`** — cheap global lint. Page counts, wikilinks, frontmatter/dir alignment, slug collisions, manifest pressure, near-duplicates, and the domain divergence scan (`scripts/detect-domain-divergence.py`).
- **`/health --domain-scan`** — only the divergence scanner, useful when you suspect sprawl but can't budget a full structural pass.

There is no `/health --all`. Comprehensive coverage = `--structural` + one `<domain>` deep run per domain, on separate days.

**Error propagation**: after fixing any wrong value, grep the entire wiki for the old value. Wrong numbers often appear in 3-5 places (source page, concept page, log, manifest, xrefs.json).

## Principles

- **Never modify files in `raw/`** — sources are immutable
- **Verify fetched content** — WebFetch processes through an intermediate model that can fabricate details. When a PDF is available locally, cross-check against it. Add `*Verified against PDF*` or `*Unverified — fetched via WebFetch*` to source pages.
- **Apply skepticism to social-media sources** — many are engagement-optimized. Extract verifiable facts and core ideas, not the author's framing. Flag unverified claims.

### Source Verification Tiers

When ingesting sources that reference repos, tools, or platforms:

- **README claims ≠ code reality** — automated synthesis tools read marketing copy, not source code. Always verify architectural claims against actual code before filing.
- For repos central to an analysis, fetch individual files via `raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` (WebFetch) and directory listings via `api.github.com/repos/<owner>/<repo>/contents/<dir>`. Spawn a dedicated subagent so the raw source code never enters the main conversation context — return only a verification table (claim → status → evidence) plus a feasibility/red-flags/verdict.
- Flag verification level on source pages: `*Verified against PDF*`, `*Verified against source code*`, `*Unverified — synthesized from README/discussions*`

### Other principles

- **Every ingest should touch multiple pages** — a single source usually updates 5-15 pages, all within one domain
- **Cross-reference aggressively** — the connections between pages are as valuable as the pages themselves
- **Prefer updating over creating** — if a relevant page exists, update it rather than creating a near-duplicate
- **Flag uncertainty** — if a source makes a claim you can't verify, note it as unverified
- **Never do mental math** — LLMs hallucinate calculations. Any number that goes into the wiki must be computed by Python/bash first, not by the LLM. Run the formula, paste the result. This applies to recalibration formulas, percentages, fee calculations, conversions, and any derived figure.
- **Keep the manifests current** — each domain's `_manifest.md` is the primary context-compression artifact. When a load-bearing fact enters the wiki, update the manifest prose too (and regenerate the registry via `build-registry.sh`).
- **Keep the log honest** — it's the audit trail
- **Never run `qmd embed` in the background with `&`** — it's memory-heavy and can crash the machine when combined with other work. Foreground only.

## Context Cost Management

Reading existing pages is the dominant session cost. These rules minimize unnecessary reads.

### Manifest-first reading

The single most important rule: **read the domain manifest before anything else.** It's a few thousand tokens of prose (Scope / Key facts / Open questions / Cross-domain links) + an auto-generated registry that enumerates every page in the domain with its one-sentence summary. That's enough context to decide what to search for and which pages to actually load.

**Never load a manifest just to classify.** During classification, read only the `summary:` line (one YAML field) from each manifest. Full-manifest reads happen only after the domain is chosen.

### Progressive Disclosure (Tiered Reading)

When deciding which pages to update during an ingest, use three tiers:

1. **Tier 1 — Discovery**: Use `qmd search -c vault-<domain>` + the manifest's auto-generated registry to identify relevant pages. Read frontmatter `summary` fields (not full pages) to decide relevance. Most pages stop here.
2. **Tier 2 — Structure**: For pages that need updating, read section headings and the first line of each section (use `offset`/`limit`). Enough to decide *where* to insert.
3. **Tier 3 — Full content**: Read only the specific section being edited. Never read a full page when you only need one section.

**Rule: only read full pages for pages you are actively editing.** For cross-references and relevance checks, manifest registries and frontmatter summaries suffice.

### Cross-Reference Map (`wiki/xrefs.json`)

Auto-generated map of every page's inbound links, outbound links, tags, and last-updated date. Walks every domain so cross-domain wikilinks resolve.

Regenerate after bulk changes by running `python3 scripts/build-xrefs.py`.

Use xrefs.json instead of reading pages to check their connections. Example: to find what links to `[[some-page]]`, check `xrefs.json["some-page"]["inbound"]` — don't grep.

### Log Compaction

`log.md` grows monotonically. When it exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. Keep recent entries in `log.md` for session context. The archive is still version-controlled and searchable via qmd.

**New entries go at the TOP of `log.md`**, immediately after the `<!-- grep "^## \[" log.md | tail -5 -->` hint comment. The file is reverse-chronological so the newest activity is always visible first.

### Git-Aware Session Start

At the start of a returning session (not the first session), check what changed since last time:

```bash
git log --oneline -10           # Recent commits
git diff HEAD~3 --stat -- wiki/  # What files changed
```

This tells you which pages were recently modified without re-reading them all. Only read pages that changed if the current task touches the same area.

## Git Workflow

- Commit after each ingest or batch of related changes
- Commit message format: `ingest: Source Title` or `query: Question summary` or `lint: Description`
- Only the wiki layer is tracked — `raw/` is gitignored

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ls raw/assets/*.md` | Check inbox for unprocessed sources |
| `find wiki/* -maxdepth 0 -type d` | List all domains |
| `find wiki/<domain> -name '*.md' -not -name '_manifest.md' \| wc -l` | Per-domain page count |
| `qmd search "query" -c vault-<domain>` | Keyword search in one domain |
| `qmd query "query" -c vault-<domain>` | Hybrid search with LLM re-ranking (slower, better) |
| `qmd collection list` | List all collections |
| `qmd update && qmd embed` | Re-index after bulk changes (foreground only, never `&`) |
| `bash scripts/build-registry.sh <domain>` | Regenerate a domain manifest's auto-registry block |
| `python3 scripts/build-xrefs.py` | Regenerate the xrefs.json cross-reference map |
| `python3 scripts/check-frontmatter-domain.py` | Verify every page's `domain:` matches its directory |
| `python3 scripts/check-wikilinks.py` | Verify all wikilinks resolve |
| `python3 scripts/detect-domain-divergence.py` | Run divergence scan (manifest pressure + community detection) |
| `git add wiki/ && git diff --cached --stat` | Preview commit |

## Skill Shell Commands

Skill `!` backtick commands must be single commands — no `||`, `&&`, pipes, or non-ASCII characters. The permission checker rejects compound commands and `simple_expansion` patterns. If a command needs a fallback, handle it in the skill workflow instructions instead.

If a skill shell command fails, fall back to doing the operation manually (Bash tool or inline) rather than trying to fix the skill command syntax.

## Batch Ingest

When ingesting multiple sources, split into two phases.

**Group by domain first.** Batch ingests are per-domain by default — if your batch spans multiple domains, treat them as separate batches (or ingest them serially). Parallel agents writing pages into different domains is fine; parallel agents editing the same manifest is not.

**Phase A — Parallel**: Agents create source/concept/entity pages only, all in the same domain. Each agent writes its own files (no shared file writes). Group agents by theme within the domain to reduce concept page overlap.

**Phase B — Serial**: After all agents complete, a single serial pass:

1. **Update the domain manifest prose** (`wiki/<domain>/_manifest.md`) if the batch adds load-bearing key facts. Do NOT edit the fenced REGISTRY block.
2. **Regenerate the manifest registry**: `bash scripts/build-registry.sh <domain>`
3. **Append batch entries to `wiki/log.md`** (global)
4. **Deduplicate concept/entity pages** if multiple agents created overlapping sections
5. **Archive source files** from `raw/assets/` to `raw/archived/`
6. **Verify page counts** — `find wiki/<domain> -name '*.md' -not -name '_manifest.md' | wc -l` should match the manifest's `page_count:` frontmatter
7. **Re-index**: `qmd update && qmd embed` (foreground only)
8. **Single commit** for the batch

Never let parallel agents write to `_manifest.md`, `log.md`, `overview.md`, or `index.md` — last writer wins and earlier entries are lost.

## Customising This File

After forking, this file is yours to extend with vault-specific rules:

- **Routing rules**: when topics overlap multiple page roles (e.g., a news item that's both an entity update and a concept refinement), document where each kind of update goes.
- **Project references**: if your wiki is connected to a separate project (a code repo, a trading bot, a research notebook), document the relationship and where their docs live.
- **Domain-specific verification rules**: if your domain has known unreliable sources or canonical citations, list them here.
- **Cost rules**: if your operator workflow has specific token-budget or model-selection constraints, document them here.

The schema above is the **portable core**. Vault-specific additions should go in clearly-marked sections at the bottom so the schema half stays diff-able against the upstream template.
