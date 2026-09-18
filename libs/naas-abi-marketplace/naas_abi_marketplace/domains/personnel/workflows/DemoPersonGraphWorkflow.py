"""Register demo person JSON sources into the personnel graph.

``mode=demo`` writes ``graphs/demo/personnel.ttl`` on disk (no triple store).
``mode=triple_store`` inserts instance triples into the configured named graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.workflow import Workflow, WorkflowConfiguration
from naas_abi_core.workflow.workflow import WorkflowParameters
from naas_abi_marketplace.domains.personnel.graph.demo import (
    build_instance_graph,
    schema_relative_paths,
    write_demo_graph_file,
)
from naas_abi_marketplace.domains.personnel.paths import (
    DEMO_GRAPH_FILE,
    DEMO_SOURCE_DIR,
    PERSONNEL_ROOT,
    module_graph_name,
)
from pydantic import Field
from rdflib import URIRef


def _path_for_report(path: Path) -> str:
    try:
        return str(path.relative_to(PERSONNEL_ROOT))
    except ValueError:
        return str(path)


@dataclass
class DemoPersonGraphWorkflowConfiguration(WorkflowConfiguration):
    triple_store: ITripleStoreService | None = None
    graph_name: str = module_graph_name()


class DemoPersonGraphWorkflowParameters(WorkflowParameters):
    mode: Annotated[
        Literal["demo", "triple_store"],
        Field(
            description=(
                "demo: serialize schema + instances to graphs/demo/personnel.ttl. "
                "triple_store: insert instances into the personnel named graph."
            ),
        ),
    ] = "demo"
    source_dir: Annotated[
        str | None,
        Field(
            description=(
                "Directory of demo person folders (each with index.json). "
                "Defaults to data/demo/person."
            ),
        ),
    ] = None
    output_path: Annotated[
        str | None,
        Field(
            description="TTL output path when mode=demo. Defaults to graphs/demo/personnel.ttl.",
        ),
    ] = None
    include_schema_in_output: Annotated[
        bool,
        Field(description="When mode=demo, merge ontology TTL schema into the output file."),
    ] = True


class DemoPersonGraphWorkflow(Workflow[DemoPersonGraphWorkflowParameters]):
    __configuration: DemoPersonGraphWorkflowConfiguration

    def __init__(self, configuration: DemoPersonGraphWorkflowConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: DemoPersonGraphWorkflowParameters) -> dict[str, object]:
        source = Path(parameters.source_dir) if parameters.source_dir else DEMO_SOURCE_DIR
        if parameters.mode == "demo":
            output, schema_triples, instance_triples = write_demo_graph_file(
                source,
                output_path=Path(parameters.output_path)
                if parameters.output_path
                else None,
                include_schema=parameters.include_schema_in_output,
                creator="DemoPersonGraphWorkflow",
            )
            return {
                "mode": "demo",
                "source_dir": _path_for_report(source),
                "output_path": _path_for_report(output),
                "schema_triples": schema_triples,
                "instance_triples": instance_triples,
                "person_count": len(list(source.glob("*/index.json"))),
            }

        store = self.__configuration.triple_store
        if store is None:
            raise ValueError(
                "mode=triple_store requires a TripleStoreService on the workflow configuration."
            )
        instances = build_instance_graph(source, creator="DemoPersonGraphWorkflow")
        graph_iri = URIRef(self.__configuration.graph_name)
        store.insert(instances, graph_name=graph_iri)
        return {
            "mode": "triple_store",
            "graph_name": self.__configuration.graph_name,
            "source_dir": _path_for_report(source),
            "instance_triples": len(instances),
            "person_count": len(list(source.glob("*/index.json"))),
        }

    def as_tools(self) -> list[BaseTool]:
        def _run(**kwargs: object) -> str:
            result = self.run(DemoPersonGraphWorkflowParameters.model_validate(kwargs))
            mode = result["mode"]
            if mode == "demo":
                return (
                    f"Wrote demo graph to {result['output_path']} "
                    f"({result['instance_triples']} instance triples, "
                    f"{result['person_count']} people)."
                )
            return (
                f"Inserted {result['instance_triples']} instance triples into "
                f"{result['graph_name']} from {result['person_count']} demo sources."
            )

        return [
            StructuredTool.from_function(
                func=_run,
                name="build_demo_person_graph",
                description=(
                    "Load data/demo/person/*/index.json and register each profile "
                    "via register_profile_from_source (working, studying, person "
                    "profile, then roster employment records). "
                    "Use mode=demo to write graphs/demo/personnel.ttl locally."
                ),
            )
        ]

    def as_api(self) -> None:
        pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("demo", "triple_store"),
        default="demo",
        help="demo writes local TTL; triple_store needs a running ABI engine",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=f"Person JSON root (default: {DEMO_SOURCE_DIR.relative_to(PERSONNEL_ROOT)})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output TTL when mode=demo (default: {DEMO_GRAPH_FILE.relative_to(PERSONNEL_ROOT)})",
    )
    args = parser.parse_args()

    triple_store = None
    if args.mode == "triple_store":
        from naas_abi_marketplace.domains.personnel import ABIModule

        triple_store = ABIModule.get_instance().engine.services.triple_store

    workflow = DemoPersonGraphWorkflow(
        DemoPersonGraphWorkflowConfiguration(triple_store=triple_store)
    )
    result = workflow.run(
        DemoPersonGraphWorkflowParameters(
            mode=args.mode,
            source_dir=str(args.source_dir) if args.source_dir else None,
            output_path=str(args.output) if args.output else None,
        )
    )

    if result["mode"] == "demo":
        print("Loading ontology schema…")
        for rel in schema_relative_paths():
            print(f"  schema  {rel}")
        print("Building demo individuals via register_profile_from_source…")
        print(
            f"\nWrote {result['output_path']} "
            f"({result['schema_triples']} schema + {result['instance_triples']} instance triples)"
        )
    else:
        print(
            f"Inserted {result['instance_triples']} triples into {result['graph_name']} "
            f"from {result['person_count']} people."
        )


if __name__ == "__main__":
    main()
