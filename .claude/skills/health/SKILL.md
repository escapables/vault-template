---
name: health
description: Health-check the wiki — two modes. `/health <domain>` runs deep per-domain checks (contradictions, math, gaps, research). `/health --structural` runs cheap global structural lint (page counts, wikilinks, frontmatter alignment, slug collisions, manifest budgets, domain divergence scan).
effort: high
argument-hint: [<domain> | --structural | --domain-scan]
---

# Health Check

Run a health check on the wiki. **Two modes** — pick the right one from the dispatch table below.

**You are a fresh auditor with no prior context. Do not trust cached assumptions about page contents — read and verify.**

## Mode dispatch

| Invocation | Mode | What it does |
|---|---|---|
| `/health <domain>` (e.g. `/health research`, `/health projects`) | Deep per-domain | Runs Phases 2 (contradictions), 3 (math), 4 (gaps), 6 (verification subagent), 7 (web research) scoped to ONE domain. Phase 1 structural lint runs only on that domain's pages. |
| `/health --structural` | Cheap global lint | Runs the structural-only checks that must be global: page counts, broken wikilinks, orphan pages, slug collisions, frontmatter/dir alignment, manifest-pressure, near-duplicate BM25 scan, **and the divergence scanner** (§9.2). No contradiction, math, or gap work. |
| `/health --domain-scan` | Divergence only | Runs ONLY the §9.2 divergence scan (manifest-pressure + graph community detection) across all domains. Useful when you suspect sprawl but haven't scheduled a full structural pass. |

**There is no `/health --all`.** Comprehensive coverage = `/health --structural` + one `/health <domain>` per domain on separate days. Running everything at once defeats the context-saving design.

Parse `$ARGUMENTS` at the top of the run and branch accordingly. If no arg: ask the user which mode.

---

## Phase 1: Structural Lint

Runs in both modes. In `--structural`, runs globally across both domain directories. In `/health <domain>`, runs scoped to that single domain.

### 1.1 Page counts

research:

!`find wiki/research -name '*.md' -not -name '_manifest.md' | wc -l`

projects:

!`find wiki/projects -name '*.md' -not -name '_manifest.md' | wc -l`

Compare against each domain's manifest `page_count:` frontmatter field. Fix any mismatch (update the manifest frontmatter — the registry regeneration in §1.8 will catch the rest).

### 1.2 Orphan pages

For every page in `wiki/{research,projects}/{sources,entities,concepts,analyses}/`, grep for `[[slug]]` across all other wiki files. A page with zero inbound links (excluding log.md, overview.md, and index.md) is an orphan. Note the domain boundary: a cross-domain wikilink still counts as an inbound link — slug resolution is global.

### 1.3 Broken wikilinks

!`python3 scripts/check-wikilinks.py`

Zero broken expected. If not, report each to the user before fixing.

### 1.4 Frontmatter compliance

Spot-check 15+ pages for YAML frontmatter. Required fields: `title`, `updated`, `tags`, `summary`, `domain`. Source pages also need `source_file`.

### 1.5 Frontmatter / directory match

!`python3 scripts/check-frontmatter-domain.py`

Every page's `domain:` frontmatter MUST equal the parent domain directory it lives in. Mismatch is a structural fail — fix by editing the frontmatter to match the directory, or move the file to the correct directory (rare, requires user sign-off).

### 1.6 Slug collision check

!`find wiki/research wiki/projects -name '*.md' -not -name '_*' -exec basename {} .md \; | sort | uniq -d`

Must return empty. Two pages sharing a slug breaks wikilink resolution because Obsidian resolves by slug, not path. `_manifest.md` files are excluded — they're referenced by path, not slug, so the two manifests sharing the `_manifest` stem is a safe false positive.

If a real collision surfaces: one page must be renamed. Rename the less-referenced one (fewer inbound links), update every inbound wikilink, commit as a separate change.

### 1.7 Manifest-pressure check (SPEC §9.2.A)

!`python3 scripts/detect-domain-divergence.py`

The divergence script reports each domain's manifest prose token count. Thresholds:

- `ok` → no action
- `warning` (≥ 2,500 tokens) → note in report, no action required
- `split_candidate` (≥ 3,000 tokens) → flag in report; investigate the graph trigger (§1.9) to find where to split
- `hard_fail` (≥ 3,500 tokens) → blocking issue; user should split the domain before the next ingest

**Do not auto-split. The script flags; the user decides.**

### 1.8 Index completeness & registry freshness

Each domain's manifest carries an auto-generated `<!-- REGISTRY:START … REGISTRY:END -->` block listing every page in the domain. After any page add/move, regenerate:

```
bash scripts/build-registry.sh research
bash scripts/build-registry.sh projects
```

Then verify:
- every page in `wiki/<domain>/` appears exactly once in the manifest's registry
- `wiki/index.md` lists every domain manifest currently in the vault

### 1.9 Domain divergence scan (SPEC §9.2.B, graph trigger)

Same script as §1.7 — it runs both triggers in one invocation. Review the `graph:` line per domain:

- Q ≥ 0.40, 2+ communities each ≥ 15 pages, top-2 cover ≥ 80%, loose cross-cluster edges → **split candidate**
- Below any of those thresholds → no action

In `/health --domain-scan` mode, this is the only check run.

### 1.10 Near-duplicate detection

!`scripts/find-near-duplicates.sh 0.70`

The script runs `qmd search` (BM25) on every page's title and flags any other page that scores within 70% of self. Output: `ratio  self=N  other=N  page-a  <->  page-b`.

**Noise filtering — IGNORE these expected patterns** (do NOT report as duplicates):

- **Entity ↔ source**: a thing's entity page and a source page about that thing share the root name (e.g., `<thing> ↔ <thing>-overview`). Intended.
- **Concept ↔ source**: a concept page and the source it cites (e.g., `<pattern-name> ↔ <paper-name>`). Intended.
- **One-word coincidence**: pairs sharing a common term ("category", "common", "topic") but obviously distinct. Score saturation artifact.
- **`<corpus-wide-term> ↔ <anything>`** — terms that appear on most pages will dominate similarity scores; ignore them.

**Genuinely investigate**:

- Two sources on the same primary artifact → likely missed overlap during ingest. Merge candidate.
- Source ↔ analysis on the same narrow topic, high ratio → fold one into the other.
- Two concept pages ranking together → concept-space duplication is the clearest slow-rot signal.

For each genuine candidate, read the `summary` frontmatter from both pages and decide: merge, differentiate, or leave alone.

**Cross-domain near-duplicates** are the worst — they violate the "one canonical copy per topic" rule in SPEC §8. Flag immediately and fix in the same session.

---

## Phase 2: Contradiction Detection (deep mode only)

Only runs in `/health <domain>` mode. Skip in `--structural` and `--domain-scan`.

For each of these high-value claim categories, use `qmd search … -c vault-<domain>` to find all pages that discuss the topic, then verify consistency. **Always pass `-c vault-<domain>`** — unscoped searches defeat the domain design.

### Domain-specific claim categories

This block is **template fill-in territory**. List the categories of claims your domain repeats across many pages (numbers, percentages, ratios, taxonomies, definitions) so the deep-lint pass can scan them for consistency. Example pattern (replace with your own):

**`/health <domain>`** claim categories:

- **<Category 1>** — search "<keyword>" "<keyword>" across <domain> pages. All should agree on the canonical value.
- **<Category 2>** — search "<keyword>". Authoritative source: <citation page>.
- **<Category 3>** — search "<formula>" "<unit>". Consistent per <subgroup>.

Flag contradictions as **FAIL**: `[page-A:line] says X, [page-B:line] says Y. Which is authoritative?`

**Cross-domain contradictions**: if a page in one domain cites a number that should come from a page in another domain, the wikilink's target is authoritative. Update the referring page to match, don't re-derive.

---

## Phase 3: Mathematical Verification (deep mode only)

**CRITICAL: All math must be verified with Python, never computed by the LLM.**

Scan analysis pages in the target domain for formulas and worked examples. **Skip any figure on a line ending with `<!-- math-verified: YYYY-MM-DD -->`** — verified with Python on that date. Only re-verify if > 90 days old or if surrounding context has changed.

For each unverified figure:

1. Extract the formula and inputs
2. Run `python3 << 'PYEOF' … PYEOF` to compute the result
3. Compare against the claimed value
4. Report any discrepancy as **FAIL**
5. If correct, mark with `<!-- math-verified: YYYY-MM-DD -->` at end of line

Priority targets per domain:

- **<domain>**: list the specific kinds of computed numbers your wiki tracks (formulas, ratios, probabilities, cost calculations, sizing examples). These are the highest-leverage claims to verify because they propagate across many pages and drive downstream decisions. Replace this block with your own domain-specific examples after forking.

---

## Phase 4: Knowledge Gap Identification (deep mode only)

Search for these patterns across the target domain:

1. **Explicit uncertainty markers**: grep for "unverified", "likely", "expected to", "no data", "unknown", "uncertain", "caveat", "assumes"
2. **Cross-platform transfer claims**: claims using a dataset or finding from one source to draw conclusions about a different source without caveats. For example, applying a benchmark from Tool A to make claims about Tool B, or treating findings from Population X as universal.
3. **Temporal staleness**: data with specific dates that may have been superseded — pay special attention to pricing, rate limits, model names, and benchmark numbers.
4. **Missing quantification**: qualitative claims that should have numbers ("significant", "large", "most")

For each gap, categorize:

- **Fillable via web search** — factual questions with likely published answers
- **Fillable via primary sources** — needs a specific paper, repo, or official doc
- **Requires user input** — subjective, jurisdictional, or preference-based
- **Unfillable** — genuinely unknown, flag as open question

The domain manifest's "Open questions" section is the canonical home for unfillable gaps. Add new ones there, not on individual pages.

---

## Phase 5: Verdict

Produce a verdict:

- **PASS** — every check run for the chosen mode came back clean.
- **PASS with DRIFT** — all checks pass, but found claims that are technically accurate yet misleading in context, or framings not directly supported by sources. List for human review.
- **FAIL** — one or more FAIL items found across any phase.

---

## Phase 6: Fix-Verify Loop (max 3 iterations, deep mode only)

Only runs when Phase 5 verdict is **FAIL** and we're in deep-mode. In `--structural` mode, report fails to the user and stop — structural fails often need human judgment (rename? move? merge?).

### Fix

1. Fix every FAIL item from Phases 1–3 (structural, contradictions, math)
2. For math fixes: compute correct value with Python, apply edit, re-read to confirm
3. For contradictions: update the wrong page to match the authoritative source
4. For structural: fix mechanically (add to manifest registry via `build-registry.sh`, fix frontmatter, add cross-references)
5. Search for each wrong value propagated elsewhere: `grep -rn "wrong_value" wiki/`

### Verify (fresh subagent)

Spawn a **fresh verification subagent** (Agent tool) with this prompt:

```
Re-verify fixes applied to the wiki during a health check.

Domain: <domain>
Files changed: [list]
Issues fixed: [list with old wrong values and new correct values]

For each fix:
1. Read the file and confirm the new value is present
2. For math fixes: run the formula in Python to confirm correctness
3. Grep wiki/<domain>/ for any remaining instances of the old wrong value
4. For contradiction fixes: confirm both pages now agree
5. Confirm the page's domain: frontmatter still matches its directory
6. Report PASS or FAIL per item
```

Track iterations:

```
HEALTH FIX LOOP: iteration N/3
Previous FAIL items: [list]
Fixes applied: [list]
Verification subagent verdict: [PASS/FAIL]
```

If iteration 3 still has FAIL items: **STOP**. Report remaining issues to the user.

---

## Phase 7: Web Research — Fillable Gaps (deep mode only)

**Run this phase only after the fix-verify loop is clean (PASS).**

Research up to **5 gaps** per run. Defer remaining to the next health check to avoid context bloat.

For gaps categorized as "fillable via web search":

1. Use WebSearch to find authoritative sources
2. **Apply source skepticism**:
   - **High trust**: official docs, peer-reviewed papers, verified repos → propose specific wiki edit
   - **Medium trust**: reputable tech blogs, well-sourced articles → propose edit with caveat note
   - **Low trust**: X threads, forum posts, unverified claims → DO NOT update wiki. Report to user: "Found [source] claiming [X]. Confidence: low. Can you find a more authoritative source?"
3. **Never silently update the wiki from web research. Always report findings first.**

---

## Phase 8: Finalize

After all fixes and research:

1. **Regenerate manifest registries** for any domain whose pages changed:
   ```
   bash scripts/build-registry.sh <domain>
   ```
2. **Re-index qmd** — run `qmd update` first (rescans files and picks up new/changed content into the BM25 index), then `qmd embed` (generates vectors for any new chunks). `qmd embed` alone is insufficient — it only embeds chunks already in the index, so if `qmd update` has been skipped, new files are invisible to vector search. Always run both, in that order. **Never run `qmd embed` in the background with `&`** — it's memory-heavy and has crashed the machine when combined with other work. Run foreground only.
3. **Verify page counts** still match each manifest's `page_count:` frontmatter field.
4. **Append to `wiki/log.md`** (global):

   For deep mode:
   ```
   ## [YYYY-MM-DD] lint | /health <domain>
   Summary. N structural fixes, N contradictions resolved, N math errors fixed.
   Knowledge gaps: N fillable (N filled), N needs user input, N unfillable.
   Iterations: N/3.
   ```

   For structural mode:
   ```
   ## [YYYY-MM-DD] lint | /health --structural
   N structural fixes. Page counts: [research=N projects=N]. Manifest budgets OK.
   Divergence scan: [split candidates / clean]. Near-duplicates: N genuine.
   ```

5. **Commit**: `lint: /health <mode> — N fixes, N gaps` (deep) or `lint: /health --structural — N fixes` (structural).

---

## Output Format

```
## Health Report — YYYY-MM-DD
Mode: [/health <domain> | /health --structural | /health --domain-scan]

### Verdict: [PASS / PASS with DRIFT / FAIL]
### Fix iterations: N/3  (deep mode only)

### Structural
- Page counts: research=N projects=N   [match/mismatch vs manifests]
- Frontmatter/dir alignment: [OK/N mismatches]
- Slug collisions: [empty / list]
- Broken wikilinks: [N broken / OK]
- Orphans: [count] found, [count] fixed
- Manifest budgets: research=N tok, projects=N tok   [ok/warning/split/hard_fail]
- Divergence scan: [clean / split candidates / merge candidates]
- Near-duplicates: N flagged, N genuine

### Contradictions  (deep mode only)
- [count] found, [count] fixed

### Math errors  (deep mode only)
- [count] found, [count] fixed (Python verified)

### DRIFT (human review)
1. [file:line] Description.

### Knowledge Gaps  (deep mode only)
| Gap | Category | Action |
|-----|----------|--------|
| ... | fillable/web | [proposed edit or "ask user"] |
| ... | needs user | [question for user] |
| ... | unfillable | [flagged as open, added to domain manifest] |

### Web Research Results  (deep mode only)
| Query | Finding | Confidence | Action |
|-------|---------|------------|--------|
| ... | ... | high/medium/low | [edit/ask user/skip] |
```

---

## Rules

- **The two modes are independent.** Don't run structural during deep mode; don't run deep checks during structural. Each is tuned for its context budget.
- **Always pass `-c vault-<domain>`** on `qmd search` in deep mode. Unscoped searches defeat the domain design.
- **Scope reads to one domain in deep mode.** Do not read the other domain's pages or manifest during `/health research` — that's the whole point.
- **The verification step in Phase 6 must spawn a fresh subagent** (Agent tool) to prevent context bias.
- **Never trust LLM-computed math** — always use Python.
- **Never silently update wiki from web research** — report and ask.
- **Never auto-split or auto-merge domains.** The divergence scanner suggests; the user decides. (SPEC §8 "Ask first before" rule.)
- **Never `qmd embed` in background with `&`.** Run foreground only; it's memory-heavy and has crashed the machine.
- **Check for error propagation** — one wrong number often appears in 3+ places.
- **DRIFT items are not failures** — flag for human review, don't fix.
- **Max 3 fix-verify iterations.** After that, escalate to user.
- **No `--all` flag.** Comprehensive coverage is `--structural` + per-domain deep runs on separate days.

---

## See Also

- `/review-analysis [page]` — deep audit of a specific analysis page
- `/ingest` — includes its own verification subagent on new content
- `scripts/detect-domain-divergence.py` — standalone divergence scanner (runs both §9.2 triggers)
- `scripts/build-registry.sh <domain>` — regenerate a domain's manifest registry block
- `scripts/check-wikilinks.py` — wikilink resolver
- `scripts/check-frontmatter-domain.py` — frontmatter/directory alignment check
