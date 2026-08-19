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

demo-graph:  ## build data/graph/personnel_demo.ttl from ontology classes
	$(PYTHON) "$(MODULE_DIR)/scripts/generate_demo_graph.py"

demo-source:  ## export apps/cockpit/data/source/person/<slug>/index.json
	$(PYTHON) "$(MODULE_DIR)/scripts/export_source_person_files.py"

demo-data: demo-graph demo-source  ## SPARQL the demo TTL → apps/cockpit/data
	$(PYTHON) "$(MODULE_DIR)/scripts/export_demo_apps_from_graph.py"

demo: demo-data  ## full demo pipeline

app-personnel-cockpit:  ## API + static UI dev server (optional PORT env)
	$(PYTHON) "$(MODULE_DIR)/$(COCKPIT_API)"
