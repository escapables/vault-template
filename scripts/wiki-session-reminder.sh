#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Vault wiki reminder:
- Route by manifest summary lines only; read a full manifest only after choosing a domain.
- In the chosen manifest, use prose, registry, and analytics before reading page bodies.
- Prefer scoped search: qmd search "<query>" -c vault-<domain>.
- After wiki edits: build-registry, build-xrefs, build-analytics, build-xrefs.
- qmd embed is manual foreground work; do not run it from hooks or background jobs.
EOF
