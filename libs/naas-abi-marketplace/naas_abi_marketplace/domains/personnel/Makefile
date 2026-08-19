# Personnel module — demo graph + cockpit datasets
# Always run via `uv` from the ABI repo root so naas_abi / marketplace imports resolve.
MODULE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ABI_ROOT := $(shell d="$(MODULE_DIR)"; while [ "$$d" != / ]; do \
	if [ -f "$$d/pyproject.toml" ] && [ -d "$$d/libs/naas-abi" ]; then echo "$$d"; exit 0; fi; \
	d=$$(dirname "$$d"); \
	done; echo "$(MODULE_DIR)")
PYTHON := uv run --directory "$(ABI_ROOT)" python
COCKPIT_API := apps/cockpit/api/dev_server.py

.PHONY: help demo-graph demo-source demo-data demo app-personnel-cockpit

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

demo-graph:  ## build graphs/demo/personnel.ttl from demo source via pipelines
	$(PYTHON) "$(MODULE_DIR)/apps/cockpit/scripts/demo_graph_builder.py"

demo-source:  ## export data/demo/person/<slug>/index.json from LinkedIn seeds
	$(PYTHON) "$(MODULE_DIR)/apps/cockpit/scripts/export_source_person_files.py"

demo-data: demo-graph  ## graph TTL → apps/cockpit/data (reference) + ObjectStorage publish
	$(PYTHON) "$(MODULE_DIR)/apps/cockpit/scripts/export_demo_apps_from_graph.py"

demo: demo-data  ## full demo pipeline

app-personnel-cockpit: demo-data  ## source JSON → cockpit data → dev server
	$(PYTHON) "$(MODULE_DIR)/$(COCKPIT_API)"
