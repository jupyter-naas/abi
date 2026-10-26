"""Registry objects <-> ``abi.tool_registry.v1`` messages, shared by the primary
(serving engine) and the client (engines reading its catalog).

A definition crosses the wire as data: its schemas are UTF-8 JSON objects with
finite numbers, and nothing of a binding does, so a binding's configuration
cannot be sent by mistake.
"""

from __future__ import annotations

import json
from typing import Any

from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    ToolAvailability,
    ToolDefinition,
    ToolFilter,
    ToolListing,
    ToolRegistryError,
    ToolRequirements,
    ToolSearchResult,
)
from naas_abi_proto.tool_registry.v1 import tool_registry_pb2 as pb
from pydantic import ValidationError

SUBJECT_PREFIX = "abi.svc.tool_registry.v1"
SERVICE_NAME = "tool_registry"
SERVICE_VERSION = "1.0.0"
OPERATIONS = ("list_tools", "get_tool", "search_tools", "invoke_tool", "cancel_tool")

# Request limits, enforced by the primary (the contract states them).
MAX_QUERY_CHARS = 2000
MAX_REF_CHARS = 512
MAX_FILTER_MODULES = 32
MAX_FILTER_MODULE_CHARS = 256
MAX_FILTER_TAGS = 16
MAX_FILTER_TAG_CHARS = 64
MAX_AFTER_CHARS = 512
DEFAULT_SEARCH_LIMIT = 5
DEFAULT_LIST_LIMIT = 100


def _json_object(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def _decode_object(data: bytes) -> dict[str, Any]:
    if not data:
        return {}
    value = json.loads(
        data.decode(),
        parse_constant=lambda constant: (_ for _ in ()).throw(
            ValueError(f"{constant} is not a JSON number")
        ),
    )
    if not isinstance(value, dict):
        raise TypeError("A schema must be a JSON object")
    return value


def definition_to_pb(definition: ToolDefinition) -> pb.ToolDefinition:
    """Raises ``ValueError`` for a schema JSON cannot carry (NaN, bytes...)."""
    return pb.ToolDefinition(
        id=str(definition.id),
        namespace=definition.namespace,
        name=definition.name,
        version=definition.version,
        module=definition.module,
        description=definition.description,
        input_schema_json=_json_object(definition.input_schema),
        output_schema_json=(
            _json_object(definition.output_schema)
            if definition.output_schema is not None
            else b""
        ),
        tags=definition.tags,
        requirements=pb.ToolRequirements(
            config=[
                pb.ConfigRequirement(
                    key=requirement.key,
                    description=requirement.description,
                    secret=requirement.secret,
                    required=requirement.required,
                )
                for requirement in definition.requirements.config
            ],
            requires_workspace=definition.requirements.requires_workspace,
        ),
        required_scopes=sorted(definition.required_scopes),
        remote=definition.remote,
    )


def definition_from_pb(message: pb.ToolDefinition) -> ToolDefinition:
    """Raises ``ToolRegistryError`` for a definition this registry would not accept."""
    try:
        definition = ToolDefinition(
            namespace=message.namespace,
            name=message.name,
            version=message.version,
            module=message.module,
            description=message.description,
            input_schema=_decode_object(message.input_schema_json),
            output_schema=(
                _decode_object(message.output_schema_json)
                if message.output_schema_json
                else None
            ),
            tags=tuple(message.tags),
            requirements=ToolRequirements(
                config=tuple(
                    ConfigRequirement(
                        key=requirement.key,
                        description=requirement.description,
                        secret=requirement.secret,
                        required=requirement.required,
                    )
                    for requirement in message.requirements.config
                ),
                requires_workspace=message.requirements.requires_workspace,
            ),
            required_scopes=tuple(message.required_scopes),
            remote=message.remote,
        )
    except (ValidationError, TypeError, ValueError) as exc:
        raise ToolRegistryError(f"Invalid tool definition on the wire: {exc}") from exc
    if message.id and message.id != str(definition.id):
        raise ToolRegistryError(
            f"Tool definition id {message.id!r} does not match its parts "
            f"{str(definition.id)!r}"
        )
    return definition


def availability_to_pb(availability: ToolAvailability) -> pb.ToolAvailability:
    return pb.ToolAvailability(
        available=availability.available, missing_config=availability.missing_config
    )


def availability_from_pb(message: pb.ToolAvailability) -> ToolAvailability:
    return ToolAvailability(
        available=message.available, missing_config=tuple(message.missing_config)
    )


def entry_to_pb(listing: ToolListing) -> pb.ToolEntry:
    return pb.ToolEntry(
        definition=definition_to_pb(listing.definition),
        availability=availability_to_pb(listing.availability),
    )


def listing_from_pb(message: pb.ToolEntry) -> ToolListing:
    return ToolListing(
        definition=definition_from_pb(message.definition),
        availability=availability_from_pb(message.availability),
    )


def match_to_pb(result: ToolSearchResult) -> pb.ToolMatch:
    return pb.ToolMatch(
        tool=entry_to_pb(
            ToolListing(definition=result.definition, availability=result.availability)
        ),
        score=result.score,
    )


def result_from_pb(message: pb.ToolMatch) -> ToolSearchResult:
    listing = listing_from_pb(message.tool)
    definition = listing.definition
    return ToolSearchResult(
        tool_id=str(definition.id),
        name=definition.name,
        description=definition.description,
        module=definition.module,
        score=message.score,
        availability=listing.availability,
        definition=definition,
    )


def filter_to_pb(filter: ToolFilter | None) -> pb.ToolFilter:
    filter = filter or ToolFilter()
    return pb.ToolFilter(
        modules=filter.modules, tags=filter.tags, available_only=filter.available_only
    )


def filter_from_pb(message: pb.ToolFilter) -> ToolFilter:
    """Raises ``ValueError`` for a filter beyond the contract's limits."""
    if len(message.modules) > MAX_FILTER_MODULES or len(message.tags) > MAX_FILTER_TAGS:
        raise ValueError("Too many filter values")
    if any(len(value) > MAX_FILTER_MODULE_CHARS for value in message.modules) or any(
        len(value) > MAX_FILTER_TAG_CHARS for value in message.tags
    ):
        raise ValueError("A filter value is too long")
    return ToolFilter(
        modules=tuple(message.modules),
        tags=tuple(message.tags),
        available_only=message.available_only,
    )
