#!/usr/bin/env bash
# Regenerate the auto-generated page registry block inside a domain manifest.
#
# Usage:
#   scripts/build-registry.sh <domain>             # write the block
#   scripts/build-registry.sh --dry-run <domain>   # print what would be written
#
# The script scans wiki/<domain>/{sources,entities,concepts,analyses}/ for
# .md pages, reads each page's `title` and `summary` frontmatter, and
# regenerates the block between the markers:
#
#   <!-- REGISTRY:START (auto-generated, do not edit by hand) -->
#   ...
#   <!-- REGISTRY:END -->
#
# Pages are sorted alphabetically within each subsection. The block does
# NOT count against the manifest's prose token budget per SPEC §4.4.

set -euo pipefail

dry_run=false
if [ "${1:-}" = "--dry-run" ]; then
  dry_run=true
  shift
fi

if [ $# -lt 1 ]; then
  echo "usage: $0 [--dry-run] <domain>" >&2
  exit 2
fi

domain=$1
script_dir=$(dirname -- "$0")
cd -- "$script_dir/.."

domain_dir="wiki/$domain"
manifest="$domain_dir/_manifest.md"

if [ ! -d "$domain_dir" ]; then
  echo "error: domain directory not found: $domain_dir" >&2
  exit 1
fi

block=$(python3 - "$domain_dir" <<'PYEOF'
import os, re, sys
from pathlib import Path

domain_dir = Path(sys.argv[1])
title_re = re.compile(r'^title:\s*"?([^"\n]+?)"?\s*$', re.M)
summary_re = re.compile(r'^summary:\s*"?(.+?)"?\s*$', re.M)

# Section order matches SPEC §4.3
sections = [
    ("Entities", "entities"),
    ("Concepts", "concepts"),
    ("Analyses", "analyses"),
    ("Sources",  "sources"),
]

lines = ["<!-- REGISTRY:START (auto-generated, do not edit by hand) -->"]

for header, subdir in sections:
    sub = domain_dir / subdir
    if not sub.is_dir():
        continue
    pages = sorted(sub.glob("*.md"))
    if not pages:
        continue
    lines.append("")
    lines.append(f"### {header}")
    lines.append("")
    for p in pages:
        try:
            content = p.read_text(encoding="utf-8")[:2500]
        except OSError:
            continue
        tm = title_re.search(content)
        sm = summary_re.search(content)
        title = tm.group(1).strip() if tm else p.stem
        summary = sm.group(1).strip() if sm else ""
        slug = p.stem
        # Truncate runaway summaries to one line for the registry
        summary_one_line = summary.split("\n")[0]
        if summary_one_line:
            lines.append(f"- `[[{slug}]]` — {summary_one_line}")
        else:
            lines.append(f"- `[[{slug}]]` — {title}")

lines.append("")
lines.append("<!-- REGISTRY:END -->")
print("\n".join(lines))
PYEOF
)

if $dry_run; then
  echo "=== DRY RUN: would write registry block to $manifest ==="
  echo "$block"
  exit 0
fi

if [ ! -f "$manifest" ]; then
  echo "error: manifest not found: $manifest" >&2
  echo "create the manifest first (with frontmatter and prose), then re-run this script" >&2
  exit 1
fi

# Replace the existing block (or append if no markers exist)
python3 - "$manifest" "$block" <<'PYEOF'
import re, sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
new_block = sys.argv[2]

content = manifest_path.read_text(encoding="utf-8")

start_marker = "<!-- REGISTRY:START"
end_marker = "<!-- REGISTRY:END -->"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx >= 0 and end_idx > start_idx:
    # Replace existing block
    end_full = end_idx + len(end_marker)
    new_content = content[:start_idx] + new_block + content[end_full:]
elif start_idx < 0 and end_idx < 0:
    # Append at end of file
    if not content.endswith("\n"):
        content += "\n"
    new_content = content + "\n" + new_block + "\n"
else:
    print("error: manifest has only one of the REGISTRY markers; refusing to mangle", file=sys.stderr)
    sys.exit(1)

manifest_path.write_text(new_content, encoding="utf-8")
print(f"OK: registry block updated in {manifest_path}")
PYEOF
