#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Copy the RIP intro module (github.com/czayas/rip-intro, private) into lib/rip-intro.
#
#   tools/update_rip_intro.sh [path to a rip-intro checkout]   (default: ../rip-intro)
#
# Only the files the build needs are copied (module, converter, logo); the
# commit they come from is written to lib/rip-intro/VERSION. Commit the result.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SRC="${1:-../rip-intro}"
[[ -f "$SRC/c64/rip_intro.a" ]] || { echo "error: $SRC is not a rip-intro checkout"; exit 1; }
DST=lib/rip-intro
rm -rf "$DST"
mkdir -p "$DST/c64" "$DST/tools" "$DST/assets"
cp "$SRC/c64/rip_intro.a" "$DST/c64/"
cp "$SRC/tools/convertir.py" "$DST/tools/"
cp "$SRC/assets/rip_logo.png" "$DST/assets/"
cp "$SRC/docs/ESPECIFICACION.md" "$DST/"
git -C "$SRC" log -1 --format='%H %cs %s' > "$DST/VERSION"
echo "lib/rip-intro updated to: $(cat $DST/VERSION)"
