#!/usr/bin/env bash
# Copy shared reference files into every skill's references/ folder so each
# skill is self-contained (required for claude.ai uploads).
# Run after editing anything in shared/. CI-friendly: use --check to fail on drift.
set -euo pipefail
cd "$(dirname "$0")/.."

check=false
[[ "${1:-}" == "--check" ]] && check=true
status=0

for skill in skills/*/; do
  mkdir -p "${skill}references"
  for f in shared/*.md; do
    dest="${skill}references/$(basename "$f")"
    if $check; then
      if ! cmp -s "$f" "$dest"; then
        echo "out of date: $dest"; status=1
      fi
    else
      cp "$f" "$dest"
    fi
  done
done

$check && [[ $status -eq 0 ]] && echo "shared references are in sync"
exit $status
