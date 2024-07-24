#!/usr/bin/env bash

# Enable conda in this script.
source /opt/conda/etc/profile.d/conda.sh

# Activate the conda environment.
conda activate /app/.abi-conda

# Executing user command.
exec "$@"