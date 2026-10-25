"""Workflow inputs checked against their JSON Schema (``jsonschema``).

Schemas come from module descriptors, so they are untrusted: references are
resolved inside the schema only. The validator gets an empty ``referencing``
registry; without one, jsonschema falls back to a registry that fetches ``http(s)``
and ``file`` references (with a DeprecationWarning). A schema this validator cannot use (invalid, or with a
reference it cannot resolve) accepts everything rather than blocking the run;
the module validates its own input anyway.
"""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import SchemaIssue
from naas_abi_core import logger
from referencing import Registry

# Enough to fix an input; a payload with hundreds of faults is not listed in full.
MAX_ISSUES = 20


def _pointer(path: Any) -> str:
    return "".join("/" + str(part).replace("~", "~0").replace("/", "~1") for part in path)


class JsonSchemaValidator:
    def validate(self, schema: dict[str, Any], payload: Any) -> list[SchemaIssue]:
        from jsonschema import exceptions, validators

        try:
            cls = validators.validator_for(schema)
            cls.check_schema(schema)
            errors = sorted(
                cls(schema, registry=Registry()).iter_errors(payload),
                key=lambda e: (list(map(str, e.absolute_path)), e.message),
            )
        except Exception as exc:  # noqa: BLE001 - a schema we cannot use must not block a run
            reason = (
                "invalid schema" if isinstance(exc, exceptions.SchemaError) else type(exc).__name__
            )
            logger.warning(f"workflow input not validated: {reason}")
            return []
        return [SchemaIssue(_pointer(e.absolute_path), e.message) for e in errors[:MAX_ISSUES]]
