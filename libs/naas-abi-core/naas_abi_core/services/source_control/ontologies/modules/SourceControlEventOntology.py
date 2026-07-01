from __future__ import annotations

import datetime
from typing import Annotated, Any, ClassVar, Optional

from pydantic import Field

from naas_abi_core.services.event.ontologies.modules.EventOntology import (
    LogProcess,
    RDFEntity,
)

_NS = "http://ontology.naas.ai/abi/source_control/"


def _common_uris(extra: dict[str, str]) -> dict[str, str]:
    base = {
        "created": "http://purl.org/dc/terms/created",
        "created_at": "http://ontology.naas.ai/abi/createdAt",
        "creator": "http://purl.org/dc/terms/creator",
        "label": "http://www.w3.org/2000/01/rdf-schema#label",
    }
    base.update(extra)
    return base


class _SourceControlEvent(LogProcess, RDFEntity):
    """Shared data properties for all source-control events."""

    created_at: Optional[
        Annotated[
            datetime.datetime,
            Field(
                description="ISO 8601 timestamp at which the event occurred. "
                "Populated by EventService.publish() if not set by the caller."
            ),
        ]
    ] = None
    label: Optional[Annotated[str, Field(description="Label of the resource.")]] = None
    created: Optional[
        Annotated[
            datetime.datetime,
            Field(description="Date of creation of the resource."),
        ]
    ] = None
    creator: Optional[
        Annotated[
            Any,
            Field(description="An entity responsible for making the resource."),
        ]
    ] = None


class ProposalOpened(_SourceControlEvent):
    """A change proposal (pull/merge request) was opened."""

    _class_uri: ClassVar[str] = f"{_NS}ProposalOpened"
    _name: ClassVar[str] = "ProposalOpened"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "repo_id": f"{_NS}repoId",
            "number": f"{_NS}number",
            "title": f"{_NS}title",
            "source_branch": f"{_NS}sourceBranch",
            "target_branch": f"{_NS}targetBranch",
            "author": f"{_NS}author",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    repo_id: Optional[
        Annotated[str, Field(description="Repository id (owner/name).")]
    ] = None
    number: Optional[
        Annotated[int, Field(description="Proposal number within the repository.")]
    ] = None
    title: Optional[Annotated[str, Field(description="Proposal title.")]] = None
    source_branch: Optional[
        Annotated[str, Field(description="Source (head) branch.")]
    ] = None
    target_branch: Optional[
        Annotated[str, Field(description="Target (base) branch.")]
    ] = None
    author: Optional[Annotated[str, Field(description="Author user id.")]] = None


class ReviewSubmitted(_SourceControlEvent):
    """A review was submitted on a proposal."""

    _class_uri: ClassVar[str] = f"{_NS}ReviewSubmitted"
    _name: ClassVar[str] = "ReviewSubmitted"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "repo_id": f"{_NS}repoId",
            "number": f"{_NS}number",
            "state": f"{_NS}state",
            "author": f"{_NS}author",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    repo_id: Optional[
        Annotated[str, Field(description="Repository id (owner/name).")]
    ] = None
    number: Optional[
        Annotated[int, Field(description="Proposal number within the repository.")]
    ] = None
    state: Optional[
        Annotated[str, Field(description="Normalized review state.")]
    ] = None
    author: Optional[Annotated[str, Field(description="Reviewer user id.")]] = None


class ProposalMerged(_SourceControlEvent):
    """A proposal was merged into its target branch."""

    _class_uri: ClassVar[str] = f"{_NS}ProposalMerged"
    _name: ClassVar[str] = "ProposalMerged"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "repo_id": f"{_NS}repoId",
            "number": f"{_NS}number",
            "sha": f"{_NS}sha",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    repo_id: Optional[
        Annotated[str, Field(description="Repository id (owner/name).")]
    ] = None
    number: Optional[
        Annotated[int, Field(description="Proposal number within the repository.")]
    ] = None
    sha: Optional[
        Annotated[str, Field(description="Resulting merge commit sha, if known.")]
    ] = None


class ProposalMergeBlocked(_SourceControlEvent):
    """A merge attempt was blocked by branch protection."""

    _class_uri: ClassVar[str] = f"{_NS}ProposalMergeBlocked"
    _name: ClassVar[str] = "ProposalMergeBlocked"
    _property_uris: ClassVar[dict] = _common_uris(
        {
            "repo_id": f"{_NS}repoId",
            "number": f"{_NS}number",
            "reason": f"{_NS}reason",
        }
    )
    _object_properties: ClassVar[set[str]] = set()

    repo_id: Optional[
        Annotated[str, Field(description="Repository id (owner/name).")]
    ] = None
    number: Optional[
        Annotated[int, Field(description="Proposal number within the repository.")]
    ] = None
    reason: Optional[
        Annotated[str, Field(description="Why the merge was blocked.")]
    ] = None


# Rebuild models to resolve forward references
ProposalOpened.model_rebuild()
ReviewSubmitted.model_rebuild()
ProposalMerged.model_rebuild()
ProposalMergeBlocked.model_rebuild()
