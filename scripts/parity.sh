#!/bin/bash
# Parity with the proof of concept (docs/PLAN.md §5): build the five release
# saves with the POC's own links and compare every file with the reference's
# checksums. Minutes, not seconds, and ~330 MB of saves: run it by hand.
#
# Usage: scripts/parity.sh [WORK_DIR]   (default: ./parity, git-ignored)
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "${1:-parity}"
work="$(cd "${1:-parity}" && pwd)"
reference="${PARITY_REFERENCE:-poc-reference-1}"

# the reference's checksums, from the POC's release of that tag
gh release download "$reference" -R diegoami/Ck-parser --dir "$work" --clobber \
  -p site-sha256.txt -p inputs-sha256.txt

# the saves, from the repository parity.toml names, checked against the inputs
uv run ck3chronicle --config "$here/parity.toml" fetch saves
(cd saves && sha256sum -c --quiet "$work/inputs-sha256.txt")

rm -rf "$work/site"
uv run ck3chronicle --config "$here/parity.toml" build saves "$work/site" --cache "$work/cache" \
  2> "$work/build.log"

cd "$work/site"
expected=$(wc -l < "$work/site-sha256.txt")
actual=$(find . -type f | wc -l)
if sha256sum -c --quiet "$work/site-sha256.txt" && [ "$expected" -eq "$actual" ]; then
  echo "parity: all $expected files identical to $reference"
else
  echo "parity: FAILED ($actual files here, $expected in $reference)" >&2
  exit 1
fi
