# Vault — A Domain-Atomized LLM Wiki

A personal knowledge wiki built on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f), reorganized around one question: **how do you keep per-session token cost flat as the wiki grows?**

A flat LLM wiki works beautifully up to ~30-60 pages. Past that, per-session read cost grows roughly linearly with total page count — a 6-source ingest on a flat ~130-page wiki spends ~60% of its tokens reading existing state before writing anything. This layout drops per-ingest read cost by **~65-71%** at that scale by making cost scale with the **touched domain** rather than the whole wiki. The savings compound as the wiki grows.

**This repo is a worked example.** The portable specification is [`PROGRAM.md`](PROGRAM.md) — a self-contained LLM prompt spec that takes an empty directory to a running vault. Use `PROGRAM.md` to adopt the pattern; use this repo to see what the result looks like.

---

## Token optimizations in this layout

Each of these is a separate lever. They compose.

### Currently implemented

- **Domain partitioning.** `wiki/` is physically split by domain (`wiki/<domain-a>/`, `wiki/<domain-b>/`, …). Each domain owns its own `_manifest.md`, its four subdirectories (`sources`, `entities`, `concepts`, `analyses`), and its search scope. Single-domain operations are the default; cross-domain is opt-in. A page in one domain linking `[[foo]]` to a page in another resolves automatically — slugs are global, but operation scope is not.

- **Scoped mechanical search by default.** Use `rg` or another scoped keyword search before reading page bodies. At low page counts, shell search is enough; around ~80 articles/pages, a scoped index such as `qmd search` usually starts paying for itself. Hybrid/vector search and LLM reranking stay opt-in because they can be slow and memory-heavy.

- **Manifest-first reading.** Each `_manifest.md` holds `Scope`, `Key facts`, `Open questions`, `Cross-domain links`, and an auto-generated registry listing every page's one-sentence summary. Reading the manifest alone is usually enough to decide what to search and what to load. Prose is budgeted at ≤ 3,000 tokens; exceeding the budget flags the domain as a split candidate.

- **Classification via `summary:` only.** During ingest and query, classification reads just the `summary:` YAML line of each manifest — **not** the full manifests. Loading a full wrong manifest wastes the entire context-savings point of the architecture.

- **Progressive disclosure (three tiers).**
  1. **Discovery** — search results + manifest registry + frontmatter `summary` fields. Most pages stop here.
  2. **Structure** — section headings + the first line of each section.
  3. **Full content** — only the specific section being edited.
  Full-page reads happen only for pages actively being edited.

- **Precomputed `xrefs.json`.** Auto-generated wikilink graph with every page's inbound and outbound links, tags, and updated date. Use this instead of grepping to answer "what connects to X".

- **Mandatory page-level `summary:`.** Every page carries a 1-2 sentence abstract that feeds the manifest registry. It is read far more often than the body.

- **Log compaction.** `log.md` is reverse-chronological (newest at top) and archives entries older than 30 days to `log-archive-YYYY.md` once it exceeds ~300 lines. Session-relevant history stays visible; long tail moves out of the hot read path.

- **Git-aware session start.** Returning sessions check `git log --oneline -10` and the diff since last time. Only pages that changed **and** are touched by the current task get re-read.

- **Phased batch ingest.** Parallel agents create source/concept/entity pages inside a single domain; a single serial pass updates shared files (manifest, log, registries). Last-writer-wins hazards on `_manifest.md` and `log.md` are structurally avoided instead of hoped against.

- **Verification discipline that prevents re-ingestion.** Every source page declares a tier (`*Verified against PDF*`, `*Verified against source code*`, `*Unverified — fetched via WebFetch*`, etc.). Low-trust pages get re-verified on demand; high-trust pages do not need to be re-read. **Never mental math** — any number that enters the wiki is computed by Python/bash first, not by the LLM.

- **Skip criteria.** Duplicate / derivative / SEO spam / too-thin / too-broad sources are archived with a log entry, not a wiki page. The wiki stays dense.

- **Structural lint as a read-cost tool.** `check-wikilinks.py`, `check-frontmatter-domain.py`, and `detect-domain-divergence.py` catch drift mechanically. Drift that becomes invisible becomes expensive — a broken wikilink survives in the graph, a mismatched `domain:` means a page gets re-read on every cross-domain op, a bloated manifest silently grows past its budget.

### Planned (see Roadmap below)

- **Derived analytics** — god nodes, cross-domain bridges, cluster summaries, stale load-bearing pages, suggested questions — computed from `xrefs.json` into each manifest (Phase 1)
- **Adapter reminders / hooks** — harness-native reminders or hooks that keep manifests, `xrefs.json`, and analytics current without making a specific harness part of the core spec (Phase 1)
- **File watcher** — debounced rebuilds on `wiki/` changes (Phase 2)
- **Multimodal pre-extraction** — LLM-vision pass on `raw/attachments/` images so figures become text-searchable (Phase 2)
- **Materialized views** — per-god-node aggregation files that answer dense in-domain queries with one read instead of fifteen (Phase 3)

---

## Getting started

**Initialization is done through [`PROGRAM.md`](PROGRAM.md), not by cloning this repo.** This repo is a reference example of what `PROGRAM.md` produces.

`PROGRAM.md` is a self-contained, harness-agnostic build program. Hand it to an LLM in any harness and it will:

1. Create the directory skeleton (`raw/`, `wiki/`, `scripts/`, `.gitignore`)
2. Write the global navigation files (`index.md`, `overview.md`, `log.md`, `xrefs.json`)
3. Ask you to name the first two domains
4. Write the manifest skeletons
5. Install the seven scripts (inlined verbatim in `PROGRAM.md` — no external downloads)
6. Verify the build with the structural lints
7. `git init` and make the first commit

After bootstrap, `PROGRAM.md` also specifies the three day-to-day operations (`ingest`, `query`, `health`), the page conventions, the context-cost rules, the invariants, and the domain evolution workflow (split / merge). A single LLM reading `PROGRAM.md` alone has everything it needs to build and run the wiki.

### If you want to fork this repo directly

Forking works too, but you are starting from a specific harness's conventions (Claude Code) rather than from the portable spec. Expect to:

1. Delete or rename the two placeholder domains in `wiki/`
2. Replace the manifest `summary:` lines with your own
3. Adjust `.claude/skills/` if you are using Claude Code, or delete it if you are not
4. Keep the lint green — `python3 scripts/check-wikilinks.py` and `python3 scripts/check-frontmatter-domain.py` should both return `OK`

---

## Roadmap

The token optimizations listed above are what's currently implemented. Three planned phases extend them, ordered roughly by payoff-over-effort.

### Phase 1 — Derived analytics + adapter automation

The biggest remaining gap is that the wiki computes nothing *about itself*. `xrefs.json` has every edge, but no script yet extracts the high-value signals from it. Phase 1 closes that with a portable analytics script; harness automation stays in adapters.

- **`scripts/build-analytics.py`** — consumes `xrefs.json` and writes a derived analytics block into each domain manifest (or a sibling `_analytics.md`) containing:
  - **God nodes** — top pages by inbound-link degree (the load-bearing pages you would protect from breaking)
  - **Cross-domain bridges** — pages with the most cross-domain wikilinks (surprising connections the wiki has learned)
  - **Cluster summaries** — Louvain community detection over the wikilink graph, top clusters per domain with their largest members
  - **Recently updated** — pages whose `updated:` frontmatter is within the last 14 days
  - **Stale load-bearing pages** — high-degree pages whose `updated:` is older than 90 days (potential rot)
  - **Suggested questions** — templated from the god nodes; gives fresh sessions a discoverability layer above the manifest
- **Harness adapter reminders** — Claude Code could use PreToolUse + SessionStart hooks; Codex or another harness should use its native reminder mechanism. The adapter-level goal is deterministic guidance like *"prefer scoped search over raw grep; manifests are the entry point"*.
- **Git hook adapter** — optional post-commit / post-checkout hooks can rebuild registries, `xrefs.json`, and analytics. Search-index refreshes are adapter-specific; heavy embedding/reranking jobs stay foreground-only and opt-in.

The three items compose: the analytics block lives in the manifest, harness reminders preload or point at the manifest, and optional git hooks keep generated files current.

### Phase 2 — Auto-sync + multimodal pre-extraction

Once Phase 1 is in place, two ingest-side improvements compound on it:

- **`scripts/watch-wiki.sh`** — long-running `inotifywait` watcher on `wiki/` that triggers debounced rebuilds of the registry, `xrefs.json`, and analytics on file changes. Search-index embedding runs on a conservative schedule (every ~30 minutes), not per-change, to avoid memory pressure.
- **`scripts/extract-images.py`** — walks `raw/attachments/`, runs each unprocessed image through an LLM vision pass (one-shot: *"describe the image, extract any data, extract any text"*), writes the result to a sibling `<image-stem>.description.md` with a SHA256 cache in frontmatter. Images become text-searchable and grep-able. Re-runs skip cached files by hash.

This closes the gap where figure-heavy sources (papers, diagrams, screenshots) are effectively invisible to the LLM unless it reads each image individually.

### Phase 3 — Materialized views (at scale)

At ~250+ pages, the largest remaining read cost is in-domain queries about dense topics — answering one question requires reading 10-15 related pages.

- **Per-god-node implementation views** — for each top-N god node, a regenerated sibling `<slug>.implementations.md` file aggregates its inbound pages with their frontmatter summaries. A query about a god-node topic reads one view file (~1,500 tokens) instead of 15+ individual page reads (~15,000+ tokens). Estimated 70-80% read cost reduction on dense in-domain queries.

Views must be regenerated reliably — stale views are worse than no views. Deferred until wiki size makes the manual-read cost painful; at smaller scales the complexity is not worth the savings.

### Deferred / optional

- **Confidence-tagged wikilinks** — mark inferred or unverified links; helps provenance tracking at 200+ pages
- **Cross-collection search wrapper** — one-shot search across multiple domain collections, useful when cross-domain queries become regular
- **Skip-list for derivative sources** — detect when a new source overlaps with an already-ingested one and surface existing coverage before re-reading
- **Opt-in hybrid-recall search for overlap and contradiction scans** — keep scoped mechanical search as the default (`rg` or `qmd search`). If the human explicitly enables hybrid/vector search, an adapter can use something like `qmd query --no-rerank` for ingest overlap and deep-health contradiction scans. Warn first: this mode can load local GGUF models, use significant RAM, run slowly on CPU-only machines, and use GPU/VRAM if available. The payoff is semantic recall for paraphrases and synonyms that BM25 can miss, but it is not part of the portable core path.

---

## Files at the repo root

| File | Purpose |
|---|---|
| [`PROGRAM.md`](PROGRAM.md) | Portable, harness-agnostic build-and-operate program. **Start here to adopt the pattern.** |
| [`CLAUDE.md`](CLAUDE.md) | Worked example of the operating schema translated into the Claude Code harness. |
| [`SPEC.md`](SPEC.md) | Architectural rationale and numeric invariants (budgets, thresholds). |
| [`README.md`](README.md) | This file. |
| `LICENSE` | MIT. |

## Directory layout

```
Vault/
├── raw/                   # Immutable sources (gitignored)
│   ├── assets/            # Inbox — unprocessed
│   ├── attachments/       # Locally-extracted images
│   └── archived/          # Processed sources
├── wiki/                  # LLM-maintained, git-tracked
│   ├── index.md           # Thin pointer → per-domain manifests
│   ├── overview.md        # One-sentence navigator per domain
│   ├── log.md             # Reverse-chronological activity log
│   ├── xrefs.json         # Precomputed wikilink graph
│   └── <domain>/
│       ├── _manifest.md   # Prose + auto-generated registry
│       ├── sources/
│       ├── entities/
│       ├── concepts/
│       └── analyses/
├── scripts/               # Lint + automation (all seven inlined in PROGRAM.md)
├── .claude/skills/        # Claude Code skill files (ingest / query / health)
├── PROGRAM.md             # Portable build-and-operate program
├── CLAUDE.md              # Harness-specific worked example
├── SPEC.md                # Architecture rationale
└── README.md
```

## A note on privacy

This is a git-versioned vault. **Anything committed to `wiki/` enters git history and is recoverable even after deletion.** A public remote means public content *and* public history.

- `raw/` is gitignored — source documents stay local. Only `wiki/` is tracked.
- `.claude/settings.local.json` is gitignored; it accumulates personal machine paths and project references. Generate your own.
- Think before pushing to a public remote. Research notes are often personal in ways that are not obvious until they are indexed.
- Force-pushing to rewrite history is rarely clean — GitHub caches forks and PRs for days, mirrors may exist, pre-rewrite clones keep the old history. See [GitHub's docs on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) before attempting one.
- The split between a private working vault and a public template is intentional. Run your personal vault in a private repo; copy the schema out into a public repo (or fork this template) rather than sanitizing the private one retroactively.

## License

MIT — see [`LICENSE`](LICENSE). The schema, scripts, and structural patterns are published in case they are useful for other wikis hitting the same scaling wall. Content in a personal vault is personal research notes; this template ships with none.
