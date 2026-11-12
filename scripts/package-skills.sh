#!/usr/bin/env bash
# Build the player and GM skill zips in dist/ (see package-skills.py).
set -euo pipefail
exec python3 "$(dirname "$0")/package-skills.py" "$@"
