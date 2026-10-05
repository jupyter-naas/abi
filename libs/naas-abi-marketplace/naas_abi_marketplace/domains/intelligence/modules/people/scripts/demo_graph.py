"""Build the people demo instance graph from ``data/demo/person`` JSON."""

from __future__ import annotations

from pathlib import Path

from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfCertificationPipeline import (
    ActOfCertificationPipeline,
    ActOfCertificationPipelineConfiguration,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.PersonProfilePipeline import (
    PersonProfilePipeline,
    PersonProfilePipelineConfiguration,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.profile_from_source import (
    apply_profile_source_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    PeopleGraphContext,
    bind_graph_prefixes,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    DEMO_GRAPH_FILE,
    DEMO_SOURCE_DIR,
    ONTOLOGIES_DIR,
    PEOPLE_ROOT,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.person_sources import (
    load_person_sources,
    payload_to_profile_source_parameters,
)
from rdflib import Graph


def load_schema_graph() -> Graph:
    graph = Graph()
    for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl")):
        if "queries" in path.parts:
            continue
        graph.parse(path, format="turtle")
    return graph


def build_instance_graph(
    source_dir: Path | None = None,
    *,
    creator: str = "demo_person_graph",
    context: PeopleGraphContext | None = None,
) -> Graph:
    """Register every demo ``index.json`` via ``register_profile_from_source`` logic.

    Pass ``context`` to build into a caller's context (the personnel demo layers
    its internal records on top of the same individuals).
    """
    root = source_dir or DEMO_SOURCE_DIR
    payloads = load_person_sources(root)

    context = context if context is not None else PeopleGraphContext(creator=creator)
    pipeline_cfg = dict(triple_store=None, persist=False, context=context)
    working = ActOfWorkingPipeline(ActOfWorkingPipelineConfiguration(**pipeline_cfg))
    studying = ActOfStudyingPipeline(ActOfStudyingPipelineConfiguration(**pipeline_cfg))
    certification = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(**pipeline_cfg)
    )
    profile_pipeline = PersonProfilePipeline(
        PersonProfilePipelineConfiguration(**pipeline_cfg)
    )

    for payload in payloads:
        apply_profile_source_payload(
            payload_to_profile_source_parameters(payload),
            context=context,
            working=working,
            studying=studying,
            profile_pipeline=profile_pipeline,
            certification=certification,
        )
    return context.graph


def write_demo_graph_file(
    source_dir: Path | None = None,
    *,
    output_path: Path | None = None,
    include_schema: bool = True,
    creator: str = "demo_person_graph",
) -> tuple[Path, int, int]:
    """Write ``graphs/demo/people.ttl`` (schema + instances by default).

    Returns ``(path, schema_triple_count, instance_triple_count)``.
    """
    schema = load_schema_graph() if include_schema else Graph()
    instances = build_instance_graph(source_dir, creator=creator)

    combined = Graph()
    combined += schema
    combined += instances
    bind_graph_prefixes(combined)

    destination = output_path or DEMO_GRAPH_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.serialize(destination=str(destination), format="turtle")
    return destination, len(schema), len(instances)


def schema_relative_paths() -> list[Path]:
    return [
        path.relative_to(PEOPLE_ROOT)
        for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl"))
        if "queries" not in path.parts
    ]
