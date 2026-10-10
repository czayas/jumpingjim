#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Jumping Jim - publish a GitHub release from a ready-made zip
#
#   tools/release.sh v1.0.0
#
# Publishes releases/jumpingjim-c64-<version>.zip (already built and committed)
# as the GitHub release <version>. Nothing is compiled.
# Requirement: the GitHub CLI logged in  ->  sudo pacman -S github-cli && gh auth login
# ---------------------------------------------------------------------------
set -euo pipefail

VERSION="${1:-}"
[[ -n "$VERSION" ]] || { echo "usage: $0 vX.Y.Z   (e.g. $0 v1.0.0)"; exit 1; }

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ZIP="releases/jumpingjim-c64-$VERSION.zip"

[[ -f "$ZIP" ]] || { echo "error: $ZIP not found"; exit 1; }
command -v gh >/dev/null || { echo "error: install the GitHub CLI: sudo pacman -S github-cli"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "error: run 'gh auth login' first"; exit 1; }

NOTES="Commodore 64 port of [Jumping Jim](https://roman126.itch.io/jumping-jim-zx-spectrum-next), the ZX Spectrum Next game by **roman126**, ported with his permission.

The zip contains \`jumpingjim.d64\` (recommended: the high score table is saved on it), \`jumpingjim.prg\`, a short README and the license.
Load with \`LOAD\"*\",8,1\` and \`RUN\`, or open the .d64 in VICE.
Keys: O/Z left, P/X right, Q/SPACE jump. Joystick in port 2 or 1.

C64 port by Carlos Zayas, developed with AI assistance, for [Retro Informática Paraguay](https://www.youtube.com/@retroinfopy). MIT licensed; see NOTICE.md."

gh release create "$VERSION" "$ZIP" --title "Jumping Jim $VERSION" --notes "$NOTES"
