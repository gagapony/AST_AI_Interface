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

# Suppress clang/libclang warnings
# Method: Use CLANG_FORCE_COLOR_DIAGNOSTICS=never and redirect stderr
export CLANG_FORCE_COLOR_DIAGNOSTICS=never
nix-shell "$SCRIPT_DIR" --run "cd $SCRIPT_DIR && python -m src.cli $ARGS 2>&1 | grep -v 'unknown warning option' | grep -v 'file not found'"
