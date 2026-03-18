#!/usr/bin/env bash
#
# run.sh - Run clang-call-analyzer in nix-shell
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running clang-call-analyzer in nix-shell..."
nix-shell "$SCRIPT_DIR" --run "cd $SCRIPT_DIR && python -m src.cli $@"
