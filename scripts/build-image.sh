#!/usr/bin/env bash
#
# Build (and optionally push) this repo's Docker image with a consistent set of
# tags and build metadata baked in.
#
# Versioning scheme
# -----------------
#   <version>            the VERSION file, e.g. 0.2.0 - moves only on a release
#   <version>-<sha>      that release built from an exact commit
#   sha-<sha>            every build, whether or not VERSION moved
#   latest               only from the release branch, and only from a clean tree
#
# `sha-<sha>` is the tag deployments should pin to: it is unambiguous and can
# never be re-pointed at different content. `latest` exists for convenience and
# is deliberately refused on a dirty tree, because an image built from uncommitted
# code that nobody can check out again is the thing that makes an incident
# unexplainable.
#
# Usage:
#   scripts/build-image.sh                       build locally
#   scripts/build-image.sh --push                build and push every tag
#   scripts/build-image.sh --registry ghcr.io/acme
#   scripts/build-image.sh --version 0.3.0       override the VERSION file
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

IMAGE_NAME="$(basename "$REPO_ROOT")"
RELEASE_BRANCH="${RELEASE_BRANCH:-main}"

# __REGISTRY__ is a placeholder: set REGISTRY in the environment, pass
# --registry, or fill it in here once the organisation's registry exists.
REGISTRY="${REGISTRY:-__REGISTRY__}"
VERSION=""
PUSH="false"
EXTRA_BUILD_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --push) PUSH="true"; shift ;;
        --registry) REGISTRY="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --build-arg) EXTRA_BUILD_ARGS+=(--build-arg "$2"); shift 2 ;;
        -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

if [[ -z "$VERSION" ]]; then
    [[ -f VERSION ]] || { echo "no VERSION file in $REPO_ROOT" >&2; exit 1; }
    VERSION="$(tr -d '[:space:]' < VERSION)"
fi

GIT_SHA="$(git rev-parse --short=7 HEAD 2>/dev/null || echo unknown)"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

DIRTY="false"
if ! git diff --quiet HEAD -- 2>/dev/null || [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    DIRTY="true"
    GIT_SHA="${GIT_SHA}-dirty"
fi

if [[ "$REGISTRY" == "__REGISTRY__" ]]; then
    IMAGE="$IMAGE_NAME"
    echo "note: REGISTRY is not configured, building the local tag '$IMAGE'."
    echo "      Set REGISTRY=<host>/<namespace> before using --push."
else
    IMAGE="${REGISTRY%/}/$IMAGE_NAME"
fi

TAGS=("$IMAGE:sha-$GIT_SHA" "$IMAGE:$VERSION-$GIT_SHA" "$IMAGE:$VERSION")

if [[ "$BRANCH" == "$RELEASE_BRANCH" && "$DIRTY" == "false" ]]; then
    TAGS+=("$IMAGE:latest")
else
    echo "note: skipping the 'latest' tag (branch=$BRANCH, dirty=$DIRTY)."
fi

TAG_ARGS=()
for tag in "${TAGS[@]}"; do TAG_ARGS+=(--tag "$tag"); done

echo "building $IMAGE_NAME"
echo "  version    $VERSION"
echo "  commit     $GIT_SHA (branch $BRANCH)"
echo "  built at   $BUILD_DATE"
printf '  tag        %s\n' "${TAGS[@]}"
echo

docker build \
    --build-arg "VERSION=$VERSION" \
    --build-arg "GIT_SHA=$GIT_SHA" \
    --build-arg "BUILD_DATE=$BUILD_DATE" \
    "${EXTRA_BUILD_ARGS[@]+"${EXTRA_BUILD_ARGS[@]}"}" \
    "${TAG_ARGS[@]}" \
    .

if [[ "$PUSH" == "true" ]]; then
    if [[ "$REGISTRY" == "__REGISTRY__" ]]; then
        echo "refusing to push: no registry configured" >&2
        exit 1
    fi
    if [[ "$DIRTY" == "true" ]]; then
        echo "refusing to push an image built from uncommitted changes" >&2
        exit 1
    fi
    for tag in "${TAGS[@]}"; do
        echo "pushing $tag"
        docker push "$tag"
    done
fi

# The digest is what a deployment should record: it survives a tag being moved.
DIGEST="$(docker image inspect "${TAGS[0]}" --format '{{index .Id}}' 2>/dev/null || echo unknown)"
echo
echo "built  ${TAGS[0]}"
echo "image  $DIGEST"
