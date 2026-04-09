#!/usr/bin/env bash
# Find near-duplicate wiki pages via qmd BM25 title search.
#
# Usage: scripts/find-near-duplicates.sh [ratio]
#
# Strategy: for each page, search for its title. The page itself should
# rank #1. If another page out-ranks it, OR if another page scores
# within `ratio` of the self-score (default 0.70 = 70%), flag the pair.
# This catches the slow-rot pattern where two pages cover the same
# topic because an ingest's overlap-search came up empty.
#
# Output: "score-ratio  self-score  other-score  page-a  <->  page-b"
# Higher ratio = more suspicious. ratio >= 1.0 = another page actually
# out-ranks self for self's own title (very strong duplicate signal).
#
# Uses BM25 (qmd search), not vector search — ~30x faster, sufficient
# signal for keyword-overlap duplicates.

set -euo pipefail

ratio=${1:-0.70}
script_dir=$(dirname -- "$0")
cd -- "$script_dir/.."

python3 - "$ratio" <<'PYEOF'
import os, re, subprocess, sys

ratio_threshold = float(sys.argv[1])
# Auto-discover domain dirs as immediate children of wiki/ that are
# directories and don't start with `_` or `.`. Add a domain by creating
# wiki/<name>/ — no script edit required.
domains = sorted(
    name for name in os.listdir("wiki")
    if os.path.isdir(os.path.join("wiki", name))
    and not name.startswith(("_", "."))
) if os.path.isdir("wiki") else []
subdirs = ["sources", "entities", "concepts", "analyses"]
title_re = re.compile(r'^title:\s*"?([^"\n]+?)"?\s*$', re.M)

pairs = {}
total = 0
flagged = 0

for domain in domains:
    collection = f"vault-{domain}"
    for sub in subdirs:
        d = os.path.join("wiki", domain, sub)
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".md"):
                continue
            total += 1
            path = os.path.join(d, fname)
            slug = os.path.splitext(fname)[0]
            with open(path, encoding="utf-8") as f:
                content = f.read(2000)
            m = title_re.search(content)
            if not m:
                continue
            title = m.group(1).strip()

            try:
                r = subprocess.run(
                    ["qmd", "search", title, "-c", collection, "-n", "5", "--files"],
                    capture_output=True, text=True, timeout=15
                )
            except subprocess.TimeoutExpired:
                continue

            results = []
            for line in r.stdout.splitlines():
                parts = line.split(",", 3)
                if len(parts) < 3 or not parts[0].startswith("#"):
                    continue
                try:
                    score = float(parts[1])
                except ValueError:
                    continue
                other_slug = os.path.splitext(os.path.basename(parts[2]))[0]
                results.append((other_slug, score))

            if not results:
                continue
            # Find self-score (may not be #1 if a duplicate exists)
            self_score = next((s for slg, s in results if slg == slug), None)
            if self_score is None or self_score <= 0:
                continue

            for other_slug, other_score in results:
                if other_slug == slug:
                    continue
                r_val = other_score / self_score
                if r_val < ratio_threshold:
                    continue
                pair = tuple(sorted([slug, other_slug]))
                if pair not in pairs or r_val > pairs[pair][0]:
                    pairs[pair] = (r_val, self_score, other_score)

for pair, (r_val, s, o) in sorted(pairs.items(), key=lambda x: -x[1][0]):
    flagged += 1
    print(f"{r_val:.2f}  self={s:.2f}  other={o:.2f}  {pair[0]}  <->  {pair[1]}")

print(f"\nScanned {total} pages, flagged {flagged} suspicious pairs (ratio >= {ratio_threshold})", file=sys.stderr)
PYEOF
