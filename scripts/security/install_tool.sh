#!/usr/bin/env bash
# Download a pinned scanner release, verify its SHA-256, and put it on PATH.
#
#   install_tool.sh <binary-name> <url> <sha256>
#
# Handles bare binaries, .tar.gz and .zip archives. Pinning the checksum here
# (not fetching it from the same release) means a tampered release asset fails
# the build instead of running on our runner.
set -euo pipefail

name="$1"
url="$2"
sha256="$3"

bin_dir="${RUNNER_TEMP:-/tmp}/security-bin"
work_dir="$(mktemp -d)"
mkdir -p "$bin_dir"
trap 'rm -rf "$work_dir"' EXIT

asset="$work_dir/$(basename "$url")"
curl --fail --silent --show-error --location --retry 3 --output "$asset" "$url"
echo "$sha256  $asset" | sha256sum --check --quiet

case "$asset" in
  *.tar.gz) tar -xzf "$asset" -C "$work_dir" ;;
  *.zip) unzip -q -o "$asset" -d "$work_dir" 2>/dev/null || python3 -m zipfile -e "$asset" "$work_dir" ;;
  *) mv "$asset" "$work_dir/$name" ;;
esac

install -m 0755 "$(find "$work_dir" -type f -name "$name" | head -n 1)" "$bin_dir/$name"

if [ -n "${GITHUB_PATH:-}" ]; then
  echo "$bin_dir" >> "$GITHUB_PATH"
fi
"$bin_dir/$name" --version 2>/dev/null | head -n 1 || true
