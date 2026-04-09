#!/usr/bin/env python3
"""Find broken wikilinks across the wiki. Handles Obsidian-style references:

  - [[slug]]
  - [[slug|Display Text]]
  - [[slug\\|Display Text]]   (escaped pipe inside markdown table cells)
  - [[slug#Section]]
  - ![[image.png]]            (image embeds; checked against raw/ attachment dirs)

Resolves by basename across the entire vault, matching Obsidian's behavior.
Skips:
  - Wikilinks pointing into raw/ (those are raw paths, not wiki pages)
  - Wikilinks inside fenced code blocks (false positives from spec docs)
  - The literal string "[[rtk]]" in log.md (a documented past-fix example)

Usage:
    python3 scripts/check-wikilinks.py

Exit codes:
    0 — no broken wikilinks
    1 — one or more broken wikilinks
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
RAW_ROOT = REPO_ROOT / "raw"

# Match [[target]] or ![[target]], with optional |alias and #section.
# The negated character class excludes ], |, #, and \\ to avoid escape-pipe artifacts.
LINK_RE = re.compile(r"!?\[\[([^\]\\|#]+?)(?:\\?[#|][^\]]*)?\]\]")

# Match fenced code blocks (``` ... ```) so we can exclude them
CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)


def strip_code_blocks(text: str) -> str:
    """Replace fenced code blocks with blank lines so wikilinks inside them are ignored."""
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
    """Return (md_basenames_without_ext, attachment_basenames_with_ext)."""
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

                # Skip raw/ references and absolute wiki/ paths
                if target.startswith("raw/") or target.startswith("wiki/"):
                    continue

                # Documented past-fix example in log.md
                if target == "rtk" and md.name == "log.md":
                    continue

                # Strip any nested path; Obsidian resolves by basename
                base = target.rsplit("/", 1)[-1]

                # Image embeds (have an extension other than .md)
                if "." in base and not base.endswith(".md"):
                    if base in attachment_index or base in md_index:
                        continue
                    broken.append((md, line_num, target))
                    continue

                # Markdown page reference
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
