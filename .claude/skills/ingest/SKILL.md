---
name: ingest
description: Ingest a source into the wiki. Use when the user adds a new document, URL, or file to raw/ and wants it processed into wiki pages.
argument-hint: [source-path-or-url] [as cross-domain a,b]
---

# Ingest Source

Process the source(s) at `$ARGUMENTS` into the wiki. **Default mode is single-domain** — the ingest routes to exactly one of `wiki/research/` or `wiki/projects/`. Cross-domain ingests are the exception and require explicit user instruction (see step 3). **Batch arguments are allowed** — if `$ARGUMENTS` describes a group of files or gives free-form batch instructions instead of naming a single file, list `raw/assets/` manually in step 1, group by domain, and run the workflow per-domain per the "Batch Ingest" section in `CLAUDE.md`.

## Local attachments lookup (per-source, run in step 1 or 2)

Attachment discovery is run manually per-source, NOT via a `!` shell hook at skill launch. Reason: `$ARGUMENTS` can contain apostrophes, spaces, or descriptive batch instructions that trip Claude Code's permission checker and block the entire skill from running. Instead, once a source file is identified in step 1, run the lookup for that specific file:

```
bash scripts/find-attachments.sh '<source-title-without-.md>'
```

Use **single quotes** around the title — Obsidian Web Clipper titles often contain `$`, `&`, `(`, `)`, or apostrophes which double quotes silently mangle. If the command returns image paths, those are locally-saved images extracted by Obsidian (Ctrl+Shift+D) from the original page. Read each one with the `Read` tool — they're often diagrams, screenshots, or figures referenced via remote URLs that may rot. Treat the local image as canonical. Empty output means no local images exist.

## Domain manifest summaries (classification input)

!`grep -h '^summary:' wiki/research/_manifest.md wiki/projects/_manifest.md 2>/dev/null | head -2`

These one-line summaries are the ONLY content you should read from the manifests during classification (step 3 below). Do not read either full manifest until after you have chosen a domain.

## Workflow

1. **Locate the source.** If `$ARGUMENTS` is a URL, fetch it with WebFetch, save as `raw/assets/YYYY-MM-DD-slug.md` with a YAML header noting the original URL. If it's a file path, read it from `raw/`.

2. **Read the source thoroughly.** Extract key information, claims, entities, and concepts. If the "Local attachments for this source" block above listed any images, Read them now alongside the markdown.

3. **Classify into a domain.** Match the source against the two manifest summaries shown above (`research` vs `projects`).
   - **Default = single-domain.** If exactly one summary obviously fits (terms from one summary appear in the source's title, frontmatter tags, or first few paragraphs and the other does not), proceed to that domain.
   - **Ambiguous = ask.** If neither fits or both fit, ask the user with a two-option choice: "Classify as `research` or `projects`?" Never silently pick one.
   - **Cross-domain = explicit opt-in only.** If the user's original instruction was `ingest X as cross-domain research,projects` (or similar), follow the cross-domain path: load BOTH manifests, create pages in the user-specified primary domain, and add explicit wikilinks to the secondary domain. Cross-domain is rare — single-domain is the default.
   - **Never load the full manifest just for classification.** The summaries are enough. Loading the wrong manifest wastes the whole context-savings point of this architecture.

   For the rest of this workflow, `<domain>` refers to the chosen primary domain.

4. **Load the chosen domain's full `_manifest.md`.** Now (and only now) read `wiki/<domain>/_manifest.md` in full — prose + auto-generated registry. The registry tells you what entities/concepts/analyses/sources already exist in the domain; the prose tells you the load-bearing key facts to check the source against.

5. **Search for overlap.** Use `qmd search "<topics>" -c vault-<domain>` where `<topics>` are derived from the source's title, frontmatter tags, and first 200 words of body. Progressive disclosure: read frontmatter summaries of qmd hits first, only read full pages you'll actually update. Always pass a `-c vault-<domain>` argument — unscoped `qmd search` (or scoping to the other domain's collection) defeats the whole domain-atomization design.

6. **Discuss with the user.** Briefly share the key takeaways and ask if they want to emphasize anything before filing.

7. **Create a summary page** in `wiki/<domain>/sources/` with (track all files created or modified in steps 7-13 for the verification prompt in step 14):
   - YAML frontmatter: `title`, `updated`, `tags`, `summary`, `domain: <domain>`, `source_file`
   - Summary of key points
   - Notable claims, data, quotes
   - `[[wikilinks]]` to relevant entity and concept pages (slug-only, no path prefix — `[[example-entity]]` not `[[research/entities/example-entity]]`)

8. **Create or update entity pages** in `wiki/<domain>/entities/` for people, organizations, places, products mentioned. **Search qmd first** (`-c vault-<domain>`) to find existing pages to update. Every entity page needs `domain: <domain>` frontmatter.

9. **Create or update concept pages** in `wiki/<domain>/concepts/` for key ideas, themes, frameworks. **Search qmd first** (`-c vault-<domain>`) to find existing pages to update. Every concept page needs `domain: <domain>` frontmatter.

10. **Update the domain manifest's prose** (`wiki/<domain>/_manifest.md`) **if** the new source adds load-bearing key facts to Scope, Key facts, Open questions, or Cross-domain links. Do NOT edit the fenced `<!-- REGISTRY:START ... REGISTRY:END -->` block — that is regenerated by script in step 11. Keep the prose region under 3,000 tokens (rough check: `awk '/<!-- REGISTRY:START/{exit} {print}' wiki/<domain>/_manifest.md | wc -w` × 0.75).

11. **Regenerate the manifest registry.** Run:
    ```
    bash scripts/build-registry.sh <domain>
    ```
    This rewrites the `<!-- REGISTRY:START ... REGISTRY:END -->` block in the manifest based on the current frontmatter of every page in the domain. Idempotent — safe to re-run.

12. **Append to `wiki/log.md`** (global — stays at wiki root):
    ```
    ## [YYYY-MM-DD] ingest | Source Title
    Domain: <domain>. Summary of what was ingested and what pages were created/updated.
    ```

13. **Flag contradictions** — if the new source contradicts existing wiki content (same domain or cross-domain via wikilinks), note it on both the source page and the contradicted page.

14. **Verify (fresh subagent)** — before archiving or committing, spawn a verification subagent (Agent tool) to audit the pages you just created or updated. The subagent has no context from the ingest — it sees only the files.

    Subagent prompt:
    ```
    Verify a wiki ingest. Read each file listed below and check:

    Source page: wiki/<domain>/sources/[name].md
    Other pages touched: [list]

    For each page:
    1. YAML frontmatter has title, updated, tags, summary, domain
    2. domain: frontmatter matches the parent directory (wiki/<domain>/...)
    3. All [[wikilinks]] resolve to existing files (run scripts/check-wikilinks.py)
    4. Any numerical claims are correct — run formulas in Python, do NOT compute mentally
    5. Claims attributed to cited sources actually match those sources (spot-check 3-5)
    6. No stale data contradicts existing wiki pages (qmd search key claims -c vault-<domain>)
    7. Source skepticism level is appropriate (X/Twitter flagged, GitHub trusted, etc.)
    8. Manifest prose region is still under 3,000 tokens if the manifest was edited

    Report PASS or FAIL per page. For FAIL items, state what's wrong and the correct value.
    ```

    If the subagent returns FAIL: fix the issues, then re-run verification (max 2 retries). If still failing after 2 retries, report to user and commit what's clean.

15. **Archive** — move processed source from `raw/assets/` to `raw/archived/`. Use **single quotes** around paths — Obsidian Web Clipper filenames often contain `$`, `&`, `()` which double quotes silently mangle. Move each file in a separate command to avoid `&&` chains silently skipping files after a mid-chain failure.

16. **Re-index** — run `qmd update` first (rescans files, adds new pages to the BM25 index), then `qmd embed` (generates vectors for the new chunks). Both commands operate across all collections, so single invocations cover both `vault-research` and `vault-projects`. `qmd embed` alone will silently skip new pages if `qmd update` hasn't run first, because `embed` only processes chunks the index already knows about.

    **Never run `qmd embed` in the background with `&`.** It's memory-heavy and has crashed the machine when combined with other work. Run foreground or use the Bash tool's `run_in_background: true`.

17. **Commit** with message format: `ingest: Source Title`. Include the domain in the commit body for per-domain audit trail.

## Cross-domain ingests (exception path)

Only taken when the user explicitly requests cross-domain, e.g. `ingest example-source as cross-domain projects+research`.

Steps that change:
- Step 4: load BOTH manifests.
- Step 5: run `qmd search` twice, once per collection (`-c vault-projects` then `-c vault-research`).
- Steps 7-9: create pages in the **primary** domain (the one listed first or explicitly marked). Add wikilinks across to the secondary domain — the linked pages remain in their own domain, never duplicated.
- Step 11: run `build-registry.sh` for the primary domain. If the secondary manifest needs updated key facts (e.g., an existing page's summary changed), re-run `build-registry.sh` for the secondary as well.
- Step 12: the log entry notes both domains: `Domain: <primary>, cross-domain with <secondary>`.

Cross-domain is rare. Single-domain is the default. If in doubt, go single-domain and link to the other side.

## Rules

- Never modify files in `raw/` (except when saving a fetched URL)
- A single source typically touches 5-15 wiki pages — all in the same domain unless cross-domain
- Use `[[wikilinks]]` (slug only) for all cross-references — Obsidian resolves by slug, so `[[example-entity]]` works whether the entity lives in `research` or elsewhere
- All new pages need YAML frontmatter with `title`, `updated`, `tags`, `summary`, and `domain`
- Every page's `domain:` frontmatter MUST match the directory it's written to (`wiki/<domain>/...`) — `scripts/check-frontmatter-domain.py` enforces this
- File names: lowercase, hyphens for spaces
- Prefer updating existing pages over creating near-duplicates
- Never duplicate a page across domains — one canonical copy per topic, linked from anywhere
