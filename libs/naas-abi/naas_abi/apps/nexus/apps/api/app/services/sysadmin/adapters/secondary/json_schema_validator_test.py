import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.json_schema_validator import (
    MAX_ISSUES,
    JsonSchemaValidator,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import SchemaIssue
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

validator = JsonSchemaValidator()


def test_a_matching_input_has_no_issues():
    assert validator.validate(fixtures.INGEST_INPUT_SCHEMA, {"filter": "news", "limit": 3}) == []


def test_issues_name_where_the_input_is_wrong():
    issues = validator.validate(fixtures.INGEST_INPUT_SCHEMA, {"limit": 0, "dry_run": "yes"})

    assert issues == [
        SchemaIssue("", "'filter' is a required property"),
        SchemaIssue("/dry_run", "'yes' is not of type 'boolean'"),
        SchemaIssue("/limit", "0 is less than the minimum of 1"),
    ]


def test_nested_paths_are_json_pointers():
    schema = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": {"type": "integer"}}},
    }

    assert validator.validate(schema, {"items": [1, "two"]}) == [
        SchemaIssue("/items/1", "'two' is not of type 'integer'")
    ]


def test_references_inside_the_schema_resolve():
    # What a pydantic model with a nested model produces.
    schema = {
        "$defs": {
            "Pair": {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
        },
        "type": "object",
        "properties": {"pair": {"$ref": "#/$defs/Pair"}},
    }

    assert validator.validate(schema, {"pair": {"a": 1}}) == []
    assert validator.validate(schema, {"pair": {}}) == [
        SchemaIssue("/pair", "'a' is a required property")
    ]


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "no-such-type"},  # invalid
        {"$ref": "https://example.invalid/schema.json"},  # never fetched
        {"$ref": "#/$defs/missing"},
    ],
)
def test_a_schema_that_cannot_be_used_accepts_everything(schema):
    assert validator.validate(schema, {"anything": 1}) == []


def test_issues_are_capped():
    schema = {"type": "array", "items": {"type": "integer"}}

    assert len(validator.validate(schema, ["x"] * 100)) == MAX_ISSUES
