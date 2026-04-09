# LLM Wiki — Schema

You maintain a personal knowledge wiki built on the LLM Wiki pattern. Your job: summarize, cross-reference, file, maintain. The human curates sources and asks questions.

This is the **agent-facing schema** for Claude Code. Companion files: `README.md` (human intro), `SPEC.md` (architecture source of truth), future `PROGRAM.md` (portable prompt spec).

**Privacy notice**: this vault is git-versioned. Anything written into `wiki/` enters git history and remains recoverable even after deletion. If you push to a public remote, your wiki (and its deleted versions) is public. Keep `raw/` gitignored, think before pushing, and decide whether a topic belongs here *before* ingesting. History rewrites are messy — see [GitHub's docs on removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) before attempting one.

## Directory Structure

The wiki is **physically partitioned by domain.** Each domain owns its pages, manifest, and search collection.

```
Vault/
├── raw/                    # Sources (human-managed, gitignored)
│   ├── assets/             # Inbox — unprocessed
│   └── archived/           # Processed
├── wiki/                   # LLM-maintained markdown
│   ├── index.md            # Thin pointer → domain manifests
│   ├── overview.md         # One-line description per domain
│   ├── log.md              # Append-only activity log
│   ├── xrefs.json          # Auto-generated cross-reference map
│   └── <domain>/
│       ├── _manifest.md    # Prose + auto-generated registry
│       ├── sources/
│       ├── entities/
│       ├── concepts/
│       └── analyses/
├── scripts/                # check-wikilinks, check-frontmatter-domain, build-registry, build-xrefs, detect-domain-divergence, ...
├── .claude/skills/         # ingest, query, health workflows
├── CLAUDE.md               # This file
├── SPEC.md                 # Architecture source of truth
└── README.md
```

The template ships with two placeholder domains (`research`, `projects`). Rename freely; scripts auto-discover domains from immediate children of `wiki/`.

### Per-domain scoping rules

- **Operations default to single-domain.** `/ingest`, `/query`, `/health` route to exactly one domain unless the user opts into cross-domain.
- **Manifest-first reading.** Read `wiki/<domain>/_manifest.md` first. It's the load-bearing context-compression artifact (≤3,000 token prose budget + auto-generated registry). Never grep the whole wiki when a manifest will do.
- **To classify, read only the `summary:` line** of each manifest — not the full file. Load a full manifest only after choosing the domain.
- **Cross-domain wikilinks are cheap** — Obsidian and qmd resolve by slug across the vault. Link freely; don't read the linked page unless the task needs it.
- **One canonical copy per topic.** Never duplicate pages across domains.
- **Every page's `domain:` frontmatter must match its parent directory.** Enforced by `scripts/check-frontmatter-domain.py`.

## Page Conventions

- YAML frontmatter minimum: `title`, `updated`, `tags`, `summary`, `domain`
- `domain:` must equal the parent directory name
- `summary` is a 1-2 sentence abstract used for context-efficient reading — keep it current
- Wikilinks use `[[slug]]` only — never `[[wiki/<domain>/entities/slug]]`
- File names: lowercase, hyphens (`machine-learning.md`)
- Every page needs at least one inbound link (another page, the manifest, or the log)
- Source pages carry exactly one of:
  - `source_file: "[[raw/archived/<filename>]]"` — local raw file
  - `source_url: "https://..."` — referenced by URL, no local copy
- For speculative "not yet a page" references in prose, use `code-span` or plain text, NOT `[[slug]]` — `check-wikilinks.py` treats every `[[slug]]` as a hard reference.

## Source Formats

`raw/` is gitignored; only the wiki layer is versioned.

Accepted: markdown, PDFs, images, URLs. For URLs: fetch, save as `raw/assets/YYYY-MM-DD-slug.md` with a YAML header noting the original URL, then ingest normally.

### PDF reading

Max 20 pages per `Read` call. For long papers plan multiple reads (intro+model, results+discussion, references last). Run `pdfinfo <file>` first to get the page count.

## Operations

### Ingest

`/ingest <source>` — see `.claude/skills/ingest/SKILL.md` for the full flow.

1. **Read** the source thoroughly
2. **Classify** — match against each manifest's `summary:` line. Ambiguous → ask. Never silently pick.
3. **Load the chosen domain's `_manifest.md`** — the only manifest loaded for this ingest
4. **Search overlap** — `qmd search "<topics>" -c vault-<domain>`. Always pass `-c`.
5. **Discuss** key takeaways with the human
6. **Create or update pages** in `wiki/<domain>/{sources,entities,concepts,analyses}/` with matching `domain:` frontmatter
7. **Update manifest prose** (Scope / Key facts / Open questions / Cross-domain links) if the source adds load-bearing facts. Never edit the fenced `<!-- REGISTRY:START … REGISTRY:END -->` block.
8. **Regenerate the registry**: `bash scripts/build-registry.sh <domain>`
9. **Append to `wiki/log.md`** with the domain noted
10. **Flag contradictions** on both pages
11. **Verify (fresh subagent)** — frontmatter/domain, wikilinks, math, manifest budget
12. **Re-index**: `qmd update && qmd embed` (foreground only — never `&`)
13. **Archive** `raw/assets/` → `raw/archived/`, **commit** `ingest: Source Title`

Cross-domain ingests require explicit instruction (`ingest X as cross-domain a,b`). Load both manifests, search both collections, but still file pages in a single *primary* domain with wikilinks into the secondary.

### Skip Criteria

Skip and archive (with a log note) when the source is **duplicate**, **derivative**, **SEO spam**, **too thin**, or **too broad**. When multiple sources cover the same event, **merge into one** rather than creating separate pages.

### Query

`/query <question>` — see `.claude/skills/query/SKILL.md`.

1. **Route** — match the question against each manifest's `summary:` line. Ambiguous → ask.
2. **Load the chosen `_manifest.md`**
3. **Search** — `qmd search -c vault-<domain>` (keyword) or `qmd query -c vault-<domain>` (hybrid + rerank). Always pass `-c`.
4. **Read** relevant pages via progressive disclosure
5. **Synthesize** an answer with `[[wikilink]]` citations
6. If substantial and reusable, **offer to file** as `wiki/<domain>/analyses/<slug>.md`, then `build-registry.sh`
7. **Append to `wiki/log.md`**

Cross-domain: `--cross-domain a,b`. File into the primary domain with cross-links.

### Health

`/health` — see `.claude/skills/health/SKILL.md`.

- **`/health <domain>`** — deep per-domain: contradictions, math, gaps, web research
- **`/health --structural`** — cheap global lint: page counts, wikilinks, frontmatter/dir alignment, slug collisions, manifest pressure, near-duplicates, divergence scan
- **`/health --domain-scan`** — divergence scanner only

No `/health --all`. Full coverage = `--structural` + one deep domain run per domain, on separate days.

**Error propagation**: after fixing a wrong value, grep the whole wiki for the old value — wrong numbers typically appear in 3-5 places (source, concept, log, manifest, xrefs.json).

## Principles

- **Never modify `raw/`** — sources are immutable
- **Verify fetched content** — WebFetch's intermediate model can fabricate. Cross-check against local PDFs. Tag source pages with `*Verified against PDF*` or `*Unverified — fetched via WebFetch*`.
- **Apply skepticism to social-media sources** — extract facts and core ideas, not framing. Flag unverified claims.
- **README claims ≠ code reality** — verify architectural claims against actual source. For central repos, spawn a subagent to fetch files via `raw.githubusercontent.com/...` (and directory listings via `api.github.com/repos/.../contents/...`) so raw code never enters the main context. Tag `*Verified against source code*` or `*Unverified — synthesized from README*`.
- **Every ingest touches multiple pages** — a single source typically updates 5-15 pages within one domain
- **Cross-reference aggressively** — connections are as valuable as pages
- **Prefer updating over creating** — avoid near-duplicates
- **Flag uncertainty** — mark unverifiable claims
- **Never do mental math** — LLMs hallucinate calculations. Compute with Python/bash first, paste the result. Applies to all derived numbers.
- **Keep manifests current** — update prose when load-bearing facts enter, then regenerate the registry
- **Keep the log honest**
- **Never run `qmd embed &`** — memory-heavy, has crashed machines. Foreground only.

## Context Cost Management

Reading pages is the dominant session cost. Minimize unnecessary reads.

- **Manifest-first.** The manifest is prose + a registry enumerating every page with its one-sentence summary — usually enough to decide what to search and load.
- **Never load a full manifest to classify.** Read only its `summary:` field.
- **Progressive disclosure (three tiers)**:
  1. **Discovery** — `qmd search` + registry + frontmatter summaries
  2. **Structure** — section headings + first line of each (use `offset`/`limit`)
  3. **Full content** — only the specific section being edited
- **Only read full pages for pages you are actively editing.**
- **Use `xrefs.json` instead of grep** to check connections. Regenerate with `python3 scripts/build-xrefs.py`.
- **Log compaction**: when `log.md` exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. New entries go at the **top** (reverse-chronological), just after the hint comment.
- **Git-aware session start**: for returning sessions, run `git log --oneline -10` and `git diff HEAD~3 --stat -- wiki/` to see what changed — only re-read pages the current task touches.

## Git Workflow

- Commit after each ingest or batch
- Format: `ingest: Title` / `query: Summary` / `lint: Description`
- Only `wiki/` is tracked; `raw/` is gitignored

## Quick Reference

| Command | Purpose |
|---------|---------|
| `ls raw/assets/*.md` | Check inbox |
| `find wiki/* -maxdepth 0 -type d` | List domains |
| `find wiki/<domain> -name '*.md' -not -name '_manifest.md' \| wc -l` | Per-domain page count |
| `qmd search "q" -c vault-<domain>` | Keyword search |
| `qmd query "q" -c vault-<domain>` | Hybrid search with rerank |
| `qmd update && qmd embed` | Re-index (foreground only) |
| `bash scripts/build-registry.sh <domain>` | Regenerate manifest registry |
| `python3 scripts/build-xrefs.py` | Regenerate xrefs.json |
| `python3 scripts/check-frontmatter-domain.py` | Verify `domain:` alignment |
| `python3 scripts/check-wikilinks.py` | Verify wikilinks resolve |
| `python3 scripts/detect-domain-divergence.py` | Divergence scan |

## Skill Shell Commands

Skill `!` backtick commands must be single commands — no `||`, `&&`, pipes, or non-ASCII. The permission checker rejects compound commands. Handle fallbacks in the skill workflow, not the command. If a skill command fails, fall back to doing the op manually.

## Batch Ingest

Group by domain first — a batch spanning multiple domains is multiple batches.

**Phase A (parallel)**: Agents create source/concept/entity pages within a single domain. No shared file writes. Group agents by theme to reduce overlap.

**Phase B (serial)**: One pass after all agents complete:
1. Update manifest prose (never the REGISTRY block)
2. `bash scripts/build-registry.sh <domain>`
3. Append batch entries to `wiki/log.md`
4. Deduplicate overlapping concept/entity pages
5. Archive sources
6. Verify page counts match manifest `page_count:` frontmatter
7. `qmd update && qmd embed` (foreground)
8. Single commit

**Never** let parallel agents write to `_manifest.md`, `log.md`, `overview.md`, or `index.md` — last writer wins.

## Customising This File

After forking, extend with vault-specific rules in clearly-marked sections at the bottom so the portable schema above stays diff-able against the upstream template:

- **Routing rules** for overlapping page roles
- **Project references** to connected code repos, notebooks, etc.
- **Domain-specific verification rules** (known unreliable sources, canonical citations)
- **Cost rules** (token budgets, model-selection constraints)
