#!/usr/bin/env python3
"""Tests for scripts/build-analytics.py."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build-analytics.py"


class BuildAnalyticsTest(unittest.TestCase):
    def test_writes_domain_analytics_from_xrefs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wiki = Path(tmp) / "wiki"
            wiki.mkdir()
            xrefs = {
                "ai/_manifest": {
                    "file": "wiki/ai/_manifest.md",
                    "domain": "ai",
                    "category": "manifest",
                    "outbound": ["alpha"],
                    "inbound": [],
                    "tags": ["meta"],
                    "updated": "2026-04-01",
                    "summary": "AI manifest.",
                },
                "alpha": {
                    "file": "wiki/ai/concepts/alpha.md",
                    "domain": "ai",
                    "category": "concepts",
                    "outbound": ["beta", "trading-one"],
                    "inbound": ["ai/_manifest", "beta", "gamma", "trading-one"],
                    "tags": ["concept"],
                    "updated": "2026-04-09",
                    "summary": "Alpha is the main AI concept.",
                },
                "beta": {
                    "file": "wiki/ai/sources/beta.md",
                    "domain": "ai",
                    "category": "sources",
                    "outbound": ["alpha"],
                    "inbound": ["alpha"],
                    "tags": ["source"],
                    "updated": "2025-12-01",
                    "summary": "Beta is older but load-bearing.",
                },
                "gamma": {
                    "file": "wiki/ai/analyses/gamma.md",
                    "domain": "ai",
                    "category": "analyses",
                    "outbound": ["alpha"],
                    "inbound": [],
                    "tags": ["analysis"],
                    "updated": "2026-04-05",
                    "summary": "Gamma points at alpha.",
                },
                "trading-one": {
                    "file": "wiki/trading/concepts/trading-one.md",
                    "domain": "trading",
                    "category": "concepts",
                    "outbound": ["alpha"],
                    "inbound": ["alpha"],
                    "tags": ["concept"],
                    "updated": "2026-04-10",
                    "summary": "Trading page linked to alpha.",
                },
            }
            (wiki / "xrefs.json").write_text(json.dumps(xrefs), encoding="utf-8")
            for domain in ("ai", "trading"):
                domain_dir = wiki / domain
                domain_dir.mkdir()
                (domain_dir / "_manifest.md").write_text(
                    "\n".join(
                        [
                            "---",
                            f'title: "{domain} manifest"',
                            f"domain: {domain}",
                            "updated: 2026-04-01",
                            "tags: [meta, manifest]",
                            f'summary: "{domain} summary."',
                            "---",
                            "",
                            f"# {domain} manifest",
                            "",
                            "<!-- REGISTRY:START (auto-generated, do not edit by hand) -->",
                            "<!-- REGISTRY:END -->",
                            "",
                        ]
                    ),
                    encoding="utf-8",
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--wiki-root",
                    str(wiki),
                    "--today",
                    "2026-04-10",
                ],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            ai = (wiki / "ai" / "_manifest.md").read_text(encoding="utf-8")
            trading = (wiki / "trading" / "_manifest.md").read_text(encoding="utf-8")

            self.assertIn("<!-- ANALYTICS:START", ai)
            self.assertIn("## AI Analytics", ai)
            self.assertIn("Generated from `wiki/xrefs.json` on 2026-04-10.", ai)
            self.assertIn("- `[[alpha]]` — inbound 3, outbound 2.", ai)
            self.assertIn("- `[[alpha]]` — cross-domain links 2.", ai)
            self.assertIn("- `[[alpha]]` — updated 2026-04-09.", ai)
            self.assertIn("- `[[beta]]` — updated 2025-12-01; degree 2.", ai)
            self.assertIn("- What does the wiki cover about alpha?", ai)

            self.assertIn("<!-- ANALYTICS:START", trading)
            self.assertIn("## Trading Analytics", trading)
            self.assertIn("- `[[trading-one]]` — cross-domain links 2.", trading)


if __name__ == "__main__":
    unittest.main()
