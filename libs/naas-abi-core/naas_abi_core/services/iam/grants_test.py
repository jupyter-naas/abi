"""Glob containment and the holdings of a giver (``grants.py``)."""

from __future__ import annotations

import pytest

from naas_abi_core.services.iam import grants
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.grants import (
    EVERYTHING,
    HeldStatement,
    Holdings,
    Side,
    covered,
    held_form,
    held_forms,
    overlaps,
    universe,
)
from naas_abi_core.services.iam.names import anywhere, container_name
from naas_abi_core.services.iam.policy import Statement
from naas_abi_core.services.iam.tests.iam_harness import (
    ACTIVITY_LOG,
    NEXUS,
    TRIPLE_STORE,
)

# The registered container types: an organisation and its workspaces.
CONTAINERS = frozenset({("nexus", "organization"), ("nexus", "workspace")})
O = container_name("nexus", "organization", "o")
W = container_name("nexus", "workspace", "w", parent=O)
W2 = container_name("nexus", "workspace", "w2", parent=O)
GRAPHS = universe("triple_store", "graph", CONTAINERS)
NOTES = universe("activity_log", "note", CONTAINERS)
P = grants.MARKS["principal.id"]
U = grants.MARKS["user.id"]

# (grant, held, within, covered)
CONTAINMENT = [
    # Literals and plain prefixes.
    (
        f"{W}/triple_store:graph/a",
        [f"{W}/triple_store:graph/a"],
        EVERYTHING,
        True,
    ),
    (
        f"{W}/triple_store:graph/a",
        [f"{W}/triple_store:graph/b"],
        EVERYTHING,
        False,
    ),
    (
        f"{W}/triple_store:graph/a",
        [f"{W}/triple_store:graph/*"],
        EVERYTHING,
        True,
    ),
    (
        f"{W}/triple_store:graph/*",
        [f"{W}/triple_store:graph/a*"],
        EVERYTHING,
        False,
    ),
    (
        f"{W}/triple_store:graph/a*",
        [f"{W}/triple_store:graph/*"],
        EVERYTHING,
        True,
    ),
    ("*", ["*"], EVERYTHING, True),
    ("*", ["abi:*"], EVERYTHING, False),
    (f"{W}/x", ["*"], EVERYTHING, True),
    # "*" crosses ":" and "/".
    (f"{W}/triple_store:graph/a/b", [f"{O}/*"], EVERYTHING, True),
    (f"{W}/triple_store:graph/a", [f"{O}/*:graph/a"], EVERYTHING, True),
    (f"{W}/triple_store:*", [f"{W}/triple_store:graph/*"], EVERYTHING, False),
    # ... but a type's names hold no other field: graphs only, the rest is no wider.
    (f"{W}/triple_store:*", [f"{W}/triple_store:graph/*"], GRAPHS, True),
    # ... and a container holds containers: below it is wider than what it holds.
    (f"{W}/*", [f"{W}/triple_store:graph/*"], GRAPHS, False),
    (
        f"{W}/*",
        [f"{W}/triple_store:graph/*", f"{W}/*/triple_store:graph/*"],
        GRAPHS,
        True,
    ),
    (f"{O}/*", [f"{W}/triple_store:graph/*"], GRAPHS, False),
    (
        f"{O}/*",
        [f"{O}/triple_store:graph/*", f"{O}/*/triple_store:graph/*"],
        GRAPHS,
        True,
    ),
    ("abi:*", anywhere("triple_store:graph/*"), GRAPHS, True),
    ("abi:*", ["abi:*/triple_store:graph/*"], GRAPHS, False),
    (f"{W}/triple_store:graph/*", [f"{W}/triple_store:graph/*/*"], GRAPHS, False),
    # Below an org reaches every workspace, at the org only the org's own.
    (f"{W}/triple_store:graph/*", [f"{O}/*/triple_store:graph/*"], GRAPHS, True),
    (f"{W}/triple_store:graph/*", [f"{O}/triple_store:graph/*"], GRAPHS, False),
    (f"{O}/*/triple_store:graph/*", [f"{W}/triple_store:graph/*"], GRAPHS, False),
    # A type stays at its level: the graphs directly in W, not those below it.
    (
        f"{W}/nexus:workspace/x/triple_store:graph/a",
        [f"{W}/triple_store:graph/*"],
        GRAPHS,
        False,
    ),
    # "?" is one character: of an id, or one of the three of "%2F".
    (f"{W}/triple_store:graph/a?", [f"{W}/triple_store:graph/*"], GRAPHS, True),
    (
        f"{W}/triple_store:graph/a%2F*",
        [f"{W}/triple_store:graph/a?2F*"],
        GRAPHS,
        True,
    ),
    (
        f"{W}/triple_store:graph/a?2F*",
        [f"{W}/triple_store:graph/a%2F*"],
        GRAPHS,
        False,
    ),
    (
        f"{W}/triple_store:graph/a???",
        [f"{W}/triple_store:graph/a%2F"],
        GRAPHS,
        False,
    ),
    (
        f"{W}/triple_store:graph/a%2F",
        [f"{W}/triple_store:graph/a???"],
        GRAPHS,
        True,
    ),
    (f"{W}/triple_store:graph/??", [f"{W}/triple_store:graph/?*"], GRAPHS, True),
    (f"{W}/triple_store:graph/?*", [f"{W}/triple_store:graph/??"], GRAPHS, False),
    (
        f"{O}/nexus:workspace/w?/triple_store:graph/*",
        [f"{O}/nexus:workspace/w*/triple_store:graph/*"],
        GRAPHS,
        True,
    ),
    # A "?" may stand for ":" or "/": here the only way it names a graph.
    (
        f"{O}/nexus?workspace/w/triple_store:graph/*",
        [f"{W}/triple_store:graph/*"],
        GRAPHS,
        True,
    ),
    (
        f"{O}?nexus:workspace/w/triple_store:graph/*",
        [f"{W}/triple_store:graph/*"],
        GRAPHS,
        True,
    ),
    # The union of what is held, not one pattern of it.
    (
        f"{W}/triple_store:graph/?",
        [f"{W}/triple_store:graph/a", f"{W}/triple_store:graph/[^a]"],
        GRAPHS,
        False,
    ),
    (
        f"{W}/triple_store:graph/*",
        [f"{W}/triple_store:graph/a*", f"{W}/triple_store:graph/?*"],
        GRAPHS,
        True,
    ),
    # Variables: the same variable form, or a wildcard, never a literal id.
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/{P}"],
        EVERYTHING,
        True,
    ),
    (
        f"{W}/activity_log:note/{P}/*",
        [f"{W}/activity_log:note/{P}/*"],
        EVERYTHING,
        True,
    ),
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/*"],
        EVERYTHING,
        True,
    ),
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/usr_1"],
        EVERYTHING,
        False,
    ),
    (
        f"{W}/activity_log:note/{P}/*",
        [f"{W}/activity_log:note/{P}"],
        EVERYTHING,
        False,
    ),
    (
        f"{W}/activity_log:note/{U}",
        [f"{W}/activity_log:note/{P}"],
        EVERYTHING,
        False,
    ),
    (
        f"{W}/activity_log:note/*",
        [f"{W}/activity_log:note/{P}/*"],
        EVERYTHING,
        False,
    ),
    # A variable is a whole id: a "?" is one character, not it.
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/?"],
        NOTES,
        False,
    ),
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/?*"],
        NOTES,
        False,
    ),
    (
        f"{W}/activity_log:note/{P}",
        [f"{W}/activity_log:note/*"],
        NOTES,
        True,
    ),
    # Nothing held, a grant naming graphs: not covered.
    (f"{W}/triple_store:graph/*", [], GRAPHS, False),
    # A grant naming no graph grants nothing on graphs: nothing to cover.
    (f"{W}/triple_store:view/*", [], GRAPHS, True),
]


@pytest.mark.parametrize("grant, held, within, expected", CONTAINMENT)
def test_containment(grant, held, within, expected):
    assert covered(grant, held, within) is expected


@pytest.mark.parametrize(
    "grant, other, within, expected",
    [
        (
            f"{W}/triple_store:graph/*",
            "abi:*/triple_store:graph/secret",
            GRAPHS,
            True,
        ),
        (
            f"{W}/triple_store:graph/a*",
            f"{W}/triple_store:graph/b*",
            GRAPHS,
            False,
        ),
        (
            f"{W}/triple_store:graph/?",
            f"{W}/triple_store:graph/ab",
            GRAPHS,
            False,
        ),
        (
            f"{W}/triple_store:graph/*",
            f"{W2}/triple_store:graph/*",
            GRAPHS,
            False,
        ),
        (f"{W}/*", "*", GRAPHS, True),
        # Not a graph at all: nothing of it is a graph's name.
        (f"{W}/triple_store:graph/*", f"{W}/triple_store:view/*", GRAPHS, False),
    ],
)
def test_overlap(grant, other, within, expected):
    assert overlaps(grant, (other,), within) is expected


def test_held_form_fills_the_scope_and_marks_the_variables():
    assert held_form("${scope}/x:y/${principal.id}", W) == f"{W}/x:y/{P}"
    assert held_form("${scope}/x:y/*", None) is None
    assert grants.shown(f"{W}/x:y/{P}") == f"{W}/x:y/" + "${principal.id}"
    # At the platform "${scope}/" reads "abi:", and "${scope}" alone is nothing.
    assert held_form("${scope}/x:y/*", "abi:") == "abi:x:y/*"
    assert held_form("${scope}", "abi:") is None
    assert held_form("${scope}", W) == W


def test_an_undecidable_containment_with_nothing_held_is_refused():
    # Nothing prefix-compatible is held: the search still runs past its budget.
    grants._covered.cache_clear()
    assert not covered(f"{W}/triple_store:graph/*a?????????????????????", [], GRAPHS)


def test_an_undecidable_containment_is_refused(monkeypatch):
    # Covered by the union only: no one pattern shows it, so the search decides.
    monkeypatch.setattr(grants, "STATE_BUDGET", 3)
    grants._covered.cache_clear()
    try:
        assert not covered(
            f"{W}/triple_store:graph/*",
            [f"{W}/triple_store:graph/a*", f"{W}/triple_store:graph/?*"],
            GRAPHS,
        )
    finally:
        grants._covered.cache_clear()


def test_a_grant_one_held_pattern_embeds_takes_no_search(monkeypatch):
    """An org-wide role covers a workspace's grant without a search: a ``*``
    under a ``*``, the rest character for character."""
    monkeypatch.setattr(grants, "CALL_BUDGET", 0)
    grants._covered.cache_clear()
    try:
        with grants.budget():
            assert covered(
                f"{W2}/nexus:module/*",
                [f"{O}/*/nexus:module/*", f"{W}/nexus:module/*"],
                universe("nexus", "module", CONTAINERS),
            )
            assert covered(
                f"{W}/activity_log:note/{P}/?",
                [f"{O}/*/activity_log:note/{P}/*"],
                NOTES,
            )
            # A "?" never takes in a variable, nor a "*" of the grant.
            with pytest.raises(grants.Exhausted):
                covered(
                    f"{W}/activity_log:note/{P}",
                    [f"{O}/*/activity_log:note/?"],
                    NOTES,
                )
    finally:
        grants._covered.cache_clear()


# -- holdings ------------------------------------------------------------------


def _registry() -> CatalogRegistry:
    registry = CatalogRegistry()
    registry.register(TRIPLE_STORE)
    registry.register(ACTIVITY_LOG)
    registry.register(NEXUS)
    return registry


def _side(*statements: HeldStatement, lacks: str = "you do not hold it") -> Side:
    return Side(tuple(statements), lacks)


def _allow(actions, resources, policy_id=None):
    return HeldStatement("Allow", tuple(actions), tuple(resources), policy_id)


def _deny(actions, resources, policy_id="pol_guard"):
    return HeldStatement("Deny", tuple(actions), tuple(resources), policy_id)


def _grant(actions, resources, effect="Allow") -> Statement:
    return Statement(effect, tuple(actions), tuple(resources))


READER = _allow(
    ["triple_store:Query", "triple_store:ListGraphs"], [f"{W}/triple_store:graph/*"]
)


def test_wildcard_actions_are_expanded_against_the_catalogs():
    holdings = Holdings([_side(READER)], _registry())
    found = holdings.first_uncovered(
        [_grant(["triple_store:*"], ["${scope}/triple_store:graph/*"])], W
    )
    assert found is not None
    assert found.action == "triple_store:QueryStream"
    assert found.resource == f"{W}/triple_store:graph/*"
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Q*y"], ["${scope}/triple_store:*"])], W
        )
        is None
    )


def test_a_deny_needs_no_cover_and_a_deny_of_the_giver_refuses():
    holdings = Holdings(
        [
            _side(
                READER,
                _deny(["triple_store:Query"], anywhere("triple_store:graph/hr*")),
            )
        ],
        _registry(),
    )
    assert (
        holdings.first_uncovered(
            [
                _grant(["*"], ["*"], effect="Deny"),
                _grant(["triple_store:ListGraphs"], ["${scope}/triple_store:graph/*"]),
            ],
            W,
        )
        is None
    )
    found = holdings.first_uncovered(
        [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])], W
    )
    assert found is not None and "pol_guard" in found.reason
    # Narrowed away from the Deny, it is held.
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/sales*"])],
            W,
        )
        is None
    )


def test_at_a_scope_only_the_scope_s_patterns_count():
    holdings = Holdings([_side(READER)], _registry())
    statement = _grant(["triple_store:Query"], ["${scope}/triple_store:graph/*", "*"])
    assert holdings.first_uncovered([statement], W) is None
    assert holdings.first_uncovered([statement], None) is not None


def test_a_sub_policy_s_grant_is_its_own_within_its_chain():
    """Only what each policy of the chain also allows counts; an action the chain
    allows nowhere is not granted."""
    holdings = Holdings([_side(READER)], _registry())
    every_graph = [_grant(["triple_store:*"], ["${scope}/triple_store:graph/*"])]
    assert holdings.first_uncovered(every_graph, W) is not None
    parent = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])]
    assert holdings.first_uncovered(every_graph, W, parents=[parent]) is None
    # A grandparent wider than the parent changes nothing; a narrower one bounds.
    wide = [_grant(["*"], ["*"])]
    assert holdings.first_uncovered(every_graph, W, parents=[parent, wide]) is None
    insert = [_grant(["triple_store:Insert"], ["${scope}/triple_store:graph/*"])]
    found = holdings.first_uncovered(every_graph, W, parents=[insert])
    assert found is not None and found.action == "triple_store:Insert"
    assert holdings.first_uncovered(every_graph, W, parents=[insert, parent]) is None
    # The parent's Allows are bounds: one beyond ${scope} bounds a scoped grant.
    sales = [_grant(["triple_store:Insert"], anywhere("triple_store:graph/sales"))]
    found = holdings.first_uncovered(every_graph, W, parents=[sales])
    assert found is not None and found.resource == f"{W}/triple_store:graph/*"


def test_a_wildcard_of_a_service_with_no_catalog_is_bounded_by_what_meets_it():
    """``mymod:*`` kept as written, under a parent naming ``mymod:Read``: the
    sub-policy grants ``mymod:Read`` there, which the giver must hold."""
    holdings = Holdings([_side(READER)], _registry())
    grant = [_grant(["mymod:*"], ["${scope}/mymod:thing/*"])]
    parent = [_grant(["mymod:Read"], ["${scope}/mymod:thing/*"])]
    found = holdings.first_uncovered(grant, W, parents=[parent])
    assert found is not None and found.action == "mymod:*"
    held = Holdings([_side(_allow(["mymod:*"], [f"{W}/mymod:thing/*"]))], _registry())
    assert held.first_uncovered(grant, W, parents=[parent]) is None
    # A parent naming another service's actions bounds nothing of it.
    other = [_grant(["othermod:Read"], ["${scope}/othermod:thing/*"])]
    assert holdings.first_uncovered(grant, W, parents=[other]) is None


def test_a_deny_of_the_giver_is_met_within_the_chain_only():
    holdings = Holdings(
        [
            _side(
                READER, _deny(["triple_store:Query"], anywhere("triple_store:graph/hr"))
            )
        ],
        _registry(),
    )
    every_graph = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])]
    assert holdings.first_uncovered(every_graph, W) is not None
    sales = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/sales*"])]
    assert holdings.first_uncovered(every_graph, W, parents=[sales]) is None


def test_what_a_sub_policy_of_the_giver_holds_is_bounded_by_its_chain():
    """Its patterns within the chain's, as far as one embeds the other."""
    child = _grant(["triple_store:*"], ["${scope}/triple_store:graph/*"])
    chain = [
        [
            _grant(["triple_store:Query"], ["${scope}/triple_store:graph/sales*"]),
            _grant(["triple_store:Insert"], anywhere("triple_store:graph/x")),
            _grant(["*"], ["*"], effect="Deny"),
        ],
        [_grant(["triple_store:*"], ["*"])],
    ]
    narrowed = grants.within_chain(child, chain, W)
    assert narrowed == [
        Statement("Allow", ("triple_store:Query",), (f"{W}/triple_store:graph/sales*",))
    ]
    holdings = Holdings(
        [
            _side(
                *(
                    grants.held_statement(n, W, principal_id="usr_x", user_id=None)
                    for n in narrowed
                )
            )
        ],
        _registry(),
    )
    sales = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/sales-1"])]
    hr = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/hr"])]
    assert holdings.first_uncovered(sales, W) is None
    assert holdings.first_uncovered(hr, W) is not None
    # Variables keep their form; a chain level that allows nothing leaves nothing.
    own = _grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])
    mine = [
        [
            _grant(
                ["triple_store:Query"], ["${scope}/triple_store:graph/${principal.id}"]
            )
        ]
    ]
    assert grants.within_chain(own, mine, W)[0].resources == (
        f"{W}/triple_store:graph/" + "${principal.id}",
    )
    assert grants.within_chain(own, [[_grant(["triple_store:Insert"], ["*"])]], W) == []


def test_every_side_must_hold_it():
    token = Side(
        (_allow(["triple_store:Query"], ["*"]),),
        "your credential's scope does not allow it",
    )
    holdings = Holdings([_side(READER), token], _registry())
    found = holdings.first_uncovered(
        [_grant(["triple_store:ListGraphs"], ["${scope}/triple_store:graph/*"])],
        W,
    )
    assert (
        found is not None
        and found.reason == "your credential's scope does not allow it"
    )


def test_an_inactive_side_holds_nothing():
    holdings = Holdings(
        [Side((READER,), "you do not hold it", active=False)], _registry()
    )
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/a"])],
            W,
        )
        is not None
    )


def test_grantable_lists_what_is_held_at_the_scope_minus_denies():
    holdings = Holdings(
        [
            _side(
                _allow(["triple_store:Query"], [f"{O}/*/triple_store:graph/*"]),
                _allow(["triple_store:Insert"], [f"{W2}/triple_store:graph/*"]),
                _allow(["activity_log:ReadNote"], [f"{W}/activity_log:note/{P}/*"]),
                _deny(["triple_store:Query"], anywhere("triple_store:graph/hr*")),
                _allow(["triple_store:DropGraph"], [f"{W}/triple_store:graph/tmp*"]),
                _deny(["triple_store:DropGraph"], ["*"]),
            )
        ],
        _registry(),
    )
    found = {c.service: {a.action: a for a in c.actions} for c in holdings.grantable(W)}
    query = found["triple_store"]["triple_store:Query"]
    # Held below the org: at the workspace and below it.
    assert query.resources == (
        "${scope}/triple_store:graph/*",
        "${scope}/*/triple_store:graph/*",
    )
    # Written as the resources are, at the scope.
    assert query.excluded == (
        "${scope}/*/triple_store:graph/hr*",
        "${scope}/triple_store:graph/hr*",
    )
    assert "triple_store:Insert" not in found["triple_store"]  # another workspace's
    assert "triple_store:DropGraph" not in found["triple_store"]  # all denied
    assert found["activity_log"]["activity_log:ReadNote"].resources == (
        "${scope}/activity_log:note/${principal.id}/*",
    )


def test_grantable_of_everything():
    holdings = Holdings([_side(_allow(["*"], ["*"]))], _registry())
    found = {c.service: c for c in holdings.grantable(W)}
    assert {a.resources for a in found["triple_store"].actions} == {("${scope}/*",)}
    # The container itself only for the actions on its type.
    nexus = {a.action: a.resources for a in found["nexus"].actions}
    assert nexus["nexus:GetWorkspace"] == ("${scope}", "${scope}/*")
    assert nexus["nexus:GetOrganization"] == ("${scope}/*",)


def test_the_searches_of_one_check_share_a_budget(monkeypatch):
    """Many costly statements do not each get a budget: past the check's, what
    is left is refused, and nothing is cached for it."""
    monkeypatch.setattr(grants, "CALL_BUDGET", 2_000)
    grants._covered.cache_clear()
    # Covered within graphs only (an id is never empty): each needs a search.
    held = _side(_allow(["triple_store:Query"], [f"{W}/triple_store:graph/?*"]))
    holdings = Holdings([held], _registry())
    statements = [
        _grant(
            ["triple_store:Query"],
            [f"${{scope}}/triple_store:graph/*b{'?' * n}*"],
        )
        for n in range(1, 40)
    ]
    try:
        found = holdings.first_uncovered(statements, W)
        assert found is not None and found.reason == grants.TOO_COSTLY
        assert found.statement < len(statements) - 1  # stopped early
        # A check of its own, with its own budget: each one alone is held.
        monkeypatch.setattr(grants, "CALL_BUDGET", 20_000)
        assert holdings.first_uncovered(statements[found.statement :][:1], W) is None
    finally:
        grants._covered.cache_clear()


def test_with_no_user_a_user_variable_is_held_by_no_one():
    statement = _grant(
        ["triple_store:Query"],
        ["${scope}/triple_store:graph/${user.id}/*", "${scope}/triple_store:graph/a"],
    )
    for_nobody = grants.held_statement(
        statement, W, principal_id="sva_ci", user_id=None
    )
    assert for_nobody.resources == (f"{W}/triple_store:graph/a",)
    for_bob = grants.held_statement(
        statement, W, principal_id="sva_ci", user_id="usr_bob"
    )
    assert for_bob.resources == (
        f"{W}/triple_store:graph/{U}/*",
        f"{W}/triple_store:graph/a",
    )


def test_a_deny_of_the_giver_s_variable_refuses_their_own_literal_id():
    deny = grants.held_statement(
        _grant(
            ["activity_log:ReadNote"],
            ["${scope}/activity_log:note/${principal.id}/*"],
            effect="Deny",
        ),
        W,
        principal_id="usr_me",
        user_id="usr_me",
        policy_id="pol_guard",
    )
    holdings = Holdings(
        [_side(_allow(["activity_log:ReadNote"], [f"{W}/activity_log:*"]), deny)],
        _registry(),
    )
    found = holdings.first_uncovered(
        [_grant(["activity_log:ReadNote"], ["${scope}/activity_log:note/usr_me/*"])],
        W,
    )
    assert found is not None and "pol_guard" in found.reason
    assert (
        holdings.first_uncovered(
            [_grant(["activity_log:ReadNote"], ["${scope}/activity_log:note/usr_b/*"])],
            W,
        )
        is None
    )


def test_a_wildcard_reaches_the_bus_actions_on_topics_only():
    """The bus has no catalog: a wildcard is checked for its two actions, on
    the topics the broker acts on (never at a scope)."""
    below = _allow(["triple_store:Query"], [f"{W}/*/triple_store:graph/*"])
    holdings = Holdings([_side(READER, below)], _registry())
    topic = "abi:bus:topic/payments"
    for actions in (["*"], ["bus:*"], ["*:Publish"], ["b*:*"]):
        found = holdings.first_uncovered([_grant(actions, [topic])], None)
        assert found is not None and found.action.startswith("bus:"), actions
        assert found.resource == topic
    # At a scope the bus's actions name no topic: nothing of them to hold.
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Q*y", "bus:*"], ["${scope}/*"])], W
        )
        is None
    )
    bus = Holdings([_side(_allow(["*"], [topic]))], _registry())
    assert bus.first_uncovered([_grant(["bus:*"], [topic])], None) is None


def test_a_wildcard_of_a_service_with_no_catalog_is_taken_as_written():
    holdings = Holdings([_side(_allow(["acme:Read"], ["*"]))], _registry())
    found = holdings.first_uncovered([_grant(["acme:*"], ["abi:acme:x/1"])], None)
    assert found is not None and found.action == "acme:*"
    held = Holdings([_side(_allow(["acme:*"], ["*"]))], _registry())
    assert held.first_uncovered([_grant(["acme:*"], ["abi:acme:x/1"])], None) is None


@pytest.mark.parametrize(
    "pattern, canonical",
    [
        ("abi:bus:topic/payments", "abi:bus:topic/payments"),
        ("abi:bus:topic/pay%6Dents", "abi:bus:topic/payments"),
        ("abi:bus:topic/pay:ments", "abi:bus:topic/pay%3Aments"),
        ("abi:bus:topic/pay%3aments", "abi:bus:topic/pay%3Aments"),
        ("abi:bus:topic/orders.eu", "abi:bus:topic/orders.eu"),
        # Patterns and variables stay as written; other names too.
        ("abi:bus:topic/pay:*", "abi:bus:topic/pay:*"),
        ("abi:bus:topic/${module.id}.x", "abi:bus:topic/${module.id}.x"),
        (f"{W}/bus:topic/pay:ments", f"{W}/bus:topic/pay:ments"),
    ],
)
def test_a_concrete_topic_is_compared_as_the_broker_grants_it(pattern, canonical):
    assert grants.canonical_topic(pattern) == canonical


def test_any_spelling_of_a_topic_needs_cover_and_meets_the_giver_s_deny():
    holdings = Holdings([_side(READER)], _registry())
    for topic in ("pay:ments", "pay%3Aments", "pay%6Dents"):
        found = holdings.first_uncovered(
            [_grant(["bus:Publish"], [f"abi:bus:topic/{topic}"])], None
        )
        assert found is not None, topic
    deny = grants.held_statement(
        _grant(["*"], ["abi:bus:topic/pay%6Dents"], effect="Deny"),
        None,
        principal_id="usr_me",
        user_id="usr_me",
        policy_id="pol_guard",
    )
    giver = Holdings([_side(_allow(["*"], ["abi:bus:topic/*"]), deny)], _registry())
    for topic in ("payments", "pay%6Dents", "p%61yments"):
        found = giver.first_uncovered(
            [_grant(["bus:*"], [f"abi:bus:topic/{topic}"])], None
        )
        assert found is not None and "pol_guard" in found.reason, topic
    assert (
        giver.first_uncovered([_grant(["bus:*"], ["abi:bus:topic/orders"])], None)
        is None
    )


@pytest.mark.parametrize(
    "pattern, canonical",
    [
        (
            "abi:bus:topic/pay%6Dents.${principal.id}",
            "abi:bus:topic/payments.${principal.id}",
        ),
        (
            "abi:bus:topic/payments.x:${principal.id}",
            "abi:bus:topic/payments.x%3A${principal.id}",
        ),
        ("abi:bus:topic/${user.id}", "abi:bus:topic/${user.id}"),
        ("abi:bus:topic/a:${user.id}:b", "abi:bus:topic/a%3A${user.id}%3Ab"),
        ("abi:bus:topic/pay:*", "abi:bus:topic/pay:*"),
    ],
)
def test_a_granted_topic_is_canonical_around_its_variables(pattern, canonical):
    assert grants.canonical_topic(pattern, variables=True) == canonical


def test_every_topic_resource_needs_cover():
    """Any run after the prefix is a topic: a raw ":", a variable alone."""
    holdings = Holdings([_side(READER)], _registry())
    for topic in ("a:b:c", "${principal.id}", "x:${principal.id}", "pay:*"):
        found = holdings.first_uncovered(
            [_grant(["bus:Publish"], [f"abi:bus:topic/{topic}"])], None
        )
        assert found is not None, topic


def test_a_deny_of_a_topic_refuses_its_sub_topics():
    deny = grants.held_statement(
        _grant(["*"], ["abi:bus:topic/payments"], effect="Deny"),
        None,
        principal_id="usr_me",
        user_id="usr_me",
        policy_id="pol_guard",
    )
    giver = Holdings([_side(_allow(["*"], ["abi:bus:topic/*"]), deny)], _registry())
    for topic in ("payments.eu", "pay%6Dents.eu.x", "payments.${principal.id}"):
        found = giver.first_uncovered(
            [_grant(["bus:*"], [f"abi:bus:topic/{topic}"])], None
        )
        assert found is not None and "pol_guard" in found.reason, topic
    assert (
        giver.first_uncovered([_grant(["bus:*"], ["abi:bus:topic/paymentsx"])], None)
        is None
    )


# -- container paths -------------------------------------------------------------


def test_a_type_s_names_are_steps_of_the_registered_containers():
    """``${scope}/triple_store:*`` is no wider than its graphs while triple_store
    declares no container; a container type of it makes names it reaches."""
    assert covered(f"{W}/triple_store:*", [f"{W}/triple_store:graph/*"], GRAPHS)
    folders = universe(
        "triple_store", "graph", CONTAINERS | {("triple_store", "folder")}
    )
    assert not covered(f"{W}/triple_store:*", [f"{W}/triple_store:graph/*"], folders)
    assert covered(
        f"{W}/triple_store:*",
        [f"{W}/triple_store:graph/*", f"{W}/triple_store:folder/*"],
        folders,
    )
    # A step of no registered container type names nothing.
    assert covered(f"{W}/crm:project/p/triple_store:graph/*", [], GRAPHS)
    assert not covered(
        f"{W}/crm:project/p/triple_store:graph/*",
        [],
        universe("triple_store", "graph", CONTAINERS | {("crm", "project")}),
    )
    # A container's id is one segment; only the last step's id is a path.
    assert covered(f"{O}/nexus:workspace/a/b/triple_store:graph/*", [], GRAPHS)


def test_held_forms_below_a_container_reach_each_container_under_it():
    below = O + "/*"
    assert held_forms("${scope}/triple_store:graph/*", below) == [
        f"{O}/triple_store:graph/*",
        f"{O}/*/triple_store:graph/*",
    ]
    assert held_forms("${scope}/*", below) == [f"{O}/*"]
    # The container itself, and with over (a grant, a Deny) each one under it.
    assert held_forms("${scope}", below) == [O]
    assert held_forms("${scope}", below, over=True) == [O, f"{O}/*"]
    # Not a step: as written under the container, or any run of it with over.
    assert held_forms("${scope}/x*", below) == [f"{O}/x*"]
    assert held_forms("${scope}/x*", below, over=True) == [f"{O}/*x*"]
    # At a container, one form; at the platform "${scope}/" reads "abi:".
    assert held_forms("${scope}/triple_store:graph/*", W) == [
        f"{W}/triple_store:graph/*"
    ]
    assert held_forms("${scope}/triple_store:graph/*", "abi:") == [
        "abi:triple_store:graph/*"
    ]
    assert held_forms("${scope}/triple_store:graph/*", None) == []


def test_a_role_below_an_org_covers_each_workspace_of_it():
    role = grants.held_statement(
        _grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"]),
        O + "/*",
        principal_id="usr_a",
        user_id=None,
    )
    assert role.resources == (
        f"{O}/triple_store:graph/*",
        f"{O}/*/triple_store:graph/*",
    )
    holdings = Holdings([_side(role)], _registry())
    every_graph = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])]
    for scope in (O, W, W2, f"{W}/*", f"{O}/*"):
        assert holdings.first_uncovered(every_graph, scope) is None, scope
    # Nothing at another org, or at the platform.
    other = container_name("nexus", "organization", "o2")
    assert holdings.first_uncovered(every_graph, other) is not None
    assert holdings.first_uncovered(every_graph, "abi:") is not None


def test_below_a_container_the_scope_alone_reaches_its_containers_for_their_actions():
    """``${scope}`` alone, below O: O itself and, for an action on a container
    type, each container under O; nothing else of what O holds."""
    role = grants.held_statement(
        _grant(["nexus:GetWorkspace", "triple_store:Query"], ["${scope}"]),
        O + "/*",
        principal_id="usr_a",
        user_id=None,
    )
    assert role.resources == (O,)
    assert role.containers_only == (f"{O}/*",)
    holdings = Holdings([_side(role)], _registry())
    itself = [_grant(["nexus:GetWorkspace"], ["${scope}"])]
    assert holdings.first_uncovered(itself, W) is None
    graphs = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])]
    assert holdings.first_uncovered(graphs, W) is not None


def test_a_grant_below_a_container_needs_cover_at_every_container_under_it():
    holdings = Holdings([_side(READER)], _registry())
    every_graph = [_grant(["triple_store:Query"], ["${scope}/triple_store:graph/*"])]
    assert holdings.first_uncovered(every_graph, W) is None
    found = holdings.first_uncovered(every_graph, f"{W}/*")
    assert found is not None and found.resource == f"{W}/*/triple_store:graph/*"


def test_the_platform_s_own_are_not_held_through_an_attachment_at_the_platform():
    """``${scope}`` never reaches the platform's own policies, groups and
    attachments, the platform's included: only an unscoped statement does."""
    from naas_abi_core.services.iam.iam_catalog import CATALOG as IAM

    registry = _registry()
    registry.register(IAM)
    at_platform = grants.held_statement(
        _grant(
            ["iam:UpdatePolicy", "triple_store:Query"],
            ["${scope}/iam:policy/*", "${scope}/triple_store:graph/*"],
        ),
        "abi:",
        principal_id="usr_a",
        user_id=None,
    )
    assert at_platform.resources == ()
    assert at_platform.not_platform_own == (
        "abi:iam:policy/*",
        "abi:triple_store:graph/*",
    )
    holdings = Holdings([_side(at_platform)], registry)
    policy = [_grant(["iam:UpdatePolicy"], ["abi:iam:policy/pol_x"])]
    assert holdings.first_uncovered(policy, None) is not None
    graph = [_grant(["triple_store:Query"], ["abi:triple_store:graph/g"])]
    assert holdings.first_uncovered(graph, None) is None
    unscoped = Holdings(
        [_side(_allow(["iam:UpdatePolicy"], ["abi:iam:policy/*"]))], registry
    )
    assert unscoped.first_uncovered(policy, None) is None


def test_grantable_below_an_org_lists_at_each_workspace():
    holdings = Holdings(
        [_side(_allow(["triple_store:Query"], anywhere("triple_store:graph/*")))],
        _registry(),
    )
    found = {c.service: {a.action: a for a in c.actions} for c in holdings.grantable(W)}
    assert found["triple_store"]["triple_store:Query"].resources == (
        "${scope}/triple_store:graph/*",
        "${scope}/*/triple_store:graph/*",
    )
    # At the platform, the platform's graphs.
    at_platform = {
        c.service: {a.action: a for a in c.actions} for c in holdings.grantable("abi:")
    }
    assert set(at_platform["triple_store"]["triple_store:Query"].resources) == {
        "${scope}/triple_store:graph/*",
        "${scope}/*/triple_store:graph/*",
    }


def test_a_universe_with_nesting_has_only_names_that_can_exist():
    """With each container's parents (``nesting``), no organisation sits in a
    workspace: what a pattern can name, for the builder; without, any container
    in any, as IAM decides."""
    parents = (
        ("nexus", "organization", ("-",)),
        ("nexus", "workspace", ("nexus:organization", "-")),
    )
    nesting = frozenset((f"{s}:{t}", p) for s, t, p in parents)
    workspaces = universe("nexus", "workspace", CONTAINERS, ("nexus:organization", "-"))
    nested = universe(
        "nexus", "workspace", CONTAINERS, ("nexus:organization", "-"), nesting
    )
    through_an_org = f"{W}/nexus:organization/*"
    assert overlaps(through_an_org, ("*",), workspaces)
    assert not overlaps(through_an_org, ("*",), nested)
    # What can exist is still named: a workspace of an organisation.
    assert overlaps(f"{O}/nexus:workspace/*", ("*",), nested)
    graphs = universe("triple_store", "graph", CONTAINERS, (), nesting)
    assert overlaps(f"{W}/triple_store:graph/*", ("*",), graphs)
    assert not overlaps(
        f"{W}/nexus:organization/*/triple_store:graph/*", ("*",), graphs
    )
