# People module — demo graph + People Search datasets
# Always run via `uv` from the ABI repo root so naas_abi / marketplace imports resolve.
MODULE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ABI_ROOT := $(shell d="$(MODULE_DIR)"; while [ "$$d" != / ]; do \
	if [ -f "$$d/pyproject.toml" ] && [ -d "$$d/libs/naas-abi" ]; then echo "$$d"; exit 0; fi; \
	d=$$(dirname "$$d"); \
	done; echo "$(MODULE_DIR)")
PYTHON := uv run --directory "$(ABI_ROOT)" python

.PHONY: help demo-graph

help:  ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'

demo-graph:  ## build graphs/demo/people.ttl from demo JSON (mode=demo workflow)
	$(PYTHON) -m naas_abi_marketplace.domains.intelligence.modules.people.workflows.DemoPersonGraphWorkflow --mode demo

# ── People Search (apps/people) ────────────────────────────────────────────
# person + experience -> graph -> datasets -> app
PEOPLE_API := apps/people/api/dev_server.py
PEOPLE_EXPORT := naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.export_people_from_graph

.PHONY: people-graph people-datasets people app-people

people-graph: demo-graph  ## demo person JSON -> pipelines -> graphs/demo/people.ttl

people-datasets: people-graph  ## graph -> SPARQL -> dataset service
	$(PYTHON) -m $(PEOPLE_EXPORT) $(EXPORT_ARGS)

people: people-datasets app-people  ## rebuild the datasets, then serve

app-people:  ## serve People Search on the existing datasets (no rebuild)
	$(PYTHON) "$(MODULE_DIR)/$(PEOPLE_API)"
