#!/usr/bin/env bash
set -euo pipefail

# Generate library reference markdown under docs/reference.
abi docs sync --source libs/naas-abi-marketplace/ --generate
abi docs sync --source libs/naas-abi-core/ --generate
abi docs sync --source libs/naas-abi-cli/ --generate
abi docs sync --source libs/naas-abi/ --generate
