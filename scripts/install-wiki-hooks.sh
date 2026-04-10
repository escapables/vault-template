#!/usr/bin/env bash
set -euo pipefail

force=0
if [ "${1:-}" = "--force" ]; then
  force=1
elif [ "${1:-}" != "" ]; then
  printf 'usage: %s [--force]\n' "$0" >&2
  exit 2
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

hooks_dir="$(git rev-parse --git-path hooks)"
mkdir -p "$hooks_dir"

install_hook() {
  name="$1"
  path="$hooks_dir/$name"
  marker="vault-wiki-maintenance"

  if [ -e "$path" ] && ! grep -q "$marker" "$path"; then
    if [ "$force" -ne 1 ]; then
      printf 'existing hook at %s; rerun with --force to back it up and replace it\n' "$path" >&2
      return 1
    fi
    cp "$path" "$path.bak.$(date +%Y%m%d%H%M%S)"
  fi

  cat > "$path" <<'HOOK'
#!/usr/bin/env bash
# vault-wiki-maintenance
repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
exec "$repo_root/scripts/wiki-maintenance-hook.sh" "$(basename "$0")"
HOOK
  chmod +x "$path"
  printf 'installed %s\n' "$path"
}

install_hook post-commit
install_hook post-checkout
