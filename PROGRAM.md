---
title: "LLM Wiki — Build Program"
version: 2
status: distribution
---

# LLM Wiki — Build Program

A single-file, harness-agnostic specification an LLM can follow to **build** a domain-atomized personal knowledge wiki from an empty directory, and then **operate** it. Read this file end-to-end; by the last page you will have produced the same repository structure found in the accompanying reference example, plus enough operating instructions to run it indefinitely.

This pattern is an evolution of the [canonical LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) that replaces the single flat namespace with physically separated per-domain directories. A flat layout works at ~30-60 pages; beyond that, per-session reading cost scales with total page count. Domain atomization fixes this by making per-session reads scale with the **touched** domain only, and replaces honor-system scoping with mechanical enforcement.

> **How to read this file.** Part I is a linear build procedure (Steps 1-9). Part II specifies the three operations (ingest, query, health) you will run against the wiki after it is built. Part III covers how domains evolve (split / merge) as the wiki grows. Part IV records meta-notes about portability. Do Part I in order before attempting anything in Part II.

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

Core requirements are file read/write, shell, git, Python, and the ability to ask the human clarifying questions. Optional web fetch helps URL ingests and staleness checks, but the wiki still works without it.

The default search mode is safe mechanical search: scoped keyword search inside the chosen domain before reading page bodies. Use `rg` if nothing else exists. Low page counts do not need an index; around ~80 articles/pages, a scoped index such as `qmd search` usually starts paying for itself. Treat ~80 as a practical threshold, not an invariant. Do not make LLM reranking, vector search, MCP tools, local GGUF models, Claude hooks, Codex skills/plugins, or any harness-specific feature part of the core path.

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

Steps 1 through 9 take an empty directory to a working, lint-clean, git-initialized vault. Do them in order.

## Step 1 — Target layout

Here is what you will produce. Create this structure in your head before you touch anything.

```
<vault-root>/
├── .gitignore
├── PROGRAM.md                # this file — copy it into the vault
├── README.md                 # a short human-facing intro (Step 9)
├── raw/                      # sources (gitignored)
│   ├── assets/               # inbox — unprocessed
│   ├── archived/             # processed
│   └── attachments/          # locally-extracted images
├── scripts/
│   ├── build-registry.sh
│   ├── build-xrefs.py
│   ├── check-wikilinks.py
│   ├── check-frontmatter-domain.py
│   ├── detect-domain-divergence.py
│   ├── find-near-duplicates.sh
│   └── find-attachments.sh
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

# Harness-specific permission allowlists — personal workflow, never commit
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
- `wiki/log.md` — append-only chronological activity log
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

Append-only chronological record of wiki activity. New entries go at the **TOP**, immediately after the hint comment below. The file is reverse-chronological so the newest activity is always visible first.

When this file exceeds ~300 lines, archive entries older than 30 days to `wiki/log-archive-YYYY.md`. The archive is still git-tracked and search-indexable.

<!-- grep "^## \[" log.md | tail -5 -->

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

Four prose sections follow the frontmatter, then the auto-generated registry block:

1. **Scope** — 2-3 paragraphs. What's in, what's out. Explicit calls on boundary cases.
2. **Key facts** — bullet list of the highest-leverage findings, each citing its source page.
3. **Open questions** — domain-specific unknowns. Explicit gaps tell future-you what's worth ingesting next.
4. **Cross-domain links** — pages in other domains this one commonly references.
5. **Registry block** — fenced with `<!-- REGISTRY:START ... -->` and `<!-- REGISTRY:END -->`. **Never edited by hand** — regenerated by `scripts/build-registry.sh`.

**Prose budget: ≤ 3,000 tokens.** Exceeding this signals the domain has grown into two domains' worth of context (see §III.2). The registry block does not count against the budget.

### 6.2 Skeleton template

Write this to `wiki/<domain-a>/_manifest.md`, substituting the real values. Repeat for `<domain-b>`.

```markdown
---
title: "<Domain Name> — Manifest"
domain: <domain-slug>
updated: YYYY-MM-DD
page_count: 0
tags: [meta, manifest, <domain-slug>]
summary: "One sentence describing what this domain covers and what kind of source or question routes here. The classification step in /ingest and /query reads ONLY this line."
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

**Important**: do not write speculative `[[slug]]` wikilinks into the placeholder sections. The link-checker in Step 7 fails on any `[[slug]]` whose target does not exist. Leave placeholder bullets as plain prose.

## Step 7 — Install the scripts

Seven scripts live in `scripts/`. Each is inlined below verbatim — write them to disk exactly. After writing, mark the shell scripts executable:

```bash
chmod +x scripts/*.sh scripts/*.py
```

All scripts assume they live in `<vault-root>/scripts/` and compute paths relative to `<vault-root>`.

### 7.1 `scripts/build-registry.sh`

Regenerates the `<!-- REGISTRY:START ... REGISTRY:END -->` block inside a domain's manifest from the pages in that domain. Sorts alphabetically. Reads only `title` and `summary` frontmatter from each page — no body scanning.

```bash
#!/usr/bin/env bash
# Regenerate the auto-generated page registry block inside a domain manifest.
#
# Usage:
#   scripts/build-registry.sh <domain>             # write the block
#   scripts/build-registry.sh --dry-run <domain>   # print what would be written

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
  exit 1
fi

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
    end_full = end_idx + len(end_marker)
    new_content = content[:start_idx] + new_block + content[end_full:]
elif start_idx < 0 and end_idx < 0:
    if not content.endswith("\n"):
        content += "\n"
    new_content = content + "\n" + new_block + "\n"
else:
    print("error: manifest has only one of the REGISTRY markers; refusing to mangle", file=sys.stderr)
    sys.exit(1)

manifest_path.write_text(new_content, encoding="utf-8")
print(f"OK: registry block updated in {manifest_path}")
PYEOF
```

### 7.2 `scripts/build-xrefs.py`

Walks the entire wiki and rebuilds `wiki/xrefs.json`: for every page, records its file path, domain, category, outbound wikilinks, inbound wikilinks, tags, updated date, and summary. Auto-discovers domain directories. Skips top-level nav files.

```python
#!/usr/bin/env python3
"""Regenerate wiki/xrefs.json by walking every domain directory.

xrefs.json is the precomputed wikilink graph for the whole vault. Use it
instead of grep to check what links to a page — it is the cheap way to
answer "what connects to X" without reading any page.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
OUT_PATH = WIKI_ROOT / "xrefs.json"

LINK_RE = re.compile(r"!?\[\[([^\]\\|#]+?)(?:\\?[#|][^\]]*)?\]\]")


def discover_domains() -> set[str]:
    if not WIKI_ROOT.is_dir():
        return set()
    return {
        p.name
        for p in WIKI_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(("_", "."))
    }


DOMAINS = discover_domains()


def strip_code_blocks(text: str) -> str:
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    block = text[4:end]
    fm: dict = {}
    list_key: str | None = None
    for line in block.splitlines():
        if not line.strip():
            list_key = None
            continue
        if line.startswith("- ") and list_key:
            fm[list_key].append(line[2:].strip().strip('"').strip("'"))
            continue
        if ":" not in line:
            list_key = None
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not value:
            fm[key] = []
            list_key = key
            continue
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip('"').strip("'") for v in value[1:-1].split(",")]
            fm[key] = [v for v in items if v]
            list_key = None
            continue
        fm[key] = value.strip('"').strip("'")
        list_key = None
    return fm


def extract_outbound(text: str) -> list[str]:
    clean = strip_code_blocks(text)
    links: list[str] = []
    for m in LINK_RE.finditer(clean):
        target = m.group(1).strip()
        if target.startswith("raw/") or target.startswith("wiki/"):
            continue
        base = target.rsplit("/", 1)[-1].rstrip("\\")
        if "." in base and not base.endswith(".md"):
            continue
        slug = base[:-3] if base.endswith(".md") else base
        if slug:
            links.append(slug)
    seen: set[str] = set()
    unique: list[str] = []
    for s in links:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def domain_key_for(path: Path) -> tuple[str, str, str]:
    rel = path.relative_to(WIKI_ROOT).parts
    if len(rel) >= 2 and rel[0] in DOMAINS:
        domain = rel[0]
        if path.stem.startswith("_"):
            category = "manifest"
            slug_key = f"{domain}/_manifest"
        else:
            category = rel[1] if len(rel) >= 3 else "root"
            slug_key = path.stem
    else:
        domain = "global"
        category = "root"
        slug_key = path.stem
    return slug_key, domain, category


def main() -> int:
    if not WIKI_ROOT.is_dir():
        print(f"ERROR: {WIKI_ROOT} not found", file=sys.stderr)
        return 2

    entries: dict[str, dict] = {}

    for md in sorted(WIKI_ROOT.rglob("*.md")):
        rel = md.relative_to(WIKI_ROOT).parts
        if len(rel) == 1 and rel[0] in ("index.md", "overview.md", "log.md"):
            continue
        try:
            raw = md.read_text(encoding="utf-8")
        except OSError:
            continue

        slug_key, domain, category = domain_key_for(md)
        fm = parse_frontmatter(raw)
        outbound = extract_outbound(raw)

        entries[slug_key] = {
            "file": str(md.relative_to(REPO_ROOT)),
            "domain": domain,
            "category": category,
            "outbound": outbound,
            "inbound": [],
            "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
            "updated": fm.get("updated", ""),
            "summary": fm.get("summary", ""),
        }

    slug_to_key = {}
    for key in entries:
        if "/" not in key:
            slug_to_key[key] = key
    for key, entry in entries.items():
        for target in entry["outbound"]:
            dest_key = slug_to_key.get(target)
            if dest_key and dest_key in entries:
                if key not in entries[dest_key]["inbound"]:
                    entries[dest_key]["inbound"].append(key)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"OK: wrote {len(entries)} entries to {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 7.3 `scripts/check-wikilinks.py`

Verifies that every `[[slug]]` in the wiki resolves to an existing page or attachment. Resolves by basename across the whole vault, matching the behavior of most Obsidian-style renderers. Skips wikilinks inside fenced code blocks.

```python
#!/usr/bin/env python3
"""Find broken wikilinks across the wiki.

Handles:
  [[slug]]                       plain reference
  [[slug|Display Text]]          with display alias
  [[slug\\|Display Text]]        escaped pipe (markdown table cells)
  [[slug#Section]]               with section anchor
  ![[image.png]]                 image embed (checked against raw/)

Skips:
  - Links pointing into raw/ or wiki/ (those are raw paths, not slugs)
  - Links inside fenced code blocks
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
RAW_ROOT = REPO_ROOT / "raw"

LINK_RE = re.compile(r"!?\[\[([^\]\\|#]+?)(?:\\?[#|][^\]]*)?\]\]")


def strip_code_blocks(text: str) -> str:
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def build_filename_index() -> tuple[set[str], set[str]]:
    md_names = set()
    if WIKI_ROOT.is_dir():
        for p in WIKI_ROOT.rglob("*.md"):
            md_names.add(p.stem)
    attachments = set()
    if RAW_ROOT.is_dir():
        for p in RAW_ROOT.rglob("*"):
            if p.is_file():
                attachments.add(p.name)
    return md_names, attachments


def main() -> int:
    md_index, attachment_index = build_filename_index()

    broken: list[tuple[Path, int, str]] = []
    total_links = 0

    for md in sorted(WIKI_ROOT.rglob("*.md")):
        try:
            raw = md.read_text(encoding="utf-8")
        except OSError:
            continue
        clean = strip_code_blocks(raw)
        for line_num, line in enumerate(clean.splitlines(), start=1):
            for m in LINK_RE.finditer(line):
                target = m.group(1).strip()
                total_links += 1

                if target.startswith("raw/") or target.startswith("wiki/"):
                    continue

                base = target.rsplit("/", 1)[-1]

                if "." in base and not base.endswith(".md"):
                    if base in attachment_index or base in md_index:
                        continue
                    broken.append((md, line_num, target))
                    continue

                slug = base[:-3] if base.endswith(".md") else base
                if slug not in md_index:
                    broken.append((md, line_num, target))

    if broken:
        print(f"FAIL: {len(broken)} broken wikilinks across {total_links} total\n")
        for md, line_num, target in broken:
            rel = md.relative_to(REPO_ROOT)
            print(f"  {rel}:{line_num} -> [[{target}]]")
        return 1

    print(f"OK: {total_links} wikilinks scanned, all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 7.4 `scripts/check-frontmatter-domain.py`

Verifies that every page's `domain:` frontmatter matches its parent domain directory. Auto-discovers domain directories as immediate children of `wiki/`.

```python
#!/usr/bin/env python3
"""Verify every wiki page's `domain:` frontmatter matches its parent directory.

Used by the health check to enforce the per-domain layout invariant.
Auto-discovers domain directories as immediate children of wiki/.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"

DOMAIN_RE = re.compile(r"^domain:\s*([\w-]+)\s*$", re.MULTILINE)


def discover_domains() -> list[str]:
    if not WIKI_ROOT.is_dir():
        return []
    return sorted(
        p.name
        for p in WIKI_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(("_", "."))
    )


def scan_domain(domain_dir: Path) -> list[tuple[Path, str | None]]:
    results = []
    if not domain_dir.is_dir():
        return results
    for md in sorted(domain_dir.rglob("*.md")):
        if md.name == "_manifest.md":
            continue
        try:
            content = md.read_text(encoding="utf-8")[:2500]
        except OSError:
            results.append((md, None))
            continue
        m = DOMAIN_RE.search(content)
        results.append((md, m.group(1) if m else None))
    return results


def main() -> int:
    if len(sys.argv) > 2:
        print("usage: check-frontmatter-domain.py [wiki/<domain>]", file=sys.stderr)
        return 2

    if len(sys.argv) == 2:
        target = Path(sys.argv[1])
        if not target.is_absolute():
            target = REPO_ROOT / target
        domains_to_check = [(target.name, target)]
    else:
        domains_to_check = [(d, WIKI_ROOT / d) for d in discover_domains()]

    any_dir_exists = False
    mismatches: list[tuple[Path, str, str | None]] = []
    total_checked = 0

    for expected_domain, dir_path in domains_to_check:
        if not dir_path.is_dir():
            continue
        any_dir_exists = True
        for md, found in scan_domain(dir_path):
            total_checked += 1
            if found != expected_domain:
                mismatches.append((md, expected_domain, found))

    if not any_dir_exists:
        print("(no domain directories exist yet — nothing to check)")
        return 0

    if mismatches:
        print(f"FAIL: {len(mismatches)} mismatches across {total_checked} pages\n")
        for md, expected, found in mismatches:
            rel = md.relative_to(REPO_ROOT)
            found_str = found if found else "(missing)"
            print(f"  {rel}: domain={found_str}, expected={expected}")
        return 1

    print(f"OK: {total_checked} pages, all `domain:` fields match their parent directory")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 7.5 `scripts/detect-domain-divergence.py`

Runs two independent triggers (§III.2): **manifest-pressure** (cheap, primary — works with no extra dependencies) and **graph community detection** (richer, secondary — requires `networkx`). Also surfaces merge candidates. This is the scanner you run when you suspect a domain is outgrowing its manifest.

```python
#!/usr/bin/env python3
"""Detect domains that should be split or merged.

Two independent split triggers:
  A. Manifest-pressure (cheap, primary): prose token count of each
     domain's _manifest.md (budget = 3,000 tokens). Works with wc alone.
  B. Graph community detection (richer, secondary): Louvain community
     detection on each domain's wikilink subgraph. Requires networkx.

Split thresholds (manifest):
  >= 2,500 tokens → warning
  >= 3,000 tokens → split candidate
  >= 3,500 tokens → hard fail

Split thresholds (graph):
  Q >= 0.40, 2+ communities each >= 15 pages, top-2 cover >= 80%,
  cross-cluster edge density < 25% of within-cluster density

Merge candidates:
  domain has < 10 pages
  >= 80% of outbound wikilinks point to a single other domain
  manifest prose < 1,000 tokens
  domain NOT marked pinned: true
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"

WORDS_PER_TOKEN = 0.75
BUDGET_WARN = 2_500
BUDGET_SPLIT = 3_000
BUDGET_HARD_FAIL = 3_500
MIN_COMMUNITY_SIZE = 15
MODULARITY_THRESHOLD = 0.40
TOP_TWO_COVERAGE = 0.80
CROSS_DENSITY_RATIO = 0.25

MERGE_PAGE_LIMIT = 10
MERGE_PROSE_LIMIT = 1_000
MERGE_OUTBOUND_FRACTION = 0.80

LINK_RE = re.compile(r"!?\[\[([^\]\\|#]+?)(?:\\?[#|][^\]]*)?\]\]")
REGISTRY_START = "<!-- REGISTRY:START"


def strip_code_blocks(text: str) -> str:
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def list_domains() -> list[str]:
    return sorted(
        p.name for p in WIKI_ROOT.iterdir()
        if p.is_dir() and (p / "_manifest.md").exists()
    )


def load_manifest_prose(domain: str) -> tuple[int, str, bool]:
    manifest = WIKI_ROOT / domain / "_manifest.md"
    text = manifest.read_text(encoding="utf-8")
    prose = text.split(REGISTRY_START)[0]
    words = len(prose.split())
    tokens = int(words * WORDS_PER_TOKEN)
    pinned = "pinned: true" in prose
    return tokens, prose, pinned


def collect_domain_pages(domain: str) -> dict[str, Path]:
    pages: dict[str, Path] = {}
    root = WIKI_ROOT / domain
    for p in root.rglob("*.md"):
        if p.stem.startswith("_"):
            continue
        pages[p.stem] = p
    return pages


def collect_all_page_domains() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for domain in list_domains():
        for slug in collect_domain_pages(domain):
            mapping[slug] = domain
    return mapping


def extract_outbound(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    clean = strip_code_blocks(raw)
    links: list[str] = []
    for m in LINK_RE.finditer(clean):
        target = m.group(1).strip()
        if target.startswith("raw/") or target.startswith("wiki/"):
            continue
        base = target.rsplit("/", 1)[-1]
        if "." in base and not base.endswith(".md"):
            continue
        slug = base[:-3] if base.endswith(".md") else base
        if slug:
            links.append(slug)
    return links


def build_domain_graph(domain: str, page_domain: dict[str, str]):
    import networkx as nx
    pages = collect_domain_pages(domain)
    g = nx.Graph()
    for slug in pages:
        g.add_node(slug)
    for slug, path in pages.items():
        for target in extract_outbound(path):
            if target == slug:
                continue
            if page_domain.get(target) == domain and target in pages:
                g.add_edge(slug, target)
    return g


def outbound_cross_domain_counts(domain: str, page_domain: dict[str, str]) -> dict[str, int]:
    pages = collect_domain_pages(domain)
    counts: dict[str, int] = {}
    for path in pages.values():
        for target in extract_outbound(path):
            dest = page_domain.get(target)
            if dest and dest != domain:
                counts[dest] = counts.get(dest, 0) + 1
    return counts


def run_graph_trigger(domain: str, page_domain: dict[str, str]) -> dict:
    try:
        import networkx as nx
        from networkx.algorithms import community as nx_community
    except ImportError:
        return {"skipped": True, "reason": "networkx not installed"}

    g = build_domain_graph(domain, page_domain)
    node_count = g.number_of_nodes()
    edge_count = g.number_of_edges()
    if node_count < 2 * MIN_COMMUNITY_SIZE:
        return {
            "skipped": False,
            "flag": False,
            "note": f"only {node_count} pages; need >= {2 * MIN_COMMUNITY_SIZE} for a meaningful split",
            "node_count": node_count,
            "edge_count": edge_count,
        }

    communities = nx_community.louvain_communities(g, seed=42)
    q = nx_community.modularity(g, communities)
    communities_sorted = sorted(communities, key=len, reverse=True)
    sizes = [len(c) for c in communities_sorted]
    big = [c for c in communities_sorted if len(c) >= MIN_COMMUNITY_SIZE]
    top_two_share = sum(sizes[:2]) / node_count if node_count else 0

    cross_density_ok = None
    if len(big) >= 2:
        within_edges = 0
        within_capacity = 0
        for c in big:
            sub = g.subgraph(c)
            n = sub.number_of_nodes()
            within_edges += sub.number_of_edges()
            within_capacity += n * (n - 1) // 2
        cross_edges = edge_count - within_edges
        cross_capacity = 0
        for i, c1 in enumerate(big):
            for c2 in big[i + 1:]:
                cross_capacity += len(c1) * len(c2)
        within_density = within_edges / within_capacity if within_capacity else 0
        cross_density = cross_edges / cross_capacity if cross_capacity else 0
        if within_density > 0:
            cross_density_ok = cross_density < CROSS_DENSITY_RATIO * within_density
        else:
            cross_density_ok = False

    flag = (
        q >= MODULARITY_THRESHOLD
        and len(big) >= 2
        and top_two_share >= TOP_TWO_COVERAGE
        and cross_density_ok is True
    )

    def top_pages(cluster: set[str], k: int = 5) -> list[str]:
        return [
            node for node, _ in sorted(
                g.subgraph(cluster).degree(), key=lambda x: x[1], reverse=True
            )[:k]
        ]

    return {
        "skipped": False,
        "flag": flag,
        "node_count": node_count,
        "edge_count": edge_count,
        "modularity": q,
        "community_count": len(communities_sorted),
        "community_sizes": sizes,
        "top_two_share": top_two_share,
        "cross_density_ok": cross_density_ok,
        "communities_top": [top_pages(c) for c in communities_sorted],
    }


def run_manifest_trigger(domain: str) -> dict:
    tokens, _, pinned = load_manifest_prose(domain)
    if tokens >= BUDGET_HARD_FAIL:
        level = "hard_fail"
    elif tokens >= BUDGET_SPLIT:
        level = "split_candidate"
    elif tokens >= BUDGET_WARN:
        level = "warning"
    else:
        level = "ok"
    return {"tokens": tokens, "budget": BUDGET_SPLIT, "level": level, "pinned": pinned}


def run_merge_trigger(domain, manifest_result, page_domain, page_counts):
    n_pages = page_counts.get(domain, 0)
    if manifest_result["pinned"]:
        return {"flag": False, "reason": "pinned: true"}
    if n_pages >= MERGE_PAGE_LIMIT:
        return {"flag": False, "reason": f"{n_pages} pages >= {MERGE_PAGE_LIMIT}"}
    if manifest_result["tokens"] >= MERGE_PROSE_LIMIT:
        return {"flag": False, "reason": f"manifest prose {manifest_result['tokens']} tok >= {MERGE_PROSE_LIMIT}"}
    cross_counts = outbound_cross_domain_counts(domain, page_domain)
    if not cross_counts:
        return {"flag": False, "reason": "no cross-domain outbound links"}
    total = sum(cross_counts.values())
    top_dest, top_count = max(cross_counts.items(), key=lambda x: x[1])
    share = top_count / total
    if share < MERGE_OUTBOUND_FRACTION:
        return {"flag": False, "reason": f"top destination {top_dest} only {share:.0%} of outbound"}
    return {
        "flag": True,
        "target_domain": top_dest,
        "outbound_share": share,
        "page_count": n_pages,
        "prose_tokens": manifest_result["tokens"],
    }


def format_report(domain, manifest, graph, merge, n_pages):
    lines = [f"=== {domain} ({n_pages} pages) ==="]
    lines.append(f"  manifest prose: {manifest['tokens']} tokens (budget {manifest['budget']}, level: {manifest['level']})")
    if manifest["pinned"]:
        lines.append("    pinned: true — merge suppression active")

    if graph.get("skipped"):
        lines.append(f"  graph trigger: SKIPPED ({graph['reason']})")
    else:
        if "modularity" not in graph:
            lines.append(f"  graph trigger: {graph['note']}")
        else:
            lines.append(
                f"  graph: Q={graph['modularity']:.3f}, "
                f"{graph['community_count']} communities, "
                f"sizes={graph['community_sizes']}, "
                f"top-2 cover {graph['top_two_share']:.0%}"
            )
            if graph.get("flag"):
                lines.append("  >> DOMAIN SPLIT CANDIDATE (graph trigger)")
                for i, top_pages in enumerate(graph["communities_top"][:3]):
                    lines.append(
                        f"     Cluster {chr(65 + i)} ({graph['community_sizes'][i]} pages): "
                        + ", ".join(top_pages)
                    )

    if manifest["level"] in ("split_candidate", "hard_fail"):
        lines.append(f"  >> DOMAIN SPLIT CANDIDATE (manifest trigger, level={manifest['level']})")

    if merge.get("flag"):
        lines.append(
            f"  >> MERGE CANDIDATE: absorb into `{merge['target_domain']}` "
            f"({merge['outbound_share']:.0%} of outbound links point there, "
            f"only {merge['page_count']} pages, prose {merge['prose_tokens']} tok)"
        )

    return lines


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Run only for this domain")
    args = parser.parse_args()

    if not WIKI_ROOT.is_dir():
        print(f"ERROR: {WIKI_ROOT} not found", file=sys.stderr)
        return 2

    domains = list_domains()
    if not domains:
        print("ERROR: no domain directories with _manifest.md found", file=sys.stderr)
        return 2

    if args.domain:
        if args.domain not in domains:
            print(f"ERROR: domain '{args.domain}' not in {domains}", file=sys.stderr)
            return 2
        domains = [args.domain]

    page_domain = collect_all_page_domains()
    page_counts = {d: len(collect_domain_pages(d)) for d in list_domains()}

    any_hard_fail = False
    report_lines = [f"Domain divergence scan — {len(domains)} domain(s)", ""]

    for domain in domains:
        manifest_result = run_manifest_trigger(domain)
        graph_result = run_graph_trigger(domain, page_domain)
        merge_result = run_merge_trigger(domain, manifest_result, page_domain, page_counts)
        n_pages = page_counts.get(domain, 0)
        report_lines.extend(format_report(domain, manifest_result, graph_result, merge_result, n_pages))
        report_lines.append("")
        if manifest_result["level"] == "hard_fail":
            any_hard_fail = True

    print("\n".join(report_lines))
    return 1 if any_hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
```

### 7.6 `scripts/find-near-duplicates.sh`

Uses the harness's keyword search tool (the reference uses `qmd`) to detect pages whose titles score suspiciously close to each other's. Catches the slow-rot pattern where two pages cover the same topic because an ingest's overlap-search came up empty. Skip this script if your harness has no search tool; substitute an equivalent that uses whatever is available.

```bash
#!/usr/bin/env bash
# Find near-duplicate wiki pages via BM25 title search.
#
# Usage: scripts/find-near-duplicates.sh [ratio]
#
# For each page, search for its title. The page itself should rank #1.
# If another page scores within `ratio` of the self-score (default 0.70),
# flag the pair. Output: "score-ratio  self-score  other-score  page-a  <->  page-b"
#
# Uses the `qmd` BM25 search tool in the reference implementation; replace
# with whatever keyword search your harness offers.

set -euo pipefail

ratio=${1:-0.70}
script_dir=$(dirname -- "$0")
cd -- "$script_dir/.."

python3 - "$ratio" <<'PYEOF'
import os, re, subprocess, sys

ratio_threshold = float(sys.argv[1])
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
            except (subprocess.TimeoutExpired, FileNotFoundError):
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
```

### 7.7 `scripts/find-attachments.sh`

Given an asset name, finds matching attachment files in `raw/attachments/<title>/`. Used during ingest to locate locally-saved images for a clipped web page.

```bash
#!/usr/bin/env bash
# Find attachment directories in raw/attachments/ matching an asset's title.
#
# Usage: scripts/find-attachments.sh <asset-path-or-title>
#
# Accepts either a full path (raw/assets/Foo.md) or a bare title (Foo).
# Strips extension and directory, then looks for an exact-match directory
# under raw/attachments/. Prints absolute paths to every file inside, one
# per line. Exits 0 even if no match is found.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <asset-path-or-title>" >&2
  exit 2
fi

input=$1
base=$(basename -- "$input")
title=${base%.*}

script_dir=$(dirname -- "$0")
cd -- "$script_dir/.."
repo_root=$(pwd)
attach_dir=$repo_root/raw/attachments/$title

if [ ! -d "$attach_dir" ]; then
  exit 0
fi

find "$attach_dir" -type f -print | sort
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

# Divergence scanner runs without error (should report 0 pages, ok level)
python3 scripts/detect-domain-divergence.py
```

If any of these fail, **stop and diagnose** before proceeding. Do not skip ahead to git init with a broken build.

## Step 9 — git init and first commit

```bash
git init
git add .gitignore PROGRAM.md README.md scripts/ wiki/
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
- `*Unverified — fetched via WebFetch*` — pulled through a summarizing web fetch, may be fabricated
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

If the source adds load-bearing facts, update the manifest's `Scope`, `Key facts`, `Open questions`, or `Cross-domain links` sections. **Never edit the fenced `<!-- REGISTRY:START ... REGISTRY:END -->` block** — it is regenerated by script.

Update the manifest's `updated:` and `page_count:` frontmatter fields.

### Step 2.8 Regenerate the registry

```bash
bash scripts/build-registry.sh <domain>
```

### Step 2.9 Update the xref graph

```bash
python3 scripts/build-xrefs.py
```

### Step 2.10 Append to the log

New entries go at the **top** of `wiki/log.md`, immediately after the hint comment. Format:

```markdown
## [YYYY-MM-DD] ingest | <source title>

Domain: <domain>. <Brief summary of what was ingested and which pages were touched.>
```

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

Prose + registry. Gives you the key facts and the list of pages worth searching.

### Step 3.3 Search

Use scoped mechanical search inside the chosen domain. Prefer a scoped keyword index if available; otherwise use `rg -n "<query terms>" wiki/<domain>`. Hybrid semantic search or LLM reranking is opt-in only after the compute-heavy warning in Part 0 §0.3.

### Step 3.4 Read relevant pages via progressive disclosure

See §5 — do not read full pages unless you are actively editing them.

### Step 3.5 Synthesize the answer

Respond with `[[wikilink]]` citations pointing to the source pages you drew from.

### Step 3.6 Offer to file the answer

If the answer is substantial and reusable, offer to file it as `wiki/<domain>/analyses/<slug>.md` with proper frontmatter. If the human accepts, write the page, regenerate the registry, and rebuild xrefs.

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
   - **Discovery**: search results + manifest registry + frontmatter `summary` fields. Most pages stop here.
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
11. `raw/` is never modified — sources are immutable.

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
6. `python3 scripts/check-frontmatter-domain.py` to confirm the layout is valid
7. Commit: `refactor: add <new> domain`

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
5. `python3 scripts/check-wikilinks.py` — wikilinks should still resolve because they are slug-based
6. Update the original manifest with a "see also" pointer to the new domain
7. Update `wiki/overview.md` and `wiki/index.md`
8. Commit: `refactor: split <old> into <old> + <new>`

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

**This file is** a portable, harness-agnostic build-and-operate program for a domain-atomized LLM Wiki. An LLM in any harness — with any set of file-read, file-write, shell, and (ideally) web-fetch tools — should be able to read this file and:

1. Bootstrap the wiki from an empty directory (Part I)
2. Operate it day-to-day (Part II)
3. Evolve its shape as it grows (Part III)

**This file is not** a tutorial, a user manual, or a theoretical defense of the design. The accompanying reference repository includes `SPEC.md` (architectural rationale), `CLAUDE.md` (a worked example of these rules translated into the Claude Code harness), and a `.claude/skills/` directory (skill files showing how individual operations are implemented for that harness). If you have access to those files and the task demands it, read them. If you do not, this file is sufficient.

## 2. Harness Portability

References to specific tools throughout this file — `qmd`, `git`, `networkx`, `tiktoken`, `pdfinfo`, WebFetch-style web tools — are examples from the working reference implementation. In a different harness, substitute the local equivalent:

- **Search**: scoped mechanical keyword search by default (`rg` or a per-domain index such as `qmd search`); hybrid semantic search or LLM reranking only after explicit opt-in and the compute-heavy warning in Part 0 §0.3
- **Graph analysis**: any library with community detection (or skip the graph trigger and rely on the manifest-pressure trigger, which needs nothing beyond `wc`)
- **Tokenizer**: any tokenizer compatible with modern LLMs (or fall back to `wc -w × 0.75`)
- **PDF reader**: any PDF tool (or skip PDF ingest)
- **Web fetcher**: any web fetch tool (or skip URL ingests)
- **Subagent spawning**: any way to get a fresh context (or run verification serially)

The **rules** — manifest-first reading, per-domain scoping, slug-based wikilinks, the 3,000-token prose budget, the invariants in Part II §6 — do not depend on any specific tool.

## 3. Extending This File

After bootstrap, the human will almost certainly want to add vault-specific rules: routing hints for topics that overlap multiple domains, project-specific verification standards, cost constraints for token-heavy operations, pointers to related code repositories, etc.

**Do not edit Parts I-IV of this file** to add those rules — keep PROGRAM.md portable and diff-able against the upstream template. Instead, create a companion file (the reference implementation uses `CLAUDE.md`) that carries the harness-specific and project-specific extensions. That file can reference this one for the portable baseline.

## 4. Quick Reference

| Situation | Action |
|---|---|
| Empty directory, need to start | Part I, Steps 1-9 |
| New source in the inbox | Part II §2 (ingest) |
| Question from the human | Part II §3 (query) |
| Structural lint | Part II §4.2 |
| Deep review of one domain | Part II §4.1 (one domain at a time, not same day as structural) |
| Manifest feels crowded | Run `detect-domain-divergence.py`; see Part III §2.1 thresholds |
| Domain feels tiny and derivative | Check merge criteria (Part III §2.5); ask the human |
| Need a new domain | Part III §1 — ask the human first |
| Number goes into the wiki | Compute with a tool, never mental math (Part II §8) |
| Uncertain which domain | Ask the human. Never silently pick. |
