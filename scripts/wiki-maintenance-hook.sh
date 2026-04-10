#!/usr/bin/env bash
set -u

event="${1:-manual}"
status=0

warn() {
  printf 'vault hook: %s\n' "$*" >&2
}

run() {
  printf 'vault hook: %s\n' "$*"
  "$@"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    warn "failed ($rc): $*"
    status=1
  fi
}

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$repo_root" ]; then
  warn "not inside a git repo; skipped"
  exit 0
fi

cd "$repo_root" || exit 0

if [ ! -d wiki ] || [ ! -d scripts ]; then
  warn "wiki/scripts directories not found; skipped"
  exit 0
fi

for manifest in wiki/*/_manifest.md; do
  [ -e "$manifest" ] || continue
  domain="$(basename "$(dirname "$manifest")")"
  run bash scripts/build-registry.sh "$domain"
done

run python3 scripts/build-xrefs.py
run python3 scripts/build-analytics.py
run python3 scripts/build-xrefs.py

if [ "${WIKI_HOOK_SKIP_QMD:-}" = "1" ]; then
  warn "qmd update skipped by WIKI_HOOK_SKIP_QMD=1"
elif command -v qmd >/dev/null 2>&1; then
  run qmd update
else
  warn "qmd not found; skipped qmd update"
fi

warn "qmd embed is not run by hooks; run it manually in foreground when re-indexing is due."

if [ "$status" -ne 0 ]; then
  warn "maintenance completed with warnings after $event; not blocking git"
fi

exit 0
