#!/usr/bin/env bash
# Find attachment directories in raw/attachments/ matching an asset's title.
#
# Usage: scripts/find-attachments.sh <asset-path-or-title>
#
# Accepts either a full path (raw/assets/Foo.md) or a bare title (Foo).
# Strips extension and directory, then looks for an exact-match directory
# under raw/attachments/. Prints absolute paths to every file inside, one
# per line, so the calling agent can Read them directly. Exits 0 even if
# no match is found (prints nothing) — callers should check for empty output.

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
