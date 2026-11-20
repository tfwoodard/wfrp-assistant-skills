#!/usr/bin/env bash
# Copy shared files into the skills so each skill is self-contained (required
# for claude.ai uploads): shared/*.md into every skill's references/ folder, and
# shared/scripts/*.py into the scripts/ folder of each skill listed for it below.
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

# shared scripts: "<file>:<skill> <skill> ..."
for spec in "library.py:wfrp-character-sheet wfrp-rules-lookup" \
            "excerpt.py:wfrp-character-sheet wfrp-rules-lookup"; do
  f="shared/scripts/${spec%%:*}"
  for skill in ${spec#*:}; do
    dest="skills/$skill/scripts/$(basename "$f")"
    if $check; then
      if ! cmp -s "$f" "$dest"; then
        echo "out of date: $dest"; status=1
      fi
    else
      mkdir -p "skills/$skill/scripts"
      cp "$f" "$dest"
    fi
  done
done

$check && [[ $status -eq 0 ]] && echo "shared references are in sync"
exit $status
