#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Jumping Jim - publish a GitHub release
#
#   tools/release.sh v1.0.0            build, tag, push and publish the release
#   tools/release.sh v1.0.0 --draft    same, but leave the release as a draft
#   tools/release.sh v1.0.0 --dry-run  build and package only (nothing is pushed)
#
# Requirements: git, make, zip, the platform toolchains (python3, acme, c1541)
# and the GitHub CLI (https://cli.github.com) logged in:  gh auth login
#
# Every directory in platforms/ whose Makefile has a "dist" target is built and
# packaged, so new ports are picked up automatically.
# ---------------------------------------------------------------------------
set -euo pipefail

VERSION="${1:-}"
MODE="${2:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"

die()  { echo "error: $*" >&2; exit 1; }
info() { echo "==> $*"; }

[[ "$VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.]+)?$ ]] ||
    die "usage: $0 vX.Y.Z [--draft|--dry-run]   (e.g. $0 v1.0.0)"
case "$MODE" in ""|--draft|--dry-run) ;; *) die "unknown option: $MODE" ;; esac

cd "$ROOT"

# --- sanity checks -----------------------------------------------------------
for tool in git make zip; do
    command -v "$tool" >/dev/null || die "'$tool' is not installed"
done
# toolchain needed to build the C64 port
command -v python3 >/dev/null || die "python3 is not installed"
python3 -c "import PIL" 2>/dev/null ||
    die "Pillow is missing: 'sudo pacman -S python-pillow' or 'pip install pillow'"
command -v acme >/dev/null || die "the ACME assembler is not installed. Build it from source:
    git clone https://github.com/meonwax/acme && make -C acme/src && sudo cp acme/src/acme /usr/local/bin/"
command -v c1541 >/dev/null || die "c1541 (part of VICE) is not installed: 'sudo pacman -S vice'"
if [[ "$MODE" != "--dry-run" ]]; then
    command -v gh >/dev/null || die "GitHub CLI 'gh' is not installed (https://cli.github.com)"
    gh auth status >/dev/null 2>&1 || die "not logged in to GitHub: run 'gh auth login'"
    [[ -z "$(git status --porcelain)" ]] || die "uncommitted changes: commit or stash them first"
    BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    [[ "$BRANCH" == "main" ]] || die "releases are made from 'main' (current: $BRANCH)"
    git fetch --quiet --tags origin
    [[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] ||
        die "local main differs from origin/main: pull/push first"
    git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null &&
        die "tag $VERSION already exists"
fi

# --- build and package every platform ----------------------------------------
rm -rf "$DIST"
mkdir -p "$DIST"
for mk in platforms/*/Makefile; do
    dir="$(dirname "$mk")"
    if grep -q '^dist:' "$mk"; then
        info "building $(basename "$dir")"
        make -C "$dir" clean >/dev/null
        make -C "$dir" dist VERSION="$VERSION"
    fi
done
ASSETS=("$DIST"/*.*)
[[ -e "${ASSETS[0]}" ]] || die "nothing was packaged"

# a short gameplay video and the poster travel with the release
cp promo/jumpingjim_c64_gameplay.mp4 "$DIST/jumpingjim-c64-gameplay.mp4"
cp promo/00_poster_mosaic.png        "$DIST/jumpingjim-poster.png"
ASSETS=("$DIST"/*.*)

info "packaged files:"
ls -l "$DIST"

# --- release notes -------------------------------------------------------------
NOTES="$DIST/RELEASE_NOTES.md"
PREV="$(git describe --tags --abbrev=0 2>/dev/null || true)"
{
    echo "## Jumping Jim $VERSION"
    echo
    echo "Commodore 64 port of [Jumping Jim](https://roman126.itch.io/jumping-jim-zx-spectrum-next),"
    echo "the ZX Spectrum Next game by **roman126**, ported with his permission."
    echo
    echo "### Downloads"
    echo "- \`jumpingjim-c64-$VERSION.d64\`: disk image (recommended: the high score table is saved on it)"
    echo "- \`jumpingjim-c64-$VERSION.prg\`: program file"
    echo "- \`jumpingjim-c64-$VERSION.zip\`: both, with README and license"
    echo
    echo "Load with \`LOAD\"*\",8,1\` and \`RUN\`, or open the .d64 in VICE."
    echo "Keys: O/Z left, P/X right, Q/SPACE jump. Joystick in port 2 or 1."
    echo
    if [[ -n "$PREV" ]]; then
        echo "### Changes since $PREV"
        git log --no-merges --format='- %s' "$PREV"..HEAD
    else
        echo "### First release"
        echo "- Complete C64 port in 6502 assembly, SID music, top-10 high score table saved to disk"
    fi
    echo
    echo "---"
    echo "C64 port by Carlos Zayas, developed with AI assistance, for"
    echo "[Retro Informática Paraguay](https://www.youtube.com/@retroinfopy). MIT licensed; see NOTICE.md."
} > "$NOTES"

if [[ "$MODE" == "--dry-run" ]]; then
    info "dry run: release notes in $NOTES - nothing was tagged or published"
    exit 0
fi

# --- tag and publish -------------------------------------------------------------
info "tagging $VERSION"
git tag -a "$VERSION" -m "Jumping Jim $VERSION"
git push origin "$VERSION"

info "creating GitHub release"
DRAFT=()
[[ "$MODE" == "--draft" ]] && DRAFT=(--draft)
ASSETS=()
for f in "$DIST"/*; do
    [[ "$f" == "$NOTES" ]] || ASSETS+=("$f")
done
gh release create "$VERSION" "${ASSETS[@]}" \
    --title "Jumping Jim $VERSION" \
    --notes-file "$NOTES" \
    --latest "${DRAFT[@]}"

info "done: $(gh release view "$VERSION" --json url --jq .url)"
