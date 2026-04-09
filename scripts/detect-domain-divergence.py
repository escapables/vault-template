#!/usr/bin/env python3
"""Detect domains that should be split, per SPEC §9.2.

Two independent triggers:
  A. Manifest-pressure (cheap, primary): prose token count of each
     domain's _manifest.md (budget = 3,000 tokens). Works with `wc`
     alone — no extra dependencies needed.
  B. Graph community detection (richer, secondary): Louvain community
     detection on each domain's wikilink subgraph. Reports modularity
     Q and flags actionable split candidates. Requires `networkx`.

Trigger thresholds (SPEC §9.2.A):
  ≥ 2,500 tokens → warning
  ≥ 3,000 tokens → split candidate
  ≥ 3,500 tokens → hard fail

Graph trigger thresholds (SPEC §9.2.B):
  Modularity Q ≥ 0.40
  ≥ 2 communities each with ≥ 15 pages
  Top 2 communities cover ≥ 80% of pages
  Cross-cluster edge density < 25% of within-cluster density

Also surfaces merge candidates per SPEC §9.6:
  domain has < 10 pages
  ≥ 80% of outbound wikilinks point to a single other domain
  manifest prose < 1,000 tokens
  domain is NOT marked pinned: true

Usage:
    python3 scripts/detect-domain-divergence.py            # all domains
    python3 scripts/detect-domain-divergence.py --domain research  # single domain

Exit codes:
    0 — no hard-fail split candidates
    1 — at least one domain at hard-fail threshold (≥ 3,500 tokens)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = REPO_ROOT / "wiki"

WORDS_PER_TOKEN = 0.75  # rough cl100k_base approximation
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
    """Every immediate child of wiki/ that contains a _manifest.md."""
    return sorted(
        p.name for p in WIKI_ROOT.iterdir()
        if p.is_dir() and (p / "_manifest.md").exists()
    )


def load_manifest_prose(domain: str) -> tuple[int, str, bool]:
    """Return (token_count, raw_prose_text, pinned)."""
    manifest = WIKI_ROOT / domain / "_manifest.md"
    text = manifest.read_text(encoding="utf-8")
    prose = text.split(REGISTRY_START)[0]
    words = len(prose.split())
    tokens = int(words * WORDS_PER_TOKEN)
    pinned = "pinned: true" in prose
    return tokens, prose, pinned


def collect_domain_pages(domain: str) -> dict[str, Path]:
    """slug → path for every page in the domain (manifest excluded)."""
    pages: dict[str, Path] = {}
    root = WIKI_ROOT / domain
    for p in root.rglob("*.md"):
        if p.stem.startswith("_"):
            continue
        pages[p.stem] = p
    return pages


def collect_all_page_domains() -> dict[str, str]:
    """slug → domain, across every domain."""
    mapping: dict[str, str] = {}
    for domain in list_domains():
        for slug in collect_domain_pages(domain):
            mapping[slug] = domain
    return mapping


def extract_outbound(path: Path) -> list[str]:
    """Every wikilink out of this page, resolved to a bare slug."""
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
            continue  # image embed
        slug = base[:-3] if base.endswith(".md") else base
        if slug:
            links.append(slug)
    return links


def build_domain_graph(domain: str, page_domain: dict[str, str]):
    """Induced subgraph: undirected, self-loops dropped, only intra-domain edges."""
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
    """For merge-candidate check: how many outbound links go where."""
    pages = collect_domain_pages(domain)
    counts: dict[str, int] = {}
    for path in pages.values():
        for target in extract_outbound(path):
            dest = page_domain.get(target)
            if dest and dest != domain:
                counts[dest] = counts.get(dest, 0) + 1
    return counts


def run_graph_trigger(domain: str, page_domain: dict[str, str]) -> dict:
    """Return structured result for the graph-community trigger."""
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
            "note": f"only {node_count} pages; need ≥ {2 * MIN_COMMUNITY_SIZE} for a meaningful split",
            "node_count": node_count,
            "edge_count": edge_count,
        }

    # Louvain is non-deterministic; seed so reports are reproducible
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


def run_merge_trigger(
    domain: str,
    manifest_result: dict,
    page_domain: dict[str, str],
    page_counts: dict[str, int],
) -> dict:
    n_pages = page_counts.get(domain, 0)
    if manifest_result["pinned"]:
        return {"flag": False, "reason": "pinned: true"}
    if n_pages >= MERGE_PAGE_LIMIT:
        return {"flag": False, "reason": f"{n_pages} pages ≥ {MERGE_PAGE_LIMIT}"}
    if manifest_result["tokens"] >= MERGE_PROSE_LIMIT:
        return {
            "flag": False,
            "reason": f"manifest prose {manifest_result['tokens']} tok ≥ {MERGE_PROSE_LIMIT}",
        }
    cross_counts = outbound_cross_domain_counts(domain, page_domain)
    if not cross_counts:
        return {"flag": False, "reason": "no cross-domain outbound links"}
    total = sum(cross_counts.values())
    top_dest, top_count = max(cross_counts.items(), key=lambda x: x[1])
    share = top_count / total
    if share < MERGE_OUTBOUND_FRACTION:
        return {
            "flag": False,
            "reason": f"top destination {top_dest} only {share:.0%} of outbound",
        }
    return {
        "flag": True,
        "target_domain": top_dest,
        "outbound_share": share,
        "page_count": n_pages,
        "prose_tokens": manifest_result["tokens"],
    }


def format_report(
    domain: str,
    manifest: dict,
    graph: dict,
    merge: dict,
    n_pages: int,
) -> list[str]:
    lines = [f"=== {domain} ({n_pages} pages) ==="]
    lines.append(
        f"  manifest prose: {manifest['tokens']} tokens "
        f"(budget {manifest['budget']}, level: {manifest['level']})"
    )
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
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
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
    report_lines: list[str] = []
    report_lines.append(f"Domain divergence scan — {len(domains)} domain(s)")
    report_lines.append("")

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
