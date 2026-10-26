"""Pipelines of a remote module, written like ``naas_abi_core.pipeline``'s.

A pipeline is ``await run(parameters)`` returning an rdflib ``Graph``. Put it
under the package's ``pipelines/`` folder; ``BaseModule`` builds it, and the
module's agents call it through ``as_tools()`` (the graph comes back as turtle).
Needs ``pip install 'naas-abi-sdk[workflows,rdf]'``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from naas_abi_sdk.processes import Process, ProcessConfiguration, ProcessParameters

try:
    from rdflib import Graph
except ImportError as exc:  # pragma: no cover - exercised without the extra
    raise ImportError(
        "naas_abi_sdk pipelines need rdflib: pip install 'naas-abi-sdk[workflows,rdf]'"
    ) from exc


@dataclass
class PipelineConfiguration(ProcessConfiguration):
    """Base configuration of pipelines: add the attributes a pipeline needs."""


class PipelineParameters(ProcessParameters):
    """Base parameters of pipelines: add the runtime parameters a run takes."""


P = TypeVar("P", bound=PipelineParameters)


class Pipeline(Process, Generic[P]):
    """Processes data into an RDF graph a module can write to the triple store."""

    kind: ClassVar[str] = "pipeline"
    _configuration_base: ClassVar[type] = PipelineConfiguration
    _parameters_base: ClassVar[type[ProcessParameters]] = PipelineParameters

    async def run(self, parameters: P) -> Graph:
        raise NotImplementedError(f"{type(self).__name__}.run is not implemented")
