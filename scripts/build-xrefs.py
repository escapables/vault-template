#!/usr/bin/env python3
"""Regenerate wiki/xrefs.json by walking both domain directories.

xrefs.json is the precomputed wikilink graph for the whole vault. Each
entry is one wiki page:

    slug: {
        "file": "wiki/<domain>/<category>/<slug>.md",
        "domain": "<domain>",
        "category": "<category>",
        "outbound": [slug, ...],
        "inbound": [slug, ...],
        "tags": [tag, ...],
        "updated": "YYYY-MM-DD",
        "summary": "..."
    }

Cross-domain wikilinks are resolved by slug — a page in one domain
linking to `[[some-entity]]` (which may live in another domain) creates
an inbound entry on the target page regardless of where the link came
from.

Manifest files (`_manifest.md`) are scanned for inbound/outbound tracking
but are keyed under `<domain>/_manifest` so they don't collide with the
slug namespace.

Usage:
    python3 scripts/build-xrefs.py
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
    """Auto-discover domain dirs as immediate children of wiki/ that are
    directories and don't start with `_` or `.`. Add a new domain by creating
    `wiki/<name>/` — no script edit required.
    """
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
        # Inline list: [a, b, c]
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
            continue  # image embed
        slug = base[:-3] if base.endswith(".md") else base
        if slug:
            links.append(slug)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in links:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def domain_key_for(path: Path) -> tuple[str, str, str]:
    """Return (slug_key, domain, category)."""
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
        # Skip top-level nav files (index.md, overview.md, log.md) — they're
        # pure navigation, not content worth indexing in the wikilink graph
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

    # Second pass: build inbound lists. Obsidian resolves wikilinks by
    # basename slug across the whole vault, so a target slug in outbound
    # resolves to whichever entry has that exact basename.
    slug_to_key = {}
    for key in entries:
        # Regular pages key on their stem; manifests key on <domain>/_manifest
        if "/" not in key:
            slug_to_key[key] = key
    for key, entry in entries.items():
        for target in entry["outbound"]:
            dest_key = slug_to_key.get(target)
            if dest_key and dest_key in entries:
                src_label = key
                if src_label not in entries[dest_key]["inbound"]:
                    entries[dest_key]["inbound"].append(src_label)

    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"OK: wrote {len(entries)} entries to {OUT_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
