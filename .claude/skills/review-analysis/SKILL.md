---
name: review-analysis
description: Verify a wiki analysis page for correctness, gaps, and stale data. Use when an analysis has been created or updated and needs auditing before trust.
argument-hint: [analysis-page-name]
effort: high
---

# Review Analysis

Audit the analysis at `wiki/analyses/$ARGUMENTS` (or the most recently modified analysis if no argument given).

**You are a fresh reviewer with no prior context about this analysis. Do not trust any number, claim, or cross-reference — verify everything mechanically.**

## Phase 1: Mathematical Verification

**CRITICAL: Never compute math in your head. Every formula must be verified with Python.**

For every formula or numerical claim in the analysis:

1. Identify the formula and its inputs
2. Run the calculation via `python3 << 'PYEOF' ... PYEOF`
3. Compare the Python output against what the analysis claims
4. Report any discrepancy as **FAIL** with the correct value

Common formulas to check:
- Recalibration: `p* = p^theta / (p^theta + (1-p)^theta)`
- EV: `P_true * (1 - P_market) - (1 - P_true) * P_market`
- Kelly: `0.25 * (EV / (1 - P_market))` for YES, `0.25 * (EV / P_market)` for NO
- Fees: `C * feeRate * p * (1 - p)`
- Brier: `mean((P_true - outcome)^2)`

## Phase 2: Source Verification

For every cited wiki page (`[[page-name]]`):

1. Verify the page exists
2. Read the relevant section
3. Confirm the analysis accurately represents the source
4. Check if the source has been updated since the analysis was written

Flag as:
- **FAIL**: analysis misrepresents the source
- **STALE**: source has been updated, analysis hasn't caught up
- **MISSING**: cited page doesn't exist

## Phase 3: Internal Consistency

- Do summary tables match detailed sections?
- Do category labels match between tables?
- Does the conclusion follow from the evidence presented?
- Are units consistent (per share vs per dollar, rate vs effective fee)?

Flag mismatches as **FAIL**.

## Phase 4: Knowledge Gaps

Identify claims that are:
- Marked "unverified", "likely", or "expected to transfer"
- Based on cross-platform data applied to a different platform
- Missing quantitative support (qualitative claims that should have numbers)
- Explicitly flagged as uncertain by the analysis itself

For each gap, assess: is this a gap we can fill with web research, or does it require primary data collection? Categorize as **GAP**.

## Phase 5: Verdict

Produce a verdict using the refine pattern:

- **PASS** — all math correct, all sources verified, internally consistent, no FAIL items.
- **PASS with DRIFT** — all criteria met, but analysis contains claims or framings not directly supported by cited sources. List drift items for human review.
- **FAIL** — one or more FAIL items found. List every FAIL item with file:line and the correct value.

## Phase 6: Fix-Verify Loop (max 3 iterations)

If verdict is **FAIL**:

1. Fix every FAIL item (use Python for correct values)
2. Re-read each fixed section to confirm the edit applied
3. Search for the wrong value propagated elsewhere: `grep -rn "wrong_value" wiki/`
4. Fix all propagated instances

Then **spawn a fresh verification subagent** (Agent tool) with this prompt:

```
Re-verify the fixes applied to wiki/analyses/[page-name].

Files changed: [list]
Issues fixed: [list with original wrong values and new correct values]

For each fix:
1. Read the file and confirm the new value is present
2. Run the formula in Python to confirm the new value is correct
3. Grep wiki/ for any remaining instances of the old wrong value
4. Report PASS or FAIL per item
```

Track iteration count:
```
REVIEW LOOP: iteration N/3
Previous FAIL items: [list]
Fixes applied: [list]
Verification subagent verdict: [PASS/FAIL]
```

If iteration 3 still has FAIL items: **STOP**. Report remaining issues to the user. Do not attempt a 4th pass — something is structurally wrong and needs human judgment.

## Output Format

```
## Analysis Review: [page name]

### Verdict: [PASS / PASS with DRIFT / FAIL]
### Iterations: N/3

### FAIL (must fix)
1. [file:line] Description. Python says X, analysis says Y. [FIXED iteration N / UNFIXED]

### STALE (should update)
1. [file:line] Description. Source now says X.

### DRIFT (human review)
1. [file:line] Claim not directly supported by cited source. May be valid inference.

### GAP (knowledge hole)
1. Description. Can fill via: [web search / primary data / user source].

### VERIFIED
- [x] Formula 1: correct (Python confirmed)
- [x] Statistic 1: matches source
...
```

## Rules

- The verification step in Phase 6 **must spawn a fresh subagent** (Agent tool) to prevent context bias — the agent that fixed the error cannot objectively verify its own fix
- Every number verified with Python, no exceptions
- Read cited sources — don't trust the analysis's characterization of them
- Check for the same error propagated across multiple files
- DRIFT items are not failures — flag for human review, don't fix
- Max 3 fix-verify iterations. After that, escalate.
- After fixes, commit with message: `review: [analysis name] — N errors fixed, N iterations`

## See Also

- `/health` — wiki-wide health check (use for broad sweeps; this skill is for targeted analysis audits)
- `/ingest` — includes its own verification subagent on new content
