#!/usr/bin/env bash
# Decides whether a naas-abi release moves the :latest tag of its container
# images. Shared by build_nexus_web_container.yml and build_abi_container.yml.
#
# Usage: release_is_latest.sh <release tag> <release commit sha> <owner/repo>
#
# A release moves :latest only when both hold:
#   (a) main contains its commit. A release from v2 (2.x fixes) or dev
#       (prereleases) carries a commit main does not contain; the compare API
#       answers "identical" or "ahead" when main contains it.
#   (b) its version is the highest of the published, non-draft, non-prerelease
#       naas-abi-vX.Y.Z releases, compared numerically (10.0.0 > 9.9.9). An
#       older release that finishes building last, or an old release built
#       again, leaves :latest where it is. Rebuilding the newest release still
#       moves it, to the rebuilt image of the same version.
#
# Run it right before tagging, so it sees releases published while the image
# was building. Prints why it decided, then `latest=true` or `latest=false`,
# also appended to $GITHUB_OUTPUT when set. A failed API call fails the script:
# it never falls back to latest=true. Needs `gh` with GH_TOKEN.
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 <release tag> <release commit sha> <owner/repo>" >&2
  exit 2
fi

RELEASE_TAG="$1"
RELEASE_SHA="$2"
REPO="$3"
PREFIX="naas-abi-v"
STABLE_TAG_RE='^naas-abi-v[0-9]+\.[0-9]+\.[0-9]+$'

decide() {
  echo "latest=$1"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    echo "latest=$1" >> "$GITHUB_OUTPUT"
  fi
}

# (a) Is the release commit on main?
STATUS=$(gh api "repos/${REPO}/compare/${RELEASE_SHA}...main?per_page=1" --jq .status)
echo "main compared with ${RELEASE_SHA}: ${STATUS}"
case "$STATUS" in
  identical|ahead) ON_MAIN=true ;;
  *) ON_MAIN=false ;;
esac

# (b) Is it the highest stable naas-abi-v* release? The repository publishes
# many package releases, so read every page. Written to a file first, so a
# failed call stops the script under `set -e`.
RELEASES=$(mktemp)
trap 'rm -f "$RELEASES"' EXIT
gh api --paginate "repos/${REPO}/releases?per_page=100" \
  --jq '.[] | select((.draft | not) and (.prerelease | not)) | .tag_name' \
  > "$RELEASES"

STABLE=$(grep -E "$STABLE_TAG_RE" "$RELEASES" | sed "s/^${PREFIX}//" | sort -V || true)
if [ -z "$STABLE" ]; then
  echo "error: no published stable ${PREFIX}X.Y.Z release found in ${REPO}" >&2
  exit 1
fi
HIGHEST="${PREFIX}$(echo "$STABLE" | tail -n 1)"
echo "highest published stable release: ${HIGHEST}"

if ! grep -qxF "$RELEASE_TAG" "$RELEASES" || ! [[ "$RELEASE_TAG" =~ $STABLE_TAG_RE ]]; then
  echo "${RELEASE_TAG} is not a published stable ${PREFIX}X.Y.Z release"
  decide false
elif [ "$ON_MAIN" != true ]; then
  echo "${RELEASE_TAG}: main does not contain its commit"
  decide false
elif [ "$RELEASE_TAG" != "$HIGHEST" ]; then
  echo "${RELEASE_TAG} is older than ${HIGHEST}"
  decide false
else
  echo "${RELEASE_TAG} is on main and the highest stable release"
  decide true
fi
