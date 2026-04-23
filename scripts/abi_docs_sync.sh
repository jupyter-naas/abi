#!/usr/bin/env bash

# Generate documentation for the packages
abi docs sync --source libs/naas-abi-marketplace/ --generate
abi docs sync --source libs/naas-abi-core/ --generate
abi docs sync --source libs/naas-abi-cli/ --generate
abi docs sync --source libs/naas-abi/ --generate

# Copy the documentation to the site
rm -rf docs/site/docs/reference/libraries
mkdir -p docs/site/docs/reference/libraries
cp -r docs/reference/{naas_abi_marketplace,naas_abi_core,naas_abi_cli,naas_abi} docs/site/docs/reference/libraries/