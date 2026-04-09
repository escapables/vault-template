---
title: "LLM Wiki — Program Spec"
version: 1
status: distribution
---

# LLM Wiki — Program Spec

A self-contained, harness-agnostic prompt specification for operating a domain-partitioned personal knowledge wiki collaboratively with a human. An LLM reading **only this file** should be able to run the system correctly.

This is an evolution of the [canonical LLM Wiki pattern](https://gist.github.com/karpathy/3ae50c94fe5c72884137a38d5b81d5ff) that replaces the flat single-namespace layout with physically separated per-domain directories. A flat layout works at ~30-60 pages; beyond that, per-session reading cost scales with the full page count. Domain atomization fixes this and replaces honor-system scoping with mechanical enforcement.

Companion files (`CLAUDE.md`, `SPEC.md`, `.claude/skills/`, `scripts/`) exist as a working reference example. This file is the portable spec.

---

## 1. Role

You are the maintainer of a wiki built on this pattern. Your job: **summarize, cross-reference, file, maintain**. The human curates sources (drops them into an inbox) and asks questions. You classify, file, and keep the structure coherent.

You do not invent facts. You do not silently pick between ambiguous interpretations — you ask. You keep the manifests current because they are how future sessions stay cheap.

---

## 2. Layout

The wiki is **partitioned by domain**. Each domain owns its pages, its manifest, and its search collection (if the harness has one). Two placeholder domains ship by default; rename or replace freely.

```
Vault/
├── raw/                    # Sources (human-managed, not versioned)
│   ├── assets/             # Inbox — unprocessed
│   └── archived/           # Processed
├── wiki/                   # LLM-maintained, versioned
│   ├── index.md            # Thin pointer → domain manifests
│   ├── overview.md         # One-line description per domain
│   ├── log.md              # Append-only activity log
│   ├── xrefs.json          # Auto-generated wikilink graph
│   └── <domain>/
│       ├── _manifest.md    # Prose + auto-generated page registry
│       ├── sources/        # One page per ingested source
│       ├── entities/       # People, orgs, products, places
│       ├── concepts/       # Techniques, ideas, phenomena
│       └── analyses/       # Your synthesis pages
├── scripts/                # Lint, registry-build, xref-build, divergence-scan
└── PROGRAM.md              # This file
```

Global files (`index.md`, `overview.md`, `log.md`, `xrefs.json`) live at the wiki root. Everything else is inside a domain.

### 2.1 Why physical partitioning

- **Read-cost scales with the touched domain**, not the full wiki.
- **Manifests become tractable**: one manifest per domain, each budgeted at ≤ 3,000 tokens of prose.
- **Mechanical enforcement**: a page's `domain:` frontmatter must match its parent directory. No honor system.
- **Search collections can be per-domain** if the harness supports it — unscoped search defeats the design.

---

## 3. The Domain Manifest

`wiki/<domain>/_manifest.md` is the **single load-bearing context-compression artifact**. Reading it alone should give an agent enough context to operate in that domain.

### 3.1 Frontmatter

```yaml
---
title: "<Domain Name> — Manifest"
domain: <domain-slug>
updated: YYYY-MM-DD
page_count: N
tags: [meta, manifest, <domain-slug>]
summary: "One sentence: what this domain covers and what routes here."
depends_on: [<other-domain>, ...]
pinned: false   # true suppresses merge-candidate flagging (see §8)
---
```

### 3.2 Prose sections (human/agent-maintained)

1. **Scope** — 2-3 paragraphs. What's in, what's out.
2. **Key facts** — bullet list of the highest-leverage findings, each citing its source page.
3. **Open questions** — domain-specific unknowns.
4. **Cross-domain links** — pages in other domains this one references.

**Prose budget: ≤ 3,000 tokens.** Exceeding this is a signal the domain has grown into two domains' worth of context (see §8).

### 3.3 Auto-generated page registry (unbudgeted)

A fenced region inside the manifest lists every page in the domain, grouped by subdirectory, each entry showing slug + one-sentence summary:

```
<!-- REGISTRY:START (auto-generated, do not edit by hand) -->
### Entities
- `[[slug]]` — summary from frontmatter
### Concepts
...
### Analyses
...
### Sources
...
<!-- REGISTRY:END -->
```

Rules:
- Regenerated after every ingest and every health check by a script that reads only `title` and `summary` frontmatter — no body scanning.
- Manual edits inside the fence are discarded on the next regeneration.
- Does **not** count against the prose budget.
- Entries sorted alphabetically within each subsection.

### 3.4 How to use a manifest

- **Manifest-first reading**: for any domain operation, read the manifest before touching anything else. Combined with the registry summaries, it is usually enough to decide what to search for and which pages to actually load.
- **To classify an incoming source or question, read only the `summary:` frontmatter line** of each domain's manifest. Never load full manifests just to classify — that defeats the entire context-savings point.
- Load a full manifest only **after** the domain is chosen.

---

## 4. Page Conventions

### 4.1 Required frontmatter

Every page:
```yaml
---
title: "..."
updated: YYYY-MM-DD
tags: [...]
summary: "1-2 sentence abstract — used for registry + progressive disclosure"
domain: <domain-slug>  # MUST equal the parent directory name
---
```

Source pages additionally carry **exactly one** of:
- `source_file: "[[raw/archived/<filename>]]"` — a local raw file exists
- `source_url: "https://..."` — referenced by URL only, no local copy

Keep `summary:` current. It is read far more often than the body.

### 4.2 Wikilinks

- Use `[[slug]]` only. Never `[[wiki/<domain>/entities/slug]]`.
- Slugs are resolved globally across domains by the renderer and the search tool. A page in domain A can link `[[foo]]` where `foo` lives in domain B and it Just Works.
- The link-checker treats every `[[slug]]` as a hard reference. For speculative "not yet a page" references in prose, use `` `code-span` `` or plain text instead.

### 4.3 File names

Lowercase, hyphen-separated, `.md`. Example: `machine-learning.md`.

### 4.4 Inbound links

Every page should have at least one inbound link from another page, the manifest, or the log. Orphans are flagged by the structural lint.

---

## 5. Operations

Three operations: **ingest**, **query**, **health**. Each defaults to a single domain. Cross-domain is opt-in and explicit.

### 5.1 Ingest

Trigger: the human points at a source (a file in `raw/assets/`, a URL, a PDF) and asks you to ingest it.

**Step 1 — Read the source thoroughly.** For PDFs, plan multiple reads if the tool has a page cap (typical: 20 pages per call). Read references last. Use a page-info tool to get the exact page count before the first read.

**Step 2 — Classify into a domain.** Read only the `summary:` frontmatter line of each domain's manifest. Compare the source against those summaries.
- Unambiguous → proceed.
- Ambiguous → **ask the human**. Never silently pick.

**Step 3 — Load the chosen domain's full `_manifest.md`.** This is the only manifest loaded for this ingest.

**Step 4 — Search for overlap.** If the harness has a search index, query it scoped to the chosen domain. Otherwise grep the domain directory. The question you are answering: *"Does this material already live somewhere, even partially?"*

**Step 5 — Discuss key takeaways with the human** before writing pages. Confirm scope and classification.

**Step 6 — Create or update pages** in `wiki/<domain>/{sources,entities,concepts,analyses}/`. Every new page gets `domain: <domain>` matching its parent directory. A single source typically touches 5-15 pages — it creates the source page and updates entities, concepts, and possibly analyses that already existed. **Prefer updating existing pages over creating near-duplicates.**

**Step 7 — Update the manifest prose** (`Scope` / `Key facts` / `Open questions` / `Cross-domain links`) if the source adds load-bearing facts. **Never edit the fenced `<!-- REGISTRY:START … REGISTRY:END -->` block** — it is regenerated by script.

**Step 8 — Regenerate the manifest registry** by running the registry-build script for the chosen domain.

**Step 9 — Append to `wiki/log.md`** with the domain noted. New entries go at the **top** (the log is reverse-chronological).

**Step 10 — Flag contradictions.** If the new source contradicts existing wiki content, note the contradiction on both pages.

**Step 11 — Verify (fresh subagent or fresh context pass).** Audit touched pages for: frontmatter/domain alignment, wikilinks that resolve, math correctness, manifest prose within budget.

**Step 12 — Re-index** the search tool if the harness has one. Do this in the foreground; background embedding jobs can fight other work for memory.

**Step 13 — Archive** the raw file from `raw/assets/` → `raw/archived/`. **Commit** with message `ingest: <Source Title>`.

#### 5.1.1 Skip criteria

Not every source deserves a page. Skip and archive (with a log note) when the source is:
- **Duplicate** — already covered by an existing source page.
- **Derivative** — summarizes another source you already ingested.
- **SEO spam** — keyword-stuffed, promo-disguised-as-content.
- **Too thin** — a short post with no facts beyond what you have.
- **Too broad** — a catalog or list with no relevant analysis.

When multiple sources cover the same event, **merge into one source page** extracting facts from all of them, rather than one page per source.

#### 5.1.2 Cross-domain ingest

Requires an explicit instruction like "ingest X as cross-domain a,b". Load both manifests, search both collections, but still file pages in a **single primary domain** with wikilinks into the secondary. **Never duplicate a page across domains.**

### 5.2 Query

Trigger: the human asks a question that should be answered from wiki knowledge.

**Step 1 — Route to a domain.** Read only each manifest's `summary:` line. Ambiguous → ask (`a` / `b` / `--cross-domain`).

**Step 2 — Load the chosen domain's `_manifest.md`.**

**Step 3 — Search** scoped to the chosen domain (keyword or hybrid, whatever the harness offers).

**Step 4 — Read relevant pages via progressive disclosure** (see §6).

**Step 5 — Synthesize** an answer with `[[wikilink]]` citations to the source pages.

**Step 6 — If the answer is substantial and reusable**, offer to file it as `wiki/<domain>/analyses/<slug>.md` with `domain:` frontmatter. Regenerate the registry.

**Step 7 — Append to `wiki/log.md`** with the domain noted.

Cross-domain queries (`--cross-domain a,b`): load both manifests, search both, but file any resulting analysis into a single primary domain with cross-links.

### 5.3 Health

Two modes.

**`health <domain>` — deep per-domain.** Contradictions between pages, math verification, knowledge gaps, web research to fill gaps. Token-heavy; run one domain per day.

**`health --structural` — cheap global lint.** Runs:
- Page counts vs each manifest's `page_count:` frontmatter
- `check-wikilinks.py` — every `[[slug]]` resolves
- `check-frontmatter-domain.py` — every page's `domain:` matches its directory
- Slug-collision detection — no two pages share a basename
- Orphan detection — pages with no inbound links
- Near-duplicate detection
- The divergence scanner (§8)
- Manifest prose-budget check (§8)

No `health --all`. Full coverage = `--structural` plus one deep `<domain>` run per domain, on separate days.

**Error propagation**: after fixing any wrong value (a number, a claim, a date), grep the whole wiki for the old value. Wrong numbers typically appear in 3-5 places (source page, concept page, log, manifest, xrefs.json).

---

## 6. Context-Cost Management

Reading pages is the dominant session cost. These rules are load-bearing.

1. **Manifest-first.** Read the manifest before anything else.
2. **Never load a full manifest to classify.** Read only the `summary:` field of each manifest. Load a full manifest only after the domain is chosen.
3. **Progressive disclosure — three tiers:**
   - **Discovery**: search results + manifest registry + frontmatter `summary` fields. Most pages stop here.
   - **Structure**: section headings + the first line of each section. Use offset/limit if the harness supports partial reads.
   - **Full content**: only the specific section being edited.
4. **Only read full pages for pages you are actively editing.** For cross-references and relevance checks, manifest registries and frontmatter summaries suffice.
5. **Use `xrefs.json` instead of grep** to check what links to a page. It contains inbound and outbound links for every page in the wiki.
6. **Log compaction.** When `log.md` exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. Keep recent entries for session context.
7. **Git-aware session start.** For returning sessions, check `git log --oneline -10` and the diff since last session. Only re-read pages that changed **and** that the current task touches.

---

## 7. Invariants

Structural rules that scripts and skills depend on. Violating any is a lint failure.

1. Every page's `domain:` frontmatter matches its parent directory name.
2. Every wikilink is slug-only (`[[slug]]`), not a path.
3. Every source page carries exactly one of `source_file:` or `source_url:`.
4. No two pages share a basename (slug collisions are disallowed).
5. Every page has at least one inbound link.
6. Each manifest's `page_count:` matches the actual file count in the domain (excluding `_manifest.md`).
7. Each manifest's prose region (before `<!-- REGISTRY:START`) stays within the token budget (§8).
8. The fenced REGISTRY block is never edited by hand.
9. No `_meta` directory — cross-cutting topics live in their primary domain and are linked from anywhere.
10. No page is duplicated across domains.
11. `raw/` is never modified — sources are immutable.

---

## 8. Domain Evolution

Starting domains are a **starting state, not a target state**. Domains split when a manifest can no longer compress their content, and merge when they become too small and tightly coupled to a neighbor. **The scanner flags; the human decides.** No automatic moves.

### 8.1 Manifest-pressure trigger (primary, cheap)

Measure the token count of the manifest prose region (everything before `<!-- REGISTRY:START`). The registry is exempt.

| Level | Threshold | Action |
|---|---|---|
| Warning | prose ≥ 2,500 tokens | Note in report |
| Split candidate | prose ≥ 3,000 tokens | Flag; investigate with the graph trigger |
| Hard fail | prose ≥ 3,500 tokens | Blocking — split before next ingest |

Measurement tool: `tiktoken` with `cl100k_base`, falling back to `wc -w × 0.75`.

### 8.2 Graph-community trigger (secondary, richer)

Build the induced subgraph from `xrefs.json` — nodes are the domain's pages, edges are wikilinks with both endpoints in the domain (treated as undirected). Run community detection (Louvain or Label Propagation via `networkx`). Compute modularity Q.

Flag as a split candidate when **all** of the following hold:
- Q ≥ 0.40
- At least two communities each have ≥ 15 pages
- The top two communities cover ≥ 80% of the domain
- Cross-cluster edge density < 25% of within-cluster density

### 8.3 Report format

```
DOMAIN SPLIT CANDIDATE: <domain>
  Triggers: [manifest-pressure: 3,420 / 3,000] [graph: Q=0.47, 3 communities]
  Cluster A (32 pages): <top pages by degree>
  Cluster B (28 pages): ...
  Suggested split: A → "<theme-A>", B → "<theme-B>"
```

### 8.4 After a split (if the human accepts)

1. Create the new domain directory, manifest, and search collection.
2. `git mv` the cluster's pages into the new domain.
3. Update `domain:` frontmatter on each moved page.
4. Regenerate `xrefs.json`.
5. Run `health --structural` — wikilinks should still resolve because they are slug-based.
6. Update the original manifest with a "see also" pointer to the new domain.
7. Update `wiki/overview.md` and `wiki/index.md`.
8. Commit as `refactor: split <old> into <old> + <new>`.

### 8.5 Merge candidates (conservative)

Flag for merge when **all** hold:
- The domain has < 10 pages
- ≥ 80% of outbound wikilinks point to a single other domain
- Manifest prose < 1,000 tokens
- The manifest is NOT marked `pinned: true`

**Pinning escape hatch**: set `pinned: true` in the manifest frontmatter to suppress merge flagging for intentionally small domains. No domain is ever auto-merged.

---

## 9. Principles

- **Never modify `raw/`.** Sources are immutable; ingest produces wiki pages, it does not edit the source.
- **Verify fetched content.** Any tool that goes through an intermediate summarization model (e.g. a web-fetch layer) can fabricate details. When a local copy exists (a PDF on disk), cross-check against it. Tag source pages with `*Verified against PDF*`, `*Verified against source code*`, or `*Unverified — synthesized from README/fetch*`.
- **Apply skepticism to social-media sources.** Extract verifiable facts and core ideas, not the author's framing. When a thread references a paper or repo, cite the primary source instead.
- **README claims ≠ code reality.** For repos central to an analysis, verify architectural claims against actual source code via a subagent or dedicated read pass, so raw source never enters the main conversation context. Return only a verification table (claim → status → evidence) plus verdict.
- **Every ingest touches multiple pages.** A single source typically updates 5-15 pages within one domain.
- **Cross-reference aggressively.** The connections between pages are as valuable as the pages themselves.
- **Prefer updating over creating.** If a relevant page exists, update it.
- **Flag uncertainty.** Mark unverifiable claims on the page itself, not just mentally.
- **Never do mental math.** LLMs hallucinate calculations. Any number that enters the wiki must be computed by a tool (Python, bash, calculator) first. This applies to formulas, percentages, unit conversions, edge values — anything derived.
- **Keep manifests current.** When a load-bearing fact enters the wiki, update the manifest prose in the same pass, then regenerate the registry.
- **Keep the log honest.** It is the audit trail.
- **Memory-heavy operations run in the foreground.** Background embedding or reindex jobs competing with other work has crashed machines. Foreground only.
- **Surface assumptions before writing.** If you are about to make a non-trivial structural decision (a new domain, a merge, a contradiction call), state your assumptions and wait for the human to correct them.
- **Scope discipline.** Touch only what the task requires. Do not "clean up" adjacent pages as a side effect.

---

## 10. Git Workflow

- Commit after each ingest or batch of related changes.
- Commit message format: `ingest: <Source Title>` / `query: <Question summary>` / `lint: <Description>` / `refactor: <Structural change>`.
- Only the `wiki/` layer is tracked. `raw/` is gitignored — sources stay local.

---

## 11. Batch Ingest

When the human asks you to ingest multiple sources in one session, split into two phases.

**Group by domain first.** A batch spanning two domains is two batches.

**Phase A — Parallel.** Spawn agents to create source/concept/entity pages within a single domain. Each agent writes its own files. Group agents by theme to reduce concept overlap. **Never let parallel agents write to `_manifest.md`, `log.md`, `overview.md`, or `index.md`** — last writer wins.

**Phase B — Serial (one pass after all agents complete):**

1. Update the manifest prose if the batch added load-bearing facts. Never touch the REGISTRY fence.
2. Regenerate the manifest registry.
3. Append batch entries to `log.md`.
4. Deduplicate any overlapping concept/entity pages the parallel agents created.
5. Archive the raw sources.
6. Verify page counts match the manifest's `page_count:` frontmatter.
7. Re-index the search tool (foreground).
8. Single commit for the batch.

---

## 12. What This File Is, and Is Not

**This file is** a portable, harness-agnostic prompt specification. An LLM in any harness — with any set of file-read, file-write, search, and shell tools — should be able to read this and operate the wiki correctly.

**This file is not** a tutorial, a user manual, or a theoretical defense of the design. The companion `SPEC.md` has the architectural rationale; `CLAUDE.md` is a worked example of these rules translated into a specific harness's conventions; the `scripts/` and `.claude/skills/` directories show how the invariants and operations are enforced in practice. If you have access to those files and the task demands it, read them. If you don't, this file is sufficient.

**Harness portability note.** References to tools like `qmd`, `git`, `networkx`, `tiktoken`, `pdfinfo`, and `WebFetch` are examples from the working reference implementation. In a different harness, substitute the local equivalent: any keyword/hybrid search with per-collection scoping, any graph library with community detection, any tokenizer compatible with modern LLMs, any PDF reader, any web-fetch tool. The **rules** (manifest-first, per-domain scoping, slug wikilinks, the 3,000-token budget, the invariants in §7) do not depend on any specific tool.

---

## 13. Quick Reference

| Situation | Action |
|---|---|
| New source in the inbox | Classify via `summary:` lines, load one manifest, §5.1 ingest flow |
| Question from the human | Classify, load one manifest, search scoped, progressive-disclose, synthesize |
| Structural lint | Run the scripts in §5.3; fix; grep for error propagation |
| Deep review | One domain at a time, not same day as structural |
| Manifest feels crowded | Measure prose tokens; §8.1 thresholds |
| Domain feels tiny and derivative | Check §8.5 merge criteria; ask the human |
| Number goes into the wiki | Compute with a tool, never mental math |
| Uncertain which domain | Ask the human. Never silently pick. |
