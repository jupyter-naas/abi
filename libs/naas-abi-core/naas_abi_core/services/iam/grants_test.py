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
    overlaps,
    universe,
)
from naas_abi_core.services.iam.policy import Statement
from naas_abi_core.services.iam.tests.iam_harness import ACTIVITY_LOG, TRIPLE_STORE

GRAPHS = universe("triple_store", "graph")
P = grants.MARKS["principal.id"]
U = grants.MARKS["user.id"]

# (grant, held, within, covered)
CONTAINMENT = [
    # Literals and plain prefixes.
    (
        "abi:o:w:triple_store:graph/a",
        ["abi:o:w:triple_store:graph/a"],
        EVERYTHING,
        True,
    ),
    (
        "abi:o:w:triple_store:graph/a",
        ["abi:o:w:triple_store:graph/b"],
        EVERYTHING,
        False,
    ),
    (
        "abi:o:w:triple_store:graph/a",
        ["abi:o:w:triple_store:graph/*"],
        EVERYTHING,
        True,
    ),
    (
        "abi:o:w:triple_store:graph/*",
        ["abi:o:w:triple_store:graph/a*"],
        EVERYTHING,
        False,
    ),
    (
        "abi:o:w:triple_store:graph/a*",
        ["abi:o:w:triple_store:graph/*"],
        EVERYTHING,
        True,
    ),
    ("*", ["*"], EVERYTHING, True),
    ("*", ["abi:*"], EVERYTHING, False),
    ("abi:o:w:x", ["*"], EVERYTHING, True),
    # "*" crosses ":" and "/".
    ("abi:o:w:triple_store:graph/a/b", ["abi:o:*"], EVERYTHING, True),
    ("abi:o:w:triple_store:graph/a", ["abi:o:*:graph/a"], EVERYTHING, True),
    ("abi:o:w:triple_store:*", ["abi:o:w:triple_store:graph/*"], EVERYTHING, False),
    # ... but a type's names hold no other field: graphs only, the rest is no wider.
    ("abi:o:w:triple_store:*", ["abi:o:w:triple_store:graph/*"], GRAPHS, True),
    ("abi:o:w:*", ["abi:o:w:triple_store:graph/*"], GRAPHS, True),
    ("abi:o:*", ["abi:o:w:triple_store:graph/*"], GRAPHS, False),
    ("abi:o:*", ["abi:o:*:triple_store:graph/*"], GRAPHS, True),
    ("abi:*", ["abi:*:*:triple_store:graph/*"], GRAPHS, True),
    ("abi:o:w:triple_store:graph/*", ["abi:o:w:triple_store:graph/*/*"], GRAPHS, False),
    # An org-wide grant reaches every workspace, an org-level one only the org's own.
    ("abi:o:w:triple_store:graph/*", ["abi:o:*:triple_store:graph/*"], GRAPHS, True),
    ("abi:o:w:triple_store:graph/*", ["abi:o:-:triple_store:graph/*"], GRAPHS, False),
    ("abi:o:*:triple_store:graph/*", ["abi:o:w:triple_store:graph/*"], GRAPHS, False),
    # "?" is one character: of an id, or one of the three of "%2F".
    ("abi:o:w:triple_store:graph/a?", ["abi:o:w:triple_store:graph/*"], GRAPHS, True),
    (
        "abi:o:w:triple_store:graph/a%2F*",
        ["abi:o:w:triple_store:graph/a?2F*"],
        GRAPHS,
        True,
    ),
    (
        "abi:o:w:triple_store:graph/a?2F*",
        ["abi:o:w:triple_store:graph/a%2F*"],
        GRAPHS,
        False,
    ),
    (
        "abi:o:w:triple_store:graph/a???",
        ["abi:o:w:triple_store:graph/a%2F"],
        GRAPHS,
        False,
    ),
    (
        "abi:o:w:triple_store:graph/a%2F",
        ["abi:o:w:triple_store:graph/a???"],
        GRAPHS,
        True,
    ),
    ("abi:o:w:triple_store:graph/??", ["abi:o:w:triple_store:graph/?*"], GRAPHS, True),
    ("abi:o:w:triple_store:graph/?*", ["abi:o:w:triple_store:graph/??"], GRAPHS, False),
    ("abi:o:w?:triple_store:graph/*", ["abi:o:w*:triple_store:graph/*"], GRAPHS, True),
    # A "?" may stand for ":": here the only way it names a graph.
    ("abi:o?w:triple_store:graph/*", ["abi:o:w:triple_store:graph/*"], GRAPHS, True),
    # The union of what is held, not one pattern of it.
    (
        "abi:o:w:triple_store:graph/?",
        ["abi:o:w:triple_store:graph/a", "abi:o:w:triple_store:graph/[^a]"],
        GRAPHS,
        False,
    ),
    (
        "abi:o:w:triple_store:graph/*",
        ["abi:o:w:triple_store:graph/a*", "abi:o:w:triple_store:graph/?*"],
        GRAPHS,
        True,
    ),
    # Variables: the same variable form, or a wildcard, never a literal id.
    (
        f"abi:o:w:activity_log:note/{P}",
        [f"abi:o:w:activity_log:note/{P}"],
        EVERYTHING,
        True,
    ),
    (
        f"abi:o:w:activity_log:note/{P}/*",
        [f"abi:o:w:activity_log:note/{P}/*"],
        EVERYTHING,
        True,
    ),
    (
        f"abi:o:w:activity_log:note/{P}",
        ["abi:o:w:activity_log:note/*"],
        EVERYTHING,
        True,
    ),
    (
        f"abi:o:w:activity_log:note/{P}",
        ["abi:o:w:activity_log:note/usr_1"],
        EVERYTHING,
        False,
    ),
    (
        f"abi:o:w:activity_log:note/{P}/*",
        [f"abi:o:w:activity_log:note/{P}"],
        EVERYTHING,
        False,
    ),
    (
        f"abi:o:w:activity_log:note/{U}",
        [f"abi:o:w:activity_log:note/{P}"],
        EVERYTHING,
        False,
    ),
    (
        "abi:o:w:activity_log:note/*",
        [f"abi:o:w:activity_log:note/{P}/*"],
        EVERYTHING,
        False,
    ),
    # A variable is a whole id: a "?" is one character, not it.
    (
        f"abi:o:w:activity_log:note/{P}",
        ["abi:o:w:activity_log:note/?"],
        universe("activity_log", "note"),
        False,
    ),
    (
        f"abi:o:w:activity_log:note/{P}",
        ["abi:o:w:activity_log:note/?*"],
        universe("activity_log", "note"),
        False,
    ),
    (
        f"abi:o:w:activity_log:note/{P}",
        ["abi:o:w:activity_log:note/*"],
        universe("activity_log", "note"),
        True,
    ),
    # Nothing held, a grant naming graphs: not covered.
    ("abi:o:w:triple_store:graph/*", [], GRAPHS, False),
    # A grant naming no graph grants nothing on graphs: nothing to cover.
    ("abi:o:w:triple_store:view/*", [], GRAPHS, True),
]


@pytest.mark.parametrize("grant, held, within, expected", CONTAINMENT)
def test_containment(grant, held, within, expected):
    assert covered(grant, held, within) is expected


@pytest.mark.parametrize(
    "grant, other, within, expected",
    [
        (
            "abi:o:w:triple_store:graph/*",
            "abi:*:*:triple_store:graph/secret",
            GRAPHS,
            True,
        ),
        (
            "abi:o:w:triple_store:graph/a*",
            "abi:o:w:triple_store:graph/b*",
            GRAPHS,
            False,
        ),
        (
            "abi:o:w:triple_store:graph/?",
            "abi:o:w:triple_store:graph/ab",
            GRAPHS,
            False,
        ),
        (
            "abi:o:w:triple_store:graph/*",
            "abi:o:w2:triple_store:graph/*",
            GRAPHS,
            False,
        ),
        ("abi:o:w:*", "*", GRAPHS, True),
        # Not a graph at all: nothing of it is a graph's name.
        ("abi:o:w:triple_store:graph/*", "abi:o:w:triple_store:view/*", GRAPHS, False),
    ],
)
def test_overlap(grant, other, within, expected):
    assert overlaps(grant, (other,), within) is expected


def test_held_form_fills_the_scope_and_marks_the_variables():
    assert held_form("${scope}:x:y/${principal.id}", "abi:o:w") == f"abi:o:w:x:y/{P}"
    assert held_form("${scope}:x:y/*", None) is None
    assert grants.shown(f"abi:o:w:x:y/{P}") == "abi:o:w:x:y/${principal.id}"


def test_an_undecidable_containment_with_nothing_held_is_refused():
    # Nothing prefix-compatible is held: the search still runs past its budget.
    grants._covered.cache_clear()
    assert not covered("abi:o:w:triple_store:graph/*a?????????????????????", [], GRAPHS)


def test_an_undecidable_containment_is_refused(monkeypatch):
    # Covered by the union only: no one pattern shows it, so the search decides.
    monkeypatch.setattr(grants, "STATE_BUDGET", 3)
    grants._covered.cache_clear()
    try:
        assert not covered(
            "abi:o:w:triple_store:graph/*",
            ["abi:o:w:triple_store:graph/a*", "abi:o:w:triple_store:graph/?*"],
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
                "abi:org-1:ws-2:nexus:module/*",
                ["abi:org-1:*:nexus:module/*", "abi:org-1:ws-1:nexus:module/*"],
                universe("nexus", "module"),
            )
            assert covered(
                f"abi:o:w:activity_log:note/{P}/?",
                [f"abi:o:*:activity_log:note/{P}/*"],
                universe("activity_log", "note"),
            )
            # A "?" never takes in a variable, nor a "*" of the grant.
            with pytest.raises(grants.Exhausted):
                covered(
                    f"abi:o:w:activity_log:note/{P}",
                    ["abi:o:*:activity_log:note/?"],
                    universe("activity_log", "note"),
                )
    finally:
        grants._covered.cache_clear()


# -- holdings ------------------------------------------------------------------


def _registry() -> CatalogRegistry:
    registry = CatalogRegistry()
    registry.register(TRIPLE_STORE)
    registry.register(ACTIVITY_LOG)
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
    ["triple_store:Query", "triple_store:ListGraphs"], ["abi:o:w:triple_store:graph/*"]
)


def test_wildcard_actions_are_expanded_against_the_catalogs():
    holdings = Holdings([_side(READER)], _registry())
    found = holdings.first_uncovered(
        [_grant(["triple_store:*"], ["${scope}:triple_store:graph/*"])], "abi:o:w"
    )
    assert found is not None
    assert found.action == "triple_store:QueryStream"
    assert found.resource == "abi:o:w:triple_store:graph/*"
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Q*y"], ["${scope}:triple_store:*"])], "abi:o:w"
        )
        is None
    )


def test_a_deny_needs_no_cover_and_a_deny_of_the_giver_refuses():
    holdings = Holdings(
        [
            _side(
                READER,
                _deny(["triple_store:Query"], ["abi:*:*:triple_store:graph/hr*"]),
            )
        ],
        _registry(),
    )
    assert (
        holdings.first_uncovered(
            [
                _grant(["*"], ["*"], effect="Deny"),
                _grant(["triple_store:ListGraphs"], ["${scope}:triple_store:graph/*"]),
            ],
            "abi:o:w",
        )
        is None
    )
    found = holdings.first_uncovered(
        [_grant(["triple_store:Query"], ["${scope}:triple_store:graph/*"])], "abi:o:w"
    )
    assert found is not None and "pol_guard" in found.reason
    # Narrowed away from the Deny, it is held.
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Query"], ["${scope}:triple_store:graph/sales*"])],
            "abi:o:w",
        )
        is None
    )


def test_at_a_scope_only_the_scope_s_patterns_count():
    holdings = Holdings([_side(READER)], _registry())
    statement = _grant(["triple_store:Query"], ["${scope}:triple_store:graph/*", "*"])
    assert holdings.first_uncovered([statement], "abi:o:w") is None
    assert holdings.first_uncovered([statement], None) is not None


def test_every_side_must_hold_it():
    token = Side(
        (_allow(["triple_store:Query"], ["*"]),),
        "your credential's scope does not allow it",
    )
    holdings = Holdings([_side(READER), token], _registry())
    found = holdings.first_uncovered(
        [_grant(["triple_store:ListGraphs"], ["${scope}:triple_store:graph/*"])],
        "abi:o:w",
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
            [_grant(["triple_store:Query"], ["${scope}:triple_store:graph/a"])],
            "abi:o:w",
        )
        is not None
    )


def test_grantable_lists_what_is_held_at_the_scope_minus_denies():
    holdings = Holdings(
        [
            _side(
                _allow(["triple_store:Query"], ["abi:o:*:triple_store:graph/*"]),
                _allow(["triple_store:Insert"], ["abi:o:w2:triple_store:graph/*"]),
                _allow(["activity_log:ReadNote"], [f"abi:o:w:activity_log:note/{P}/*"]),
                _deny(["triple_store:Query"], ["abi:*:*:triple_store:graph/hr*"]),
                _allow(["triple_store:DropGraph"], ["abi:o:w:triple_store:graph/tmp*"]),
                _deny(["triple_store:DropGraph"], ["*"]),
            )
        ],
        _registry(),
    )
    found = {
        c.service: {a.action: a for a in c.actions}
        for c in holdings.grantable("abi:o:w")
    }
    query = found["triple_store"]["triple_store:Query"]
    assert query.resources == ("${scope}:triple_store:graph/*",)
    # Written as the resources are, at the scope.
    assert query.excluded == ("${scope}:triple_store:graph/hr*",)
    assert "triple_store:Insert" not in found["triple_store"]  # another workspace's
    assert "triple_store:DropGraph" not in found["triple_store"]  # all denied
    assert found["activity_log"]["activity_log:ReadNote"].resources == (
        "${scope}:activity_log:note/${principal.id}/*",
    )


def test_grantable_of_everything():
    holdings = Holdings([_side(_allow(["*"], ["*"]))], _registry())
    found = {c.service: c for c in holdings.grantable("abi:o:w")}
    assert {a.resources for a in found["triple_store"].actions} == {("${scope}:*",)}


def test_the_searches_of_one_check_share_a_budget(monkeypatch):
    """Many costly statements do not each get a budget: past the check's, what
    is left is refused, and nothing is cached for it."""
    monkeypatch.setattr(grants, "CALL_BUDGET", 2_000)
    grants._covered.cache_clear()
    # Covered within graphs only (an id is never empty): each needs a search.
    held = _side(_allow(["triple_store:Query"], ["abi:o:w:triple_store:graph/?*"]))
    holdings = Holdings([held], _registry())
    statements = [
        _grant(
            ["triple_store:Query"],
            [f"${{scope}}:triple_store:graph/*b{'?' * n}*"],
        )
        for n in range(1, 40)
    ]
    try:
        found = holdings.first_uncovered(statements, "abi:o:w")
        assert found is not None and found.reason == grants.TOO_COSTLY
        assert found.statement < len(statements) - 1  # stopped early
        # A check of its own, with its own budget: each one alone is held.
        monkeypatch.setattr(grants, "CALL_BUDGET", 20_000)
        assert (
            holdings.first_uncovered(statements[found.statement :][:1], "abi:o:w")
            is None
        )
    finally:
        grants._covered.cache_clear()


def test_with_no_user_a_user_variable_is_held_by_no_one():
    statement = _grant(
        ["triple_store:Query"],
        ["${scope}:triple_store:graph/${user.id}/*", "${scope}:triple_store:graph/a"],
    )
    for_nobody = grants.held_statement(
        statement, "abi:o:w", principal_id="sva_ci", user_id=None
    )
    assert for_nobody.resources == ("abi:o:w:triple_store:graph/a",)
    for_bob = grants.held_statement(
        statement, "abi:o:w", principal_id="sva_ci", user_id="usr_bob"
    )
    assert for_bob.resources == (
        f"abi:o:w:triple_store:graph/{U}/*",
        "abi:o:w:triple_store:graph/a",
    )


def test_a_deny_of_the_giver_s_variable_refuses_their_own_literal_id():
    deny = grants.held_statement(
        _grant(
            ["activity_log:ReadNote"],
            ["${scope}:activity_log:note/${principal.id}/*"],
            effect="Deny",
        ),
        "abi:o:w",
        principal_id="usr_me",
        user_id="usr_me",
        policy_id="pol_guard",
    )
    holdings = Holdings(
        [_side(_allow(["activity_log:ReadNote"], ["abi:o:w:activity_log:*"]), deny)],
        _registry(),
    )
    found = holdings.first_uncovered(
        [_grant(["activity_log:ReadNote"], ["${scope}:activity_log:note/usr_me/*"])],
        "abi:o:w",
    )
    assert found is not None and "pol_guard" in found.reason
    assert (
        holdings.first_uncovered(
            [_grant(["activity_log:ReadNote"], ["${scope}:activity_log:note/usr_b/*"])],
            "abi:o:w",
        )
        is None
    )


def test_a_wildcard_reaches_the_bus_actions_on_topics_only():
    """The bus has no catalog: a wildcard is checked for its two actions, on
    the topics the broker acts on (never at a scope)."""
    holdings = Holdings([_side(READER)], _registry())
    topic = "abi:-:-:bus:topic/payments"
    for actions in (["*"], ["bus:*"], ["*:Publish"], ["b*:*"]):
        found = holdings.first_uncovered([_grant(actions, [topic])], None)
        assert found is not None and found.action.startswith("bus:"), actions
        assert found.resource == topic
    # At a scope the bus's actions name no topic: nothing of them to hold.
    assert (
        holdings.first_uncovered(
            [_grant(["triple_store:Q*y", "bus:*"], ["${scope}:*"])], "abi:o:w"
        )
        is None
    )
    bus = Holdings([_side(_allow(["*"], [topic]))], _registry())
    assert bus.first_uncovered([_grant(["bus:*"], [topic])], None) is None


def test_a_wildcard_of_a_service_with_no_catalog_is_taken_as_written():
    holdings = Holdings([_side(_allow(["acme:Read"], ["*"]))], _registry())
    found = holdings.first_uncovered([_grant(["acme:*"], ["abi:-:-:acme:x/1"])], None)
    assert found is not None and found.action == "acme:*"
    held = Holdings([_side(_allow(["acme:*"], ["*"]))], _registry())
    assert (
        held.first_uncovered([_grant(["acme:*"], ["abi:-:-:acme:x/1"])], None) is None
    )
