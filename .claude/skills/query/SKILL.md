---
name: query
description: Query the wiki to answer a question. Use when the user asks a question that should be answered from wiki knowledge, with citations.
argument-hint: [question] [--cross-domain a,b]
---

# Query Wiki

Answer the question: **$ARGUMENTS**

**Default mode is single-domain.** The query routes to exactly one of `wiki/research/` or `wiki/projects/`. Cross-domain queries require `--cross-domain a,b` and pay a higher context cost — only use when the question genuinely spans domains.

## Domain manifest summaries (routing input)

!`grep -h '^summary:' wiki/research/_manifest.md wiki/projects/_manifest.md 2>/dev/null`

These one-line summaries are the ONLY manifest content you should load during routing. Do not read either full manifest until after you have chosen a domain.

## Workflow

1. **Parse arguments.** Separate the question from flags. If `$ARGUMENTS` contains `--cross-domain a,b` (or `--cross-domain research+projects`), strip it and take the cross-domain path (step 2b). Otherwise, take the single-domain path (step 2a).

2a. **Route to a domain (single-domain default).** Match the question against the two manifest summaries shown above:
   - **Unambiguous** — if exactly one summary obviously fits (terms from the question appear in one summary and not the other), proceed to that domain.
   - **Ambiguous** — if neither fits or both fit, ask the user with a two-option choice: "Answer from `research`, `projects`, or `--cross-domain`?" Never silently pick.
   - **Never load the full manifest just to route.** The summaries are enough.

   For the rest of this workflow, `<domain>` refers to the chosen domain.

2b. **Cross-domain routing.** Parse the `--cross-domain` argument to get the list of domains (usually two). Proceed to step 3 with that list — you'll load multiple manifests and search multiple collections.

3. **Load the chosen domain's manifest** — read `wiki/<domain>/_manifest.md` in full (or both manifests for cross-domain). The prose tells you the load-bearing key facts; the auto-generated registry tells you which pages exist so you know what to search for.

4. **Search the chosen collection(s).** Use:
   ```
   qmd search "<question>" -c vault-<domain> -n 10 --files
   ```
   For complex questions, also run:
   ```
   qmd query "<question>" -c vault-<domain>
   ```
   (hybrid BM25 + LLM re-ranking, slower but higher recall). For cross-domain, run the same search once per collection and merge results.

   **Always pass `-c vault-<domain>`** — unscoped search or searching the wrong collection defeats the whole domain-atomization design.

5. **Read relevant pages** — use progressive disclosure. First read the `summary:` frontmatter of each hit (cheap). Only Read the full body of pages you need. Follow `[[wikilinks]]` to gather context — cross-domain wikilinks resolve by slug, so a `projects` page linking to `[[some-entity]]` will load that `research` page if you actually need it (be deliberate about crossing the boundary).

6. **Synthesize an answer** with citations: `(see [[page-name]])`. Draw from multiple pages when the question spans topics. If the answer pulls from both domains (via wikilinks), make the cross-domain nature explicit in the answer.

7. **Offer to file the answer.** If the answer is substantial and reusable, offer to save it as an analysis page:
   - Single-domain: `wiki/<domain>/analyses/<slug>.md`
   - Cross-domain: file in the *primary* domain (the domain the question's core belongs to) with explicit wikilinks into the secondary. Never duplicate across domains.

   If filed:
   - Add YAML frontmatter: `title`, `updated`, `tags`, `summary`, `domain: <domain>`
   - Run `bash scripts/build-registry.sh <domain>` to refresh the manifest registry so the new analysis appears in it
   - If the answer adds a load-bearing key fact that belongs in the manifest prose, propose an edit to the manifest's Key facts / Open questions section — do not edit the fenced REGISTRY block
   - Append to `wiki/log.md` (global):
     ```
     ## [YYYY-MM-DD] query | Question summary
     Domain: <domain>. Filed as [[analyses/page-name]]. Pages referenced: ...
     ```
   - Commit with message format: `query: Question summary`

## Rules

- Cite wiki pages, not raw sources (unless no wiki page covers it yet)
- Use `[[slug]]` wikilinks — never `[[wiki/research/entities/slug]]` or other path forms
- If the wiki lacks information to answer, say so and suggest sources to ingest (in the appropriate domain)
- Good answers compound the wiki — always offer to file substantial results
- **Default to single-domain.** Cross-domain is the exception. If in doubt, pick one domain and link across.
- **Every filed analysis needs `domain:` frontmatter** matching its parent directory. `scripts/check-frontmatter-domain.py` enforces this.
- **Never duplicate a page across domains.** One canonical copy per topic, linked from anywhere.
