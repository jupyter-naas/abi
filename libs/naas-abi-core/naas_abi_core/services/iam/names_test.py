import pytest

from naas_abi_core.services.iam.names import (
    PLATFORM,
    UNRESOLVED,
    anywhere,
    as_container,
    below,
    container_name,
    container_of_scope,
    encode_id,
    expand_scope,
    is_below,
    literal_prefix,
    matches,
    owner_ancestors,
    parent_of,
    parse_container,
    parse_resource_name,
    path_parts,
    resource_name,
    split_action,
    substitute,
    top_container,
    validate_owner_scope,
    validate_scope,
    within,
    within_owner,
)

ORG = container_name("nexus", "organization", "org-1")
WS = container_name("nexus", "workspace", "ws-2", parent=ORG)
PROJECT = container_name("crm", "project", "p-9", parent=WS)


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


def test_containers_are_steps_of_a_path():
    assert ORG == "abi:nexus:organization/org-1"
    assert WS == "abi:nexus:organization/org-1/nexus:workspace/ws-2"
    assert PROJECT == WS + "/crm:project/p-9"
    # An id with a "/" or a ":" never breaks the path.
    odd = container_name("crm", "project", "a/b:c", parent=WS)
    assert odd == WS + "/crm:project/a%2Fb%3Ac"
    assert parse_container(odd)[-1].id == "a%2Fb%3Ac"
    assert parse_container(odd)[-1].value == "a/b:c"
    assert parse_container(PLATFORM) == ()
    assert [step.type for step in parse_container(PROJECT)] == [
        "organization",
        "workspace",
        "project",
    ]
    assert parent_of(PROJECT) == WS
    assert parent_of(ORG) == PLATFORM
    assert top_container(PROJECT) == ORG
    assert top_container(PLATFORM) == PLATFORM


def test_names_round_trip_at_every_level():
    graph = resource_name("triple_store", "graph", "http://x/g", container=WS)
    assert graph == WS + "/triple_store:graph/http%3A%2F%2Fx%2Fg"
    parsed = parse_resource_name(graph)
    assert (parsed.service, parsed.type, parsed.id) == (
        "triple_store",
        "graph",
        "http%3A%2F%2Fx%2Fg",
    )
    assert parsed.segments == ("http://x/g",)
    assert parsed.container == WS
    assert str(parsed) == graph
    platform = resource_name("model_registry", "model", "gpt-x")
    assert platform == "abi:model_registry:model/gpt-x"
    assert parse_resource_name(platform).container == PLATFORM
    assert parse_resource_name("abi:cache:service/-").segments == ()
    member = resource_name("nexus", "member", "u-7", container=ORG)
    assert member == "abi:nexus:organization/org-1/nexus:member/u-7"
    # A container's own name is its resource name, placed in its parent.
    assert parse_resource_name(WS).container == ORG
    assert parse_resource_name(WS).type == "workspace"


def test_every_id_kind():
    path = resource_name(
        "document", "document", ["people", "c", "a b"], kind="path", container=PROJECT
    )
    assert path == PROJECT + "/document:document/people/c/a%20b"
    assert parse_resource_name(path).segments == ("people", "c", "a b")
    assert parse_resource_name(path).container == PROJECT
    single = resource_name("cache", "service", (), kind="singleton", container=WS)
    assert single == WS + "/cache:service/-"
    parts = path_parts("/workspaces/ws-1/files/") + ["q3 report.pdf"]
    assert resource_name("object_storage", "object", parts, kind="path") == (
        "abi:object_storage:object/workspaces/ws-1/files/q3%20report.pdf"
    )


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "abi:",
        "abi:graph/x",
        "abi:triple_store:graph",
        "abi:triple_store:graph/",
        "abi:Triple:graph/x",
        "abi:triple_store:graph/a b",
        "abi:triple_store:graph/*",
        "abi:nexus:organization/a/b/triple_store:graph/x",  # a path id before the last step
        "abi:nexus:organization//triple_store:graph/x",  # an empty container id
        "abi:-:-:triple_store:graph/x",  # the grammar before container paths
        "urn:triple_store:graph/x",
    ],
)
def test_malformed_names_are_refused(bad):
    with pytest.raises(ValueError):
        parse_resource_name(bad)


@pytest.mark.parametrize(
    "bad",
    [
        "abi:-:-",
        "abi:org-1:ws-2",
        "abi:nexus:organization",
        "abi:x:y/a/b",
        PROJECT + "/*/",
    ],
)
def test_malformed_containers_are_refused(bad):
    with pytest.raises(ValueError):
        parse_container(bad)


def test_scopes():
    assert validate_scope(WS) == WS
    assert validate_scope(PLATFORM) == PLATFORM
    assert validate_scope(below(ORG)) == ORG + "/*"
    assert is_below(ORG + "/*") and not is_below(ORG)
    assert container_of_scope(ORG + "/*") == ORG
    for bad in ("abi:-:-", "abi:org-1:*", "abi:*", "abi:*:*", ORG + "/x", "abi:/*", ORG + "/*/*"):
        with pytest.raises(ValueError):
            validate_scope(bad)
    assert validate_owner_scope(WS) == WS
    assert validate_owner_scope(PLATFORM) == PLATFORM
    with pytest.raises(ValueError):
        validate_owner_scope(ORG + "/*")


def test_within_and_owners():
    assert within(PROJECT, WS) and within(WS, WS) and within(WS, PLATFORM)
    assert not within(ORG, WS)
    assert not within(container_name("nexus", "organization", "org-10"), ORG)
    # An owner's attachments: at it or at a container below it, below one too.
    assert within_owner(ORG, ORG)
    assert within_owner(ORG, below(ORG))
    assert within_owner(ORG, WS)
    assert within_owner(ORG, below(PROJECT))
    assert not within_owner(WS, ORG)
    assert not within_owner(WS, None)
    assert within_owner(PLATFORM, None)
    assert within_owner(PLATFORM, WS)
    assert owner_ancestors(PROJECT) == [WS, ORG, PLATFORM]
    assert owner_ancestors(PLATFORM) == []


def test_within_an_owner_of_the_grammar_before_container_paths():
    """The start-up moves write the old grammar until the names are rewritten:
    it follows its own rules, and an owner of one grammar never holds a scope of
    the other (both were ``UNRESOLVED``, so always within each other)."""
    assert within_owner("abi:o1:-", "abi:o1:-")
    assert within_owner("abi:o1:-", "abi:o1:*")
    assert within_owner("abi:o1:-", "abi:o1:w1")
    assert within_owner("abi:o1:w1", "abi:o1:w1")
    assert not within_owner("abi:o1:-", "abi:o2:w")
    assert not within_owner("abi:o1:-", "abi:o2:-")
    assert not within_owner("abi:o1:w1", "abi:o1:w2")
    assert not within_owner("abi:o1:w1", "abi:o1:-")
    assert not within_owner("abi:o1:w1", "abi:o1:*")
    assert within_owner("abi:-:-", "abi:o2:w")
    # Never across grammars, and nothing is within UNRESOLVED.
    assert not within_owner("abi:o1:-", WS)
    assert not within_owner(ORG, "abi:o1:w1")
    assert not within_owner(UNRESOLVED, UNRESOLVED)
    assert not within_owner(ORG, UNRESOLVED)


def test_the_wildcards_table():
    graph = resource_name("triple_store", "graph", "g", container=WS)
    deal = resource_name("crm", "deal", "d-1", container=PROJECT)
    org_member = resource_name("nexus", "member", "u-7", container=ORG)
    ws_member = resource_name("nexus", "member", "u-8", container=WS)
    other_org_graph = resource_name(
        "triple_store",
        "graph",
        "g",
        container=container_name(
            "nexus",
            "workspace",
            "ws-3",
            parent=container_name("nexus", "organization", "org-10"),
        ),
    )
    everything = [graph, deal, org_member, ws_member, other_org_graph, WS, ORG]

    def matched(pattern):
        return {name for name in everything if matches(pattern, name)}

    # Everything in ws-2, what its projects hold included.
    assert matched(WS + "/*") == {graph, deal, ws_member}
    # Everything in org-1 and in all its workspaces.
    assert matched(ORG + "/*") == {graph, deal, org_member, ws_member, WS}
    # A type stays at its level: org-1's members only.
    assert matched(ORG + "/nexus:member/*") == {org_member}
    # Every graph anywhere under org-1.
    assert matched(ORG + "/*/triple_store:graph/*") == {graph}
    # The container itself.
    assert matched(ORG) == {ORG}
    # "Anywhere": the platform's and every container's.
    assert set(anywhere("triple_store:graph/g")) == {
        "abi:triple_store:graph/g",
        "abi:*/triple_store:graph/g",
    }
    assert {
        n for n in everything for p in anywhere("triple_store:graph/*") if matches(p, n)
    } == {
        graph,
        other_org_graph,
    }


def test_expanding_scope():
    assert expand_scope("${scope}/triple_store:graph/*", WS) == (
        WS + "/triple_store:graph/*"
    )
    assert expand_scope("${scope}", WS) == WS
    # At the platform, "${scope}/" reads "abi:" and "${scope}" alone matches nothing.
    assert expand_scope("${scope}/triple_store:graph/*", PLATFORM) == (
        "abi:triple_store:graph/*"
    )
    assert expand_scope("${scope}", PLATFORM) is None
    assert expand_scope("abi:x:y/1", PLATFORM) == "abi:x:y/1"
    assert (
        substitute(
            "${scope}/module:agent/${principal.id}",
            {
                "scope": PLATFORM,
                "principal.id": "usr_1",
            },
        )
        == "abi:module:agent/usr_1"
    )


def test_old_names_resolve_nowhere():
    assert as_container("abi:org-1:ws-2") == UNRESOLVED
    assert as_container("abi:-:-") == PLATFORM
    assert as_container(WS) == WS
    assert as_container(PLATFORM) == PLATFORM
    parse_container(UNRESOLVED)  # a valid name nobody registers


def test_wildcards():
    assert matches("*", "abi:anything")
    assert matches(WS + "/*", WS + "/triple_store:graph/x")
    assert not matches(WS + "/*", WS)
    assert matches("abi:nexus:organization/org-?", ORG)
    assert literal_prefix(WS + "/triple_store:graph/sales-*") == (
        WS + "/triple_store:graph/sales-"
    )


def test_variables():
    assert substitute("${scope}/x:y/${user.id}", {"scope": WS, "user.id": "u1"}) == (
        WS + "/x:y/u1"
    )
    assert substitute("${scope}/x:y/${user.id}", {"scope": WS, "user.id": None}) is None


def test_actions():
    assert split_action("triple_store:Query") == ("triple_store", "Query")
    with pytest.raises(ValueError):
        split_action("triple_store:query")
