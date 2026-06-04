#!/usr/bin/env bash
# Thin wrapper around the X tweet-dump generator that runs through
# `abi run script` so the engine is preloaded for the Python entry point.
#
# Usage (from anywhere — the script self-locates and cd's to the
# project root before delegating, so you don't need to be in the repo
# root):
#
#   /…/applications/x/scripts/generate_tweet_dump.sh \
#       --query '(openai OR anthropic) lang:en -is:retweet' \
#       --max-pages 5
#
# Pass --help to see the underlying argparse options:
#
#   /…/applications/x/scripts/generate_tweet_dump.sh --help
#
# The `--` separator stops `abi run script` from intercepting `--help`
# (and any other flags it knows about) and forwards them verbatim to
# the Python script's argparse layer instead.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/generate_tweet_dump.py"

# `Engine().load()` reads ./config.yaml via a cwd-relative path, and
# `abi`'s project-root re-exec preserves the invocation cwd — so if the
# user runs this from inside scripts/ or anywhere else under the tree
# the engine boot fails with "Configuration file not found". Walk up
# from this script's location looking for config.yaml and cd there
# before delegating, so the wrapper works from any pwd.
ROOT="$HERE"
while [ "$ROOT" != "/" ] && [ ! -f "$ROOT/config.yaml" ]; do
    ROOT="$(dirname "$ROOT")"
done
if [ ! -f "$ROOT/config.yaml" ]; then
    echo "error: could not find config.yaml in any parent of $HERE" >&2
    exit 1
fi
cd "$ROOT"

exec abi run script "$SCRIPT" -- "$@"
