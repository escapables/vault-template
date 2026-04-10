---
title: "LLM Wiki — Build and Operate Contract"
version: 2
status: distribution
---

# LLM Wiki — Build and Operate Contract

This is a harness-agnostic contract an LLM can follow to **build** and **operate** a domain-atomized personal knowledge wiki using the accompanying reference repository. The reference repo is assumed to be present because this file ships inside it; use the repo's scripts and example files as canonical artifacts, and use this file to define the invariants and verification gates.

This pattern is an evolution of the [canonical LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) that replaces the single flat namespace with physically separated per-domain directories. A flat layout works at ~30-60 pages; beyond that, per-session reading cost scales with total page count. Domain atomization fixes this by making per-session reads scale with the **touched** domain only, and replaces honor-system scoping with mechanical enforcement.

> **How to read this file.** Part I is a linear build contract (Steps 1-9). Part II specifies the three operations (ingest, query, health) you will run against the wiki after it is built. Part III covers how domains evolve (split / merge) as the wiki grows. Part IV records meta-notes about portability. Do Part I in order before attempting anything in Part II.

---

## Part 0 — Preamble

### 0.1 Role

You are the maintainer of a knowledge wiki. Your job is to **summarize, cross-reference, file, and maintain**. The human curates sources (drops them into an inbox) and asks questions. You classify, file, and keep the structure coherent. You do not invent facts. You do not silently pick between ambiguous interpretations — you ask. You keep the manifests current because they are how future sessions stay cheap.

### 0.2 Prerequisites

Before Step 1, confirm the following are available:

- A POSIX-like shell (bash, zsh, or equivalent)
- Python 3.8+
- `git`
- Write access to an empty directory (the vault root)
- A file-read, file-write, shell, and (ideally) web-fetch tool exposed by the harness

**Optional but recommended** (used by late-stage features; the core wiki works without them):

- A scoped keyword search tool. The reference example uses [`qmd search`](https://github.com/qmd-search/qmd); `rg -n "<terms>" wiki/<domain>` is the portable fallback.
- `networkx` (`pip install networkx`) — for the graph-based divergence scanner (§III.2)
- `tiktoken` (`pip install tiktoken`) — for precise manifest token measurement; falls back to `wc -w × 0.75`
- `pdfinfo` (from `poppler-utils`) — for PDF page counting before reads

### 0.3 Portability contract

Core requirements are access to this reference repository, file read/write, shell, git, Python, and the ability to ask the human clarifying questions. Optional web fetch helps URL ingests and staleness checks, but the wiki still works without it.

Path variables used below:

- `<reference-root>` — the directory containing this `PROGRAM.md`, `CLAUDE.md`, `scripts/`, `SPEC.md`, and the example `wiki/`.
- `<vault-root>` — the target vault directory being built or operated.
- If bootstrapping in place from a fork of this repo, `<reference-root>` and `<vault-root>` are the same directory. In that case, do not copy files over themselves; verify the existing artifacts instead.

The default search mode is safe mechanical search: scoped keyword search inside the chosen domain before reading page bodies. Use `rg` if nothing else exists. Low page counts do not need an index; around ~80 articles/pages, a scoped index such as `qmd search` usually starts paying for itself. Treat ~80 as a practical threshold, not an invariant. Do not make LLM reranking, vector search, MCP tools, local GGUF models, hooks, skills/plugins, or any harness-specific feature part of the core path.

If the human asks to enable hybrid semantic search or LLM reranking, warn first: it can load local GGUF models, use significant RAM, run slowly on CPU-only machines, and use GPU/VRAM if available. Keep that mode opt-in; the default remains mechanical scoped search.

Harness-specific features belong in adapter files or examples. Each implementing agent should use the best practices native to its own harness while preserving the rules here: domain atomization, manifest-first reading, scoped search, registries, xrefs, health checks, math verification, and single-domain default operations.

### 0.4 Glossary

| Term | Meaning |
|---|---|
| **vault** | The top-level directory containing everything: `raw/`, `wiki/`, `scripts/`, etc. |
| **wiki** | The `wiki/` subdirectory. The LLM-maintained, git-versioned layer. |
| **raw** | The `raw/` subdirectory. Human-managed source material. **Gitignored**. Immutable from your perspective. |
| **domain** | A top-level partition of the wiki (`wiki/<domain>/`). A domain owns a manifest and four subdirectories (`sources`, `entities`, `concepts`, `analyses`). |
| **manifest** | `wiki/<domain>/_manifest.md`. The load-bearing context-compression artifact for a domain. |
| **registry** | An auto-generated block inside each manifest listing every page in the domain with its one-sentence summary. |
| **slug** | A page's file basename without the `.md` extension. The unit of wikilink resolution. |
| **wikilink** | `[[slug]]` — resolved by basename across the whole vault, regardless of which domain the slug lives in. |

---

# Part I — Build the Wiki

Steps 1 through 9 take an empty target directory to a working, lint-clean, git-initialized vault by copying canonical artifacts from the reference repo and verifying the resulting contracts. Do them in order.

## Step 1 — Target layout

Here is what you will produce. Create this structure in your head before you touch anything.

```
<vault-root>/
├── .gitignore
├── PROGRAM.md                # copied from <reference-root>/PROGRAM.md unless bootstrapping in place
├── CLAUDE.md                 # harness-agnostic agent notes; compatibility filename
├── README.md                 # a short human-facing intro (Step 9)
├── raw/                      # sources (gitignored)
│   ├── assets/               # inbox — unprocessed
│   ├── archived/             # processed
│   └── attachments/          # locally-extracted images
├── scripts/
│   ├── build-registry.sh
│   ├── build-xrefs.py
│   ├── build-analytics.py
│   ├── check-wikilinks.py
│   ├── check-frontmatter-domain.py
│   ├── detect-domain-divergence.py
│   ├── find-near-duplicates.sh
│   ├── find-attachments.sh
│   ├── install-wiki-hooks.sh
│   ├── wiki-maintenance-hook.sh
│   └── wiki-session-reminder.sh
└── wiki/
    ├── index.md              # thin pointer index
    ├── overview.md           # one-sentence description per domain
    ├── log.md                # reverse-chronological activity log
    ├── xrefs.json            # auto-generated wikilink graph
    ├── <domain-a>/
    │   ├── _manifest.md
    │   ├── sources/
    │   ├── entities/
    │   ├── concepts/
    │   └── analyses/
    └── <domain-b>/
        ├── _manifest.md
        ├── sources/
        ├── entities/
        ├── concepts/
        └── analyses/
```

## Step 2 — Create the directory skeleton

```bash
mkdir -p raw/assets raw/archived raw/attachments scripts wiki
```

If `<reference-root>` and `<vault-root>` are different directories, copy the portable contract and the harness-agnostic agent notes into the target vault now:

```bash
cp <reference-root>/PROGRAM.md <vault-root>/PROGRAM.md
cp <reference-root>/CLAUDE.md <vault-root>/CLAUDE.md
cmp <reference-root>/PROGRAM.md <vault-root>/PROGRAM.md
cmp <reference-root>/CLAUDE.md <vault-root>/CLAUDE.md
```

Do not create the domain subdirectories yet — you choose their names in Step 5 with the human.

## Step 3 — Create `.gitignore`

Write the following to `<vault-root>/.gitignore`:

```
# Source material is local-only; never commit it.
raw/

# Editor/OS cruft
.DS_Store
.trash/
*.AppImage

# Obsidian state (if you use Obsidian as a renderer)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/plugins/*/main.js
.obsidian/plugins/*/styles.css
.obsidian/plugins/*/data.json

# Optional adapter permission allowlists — personal workflow, never commit
.claude/settings.local.json
```

## Step 4 — Create the global navigation files

Four files live at `wiki/` root. They exist from the moment of setup; they are not optional.

### 4.1 `wiki/index.md`

A thin pointer. It does not enumerate per-domain pages — that is the manifest's job.

```markdown
---
title: Wiki Index
tags: [meta, navigation]
---

# Wiki Index

This is the thin pointer index for the vault. It lists the domain manifests and global navigation files. It does NOT enumerate per-domain pages — the domain manifests own that.

## Domains

- **<domain-a>** — see `wiki/<domain-a>/_manifest.md`
- **<domain-b>** — see `wiki/<domain-b>/_manifest.md`

## Global navigation

- `wiki/overview.md` — top-level navigator with a one-sentence description per domain
- `wiki/log.md` — reverse-chronological activity log
- `wiki/xrefs.json` — auto-generated wikilink graph

## Adding a domain

1. Create `wiki/<name>/` with the four standard subdirectories: `sources/`, `entities/`, `concepts/`, `analyses/`
2. Write `wiki/<name>/_manifest.md` per Part II §2
3. (If you use a search tool with per-collection scoping) add a collection for the new domain
4. Add the new domain to this index and to `overview.md`
```

Fill in `<domain-a>` / `<domain-b>` with the real names you pick in Step 5.

### 4.2 `wiki/overview.md`

A pure navigator. One sentence per domain. No page enumeration, no numbers.

```markdown
---
title: Wiki Overview
tags: [meta, navigation]
---

# Wiki Overview

A pure navigator. One sentence per domain, with a link to the manifest. No page enumeration, no key facts, no numbers — those live in the manifests.

## Domains

- **<domain-a>** (`wiki/<domain-a>/_manifest.md`) — <one-sentence description of what this domain covers>.
- **<domain-b>** (`wiki/<domain-b>/_manifest.md`) — <one-sentence description of what this domain covers>.

Rename, replace, or split these to fit your knowledge. Two starting domains is the minimum that makes the architecture meaningful — start small, let new domains emerge organically when the divergence scanner flags real clusters.
```

### 4.3 `wiki/log.md`

Reverse-chronological. **New entries go at the top.**

```markdown
---
title: Wiki Log
tags: [meta]
---

# Wiki Log

Reverse-chronological record of wiki activity. New entries go at the **TOP**, immediately after the hint comment below, so the newest activity is always visible first.

When this file exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. The archive is still git-tracked and search-indexable.

<!-- grep "^## \[" log.md | head -5 -->

## [YYYY-MM-DD] setup | Initial vault bootstrap

Domain: n/a. Built the vault from PROGRAM.md. Created two starting domains: <domain-a>, <domain-b>. Scripts installed, lints passing, first commit made.
```

### 4.4 `wiki/xrefs.json`

Must exist from setup (even empty) so scripts that read it don't crash. Initialize with an empty object:

```json
{}
```

## Step 5 — Choose the first two domains

**Ask the human.** Do not silently pick. The conversation:

> "We need two starting domains. A domain is a top-level partition of the wiki — each owns its own manifest and its own search scope. Two is the minimum that makes this architecture meaningful. The reference example uses `research` (external sources — papers, articles) and `projects` (things you build, decide, operate). What two domains fit the knowledge you want to accumulate?"

**Constraints:**

- **Two minimum, two recommended to start.** More can be added later via §III.1; the divergence scanner (§III.2) will tell you when.
- **Names must be lowercase, hyphen-free if possible** (they become directory names and search-collection names).
- **Domains should be broad enough** that most sources the human ingests clearly belong to one of them. If the human's first three example sources each route to a different domain, you have too many or too narrow.
- **Domains should be disjoint enough** that classification via the `summary:` line of each manifest is usually unambiguous. If two proposed domains overlap heavily, suggest merging them into one.

Once the human commits to two names — call them `<domain-a>` and `<domain-b>` below — create the subdirectories:

```bash
mkdir -p wiki/<domain-a>/{sources,entities,concepts,analyses}
mkdir -p wiki/<domain-b>/{sources,entities,concepts,analyses}
```

Then go back and substitute the real names into `wiki/index.md` and `wiki/overview.md` (Step 4.1 and 4.2 had placeholder `<domain-a>` / `<domain-b>` — replace those now).

## Step 6 — Write the manifest skeletons

Each domain gets one `_manifest.md`. This is the **load-bearing context-compression artifact** — reading it alone should give an agent enough context to operate in that domain. At setup time it is mostly placeholder text; it fills up as you ingest.

### 6.1 Manifest schema

```yaml
---
title: "<Domain Name> — Manifest"
domain: <domain-slug>            # MUST equal the parent directory name
updated: YYYY-MM-DD
page_count: 0                    # updated after every ingest
tags: [meta, manifest, <domain-slug>]
summary: "One sentence: what this domain covers and what routes here."
depends_on: []                   # list of other domains this one references
pinned: false                    # true suppresses merge-candidate flagging (§III.2)
---
```

Four prose sections follow the frontmatter, then the auto-generated blocks:

1. **Scope** — 2-3 paragraphs. What's in, what's out. Explicit calls on boundary cases.
2. **Key facts** — bullet list of the highest-leverage findings, each citing its source page.
3. **Open questions** — domain-specific unknowns. Explicit gaps tell future-you what's worth ingesting next.
4. **Cross-domain links** — pages in other domains this one commonly references.
5. **Registry block** — fenced with `<!-- REGISTRY:START ... -->` and `<!-- REGISTRY:END -->`. **Never edited by hand** — regenerated by `scripts/build-registry.sh`.
6. **Analytics block** — fenced with `<!-- ANALYTICS:START ... -->` and `<!-- ANALYTICS:END -->`. **Never edited by hand** — regenerated by `scripts/build-analytics.py`.

**Prose budget: ≤ 3,000 tokens.** Exceeding this signals the domain has grown into two domains' worth of context (see §III.2). The registry and analytics blocks do not count against the budget.

### 6.2 Skeleton template

Write this to `wiki/<domain-a>/_manifest.md`, substituting the real values. Repeat for `<domain-b>`.

```markdown
---
title: "<Domain Name> — Manifest"
domain: <domain-slug>
updated: YYYY-MM-DD
page_count: 0
tags: [meta, manifest, <domain-slug>]
summary: "One sentence describing what this domain covers and what kind of source or question routes here. The ingest and query classification steps read ONLY this line."
depends_on: []
pinned: false
---

# <Domain Name> — Manifest

This is a placeholder manifest. After setup, the Scope / Key facts / Open questions / Cross-domain links sections fill in as you ingest sources.

## Scope

Two or three paragraphs describing what's in this domain and what's out. Boundary cases (topics that could fit either this domain or another) get explicit calls here.

## Key facts

Bullet list of the highest-leverage findings, decisions, and constraints in this domain. Numbers must be authoritative — cite the page they come from.

- (empty until first ingest)

## Open questions

Known unknowns specific to this domain. The list itself is part of the wiki's knowledge — explicit gaps tell future-you and future-agents what's worth ingesting next.

1. (empty until first ingest)

## Cross-domain links

Pages in OTHER domains that this domain commonly references. Makes cross-domain dependencies legible without loading the other domain's full manifest.

- (empty until first ingest)

<!-- REGISTRY:START (auto-generated, do not edit by hand) -->

<!-- REGISTRY:END -->
```

**Important**: do not write speculative `[[slug]]` wikilinks into the placeholder sections. Verification fails on any `[[slug]]` whose target does not exist. Leave placeholder bullets as plain prose.

## Step 7 — Install the scripts

The reference repository is part of this contract, so do not regenerate the scripts from prose when the repo is present. Copy the files from the reference repo into `<vault-root>/scripts/` unchanged unless the human explicitly asks for a new implementation:

- `scripts/build-registry.sh`
- `scripts/build-xrefs.py`
- `scripts/build-analytics.py`
- `scripts/check-wikilinks.py`
- `scripts/check-frontmatter-domain.py`
- `scripts/detect-domain-divergence.py`
- `scripts/find-near-duplicates.sh`
- `scripts/find-attachments.sh`
- `scripts/install-wiki-hooks.sh`
- `scripts/wiki-maintenance-hook.sh`
- `scripts/wiki-session-reminder.sh`

After copying, mark them executable:

```bash
chmod +x scripts/*.sh scripts/*.py
```

Verify script identity before behavior. If `<reference-root>` and `<vault-root>` are different, compare each copied script against the reference:

```bash
reference_root=<absolute path to reference repo>
vault_root=<absolute path to target vault>
for f in \
  scripts/build-registry.sh \
  scripts/build-xrefs.py \
  scripts/build-analytics.py \
  scripts/check-wikilinks.py \
  scripts/check-frontmatter-domain.py \
  scripts/detect-domain-divergence.py \
  scripts/find-near-duplicates.sh \
  scripts/find-attachments.sh \
  scripts/install-wiki-hooks.sh \
  scripts/wiki-maintenance-hook.sh \
  scripts/wiki-session-reminder.sh
do
  cmp "$reference_root/$f" "$vault_root/$f" || exit 1
done
```

Contract for these scripts:

- `build-registry.sh <domain>` regenerates only the registry block inside `wiki/<domain>/_manifest.md`.
- `build-xrefs.py` regenerates global `wiki/xrefs.json` from slug-only wikilinks.
- `build-analytics.py` consumes `wiki/xrefs.json` and writes a derived analytics block (god nodes, bridges, clusters, recent, stale, questions) into each domain manifest.
- `check-wikilinks.py` fails on broken slug links or slug collisions.
- `check-frontmatter-domain.py` fails when page `domain:` frontmatter does not match the parent domain directory.
- `detect-domain-divergence.py` reports manifest pressure, graph-community split candidates, and conservative merge candidates; it never moves pages.
- `find-near-duplicates.sh` is optional and adapter-backed; skip or replace it when no scoped search index exists.
- `find-attachments.sh` maps raw source titles to local attachment files.
- `install-wiki-hooks.sh` installs optional post-commit / post-checkout git hooks that call `wiki-maintenance-hook.sh`.
- `wiki-maintenance-hook.sh` rebuilds registries, `xrefs.json`, and analytics after commits; non-blocking on failure.
- `wiki-session-reminder.sh` prints a harness-agnostic reminder of context-cost rules.

Verify behavior rather than reproducing implementation text:

```bash
bash -n scripts/*.sh
python3 scripts/check-wikilinks.py
python3 scripts/check-frontmatter-domain.py
python3 scripts/detect-domain-divergence.py
```

## Step 8 — Verify the build

Run each of the following. Every one should succeed.

```bash
# Directory structure exists
test -d raw/assets && test -d raw/archived && test -d scripts && test -d wiki

# Both domains exist with all four subdirectories
for d in <domain-a> <domain-b>; do
  for sub in sources entities concepts analyses; do
    test -d "wiki/$d/$sub" || echo "missing: wiki/$d/$sub"
  done
  test -f "wiki/$d/_manifest.md" || echo "missing: wiki/$d/_manifest.md"
done

# Global files exist
test -f wiki/index.md
test -f wiki/overview.md
test -f wiki/log.md
test -f wiki/xrefs.json

# Scripts are in place and executable
ls -la scripts/
test -x scripts/build-registry.sh

# Lints pass (should both print OK)
python3 scripts/check-wikilinks.py
python3 scripts/check-frontmatter-domain.py

# Manifest registries regenerate cleanly (should print "OK: registry block updated")
bash scripts/build-registry.sh <domain-a>
bash scripts/build-registry.sh <domain-b>

# xrefs graph rebuilds cleanly
python3 scripts/build-xrefs.py

# analytics blocks regenerate cleanly
python3 scripts/build-analytics.py

# xrefs refreshes again to capture generated manifest links
python3 scripts/build-xrefs.py

# Divergence scanner runs without error (should report 0 pages, ok level)
python3 scripts/detect-domain-divergence.py
```

If any of these fail, **stop and diagnose** before proceeding. Do not skip ahead to git init with a broken build.

## Step 9 — git init and first commit

```bash
git init
git add .gitignore PROGRAM.md CLAUDE.md README.md scripts/ wiki/
git status                     # sanity-check: raw/ should NOT appear
git commit -m "initial: bootstrap LLM Wiki from PROGRAM.md"
```

**Check `git status` carefully.** If any file under `raw/` appears in the staging area, the `.gitignore` is wrong — fix it before committing. `raw/` content is intentionally local-only and must never enter history.

If the human wants a README that introduces the project to other humans, write one now (it can be as short as a paragraph pointing at PROGRAM.md). PROGRAM.md is the operating spec; README is the landing page.

### Build is complete

You now have a working, lint-clean, git-initialized LLM Wiki. You can ingest your first source. Go to Part II.

---

# Part II — Operate the Wiki

Part II specifies the three operations you run against the wiki after setup: **ingest**, **query**, and **health**. Before diving in, read the page conventions (§1) and the context-cost rules (§5) — they are preconditions for everything that follows.

## 1. Page Conventions

### 1.1 Frontmatter

Every wiki page has YAML frontmatter at minimum:

```yaml
---
title: "..."
updated: YYYY-MM-DD
tags: [...]
summary: "1-2 sentence abstract — feeds the manifest registry"
domain: <domain-slug>        # MUST equal the parent directory name
---
```

Source pages additionally carry **exactly one** of:

- `source_file: "[[raw/archived/<filename>]]"` — a local raw file exists
- `source_url: "https://..."` — referenced by URL only, no local copy

Keep `summary:` current. It is read far more often than the body.

### 1.2 Wikilinks

- Use `[[slug]]` only. Never `[[wiki/<domain>/entities/slug]]`.
- Slugs resolve globally across domains. A page in domain A can link `[[foo]]` where `foo` lives in domain B; it works.
- `check-wikilinks.py` treats every `[[slug]]` as a hard reference — even inside tables and list items. **For speculative "not yet a page" references, use `` `code-span` `` or plain text instead.**

### 1.3 File names

Lowercase, hyphen-separated, `.md`. Example: `machine-learning.md`.

### 1.4 Inbound links

Every page should have at least one inbound link — from another page, the manifest, or the log. Orphans are flagged by the health check.

### 1.5 Verification tier

Every source page declares how trustworthy its content is, as italic prose near the top:

- `*Verified against PDF*` — cross-checked against a local PDF copy
- `*Verified against source code*` — cross-checked against actual source files
- `*Unverified — fetched via web tool*` — pulled through a summarizing web fetch, may be fabricated
- `*Unverified — synthesized from README/discussions*` — derived from marketing material, not primary evidence

Future-you and future-agents use this to decide how much to trust the page.

## 2. Ingest

Trigger: the human points at a source (a file in `raw/assets/`, a URL, a PDF) and asks you to ingest it.

### Step 2.1 Read the source

Read the source thoroughly. For PDFs, plan multiple reads if the tool has a page cap (typical: 20 pages per call). Read references last — they are lowest priority. Use `pdfinfo <file>` to get the exact page count before the first read.

For clipped web pages with associated local images, run `bash scripts/find-attachments.sh "<asset-title>"` to discover and read them — they are the canonical copies if the remote URLs rot.

### Step 2.2 Classify into a domain

Read only the `summary:` frontmatter line of each domain's manifest. Do **not** load full manifests. Compare the source against those summaries.

- Unambiguous → proceed with that domain.
- Ambiguous → **ask the human**. Never silently pick.

### Step 2.3 Load the chosen domain's full manifest

This is the only manifest loaded for this ingest. Read the prose (Scope / Key facts / Open questions / Cross-domain links) and the registry.

### Step 2.4 Search for overlap

Use scoped mechanical search inside the chosen domain before reading page bodies. Portable fallback:

```bash
rg -n "<query terms>" wiki/<domain>
```

Reference implementation:

```bash
qmd search "<topics>" -c vault-<domain>
```

Do not default to LLM reranking or local-model hybrid search. If the human explicitly enables those, warn that they can load local GGUF models, use significant RAM, run slowly on CPU-only machines, and use GPU/VRAM if available. The question you are answering: *does this material already live somewhere, even partially?*

### Step 2.5 Discuss takeaways with the human

Before writing pages, confirm scope and classification. Summarize what the source says, what new facts it adds, and which existing pages it likely touches.

### Step 2.6 Create or update pages

Write or update files in `wiki/<domain>/{sources,entities,concepts,analyses}/`. Every new page gets `domain: <domain>` matching its parent directory. A single source typically touches 5-15 pages — it creates the source page and updates entities, concepts, and possibly analyses that already existed. **Prefer updating existing pages over creating near-duplicates.**

Each subdirectory has a purpose:

- **`sources/`** — one page per ingested source. Summarizes what the source says. Links to entities/concepts/analyses it touches.
- **`entities/`** — people, organizations, products, places. The wiki's "who and what".
- **`concepts/`** — techniques, ideas, phenomena. The wiki's "how things work".
- **`analyses/`** — your synthesis pages. Opinion and argument built from the other three layers.

### Step 2.7 Update the manifest prose

If the source adds load-bearing facts, update the manifest's `Scope`, `Key facts`, `Open questions`, or `Cross-domain links` sections. **Never edit the fenced `<!-- REGISTRY:START ... REGISTRY:END -->` or `<!-- ANALYTICS:START ... ANALYTICS:END -->` blocks** — they are regenerated by script.

Update the manifest's `updated:` and `page_count:` frontmatter fields.

### Step 2.8 Regenerate the registry

```bash
bash scripts/build-registry.sh <domain>
```

### Step 2.9 Append to the log

New entries go at the **top** of `wiki/log.md`, immediately after the hint comment. Format:

```markdown
## [YYYY-MM-DD] ingest | <source title>

Domain: <domain>. <Brief summary of what was ingested and which pages were touched.>
```

### Step 2.10 Rebuild generated maps

```bash
python3 scripts/build-xrefs.py
python3 scripts/build-analytics.py
python3 scripts/build-xrefs.py
```

The second `build-xrefs.py` pass records links added by the generated analytics block.

### Step 2.11 Flag contradictions

If the new source contradicts existing wiki content, note the contradiction on both pages. Do not silently overwrite.

### Step 2.12 Verify (fresh context pass)

Audit the touched pages for:

- Frontmatter/domain alignment (`python3 scripts/check-frontmatter-domain.py`)
- Wikilinks resolve (`python3 scripts/check-wikilinks.py`)
- Math correctness (see §8 principles — no mental math)
- Manifest prose within budget (run `python3 scripts/detect-domain-divergence.py`)

If the harness offers a fresh-context/subagent mechanism, use it here to reduce context bias. Otherwise, run the same checks serially.

### Step 2.13 Re-index search

If your harness has a search index, refresh it. **Run indexing in the foreground** — background indexers competing for memory with other work have crashed machines in the reference example.

### Step 2.14 Archive and commit

Move the raw source from `raw/assets/` to `raw/archived/`. Commit the wiki changes:

```bash
git add wiki/
git commit -m "ingest: <Source Title>"
```

### 2.A Skip criteria

Not every source in the inbox deserves a page. Skip and archive (with a log note) when the source is:

- **Duplicate** — already covered by an existing source page
- **Derivative** — summarizes another source you already ingested
- **SEO spam** — keyword-stuffed, promo disguised as content
- **Too thin** — short post with no facts beyond what you have
- **Too broad** — catalog or list with no relevant analysis

When multiple sources cover the same event, **merge into one page** extracting facts from all of them, rather than one page per source.

### 2.B Cross-domain ingest

Cross-domain ingests require an **explicit instruction** from the human like *"ingest X as cross-domain a,b"*. Load both manifests, search both domain scopes, but still file pages in a **single primary domain** with wikilinks into the secondary. **Never duplicate a page across domains.**

### 2.C Batch ingest

When ingesting multiple sources in one session, split into two phases.

**Group by domain first.** A batch spanning two domains is two batches.

**Phase A — Parallel.** Spawn agents (or do it serially) to create source/concept/entity pages within a single domain. Each agent writes its own files. Group agents by theme to reduce concept overlap. **Never let parallel agents write to `_manifest.md`, `log.md`, `overview.md`, or `index.md`** — last writer wins.

**Phase B — Serial.** One pass after all agents complete:

1. Update the manifest prose if the batch added load-bearing facts. Never touch the REGISTRY fence.
2. Regenerate the registry for each touched domain.
3. Append batch entries to `log.md`.
4. Deduplicate overlapping concept/entity pages the parallel agents created.
5. Archive the raw sources.
6. Verify page counts match the manifest's `page_count:` frontmatter.
7. Re-index the search tool (foreground).
8. Single commit for the batch.

## 3. Query

Trigger: the human asks a question that should be answered from wiki knowledge.

### Step 3.1 Route to a domain

Read only each manifest's `summary:` line. Ambiguous → ask (*"this question could route to a or b — which should I use?"*).

### Step 3.2 Load the chosen domain's manifest

Prose + registry + analytics block. Gives you the key facts, high-degree pages, cross-domain bridges, stale load-bearing pages, and the list of pages worth searching.

### Step 3.3 Search

Use scoped mechanical search inside the chosen domain. Prefer a scoped keyword index if available; otherwise use `rg -n "<query terms>" wiki/<domain>`. Hybrid semantic search or LLM reranking is opt-in only after the compute-heavy warning in Part 0 §0.3.

### Step 3.4 Read relevant pages via progressive disclosure

See §5 — do not read full pages unless you are actively editing them.

### Step 3.5 Synthesize the answer

Respond with `[[wikilink]]` citations pointing to the source pages you drew from.

### Step 3.6 Offer to file the answer

If the answer is substantial and reusable, offer to file it as `wiki/<domain>/analyses/<slug>.md` with proper frontmatter. If the human accepts, write the page, regenerate the registry, prepend the log entry, rebuild xrefs, rebuild analytics, then rebuild xrefs again.

### Step 3.7 Append to the log

```markdown
## [YYYY-MM-DD] query | <question summary>

Domain: <domain>. <Brief summary of the answer and pages consulted.>
```

### 3.A Cross-domain query

Requires `--cross-domain a,b` or equivalent explicit instruction. Load both manifests, search both domain scopes, but file any resulting analysis into a single primary domain with cross-links.

## 4. Health

Two modes.

### 4.1 `health <domain>` — deep per-domain

Runs contradictions, math verification, knowledge gaps, and (optionally) web research to fill gaps. Token-heavy. Run one domain per day.

**Checks:**

- All structural checks from §4.2, scoped to the domain
- Contradiction detection — for each high-value claim category in the domain, search all pages that discuss it and verify consistency
- Math verification — **all math verified with Python**, never computed by the LLM. Mark verified lines with `<!-- math-verified: YYYY-MM-DD -->`. Re-verify if > 90 days old.
- Knowledge gap identification — grep for uncertainty markers, cross-source transfer claims without caveats, temporal staleness, unquantified qualitative claims
- Web research — fill fillable gaps via high-trust sources. **Never silently update the wiki from web research.** Report findings, let the human approve.

**Fix-verify loop.** If the check finds FAILs, fix them, then verify the fixes landed and did not introduce new errors. If the harness offers a fresh-context/subagent mechanism, use it for independent verification; otherwise verify serially in the same harness. Max 3 iterations; escalate to the human after that.

### 4.2 `health --structural` — cheap global lint

Runs across all domains:

- Page counts vs each manifest's `page_count:` frontmatter
- `python3 scripts/check-wikilinks.py` — every `[[slug]]` resolves
- `python3 scripts/check-frontmatter-domain.py` — every page's `domain:` matches its directory
- Slug collision check: `find wiki/*/ -name '*.md' -not -name '_*' -exec basename {} .md \; | sort | uniq -d` should be empty
- Orphan detection — pages with no inbound links (excluding log, overview, index)
- `python3 scripts/detect-domain-divergence.py` — manifest pressure + graph community detection
- `bash scripts/find-near-duplicates.sh 0.70` — optional BM25 near-duplicate scan when a scoped search adapter is configured; skip or replace it if the harness has no indexed search

### 4.3 `health --domain-scan` — divergence only

Runs only `detect-domain-divergence.py`. Useful when you suspect sprawl but cannot budget a full structural pass.

### 4.4 No `health --all`

There is no combined mode. Comprehensive coverage = one `--structural` run + one `health <domain>` run per domain, on **separate days**. Running everything at once defeats the context-saving design.

### 4.5 Error propagation

After fixing any wrong value (a number, a claim, a date), **grep the whole wiki for the old value**. Wrong numbers typically appear in 3-5 places: source page, concept page, log, manifest, xrefs.json.

## 5. Context-Cost Management

Reading pages is the dominant session cost. These rules are load-bearing.

1. **Manifest-first.** Read the manifest before anything else.
2. **Never load a full manifest to classify.** Read only the `summary:` field of each manifest. Load a full manifest only after the domain is chosen.
3. **Progressive disclosure — three tiers:**
   - **Discovery**: search results + manifest registry + analytics block + frontmatter `summary` fields. Most pages stop here.
   - **Structure**: section headings + first line of each section. Use offset/limit if the harness supports partial reads.
   - **Full content**: only the specific section being edited.
4. **Only read full pages for pages you are actively editing.** For cross-references and relevance checks, manifest registries and frontmatter summaries suffice.
5. **Use `xrefs.json` instead of grep** to check what links to a page. It contains inbound and outbound links for every page in the wiki.
6. **Log compaction.** When `log.md` exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. Keep recent entries for session context.
7. **Git-aware session start.** For returning sessions, check `git log --oneline -10` and `git diff HEAD~3 --stat -- wiki/`. Only re-read pages that changed **and** that the current task touches.

## 6. Invariants

Structural rules that scripts enforce. Violating any is a lint failure.

1. Every page's `domain:` frontmatter matches its parent directory name.
2. Every wikilink is slug-only (`[[slug]]`), not a path.
3. Every source page carries exactly one of `source_file:` or `source_url:`.
4. No two pages share a basename (slug collisions are disallowed).
5. Every page has at least one inbound link.
6. Each manifest's `page_count:` matches the actual file count in the domain (excluding `_manifest.md`).
7. Each manifest's prose region (before `<!-- REGISTRY:START`) stays within the 3,000-token budget.
8. The fenced REGISTRY block is never edited by hand.
9. No `_meta` directory — cross-cutting topics live in their primary domain and are linked from anywhere.
10. No page is duplicated across domains.
11. Raw source contents are immutable. The allowed mutation is moving processed inbox files from `raw/assets/` to `raw/archived/`.

## 7. Git Workflow

- Commit after each ingest or batch of related changes.
- Format: `ingest: <Source Title>` / `query: <Question summary>` / `lint: <Description>` / `refactor: <Structural change>`.
- Only `wiki/` is tracked. `raw/` is gitignored — sources stay local.

## 8. Principles

- **Never modify `raw/`.** Sources are immutable; ingest produces wiki pages, it does not edit the source.
- **Verify fetched content.** Any tool that goes through an intermediate summarizing model (e.g. a web-fetch layer) can fabricate details. When a local copy exists, cross-check against it. Tag source pages with the verification tier from §1.5.
- **Apply skepticism to social-media sources.** Extract verifiable facts and core ideas, not the author's framing. When a thread references a paper or repo, cite the primary source instead.
- **README claims ≠ code reality.** For repos central to an analysis, verify architectural claims against actual source code via a fresh-context/subagent mechanism if available, or a dedicated read pass otherwise. Keep the main context lean: return only a verification table (claim → status → evidence) plus verdict.
- **Every ingest touches multiple pages.** A single source typically updates 5-15 pages within one domain.
- **Cross-reference aggressively.** The connections between pages are as valuable as the pages themselves.
- **Prefer updating over creating.** If a relevant page exists, update it.
- **Flag uncertainty.** Mark unverifiable claims on the page itself, not just mentally.
- **Never do mental math.** LLMs hallucinate calculations. Any number that enters the wiki must be computed by a tool (Python, bash, calculator) first. This applies to formulas, percentages, unit conversions, edge values — anything derived.
- **Keep manifests current.** When a load-bearing fact enters the wiki, update the manifest prose in the same pass, then regenerate the registry.
- **Keep the log honest.** It is the audit trail.
- **Memory-heavy operations run in the foreground.** Background indexing jobs competing with other work has crashed machines.
- **Surface assumptions before writing.** If you are about to make a non-trivial structural decision (a new domain, a merge, a contradiction call), state your assumptions and wait for the human to correct them.
- **Scope discipline.** Touch only what the task requires. Do not "clean up" adjacent pages as a side effect.

---

# Part III — Evolve the Wiki

## 1. Adding a Domain

You need a new domain when the divergence scanner (§2) flags an existing domain as too broad, or when the human brings a new topic area that does not fit any existing domain's `summary:`.

**Always ask the human first.** Adding a domain is an architectural decision.

Once approved:

1. `mkdir -p wiki/<new>/{sources,entities,concepts,analyses}`
2. Write `wiki/<new>/_manifest.md` using the skeleton template from Part I §6.2
3. Add the new domain to `wiki/index.md` and `wiki/overview.md`
4. If your harness has a search tool with per-collection scoping, register a new collection
5. `python3 scripts/build-xrefs.py` to refresh the graph
6. `python3 scripts/build-analytics.py` when the new domain has real pages beyond its manifest
7. `python3 scripts/build-xrefs.py` again after analytics generation
8. `python3 scripts/check-frontmatter-domain.py` to confirm the layout is valid
9. Commit: `refactor: add <new> domain`

The scripts (`check-frontmatter-domain.py`, `check-wikilinks.py`, `build-xrefs.py`, `detect-domain-divergence.py`, `find-near-duplicates.sh`) auto-discover domains from immediate children of `wiki/`. You do not need to edit any script.

## 2. Domain Evolution (Split / Merge)

Starting domains are a **starting state, not a target state**. Domains split when a manifest can no longer compress their content, and merge when they become too small and tightly coupled to a neighbor. **The scanner flags; the human decides.** No automatic moves.

### 2.1 Manifest-pressure trigger (primary, cheap)

Measure the token count of the manifest prose region (everything before `<!-- REGISTRY:START`). The registry is exempt.

| Level | Threshold | Action |
|---|---|---|
| Warning | prose ≥ 2,500 tokens | Note in report |
| Split candidate | prose ≥ 3,000 tokens | Flag; investigate with the graph trigger |
| Hard fail | prose ≥ 3,500 tokens | Blocking — split before next ingest |

Measurement: `detect-domain-divergence.py` approximates via `wc -w × 0.75`. For precise measurement, install `tiktoken` and use `cl100k_base`.

### 2.2 Graph-community trigger (secondary, richer)

Requires `networkx`. `detect-domain-divergence.py` runs this automatically when available. It builds the induced subgraph from `xrefs.json` (nodes = domain pages, edges = wikilinks with both endpoints in the domain, undirected), runs Louvain community detection, and computes modularity Q.

Flag as a split candidate when **all** of the following hold:

- Q ≥ 0.40
- At least two communities each have ≥ 15 pages
- The top two communities cover ≥ 80% of the domain
- Cross-cluster edge density < 25% of within-cluster density

### 2.3 Split report

```
DOMAIN SPLIT CANDIDATE: <domain>
  Triggers: [manifest-pressure: 3,420 / 3,000] [graph: Q=0.47, 3 communities]
  Cluster A (32 pages): <top pages by degree>
  Cluster B (28 pages): ...
```

### 2.4 After a split (if the human accepts)

1. Create the new domain directory, manifest, and (if applicable) search collection — per §III.1
2. `git mv` the cluster's pages into the new domain
3. Update `domain:` frontmatter on each moved page to match the new directory
4. `python3 scripts/build-xrefs.py`
5. `python3 scripts/build-analytics.py`
6. `python3 scripts/build-xrefs.py`
7. `python3 scripts/check-wikilinks.py` — wikilinks should still resolve because they are slug-based
8. Update the original manifest with a "see also" pointer to the new domain
9. Update `wiki/overview.md` and `wiki/index.md`
10. Commit: `refactor: split <old> into <old> + <new>`

### 2.5 Merge candidates (conservative)

`detect-domain-divergence.py` flags a domain for merge when **all** hold:

- < 10 pages
- ≥ 80% of outbound wikilinks point to a single other domain
- Manifest prose < 1,000 tokens
- Not marked `pinned: true` in manifest frontmatter

**Pinning escape hatch.** Set `pinned: true` in the manifest frontmatter to suppress merge flagging for intentionally small domains. No domain is ever auto-merged.

### 2.6 Removing a domain

Move or delete its pages (`git mv` preserves history), `rm -rf wiki/<name>/`, remove its entry from `index.md` and `overview.md`, rebuild xrefs, run the link checker to confirm nothing dangles.

---

# Part IV — Meta

## 1. What This File Is, and Is Not

**This file is** a portable, harness-agnostic build-and-operate contract for a domain-atomized LLM Wiki. An LLM in any harness — with this reference repository plus file-read, file-write, shell, and (ideally) web-fetch tools — should be able to read this file and:

1. Bootstrap a target vault from the reference repo (Part I)
2. Operate it day-to-day (Part II)
3. Evolve its shape as it grows (Part III)

**This file is not** a standalone artifact dump, tutorial, user manual, or theoretical defense of the design. The accompanying reference repository is part of the contract and includes `SPEC.md` (architectural rationale), `scripts/` (canonical verification and generation tools), `CLAUDE.md` (harness-agnostic agent operating notes using a compatibility filename), and a `.claude/skills/` directory (optional adapter examples).

## 2. Harness Portability

References to specific tools throughout this file — `qmd`, `git`, `networkx`, `tiktoken`, `pdfinfo`, web fetch tools — are examples from the working reference implementation. In a different harness, substitute the local equivalent:

- **Search**: scoped mechanical keyword search by default (`rg` or a per-domain index such as `qmd search`); hybrid semantic search or LLM reranking only after explicit opt-in and the compute-heavy warning in Part 0 §0.3
- **Graph analysis**: any library with community detection (or skip the graph trigger and rely on the manifest-pressure trigger, which needs nothing beyond `wc`)
- **Tokenizer**: any tokenizer compatible with modern LLMs (or fall back to `wc -w × 0.75`)
- **PDF reader**: any PDF tool (or skip PDF ingest)
- **Web fetcher**: any web fetch tool (or skip URL ingests)
- **Subagent spawning**: any way to get a fresh context (or run verification serially)

The **rules** — manifest-first reading, per-domain scoping, slug-based wikilinks, the 3,000-token prose budget, the invariants in Part II §6 — do not depend on any specific tool.

## 3. Extending This File

After bootstrap, the human will almost certainly want to add vault-specific rules: routing hints for topics that overlap multiple domains, project-specific verification standards, cost constraints for token-heavy operations, pointers to related code repositories, etc.

**Do not edit Parts I-IV of this file** to add those rules — keep PROGRAM.md portable and diff-able against the upstream template. Instead, create or update a companion agent-notes file. The reference implementation uses `CLAUDE.md` as a compatibility filename; mirror it to `AGENTS.md` or another harness-native filename if needed. That file can reference this one for the portable baseline.

## 4. Quick Reference

| Situation | Action |
|---|---|
| New target vault, need to start | Part I, Steps 1-9 |
| New source in the inbox | Part II §2 (ingest) |
| Question from the human | Part II §3 (query) |
| Structural lint | Part II §4.2 |
| Deep review of one domain | Part II §4.1 (one domain at a time, not same day as structural) |
| Manifest feels crowded | Run `detect-domain-divergence.py`; see Part III §2.1 thresholds |
| Domain feels tiny and derivative | Check merge criteria (Part III §2.5); ask the human |
| Need a new domain | Part III §1 — ask the human first |
| Number goes into the wiki | Compute with a tool, never mental math (Part II §8) |
| Uncertain which domain | Ask the human. Never silently pick. |
