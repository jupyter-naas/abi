#!/usr/bin/env bash
# Thin wrapper around the X tweet-dump generator that runs through
# `abi run script` so the engine is preloaded for the Python entry point.
#
# Usage (anywhere — the script self-locates relative to itself):
#
#   libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/scripts/generate_tweet_dump.sh \
#       --query '(openai OR anthropic) lang:en -is:retweet' \
#       --max-pages 5
#
# Pass --help to see the underlying argparse options:
#
#   libs/naas-abi-marketplace/naas_abi_marketplace/applications/x/scripts/generate_tweet_dump.sh --help
#
# The `--` separator stops `abi run script` from intercepting `--help`
# (and any other flags it knows about) and forwards them verbatim to
# the Python script's argparse layer instead.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/generate_tweet_dump.py"

exec abi run script "$SCRIPT" -- "$@"
