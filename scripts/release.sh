#!/usr/bin/env bash
#
# Move the VERSION file and tag the commit. Does not build or push: the image is
# built from the tagged commit afterwards, so the tag and the image always agree.
#
# Usage:
#   scripts/release.sh 0.3.0
#   scripts/release.sh patch|minor|major
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

[[ $# -eq 1 ]] || { echo "usage: $0 <version|patch|minor|major>" >&2; exit 2; }

CURRENT="$(tr -d '[:space:]' < VERSION)"
IFS='.' read -r major minor patch <<< "$CURRENT"

case "$1" in
    major) NEXT="$((major + 1)).0.0" ;;
    minor) NEXT="${major}.$((minor + 1)).0" ;;
    patch) NEXT="${major}.${minor}.$((patch + 1))" ;;
    *)
        [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
            echo "not a semantic version: $1" >&2; exit 2; }
        NEXT="$1"
        ;;
esac

if [[ -n "$(git status --porcelain)" ]]; then
    echo "working tree is not clean - commit or stash first" >&2
    exit 1
fi

echo "$NEXT" > VERSION
git add VERSION
git commit -m "Release $NEXT"
git tag -a "v$NEXT" -m "Release $NEXT"

echo
echo "released $CURRENT -> $NEXT"
echo "next:"
echo "  git push && git push --tags"
echo "  scripts/build-image.sh --push"
