---
name: health
description: Health-check the wiki — two modes. `/health <domain>` runs deep per-domain checks (contradictions, math, gaps, research). `/health --structural` runs cheap global structural lint (page counts, wikilinks, frontmatter alignment, slug collisions, manifest budgets, domain divergence scan).
effort: high
argument-hint: [<domain> | --structural | --domain-scan]
---

# Health Check

**You are a fresh auditor with no prior context. Do not trust cached assumptions about page contents — read and verify.**

## Mode dispatch

| Invocation | Mode | Scope |
|---|---|---|
| `/health <domain>` | Deep per-domain | Phases 1-7 scoped to ONE domain |
| `/health --structural` | Cheap global lint | Phase 1 only, across all domains |
| `/health --domain-scan` | Divergence only | Phase 1.7 + 1.9 across all domains |

**No `/health --all`.** Coverage = `--structural` + one deep run per domain on separate days. Parse `$ARGUMENTS` and branch. If no arg: ask.

---

## Phase 1: Structural Lint

Runs in both modes. `--structural` runs it globally; `/health <domain>` scopes to one domain.

### 1.1 Page counts

!`find wiki/research -name '*.md' -not -name '_manifest.md' | wc -l`
!`find wiki/projects -name '*.md' -not -name '_manifest.md' | wc -l`

Compare against each manifest's `page_count:` frontmatter. Fix mismatches.

### 1.2 Orphan pages

For every page under `wiki/<domain>/{sources,entities,concepts,analyses}/`, grep for `[[slug]]` across the wiki. Zero inbound links (excluding log/overview/index) = orphan. Cross-domain inbound links count — slug resolution is global.

### 1.3 Broken wikilinks

!`python3 scripts/check-wikilinks.py`

Zero broken expected. Report before fixing.

### 1.4 Frontmatter compliance

Spot-check 15+ pages. Required: `title`, `updated`, `tags`, `summary`, `domain`. Source pages also need `source_file` or `source_url`.

### 1.5 Frontmatter / directory match

!`python3 scripts/check-frontmatter-domain.py`

Every page's `domain:` must equal its parent directory. Fix by editing frontmatter (or moving the file — rare, requires user sign-off).

### 1.6 Slug collisions

!`find wiki/research wiki/projects -name '*.md' -not -name '_*' -exec basename {} .md \; | sort | uniq -d`

Must be empty. Two pages sharing a slug breaks wikilink resolution. If a real collision surfaces: rename the less-referenced page, update inbound wikilinks, commit separately.

### 1.7 Manifest-pressure check (SPEC §9.2.A)

!`python3 scripts/detect-domain-divergence.py`

Reports each domain's prose token count. Thresholds: `ok` / `warning` (≥ 2,500) / `split_candidate` (≥ 3,000) / `hard_fail` (≥ 3,500). **Do not auto-split.** The script flags; the user decides.

### 1.8 Registry freshness

After any page add/move, regenerate the manifest registry:

```
bash scripts/build-registry.sh <domain>
```

Verify each page in `wiki/<domain>/` appears in its manifest registry, and `wiki/index.md` lists every domain manifest.

### 1.9 Graph divergence (SPEC §9.2.B)

Same script as §1.7 runs both triggers. Review the `graph:` line: Q ≥ 0.40 with ≥ 2 communities of ≥ 15 pages covering ≥ 80% → split candidate. `/health --domain-scan` runs only §1.7 + §1.9.

### 1.10 Near-duplicates

!`scripts/find-near-duplicates.sh 0.70`

Runs BM25 on every page title, flags matches within 70% of self.

**Ignore (expected noise):**
- Entity ↔ source page for the same thing
- Concept ↔ source it cites
- One-word coincidences and corpus-wide terms

**Investigate:**
- Two sources on the same artifact → merge candidate
- Source ↔ analysis on the same narrow topic → fold one in
- Two concept pages ranking together → concept-space duplication
- **Cross-domain near-duplicates** are worst — they violate "one canonical copy per topic". Fix immediately.

---

## Phase 2: Contradiction Detection (deep mode only)

For each high-value claim category in the target domain, `qmd search "<keyword>" -c vault-<domain>` to find every page that discusses it, then verify consistency. **Always pass `-c vault-<domain>`**.

This is **template fill-in territory**: list the categories of claims your domain repeats across pages (numbers, percentages, ratios, taxonomies, definitions) so this pass has something to scan. Example:

- **<Category 1>** — search "<keyword>". Authoritative source: <citation page>.
- **<Category 2>** — search "<formula>" "<unit>".

Flag as **FAIL**: `[page-A:line] says X, [page-B:line] says Y. Which is authoritative?`

**Cross-domain contradictions**: the wikilink target is authoritative. Update the referrer, don't re-derive.

---

## Phase 3: Mathematical Verification (deep mode only)

**All math verified with Python, never computed by the LLM.**

Scan analysis pages for formulas. Skip lines ending with `<!-- math-verified: YYYY-MM-DD -->` unless > 90 days old. For each unverified figure: extract formula + inputs, run `python3 << 'PYEOF' … PYEOF`, compare, report discrepancies as FAIL, mark verified lines.

Priority targets per domain are **template fill-in territory** — after forking, list the specific kinds of computed numbers your wiki tracks (formulas, ratios, probabilities, cost calcs, sizing examples).

---

## Phase 4: Knowledge Gap Identification (deep mode only)

Grep for:
1. Uncertainty markers: "unverified", "likely", "expected to", "no data", "unknown", "assumes"
2. Cross-source transfer claims without caveats (applying findings from one source/population to another)
3. Temporal staleness (dated pricing, rate limits, model names, benchmarks)
4. Qualitative claims that should have numbers ("significant", "large", "most")

Categorize each gap as: **fillable via web**, **fillable via primary sources**, **requires user input**, or **unfillable** (goes in the manifest's Open questions section).

---

## Phase 5: Verdict

- **PASS** — all checks clean
- **PASS with DRIFT** — clean but with misleading framings or unsupported claims flagged for human review
- **FAIL** — one or more FAIL items

---

## Phase 6: Fix-Verify Loop (deep mode only, max 3 iterations)

Only on FAIL + deep mode. `--structural` fails stop and report — they need human judgment (rename? move? merge?).

### Fix

Fix FAIL items. For math: compute with Python, apply edit, re-read. For contradictions: update the wrong page to match the authoritative source. For structural: `build-registry.sh`, frontmatter, cross-refs. **Grep for wrong values propagated elsewhere** (typically 3-5 places).

### Verify (fresh subagent)

Spawn an Agent with:

```
Re-verify fixes applied during a health check.
Domain: <domain>
Files changed: [list]
Issues fixed: [list with old/new values]

For each fix:
1. Read the file; confirm the new value is present
2. Math fixes: run in Python to confirm
3. Grep wiki/<domain>/ for remaining instances of the old value
4. Contradictions: confirm both pages agree
5. Confirm page's domain: frontmatter matches directory
6. Report PASS/FAIL per item
```

If iteration 3 still FAILs: **STOP**, report to user.

---

## Phase 7: Web Research — Fillable Gaps (deep mode only)

Only after fix-verify is clean. Research up to **5 gaps** per run; defer the rest.

1. WebSearch for authoritative sources
2. **Source skepticism**:
   - **High trust** (official docs, peer-reviewed, verified repos) → propose edit
   - **Medium trust** (reputable blogs, well-sourced articles) → propose edit with caveat
   - **Low trust** (social media, forum posts, unverified) → DO NOT update. Report and ask.
3. **Never silently update from web research** — always report first.

---

## Phase 8: Finalize

1. Regenerate registries: `bash scripts/build-registry.sh <domain>` for each touched domain
2. Re-index: `qmd update && qmd embed` (in that order — `qmd embed` alone is insufficient; it only embeds chunks already in the index). **Foreground only** — never `qmd embed &`; it's memory-heavy and has crashed machines.
3. Verify `page_count:` frontmatter still matches actual counts
4. Append to `wiki/log.md` (at top):

```
## [YYYY-MM-DD] lint | /health <mode>
<summary: N structural fixes, N contradictions, N math, N gaps, iterations N/3>
```

5. Commit: `lint: /health <mode> — N fixes`

---

## Output Format

```
## Health Report — YYYY-MM-DD
Mode: [/health <domain> | /health --structural | /health --domain-scan]
Verdict: [PASS / PASS with DRIFT / FAIL]
Fix iterations: N/3  (deep only)

### Structural
- Page counts: research=N projects=N  [match/mismatch]
- Frontmatter/dir: [OK / N mismatches]
- Slug collisions: [empty / list]
- Broken wikilinks: [N / OK]
- Orphans: [count]
- Manifest budgets: research=N tok, projects=N tok  [ok/warning/split/hard_fail]
- Divergence: [clean / split candidates / merge candidates]
- Near-duplicates: N flagged, N genuine

### Contradictions / Math  (deep only)
- N found, N fixed (Python verified)

### DRIFT (human review)
1. [file:line] Description.

### Knowledge Gaps  (deep only)
| Gap | Category | Action |

### Web Research  (deep only)
| Query | Finding | Confidence | Action |
```

---

## Rules

- **Modes are independent.** Don't mix structural and deep.
- **Always `-c vault-<domain>`** on qmd searches in deep mode.
- **Scope reads to one domain** in deep mode — that's the whole point.
- **Phase 6 verify must be a fresh subagent** (prevents context bias).
- **Never trust LLM-computed math** — always Python.
- **Never silently update wiki from web research.**
- **Never auto-split or auto-merge domains** — scanner suggests, user decides.
- **Never `qmd embed &`** — foreground only.
- **Check error propagation** — one wrong number often lives in 3+ places.
- **DRIFT ≠ FAIL** — flag, don't fix.
- **Max 3 fix-verify iterations.**

---

## See Also

- `/review-analysis [page]` — deep audit of a specific analysis
- `/ingest` — has its own verification subagent
- `scripts/detect-domain-divergence.py`, `scripts/build-registry.sh`, `scripts/check-wikilinks.py`, `scripts/check-frontmatter-domain.py`
