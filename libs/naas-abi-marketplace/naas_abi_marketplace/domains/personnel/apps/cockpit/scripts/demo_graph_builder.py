#!/usr/bin/env python3
"""Build the personnel demo instance graph via DemoPersonGraphWorkflow.

Reads ``data/demo/person/*/index.json``, runs ``register_profile_from_source``
for each person, and writes ``graphs/demo/personnel.ttl``.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.paths import PERSONNEL_ROOT
from naas_abi_marketplace.domains.personnel.workflows.DemoPersonGraphWorkflow import (
    DemoPersonGraphWorkflow,
    DemoPersonGraphWorkflowConfiguration,
    DemoPersonGraphWorkflowParameters,
)
from naas_abi_marketplace.domains.personnel.graph.demo import schema_relative_paths


def build_and_write_demo_graph(source_dir=None):
    from pathlib import Path

    print("Loading ontology schema…")
    for rel in schema_relative_paths():
        print(f"  schema  {rel}")
    print("Building demo individuals via register_profile_from_source…")

    workflow = DemoPersonGraphWorkflow(DemoPersonGraphWorkflowConfiguration())
    result = workflow.run(
        DemoPersonGraphWorkflowParameters(
            mode="demo",
            source_dir=str(source_dir) if source_dir else None,
        )
    )
    print(
        f"\nWrote {result['output_path']} "
        f"({result['schema_triples']} schema + {result['instance_triples']} instance triples)"
    )
    return PERSONNEL_ROOT / result["output_path"]


def main() -> None:
    build_and_write_demo_graph()


if __name__ == "__main__":
    main()
