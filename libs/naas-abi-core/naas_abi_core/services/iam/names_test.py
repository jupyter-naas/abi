import pytest

from naas_abi_core.services.iam.names import (
    encode_id,
    literal_prefix,
    matches,
    parse_resource_name,
    path_parts,
    resource_name,
    split_action,
    substitute,
    validate_scope,
)


def test_ids_are_percent_encoded_by_kind():
    assert encode_id("http://ontology.naas.ai/graph/x") == (
        "http%3A%2F%2Fontology.naas.ai%2Fgraph%2Fx"
    )
    assert encode_id("nexus:session:42") == "nexus%3Asession%3A42"
    assert encode_id(["people", "contacts", "a b"], "path") == "people/contacts/a%20b"
    assert encode_id(["a/b", "c"], "path") == "a%2Fb/c"
    assert encode_id([], "singleton") == "-"
    assert encode_id("*?%") == "%2A%3F%25"
    with pytest.raises(ValueError):
        encode_id(["a", "b"], "opaque")
    with pytest.raises(ValueError):
        encode_id("")


def test_object_paths_join_prefix_and_key():
    parts = path_parts("/workspaces/ws-1/files/") + ["q3 report.pdf"]
    assert resource_name("object_storage", "object", parts, kind="path") == (
        "abi:-:-:object_storage:object/workspaces/ws-1/files/q3%20report.pdf"
    )


def test_names_round_trip():
    name = resource_name(
        "triple_store",
        "graph",
        "http://x/g",
        org="org-1a2b3c4d5e6f",
        workspace="ws-0f1e2d3c4b5a",
    )
    assert (
        name
        == "abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a:triple_store:graph/http%3A%2F%2Fx%2Fg"
    )
    parsed = parse_resource_name(name)
    assert (parsed.org, parsed.workspace, parsed.service, parsed.type) == (
        "org-1a2b3c4d5e6f",
        "ws-0f1e2d3c4b5a",
        "triple_store",
        "graph",
    )
    assert parsed.segments == ("http://x/g",)
    assert parsed.scope == "abi:org-1a2b3c4d5e6f:ws-0f1e2d3c4b5a"
    assert str(parsed) == name
    assert parse_resource_name("abi:-:-:cache:service/-").segments == ()


@pytest.mark.parametrize(
    "bad",
    [
        "arn:x",
        "abi:-:-:graph/x",
        "abi:ORG:-:svc:type/x",
        "abi:-:-:svc:type",
        "abi:-:-:svc:type/a b",
        "abi:-:-:svc:type/a*",
        "abi:-:-:svc:type/%2a",
        "abi:-:-:Svc:type/x",
    ],
)
def test_malformed_names_are_refused(bad):
    with pytest.raises(ValueError):
        parse_resource_name(bad)


def test_scopes():
    for scope in ("abi:org-1:ws-1", "abi:org-1:-", "abi:org-1:*", "abi:-:-"):
        assert validate_scope(scope) == scope
    for bad in ("abi:-:ws-1", "org-1:ws-1", "abi:org-1", "abi:*:*"):
        with pytest.raises(ValueError):
            validate_scope(bad)


def test_wildcards():
    assert matches("*", "anything")
    assert matches("abi:org-1:*", "abi:org-1:ws-1:svc:t/x")
    assert not matches("abi:org-1:*", "abi:org-10:ws-1:svc:t/x")
    assert matches("abi:-:-:svc:t/a?c", "abi:-:-:svc:t/abc")
    assert not matches("abi:-:-:svc:t/a?c", "abi:-:-:svc:t/ac")
    assert matches("triple_store:List*", "triple_store:ListGraphs")
    assert not matches("triple_store:list*", "triple_store:ListGraphs")
    # Regex characters are literal.
    assert not matches("abi:-:-:svc:t/a.c", "abi:-:-:svc:t/abc")
    assert matches("a+b(c)[d]", "a+b(c)[d]")
    assert literal_prefix("abi:org-1:*:x") == "abi:org-1:"
    assert literal_prefix("abi:-:-:t/a?") == "abi:-:-:t/a"
    assert literal_prefix("*") == ""


def test_variables():
    values = {"scope": "abi:org-1:ws-1", "principal.id": "usr_1", "user.id": None}
    assert substitute("${scope}:svc:t/*", values) == "abi:org-1:ws-1:svc:t/*"
    assert (
        substitute("abi:-:-:svc:t/${principal.id}/*", values) == "abi:-:-:svc:t/usr_1/*"
    )
    assert substitute("abi:-:-:svc:t/${user.id}", values) is None
    assert substitute("abi:-:-:svc:t/${nope}", values) is None


def test_actions():
    assert split_action("triple_store:ListGraphs") == ("triple_store", "ListGraphs")
    for bad in ("triple_store", "Triple:Get", "svc:get", "svc:Get*"):
        with pytest.raises(ValueError):
            split_action(bad)


def test_every_workspace_of_an_org_has_its_own_name():
    from naas_abi_core.services.iam.names import ALL_WORKSPACES

    name = resource_name(
        "iam",
        "attachment",
        ["p", "u"],
        kind="path",
        org="acme",
        workspace=ALL_WORKSPACES,
    )
    assert name == "abi:acme:%2A:iam:attachment/p/u"
    assert parse_resource_name(name).workspace == ALL_WORKSPACES
    assert matches("abi:acme:*", name)
    assert not matches("abi:acme:-:*", name)
    with pytest.raises(ValueError):
        resource_name("svc", "t", "x", workspace=ALL_WORKSPACES)


def test_every_workspace_is_refused_outside_iam_attachments():
    from naas_abi_core.services.iam.names import ALL_WORKSPACES

    for service, type_ in (
        ("iam", "scope"),
        ("iam", "placement"),
        ("document", "attachment"),
    ):
        with pytest.raises(ValueError):
            resource_name(service, type_, "x", org="acme", workspace=ALL_WORKSPACES)
        with pytest.raises(ValueError):
            parse_resource_name(f"abi:acme:%2A:{service}:{type_}/x")


def test_every_org_is_a_name_for_unscoped_attachments_only():
    from naas_abi_core.services.iam.names import ALL_ORGS, ALL_WORKSPACES

    name = resource_name(
        "iam",
        "attachment",
        ["p", "u"],
        kind="path",
        org=ALL_ORGS,
        workspace=ALL_WORKSPACES,
    )
    assert name == "abi:%2A:%2A:iam:attachment/p/u"
    assert parse_resource_name(name).org == ALL_ORGS
    # No ${scope} expansion reaches it; only grants for every org do.
    for scope in ("abi:-:-", "abi:acme:-", "abi:acme:*", "abi:acme:ws1"):
        assert not matches(f"{scope}:iam:attachment/*", name)
    assert matches("*", name) and matches("abi:*:iam:attachment/*", name)
    for org, workspace, type_ in (
        (ALL_ORGS, "-", "attachment"),
        (ALL_ORGS, "ws1", "attachment"),
        (ALL_ORGS, ALL_WORKSPACES, "scope"),
    ):
        with pytest.raises(ValueError):
            resource_name("iam", type_, "x", org=org, workspace=workspace)
