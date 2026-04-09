#!/usr/bin/env python3
"""Verify that every wiki page's `domain:` frontmatter matches its parent
domain directory. Used by /health --structural to enforce the per-domain
layout invariant.

Usage:
    python3 scripts/check-frontmatter-domain.py                  # scan all domain dirs
    python3 scripts/check-frontmatter-domain.py wiki/<domain>    # scan one domain

Domain directories are auto-discovered as the immediate children of `wiki/`
that are directories and don't start with `_` or `.`. Add a new domain by
creating `wiki/<name>/` — no script edit required.

Exit codes:
    0 — all pages OK (or no domain dirs exist yet)
    1 — one or more mismatches
    2 — usage error
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"

# Match: ^domain: <value>$ in YAML frontmatter
DOMAIN_RE = re.compile(r"^domain:\s*([\w-]+)\s*$", re.MULTILINE)


def discover_domains() -> list[str]:
    """Return the list of domain directory names under wiki/."""
    if not WIKI_ROOT.is_dir():
        return []
    return sorted(
        p.name
        for p in WIKI_ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(("_", "."))
    )


def scan_domain(domain_dir: Path) -> list[tuple[Path, str | None]]:
    """Return [(path, found_domain_or_None), ...] for every .md page in the dir."""
    results = []
    if not domain_dir.is_dir():
        return results
    for md in sorted(domain_dir.rglob("*.md")):
        # Skip the manifest itself — its `domain:` field is the dir name by definition
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
