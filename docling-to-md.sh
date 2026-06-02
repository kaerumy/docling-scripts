#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Resolve args relative to the caller's cwd, not the script dir
args=()
for arg in "$@"; do
    if [[ -f "$arg" && ! "$arg" = /* ]]; then
        args+=("$(realpath "$arg")")
    else
        args+=("$arg")
    fi
done

cd "$SCRIPT_DIR"
exec uv run python docling-to-md.py "${args[@]}"
