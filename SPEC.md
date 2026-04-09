---
title: "LLM Wiki Template — Domain-Atomized Architecture (Spec)"
status: template
---

# LLM Wiki Template — Domain-Atomized Architecture

This is the architectural source of truth for the template. It documents the invariants, the file layout, and the enforcement rules. `CLAUDE.md` is the agent-facing operational schema; this file is the formal spec that explains *why* the schema is shaped the way it is.

## 1. Objective

Restructure the canonical [LLM Wiki](https://gist.github.com/karpathy/3ae50c94fe5c72884137a38d5b81d5ff) pattern from a single flat namespace into **physically separated per-domain directories**, each with its own search collection, manifest file, and scoped operations. Eliminate the "honor system" where agents are told not to read across topics but mechanically can. After setup, an ingest, query, or health check defaults to a single domain unless the user explicitly opts into a cross-domain operation.

### Why domain atomization

- The flat layout works at small scale (~30-60 pages). Past that, per-session reading cost grows roughly linearly with total page count even when most pages are irrelevant to the current task.
- Per-domain manifests are load-bearing context-compression artifacts: a single ~1,500-3,000 token file that captures the load-bearing knowledge for any operation in that domain.
- Physical separation is enforced mechanically (`scripts/check-frontmatter-domain.py`), not just by skill-prompt discipline. New agents and subagents cannot bypass it accidentally.

### Success criteria for any deployment

1. Every wiki page lives in exactly one domain directory.
2. Per-domain `qmd` collections exist and `qmd search/vsearch/query -c vault-<domain>` returns only that domain's pages.
3. `/ingest` defaults to single-domain operation, reading only the target domain's manifest before classification and overlap-search.
4. `/health <domain>` runs deep checks (contradictions, math, gaps, near-duplicates) over a single domain; `/health --structural` runs cheap global checks (broken wikilinks, page counts, frontmatter alignment, slug collisions, manifest pressure, near-duplicates, divergence).
5. `/query` asks for a domain when ambiguous, supports `--cross-domain a,b` for explicit multi-domain runs, and reads each manifest before searching.
6. All wikilinks resolve via slug-based resolution. Cross-domain wikilinks Just Work — Obsidian and qmd resolve by basename slug across the whole vault.
7. The total context cost of an average ingest scales with the **touched domain's** page count, not the total wiki's page count.

---

## 2. Domain Definitions

The template ships with two placeholder domains: **`research`** and **`projects`**. They are starter examples — rename, replace, or split them to fit your knowledge.

- **`research`** — pages capturing what you've learned from external sources: papers, articles, talks, reference docs.
- **`projects`** — pages capturing what you're building, deciding, or operating: ongoing work, decisions, post-mortems.

Two starting domains is the minimum that makes the architecture meaningful. Start small. Sub-domains should emerge organically as the wiki grows and the divergence scanner (§9) flags real clusters within an existing domain.

**No `_meta` directory.** Cross-cutting topics live in their primary domain and are linked from anywhere via wikilinks (the Wikipedia model — one canonical entry per topic).

### Adding a new domain

1. Create `wiki/<name>/` with the four standard subdirectories: `sources/`, `entities/`, `concepts/`, `analyses/`
2. Write `wiki/<name>/_manifest.md` per §4 (frontmatter, prose sections, empty registry block)
3. Create the qmd collection: `qmd collection add wiki/<name> --name vault-<name> --mask "**/*.md"`
4. Run `qmd update && qmd embed` (foreground only)
5. Update `wiki/index.md` and `wiki/overview.md` to list the new domain
6. The scripts (`build-xrefs.py`, `check-frontmatter-domain.py`, `find-near-duplicates.sh`) auto-discover domains from `wiki/` immediate children — no script edit required

### Removing a domain

1. Move its pages into another domain (one canonical copy per topic), or delete them
2. Delete `wiki/<name>/`
3. Drop the qmd collection: `qmd collection remove vault-<name>`
4. Run `qmd update`
5. Run `python3 scripts/check-wikilinks.py` to confirm nothing pointed at the removed pages

---

## 3. Directory Structure

```
Vault/
├── CLAUDE.md                  # Agent-facing schema (operational)
├── SPEC.md                    # This file (architectural)
├── README.md                  # Human-readable explanation + roadmap
├── raw/                       # Source documents (gitignored)
│   ├── assets/                # Inbox
│   ├── attachments/           # Locally-extracted images
│   └── archived/              # Processed sources
├── scripts/                   # Lint, build, and helper scripts
├── .claude/skills/            # ingest, query, health, review-analysis
├── .mcp.json                  # MCP config (qmd)
├── .gitignore
└── wiki/
    ├── index.md               # GLOBAL: thin pointer index to domain manifests
    ├── overview.md            # GLOBAL: pure navigator (no page enumeration)
    ├── log.md                 # GLOBAL: chronological activity log
    ├── log-archive/           # GLOBAL: compacted old log entries (after 30 days)
    ├── xrefs.json             # GLOBAL: auto-generated wikilink graph
    └── <domain>/
        ├── _manifest.md       # Prose + auto-generated registry
        ├── sources/
        ├── entities/
        ├── concepts/
        └── analyses/
```

**`overview.md` is a pure navigator** — no page enumeration, no key facts, no numbers. The content ceiling is: domain name, one-sentence domain description, manifest link. Anything richer belongs in a manifest. This boundary exists to prevent `overview.md` from re-accumulating page-level detail that the manifests are supposed to own.

**`index.md` is a thin pointer index** listing the domain manifests and any global navigation files. It does not enumerate per-domain pages.

---

## 4. The Domain Manifest (`_manifest.md`)

Each domain's `_manifest.md` is the **only file an agent should need** to understand the domain at a glance. It is the load-bearing context-compression artifact of this whole architecture.

### 4.1 Required frontmatter

```yaml
---
title: "<Domain Name> — Manifest"
domain: <domain-slug>
updated: YYYY-MM-DD
page_count: N
tags: [meta, manifest, <domain-slug>]
summary: "One sentence: what this domain covers and what kind of question routes here."
depends_on: [<other-domain>, ...]   # Domains routinely cross-referenced from this one
pinned: false                        # If true, suppresses §9.6 merge-candidate flagging
---
```

### 4.2 Required sections (prose — human-maintained)

These sections are written by the agent during ingest and by the human during curation. They are subject to the token budget in §4.4.

1. **Scope** — 2-3 paragraphs. What's in, what's out. Boundary cases.
2. **Key facts** — bullet list of the highest-leverage findings. Numbers must be authoritative; cite the page they come from.
3. **Open questions** — known unknowns specific to this domain.
4. **Cross-domain links** — explicit list of pages in OTHER domains that this domain commonly references.

### 4.3 Page registry (auto-generated, unbudgeted)

The page registry is **NOT part of the prose manifest**. It is generated by `scripts/build-registry.sh <domain>` which scans every page in the domain, reads its `title` and `summary` frontmatter, and emits a formatted list at the bottom of `_manifest.md` inside a fenced region:

```
<!-- REGISTRY:START (auto-generated, do not edit by hand) -->
### Entities
- `[[entity-slug]]` — one-sentence summary from frontmatter
...
### Concepts
...
### Analyses
...
### Sources
...
<!-- REGISTRY:END -->
```

Rules:

- The registry region is **re-generated on every ingest or `/health` run** — manual edits inside the fenced region are discarded
- The registry **does NOT count against the 3K-token budget** in §4.4 — only the prose above the `REGISTRY:START` marker is budgeted
- Entries are sorted alphabetically within each subsection
- The script uses ONLY the `title` and `summary` frontmatter fields — no page-body scanning, so regeneration is fast

### 4.4 Token budget (prose only)

Target: the prose sections (§4.2) stay under **~3,000 tokens combined**. The registry (§4.3) is exempt.

**Measurement methods**:

- Quick: `wc -w <manifest>` for the prose region × 0.75 (rough word-to-token conversion)
- Precise: `python3 -c 'import tiktoken; enc = tiktoken.get_encoding("cl100k_base"); print(len(enc.encode(open("<manifest>").read().split("<!-- REGISTRY:START")[0])))'`

If prose grows beyond the budget, the domain is too large and should be split (see §9). The 3K limit is a heuristic — the underlying constraint is "an agent can hold this in working memory before doing anything else."

---

## 5. Skill / Tooling Changes

### 5.1 `/ingest`

**Behavior**: required argument is `<source>` AND inferred-or-asked `domain`. The skill:

1. Locates the source
2. Reads the source thoroughly
3. **Classifies into a domain.** Read ONLY the `summary:` frontmatter line from each domain's manifest (just the YAML field — typically ~30 tokens per domain). Match the source against those summaries:
   - If exactly one summary obviously fits, proceed to that domain
   - If neither fits or both fit, ask the user with a two-option choice. Do NOT silently pick
   - **Never load the full manifest just for classification.** That defeats the cost savings
4. **Load the chosen domain's full `_manifest.md`** (~2-3K tokens of prose + auto-generated registry)
5. Runs `qmd search "<topics>" -c vault-<domain>` for overlap detection
6. Creates pages in `wiki/<domain>/{sources,entities,concepts,analyses}/`
7. Updates the prose sections of `wiki/<domain>/_manifest.md` if the new source adds load-bearing key facts. The auto-generated registry block is regenerated by the registry script — not edited by hand
8. Updates `wiki/log.md` (stays global)
9. Verification subagent
10. Archive + commit

**Cross-domain ingests** require explicit user instruction. Default is single-domain. The cross-domain path loads both manifests and creates pages in the user-specified primary domain, with explicit cross-references to the secondary.

### 5.2 `/health`

Two modes:

**`/health <domain>`** — deep per-domain check. Runs contradictions, math, gaps, verification subagent, and web research scoped to one domain. Phase 1 structural lint runs only on the domain's pages.

**`/health --structural`** — cheap global lint:

- Page count consistency (manifests vs reality)
- Broken wikilinks (cross-domain links must resolve)
- Orphan pages (no inbound links from anywhere except indexes/log)
- **Slug collision check** — `find wiki/* -name '*.md' -exec basename {} .md \; | sort | uniq -d` must return empty. Two pages sharing a slug breaks wikilink resolution
- **Frontmatter/directory match** — every page's `domain:` frontmatter must equal the domain directory it lives in. Mismatch is a fail
- Near-duplicate scan
- **Domain divergence scan** (see §9) — runs both manifest-pressure check and graph community detection and reports any split candidates

There is **no `/health --all`**. Comprehensive coverage = `/health --structural` + one `/health <domain>` per domain, scheduled on different days.

### 5.3 `/query`

1. If the query is unambiguous to one domain, route there directly
2. If ambiguous, ask the user which domain (or "cross-domain")
3. For single-domain: read that manifest, then `qmd search/vsearch -c vault-<domain>`, then synthesize
4. For cross-domain: read all relevant manifests first, then search each domain's collection, then synthesize. Higher context cost — only use when necessary

### 5.4 `qmd` collections

After setting up a domain:

```bash
qmd collection add wiki/<domain> --name vault-<domain> --mask "**/*.md"
```

The `qmd update && qmd embed` workflow runs against all collections in one invocation. The `wiki/index.md`, `wiki/overview.md`, `wiki/log.md` files at the global root are NOT in any collection (they're navigation, not content).

### 5.5 `xrefs.json`

Regenerated globally across all domain directories. The wikilink graph crosses domains by design — a page in one domain wikilinking to `[[some-entity]]` (which lives in another) should resolve. The xrefs generation script walks all domain directories under `wiki/` (auto-discovered).

### 5.6 `find-near-duplicates.sh`

Already global. Scans all domains by default. Domain list is auto-discovered.

---

## 6. Doc Style

### 6.1 Frontmatter

Every page MUST have `domain:` frontmatter matching the directory it lives in. Mismatch is a structural lint failure.

### 6.2 Wikilinks across domains

Use the same `[[slug]]` syntax. Obsidian and qmd resolve by slug, not path, so cross-domain links Just Work. Do **not** include the path in the wikilink (i.e., `[[some-entity]]`, not `[[research/entities/some-entity]]`).

### 6.3 Cross-domain cross-references

When a page in one domain references a page in another, the link is treated as a "soft" reference — the linked page is the canonical source of truth, and the referring page should not duplicate detail.

---

## 7. Validation / Acceptance Criteria

After setup:

1. **Both domain dirs exist**, each with `_manifest.md` and the four standard subdirectories
2. **Page counts add up**: every domain manifest's `page_count:` frontmatter matches `find wiki/<domain> -name '*.md' -not -name '_manifest.md' | wc -l`
3. **All wikilinks resolve**: `python3 scripts/check-wikilinks.py` returns clean
4. **No slug collisions**: `find wiki/*/  -name '*.md' -exec basename {} .md \; | sort | uniq -d` returns empty
5. **Frontmatter matches directory**: `python3 scripts/check-frontmatter-domain.py` returns clean
6. **All qmd collections exist and are queryable**: `qmd collection list` shows one per domain
7. **Each manifest's prose region is under the 3K-token budget**
8. **`/health --structural` passes globally**
9. **`/health <domain>` runs cleanly for each domain**
10. **`/ingest` of a test source routes correctly to a single domain** and updates only that domain's manifest

---

## 8. Boundaries

### Always do

- **Maintain wikilink-by-slug semantics.** Never include domain paths in wikilinks. The slug is the contract.
- **Update the relevant manifest after every ingest.** If a manifest goes stale, the entire architecture's value collapses.
- **Scope operations to one domain by default.** The default IS the constraint; cross-domain is the exception.
- **Re-run `qmd update && qmd embed` after every batch of file moves.**
- **Keep `_manifest.md` prose under 3K tokens.** If it grows past that, the domain is too large — see §9 for the split workflow.
- **Use `git mv` for page relocations**, not `rm` + `write`. Git history follows the file across moves only when `git mv` is used.

### Ask first before

- **Splitting a domain.** Domain count is a load-bearing decision; never change it without confirmation, even when the divergence scanner has flagged it. The scanner suggests; the user decides.
- **Merging a domain** into another. Same rule.
- **Moving a page from one domain to another** after the initial setup. Wikilinks still resolve (slug-based), but the page's inclusion in its new domain's manifest must be reconciled.
- **Adding a new domain.**
- **Removing or renaming a manifest.** It's the canonical entry point for a domain.

### Never

- **Create a `_meta` directory.** Cross-cutting topics live in their primary domain and are linked from elsewhere.
- **Duplicate a page across domains.** One canonical copy per topic, period.
- **Read other domains' manifests during a single-domain operation** unless explicitly instructed. The whole point of separation is to not pay that cost. The exception is the §5.1 step 3 "summary-only" classification read.
- **Skip the verification subagent step in `/ingest` or `/health`.**
- **Run `qmd embed` in the background with `&`.** It's memory-heavy and can crash the machine. Foreground only.

---

## 9. Domain Evolution Policy

The starting domains are a **starting state, not a target state**. Domains should be allowed to emerge organically as the wiki grows and pages within an existing domain begin to cluster around clearly distinct themes.

### 9.1 The principle

A domain exists to compress context: an agent reading one domain's manifest should get the load-bearing knowledge for any question that routes there. If a domain's pages drift into two or more loosely-connected clusters, the manifest can no longer compress them efficiently — readers get noise from one cluster while looking for answers in the other. That is the moment to split.

### 9.2 Mechanical detection

Run inside `/health --structural`. **Two independent triggers** can flag a domain as a split candidate. They are complementary, not redundant.

#### 9.2.A Manifest-pressure trigger (cheap, primary)

The token count of the manifest's prose region is itself a direct signal of whether the domain still fits its compression target.

**Thresholds**:

- **Warning** (`prose ≥ 2,500 tokens`): the domain is approaching the budget. Note in the report. No action required.
- **Split candidate** (`prose ≥ 3,000 tokens`): the domain is over budget. Flag in the report and suggest investigating natural sub-clusters via the graph trigger (§9.2.B) to identify where to split.
- **Hard fail** (`prose ≥ 3,500 tokens`): the manifest is failing its compression duty. Flag as a blocking issue — the user should split before the next ingest.

**How to measure**: read `_manifest.md`, slice everything before the `<!-- REGISTRY:START -->` marker, count tokens via `tiktoken` (`cl100k_base` encoding) or fall back to `wc -w × 0.75`. The registry block itself is exempt.

**Why this works**: humans curate the manifest prose. The size of that prose IS the size of the irreducible "you must know this to operate in this domain" knowledge. If that exceeds 3K tokens, the domain has become two domains worth of context glued together.

#### 9.2.B Graph-community trigger (richer, secondary)

When 9.2.A flags a domain — or on a routine basis to catch divergence early — run community detection on the domain's wikilink subgraph to identify *where* the natural split lines lie.

1. **Build the graph**: read `wiki/xrefs.json`. Nodes are pages; directed edges are wikilinks. Within a domain, build the **induced subgraph** containing only pages that live in that domain and only edges where both endpoints are in the domain.
2. **Run community detection**: use a standard algorithm (Louvain or Label Propagation) on each domain's subgraph. Treat edges as undirected for community-finding purposes.
3. **Compute modularity**: the standard modularity score Q for the partition. Higher Q = more clearly separable communities; Q > 0.4 is generally meaningful, Q > 0.5 is strong.
4. **Filter for actionable splits**: a domain is flagged when ALL of these hold:
   - Modularity Q ≥ 0.40
   - At least 2 communities each have ≥ 15 pages (small communities are noise)
   - The two largest communities together cover ≥ 80% of the domain's pages
   - Cross-cluster edge density is < 25% of within-cluster density

#### 9.2.C Combined report

For each split candidate (from either trigger), the structural lint emits:

```
DOMAIN SPLIT CANDIDATE: <domain>
  Triggers: [manifest-pressure: 3,420 tokens / 3,000 budget] [graph: Q=0.47, 3 communities]
  Cluster A (32 pages): <top 5 pages by inbound-degree>, <top 5 by outbound-degree>
  Cluster B (28 pages): ...
  Suggested split: A → "<theme-A>", B → "<theme-B>"
```

The agent should NOT auto-rename or auto-move. It just flags. The user decides whether to split, when, and what to call the new domains.

**Dependency note**: the graph trigger requires `networkx`. Install with `pip install networkx` if missing. The manifest-pressure trigger has no extra dependencies.

### 9.3 Manual triggers

Beyond the mechanical detection, the user can request a domain split scan at any time with:

```
/health --domain-scan
```

This runs only the divergence detection (skipping the rest of structural lint). Useful when you suspect a domain is sprawling but haven't run a full health check yet.

### 9.4 What happens after a split

When the user accepts a split:

1. Create the new domain dir, manifest, and qmd collection (per §3 and §5.4)
2. Move the cluster's pages into the new domain dir (use `git mv`)
3. Update the `domain:` frontmatter on each moved page
4. Regenerate `xrefs.json`
5. Run `/health --structural` to confirm zero broken wikilinks (slug-based, so this should always pass — but verify)
6. Update the original domain's manifest to remove the split-out pages and add a "see also" pointer to the new domain
7. Update `wiki/overview.md` and `wiki/index.md` to list the new domain
8. Commit as `refactor: split <old-domain> into <old> + <new>`

### 9.5 The merging case

The same divergence detection can flag the **opposite** problem: a domain that's too small and tightly coupled to another. The merging trigger is conservative because merging is more disruptive than splitting.

**Merge candidate criteria** (ALL must hold):

- Domain has **< 10 pages**
- ≥ 80% of the domain's outbound wikilinks point to a single other domain
- Domain's manifest prose is **< 1,000 tokens**
- Domain is NOT marked `pinned: true` in its manifest frontmatter

**Pinning escape hatch**: a domain can set `pinned: true` in its manifest frontmatter to suppress merge-candidate flagging. Use this when a domain is intentionally small but worth keeping distinct.

**No domain should be auto-merged.** The structural lint reports the candidate; the user decides.

---

## 10. Out of Scope

The following are explicitly NOT part of this spec:

- **Migrating `raw/`** — sources stay flat in `raw/assets/` and `raw/archived/`. The domain split is a wiki-layer concern only.
- **Splitting CLAUDE.md per domain** — there's one schema file at vault root. Per-domain conventions can go in the manifests.
- **Multi-vault separation** — this is one Obsidian vault, one git repo. Splitting into multiple vaults is a different and larger conversation.
- **Per-domain commit scoping** — commits can still touch multiple domains; the domain separation is about read-time scoping, not write-time.
- **Automated domain reclassification** — once a page is placed, it stays put unless explicitly moved.
