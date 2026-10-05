#!/usr/bin/env python3
"""Build the personnel demo graph via DemoPersonnelGraphWorkflow.

Reads the people module's ``data/demo/person/*/index.json``, registers each
person as the people module does, adds the employer's records on top, and
writes ``graphs/demo/personnel.ttl``.
"""

from __future__ import annotations

from naas_abi_marketplace.domains.personnel.scripts.demo_graph import (
    schema_relative_paths,
)
from naas_abi_marketplace.domains.personnel.utils.paths import PERSONNEL_ROOT
from naas_abi_marketplace.domains.personnel.workflows.DemoPersonnelGraphWorkflow import (
    DemoPersonnelGraphWorkflow,
    DemoPersonnelGraphWorkflowConfiguration,
    DemoPersonnelGraphWorkflowParameters,
)


def build_and_write_demo_graph(source_dir=None):

    print("Loading ontology schema…")
    for rel in schema_relative_paths():
        print(f"  schema  {rel}")
    print("Building demo individuals and the employer's records…")

    workflow = DemoPersonnelGraphWorkflow(DemoPersonnelGraphWorkflowConfiguration())
    result = workflow.run(
        DemoPersonnelGraphWorkflowParameters(
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
