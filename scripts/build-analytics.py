#!/usr/bin/env python3
"""Regenerate derived analytics blocks in domain manifests.

The script consumes wiki/xrefs.json and writes an auto-generated analytics
block to each domain manifest. It does not edit curated manifest prose or the
registry block.

Usage:
    python3 scripts/build-analytics.py
    python3 scripts/build-analytics.py --today YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"
XREFS_NAME = "xrefs.json"

ANALYTICS_START = "<!-- ANALYTICS:START (auto-generated, do not edit by hand) -->"
ANALYTICS_END = "<!-- ANALYTICS:END -->"
REGISTRY_END = "<!-- REGISTRY:END -->"

GOD_NODE_LIMIT = 10
BRIDGE_LIMIT = 10
CLUSTER_LIMIT = 5
RECENT_LIMIT = 10
STALE_LIMIT = 10
QUESTION_LIMIT = 5
RECENT_DAYS = 14
STALE_DAYS = 90


@dataclass(frozen=True)
class Page:
    slug: str
    domain: str
    category: str
    outbound: tuple[str, ...]
    inbound: tuple[str, ...]
    updated: str
    summary: str


def parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def is_regular_page(slug: str, entry: dict[str, Any]) -> bool:
    domain = entry.get("domain", "")
    category = entry.get("category", "")
    if domain in ("", "global"):
        return False
    if category == "manifest":
        return False
    if "/" in slug:
        return False
    return True


def load_pages(xrefs_path: Path) -> dict[str, Page]:
    try:
        raw = json.loads(xrefs_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"error: missing {xrefs_path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid JSON in {xrefs_path}: {exc}")

    pages: dict[str, Page] = {}
    for slug, entry in raw.items():
        if not isinstance(entry, dict) or not is_regular_page(slug, entry):
            continue
        outbound = tuple(str(v) for v in entry.get("outbound", []) if isinstance(v, str))
        inbound = tuple(str(v) for v in entry.get("inbound", []) if isinstance(v, str))
        pages[slug] = Page(
            slug=slug,
            domain=str(entry.get("domain", "")),
            category=str(entry.get("category", "")),
            outbound=outbound,
            inbound=inbound,
            updated=str(entry.get("updated", "")),
            summary=str(entry.get("summary", "")),
        )
    return pages


def clean_inbound(page: Page, pages: dict[str, Page]) -> list[str]:
    return [src for src in page.inbound if src in pages]


def clean_outbound(page: Page, pages: dict[str, Page]) -> list[str]:
    return [dst for dst in page.outbound if dst in pages]


def page_degree(page: Page, pages: dict[str, Page]) -> int:
    return len(clean_inbound(page, pages)) + len(clean_outbound(page, pages))


def page_sort_key(page: Page, pages: dict[str, Page]) -> tuple[int, int, str]:
    return (-len(clean_inbound(page, pages)), -len(clean_outbound(page, pages)), page.slug)


def short_summary(page: Page, limit: int = 140) -> str:
    summary = " ".join(page.summary.split())
    if len(summary) <= limit:
        return summary
    return summary[: limit - 1].rstrip() + "..."


def domain_pages(pages: dict[str, Page], domain: str) -> list[Page]:
    return sorted((p for p in pages.values() if p.domain == domain), key=lambda p: p.slug)


def cross_domain_score(page: Page, pages: dict[str, Page]) -> int:
    count = 0
    for dst in clean_outbound(page, pages):
        if pages[dst].domain != page.domain:
            count += 1
    for src in clean_inbound(page, pages):
        if pages[src].domain != page.domain:
            count += 1
    return count


def build_adjacency(pages: dict[str, Page], domain: str) -> dict[str, set[str]]:
    nodes = {p.slug for p in domain_pages(pages, domain)}
    adjacency: dict[str, set[str]] = {slug: set() for slug in nodes}
    for slug in sorted(nodes):
        page = pages[slug]
        for dst in clean_outbound(page, pages):
            if dst in nodes and dst != slug:
                adjacency[slug].add(dst)
                adjacency[dst].add(slug)
    return adjacency


def label_clusters(pages: dict[str, Page], domain: str) -> list[list[str]]:
    adjacency = build_adjacency(pages, domain)
    if not adjacency:
        return []
    labels = {node: node for node in adjacency}
    for _ in range(20):
        changed = False
        for node in sorted(adjacency):
            if not adjacency[node]:
                continue
            counts = Counter(labels[n] for n in adjacency[node])
            best = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
            if best != labels[node]:
                labels[node] = best
                changed = True
        if not changed:
            break

    grouped: dict[str, list[str]] = defaultdict(list)
    for node, label in labels.items():
        grouped[label].append(node)
    clusters = [sorted(nodes) for nodes in grouped.values()]
    return sorted(clusters, key=lambda nodes: (-len(nodes), nodes[0]))


def bullet_or_none(lines: list[str]) -> str:
    return "\n".join(lines) if lines else "- (none)"


def domain_title(domain: str) -> str:
    words = domain.replace("-", " ").split()
    return " ".join(word.upper() if len(word) <= 2 else word.title() for word in words)


def render_domain(domain: str, pages: dict[str, Page], today: date) -> str:
    in_domain = domain_pages(pages, domain)

    god_nodes = sorted(in_domain, key=lambda p: page_sort_key(p, pages))[:GOD_NODE_LIMIT]
    god_lines = []
    for page in god_nodes:
        inbound = len(clean_inbound(page, pages))
        outbound = len(clean_outbound(page, pages))
        summary = short_summary(page)
        suffix = f" {summary}" if summary else ""
        god_lines.append(f"- `[[{page.slug}]]` — inbound {inbound}, outbound {outbound}.{suffix}")

    bridges = sorted(
        (p for p in in_domain if cross_domain_score(p, pages) > 0),
        key=lambda p: (-cross_domain_score(p, pages), p.slug),
    )[:BRIDGE_LIMIT]
    bridge_lines = [
        f"- `[[{page.slug}]]` — cross-domain links {cross_domain_score(page, pages)}."
        for page in bridges
    ]

    clusters = label_clusters(pages, domain)[:CLUSTER_LIMIT]
    cluster_lines = []
    for idx, cluster in enumerate(clusters, start=1):
        top = sorted(cluster, key=lambda slug: (-page_degree(pages[slug], pages), slug))[:3]
        linked = ", ".join(f"`[[{slug}]]`" for slug in top)
        cluster_lines.append(f"- Cluster {idx} ({len(cluster)} pages): {linked}")

    recent = []
    for page in in_domain:
        updated = parse_date(page.updated)
        if updated is None:
            continue
        age = (today - updated).days
        if 0 <= age <= RECENT_DAYS:
            recent.append((updated, page))
    recent_lines = [
        f"- `[[{page.slug}]]` — updated {page.updated}."
        for _, page in sorted(recent, key=lambda item: (-item[0].toordinal(), item[1].slug))[:RECENT_LIMIT]
    ]

    load_bearing = sorted(in_domain, key=lambda p: (-page_degree(p, pages), p.slug))[:20]
    stale_lines = []
    for page in load_bearing:
        updated = parse_date(page.updated)
        if updated is None:
            continue
        if (today - updated).days > STALE_DAYS:
            stale_lines.append(
                f"- `[[{page.slug}]]` — updated {page.updated}; degree {page_degree(page, pages)}."
            )
        if len(stale_lines) >= STALE_LIMIT:
            break

    question_lines = []
    for page in god_nodes[:QUESTION_LIMIT]:
        question_lines.append(f"- What does the wiki cover about {page.slug}?")

    title = domain_title(domain)
    return "\n".join(
        [
            ANALYTICS_START,
            "",
            f"## {title} Analytics",
            "",
            f"Generated from `wiki/xrefs.json` on {today.isoformat()}.",
            "",
            "### God nodes",
            "",
            bullet_or_none(god_lines),
            "",
            "### Cross-domain bridges",
            "",
            bullet_or_none(bridge_lines),
            "",
            "### Link clusters",
            "",
            bullet_or_none(cluster_lines),
            "",
            "### Recently updated",
            "",
            bullet_or_none(recent_lines),
            "",
            "### Stale load-bearing pages",
            "",
            bullet_or_none(stale_lines),
            "",
            "### Suggested questions",
            "",
            bullet_or_none(question_lines),
            "",
            ANALYTICS_END,
            "",
        ]
    )


def replace_or_append_analytics(manifest_text: str, analytics_block: str) -> str:
    pattern = re.compile(
        re.escape(ANALYTICS_START) + r".*?" + re.escape(ANALYTICS_END) + r"\n?",
        re.DOTALL,
    )
    if pattern.search(manifest_text):
        return pattern.sub(analytics_block, manifest_text)

    if REGISTRY_END in manifest_text:
        idx = manifest_text.find(REGISTRY_END) + len(REGISTRY_END)
        prefix = manifest_text[:idx].rstrip()
        suffix = manifest_text[idx:].lstrip("\n")
        joined = prefix + "\n\n" + analytics_block
        if suffix:
            joined += "\n" + suffix
        return joined

    return manifest_text.rstrip() + "\n\n" + analytics_block


def write_domain_manifest(domain: str, wiki_root: Path, analytics_block: str) -> None:
    manifest = wiki_root / domain / "_manifest.md"
    if not manifest.exists():
        raise SystemExit(f"error: missing manifest for domain {domain}: {manifest}")
    original = manifest.read_text(encoding="utf-8")
    updated = replace_or_append_analytics(original, analytics_block)
    manifest.write_text(updated, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wiki-root", type=Path, default=WIKI_ROOT)
    parser.add_argument("--today", default=date.today().isoformat())
    args = parser.parse_args(argv)

    today = parse_date(args.today)
    if today is None:
        print(f"error: invalid --today date: {args.today}", file=sys.stderr)
        return 2

    wiki_root = args.wiki_root
    pages = load_pages(wiki_root / XREFS_NAME)
    domains = sorted({page.domain for page in pages.values()})
    for domain in domains:
        block = render_domain(domain, pages, today)
        write_domain_manifest(domain, wiki_root, block)

    print(f"OK: analytics blocks updated for {len(domains)} domain(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
