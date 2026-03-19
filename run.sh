#!/usr/bin/env bash
#
# run.sh - Run clang-call-analyzer in nix-shell
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running clang-call-analyzer in nix-shell..."

# Quote arguments properly to prevent nix-shell from parsing them as nix files
ARGS=""
for arg in "$@"; do
    ARGS="$ARGS '$arg'"
done

nix-shell "$SCRIPT_DIR" --run "cd $SCRIPT_DIR && python -m src.cli $ARGS"
