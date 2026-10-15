import json

import pytest

from naas_abi_core.services.iam.catalog import (
    ActionCatalog,
    ActionSpec,
    CatalogError,
    CatalogRegistry,
    ResourceType,
)
from naas_abi_core.services.iam.policy import (
    POLICY_VERSION,
    PolicyDocument,
    PolicyValidationError,
    parse_policy_document,
)

CATALOG = ActionCatalog(
    service="triple_store",
    version=1,
    resource_types=(ResourceType("graph"),),
    actions=(
        ActionSpec("Query", "read", ("graph",)),
        ActionSpec("ListGraphs", "list", ("graph",)),
    ),
)


def registry() -> CatalogRegistry:
    found = CatalogRegistry()
    found.register(CATALOG)
    return found


YAML = """
version: "2026-10-13"
statements:
  - sid: ReadSalesGraph
    effect: Allow
    actions: [triple_store:Query, triple_store:ListGraphs]
    resources:
      - "abi:org-1:ws-1:triple_store:graph/http%3A%2F%2Fx%2Fsales-*"
  - effect: Deny
    actions: ["triple_store:*"]
    resources: ["*"]
"""


def test_yaml_and_json_parse_to_the_same_document():
    from_yaml = parse_policy_document(YAML, registry())
    from_json = parse_policy_document(json.dumps(from_yaml.to_dict()), registry())
    assert from_yaml == from_json
    assert from_yaml.statements[0].sid == "ReadSalesGraph"
    assert from_yaml.statements[1].effect == "Deny"
    assert PolicyDocument.from_dict(json.loads(from_yaml.to_json())) == from_yaml


def test_every_error_is_listed():
    with pytest.raises(PolicyValidationError) as invalid:
        parse_policy_document(
            {
                "version": "2012-10-17",
                "extra": 1,
                "statements": [
                    {
                        "sid": "bad sid",
                        "effect": "allow",
                        "actions": [],
                        "resources": ["*"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["triple_store:Query"],
                        "resources": ["graph/x"],
                        "conditions": {},
                    },
                    {
                        "sid": "Dup",
                        "effect": "Allow",
                        "actions": ["*"],
                        "resources": ["*"],
                    },
                    {
                        "sid": "Dup",
                        "effect": "Allow",
                        "actions": ["*"],
                        "resources": ["*"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["triple_store:${x}"],
                        "resources": ["abi:-:-:t/${unknown}"],
                    },
                ],
            }
        )
    errors = invalid.value.errors
    joined = " | ".join(errors)
    for expected in (
        "unknown field 'extra'",
        "version must be",
        "sid must match",
        "effect must be exactly",
        "1 to 100 patterns",
        "conditions are reserved",
        "'graph/x' is '*' or starts with 'abi:'",
        "duplicate sid 'Dup'",
        "variables are not allowed in actions",
        "unknown variable ${unknown}",
    ):
        assert expected in joined, expected


def test_actions_are_checked_against_catalogs():
    def check(actions):
        return parse_policy_document(
            {
                "version": POLICY_VERSION,
                "statements": [
                    {"effect": "Allow", "actions": actions, "resources": ["*"]}
                ],
            },
            registry(),
        )

    check(["triple_store:Query"])
    check(["triple_store:List*", "*", "triple_store:*"])
    for bad in (["triple_store:Drop"], ["dataset:*"], ["triple_store:X?z"]):
        with pytest.raises(PolicyValidationError):
            check(bad)
    # Without catalogs only the shape is checked.
    parse_policy_document(
        {
            "version": POLICY_VERSION,
            "statements": [
                {"effect": "Allow", "actions": ["dataset:*"], "resources": ["*"]}
            ],
        }
    )


def test_limits():
    statement = {"effect": "Allow", "actions": ["*"], "resources": ["*"]}
    with pytest.raises(PolicyValidationError):
        parse_policy_document({"version": POLICY_VERSION, "statements": []})
    with pytest.raises(PolicyValidationError):
        parse_policy_document(
            {"version": POLICY_VERSION, "statements": [statement] * 101}
        )
    big = {**statement, "resources": ["abi:-:-:t/" + "x" * 400] * 99}
    with pytest.raises(PolicyValidationError, match="exceeds"):
        parse_policy_document({"version": POLICY_VERSION, "statements": [big]})
    with pytest.raises(PolicyValidationError):
        parse_policy_document("- not a mapping")


def test_scope_use_is_detected():
    document = parse_policy_document(
        {
            "version": POLICY_VERSION,
            "statements": [
                {"effect": "Allow", "actions": ["*"], "resources": ["${scope}:svc:t/*"]}
            ],
        }
    )
    assert document.uses_scope


def test_catalogs_validate_themselves():
    with pytest.raises(CatalogError):
        ActionCatalog(service="Bad", version=1)
    with pytest.raises(CatalogError):
        ActionCatalog(
            service="svc",
            version=1,
            resource_types=(ResourceType("t"),),
            actions=(ActionSpec("Get", "read", ("missing",)),),
        )
    with pytest.raises(CatalogError):
        ActionCatalog(
            service="svc",
            version=1,
            resource_types=(ResourceType("t"),),
            actions=(
                ActionSpec("Get", "read", ("t",)),
                ActionSpec("Get", "list", ("t",)),
            ),
        )
    assert ActionCatalog.from_dict(CATALOG.to_dict()) == CATALOG
    found = registry()
    assert found.actions_on("triple_store", "graph") == [
        "triple_store:Query",
        "triple_store:ListGraphs",
    ]
    assert found.matching("triple_store:List*") == ["triple_store:ListGraphs"]


def test_an_unquoted_yaml_version_reads_as_the_version():
    document = parse_policy_document(
        "version: 2026-10-13\nstatements:\n"
        "  - {effect: Allow, actions: ['*'], resources: ['*']}\n"
    )
    assert document.version == POLICY_VERSION
    with pytest.raises(PolicyValidationError, match="version must be"):
        parse_policy_document(
            "version: 2012-10-17\nstatements:\n"
            "  - {effect: Allow, actions: ['*'], resources: ['*']}\n"
        )


def test_scope_confinement():
    def doc(*resources):
        return parse_policy_document(
            {
                "version": POLICY_VERSION,
                "statements": [
                    {"effect": "Allow", "actions": ["*"], "resources": list(resources)}
                ],
            }
        )

    assert doc("${scope}:svc:t/*", "${scope}:svc:u/${principal.id}").confined_to_scope
    assert not doc("${scope}:svc:t/*", "*").confined_to_scope
    assert not doc("${scope}*").confined_to_scope
    assert not doc("abi:acme:ws1:svc:t/*").confined_to_scope
