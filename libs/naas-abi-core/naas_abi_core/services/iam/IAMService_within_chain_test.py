"""A sub-policy names nothing its chain allows nowhere: written out, an action or a
resource the parent does not allow would grant nothing, silently; IAM refuses it,
naming it (``_require_within_chain``). Wildcards stay bounded by the chain."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    document,
    statement,
    workspace,
)

USE = "module:UseAgent"
OPEN = "module:OpenApp"
WS1 = workspace("ws-1")


def _parent(h: IAMHarness):
    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    root = h.user("root")
    h.attach("builtin.platform_admin", root.id)
    parent = h.admin(
        "create_policy",
        "Acme access",
        document(statement("Allow", [USE], ["${scope}/module:agent/people/*"])),
    )
    return root, parent


def _agents(*names: str, actions: list[str] | None = None) -> dict:
    return document(
        statement(
            "Allow",
            actions or [USE],
            [f"${{scope}}/module:agent/{name}" for name in names],
        )
    )


def test_a_resource_its_parent_does_not_allow_is_refused_naming_both(h):
    root, parent = _parent(h)
    with h.as_(root), pytest.raises(ValueError) as refused:
        h.iam.create_policy(
            "Alpha access",
            _agents("people/recruiter", "market/pricer"),
            scope=WS1,
            parent=parent.id,
        )
    assert "module:agent/market/pricer" in str(refused.value)
    assert parent.id in str(refused.value) and "grant nothing" in str(refused.value)


def test_an_action_its_parent_allows_on_nothing_is_refused(h):
    root, parent = _parent(h)
    with h.as_(root), pytest.raises(ValueError, match=OPEN):
        h.iam.create_policy(
            "apps", _agents("people/*", actions=[OPEN]), scope=WS1, parent=parent.id
        )


def test_wildcards_stay_bounded_by_the_chain(h):
    root, parent = _parent(h)
    with h.as_(root):
        child = h.iam.create_policy(
            "every agent",
            _agents("*", actions=["module:*"]),
            scope=WS1,
            parent=parent.id,
        )
    assert child.parent_id == parent.id


def test_an_update_naming_what_the_parent_does_not_allow_is_refused(h):
    root, parent = _parent(h)
    with h.as_(root):
        child = h.iam.create_policy(
            "Alpha access", _agents("people/recruiter"), scope=WS1, parent=parent.id
        )
        with pytest.raises(ValueError, match="market/pricer"):
            h.iam.update_policy(
                child.id,
                expected_revision=1,
                document=_agents("people/recruiter", "market/pricer"),
            )
        # Narrowing the parent below it is never refused for what is below.
        h.iam.update_policy(
            parent.id,
            expected_revision=1,
            document=document(
                statement("Allow", [USE], ["${scope}/module:agent/people/scout"])
            ),
        )


def test_a_first_party_account_writing_for_nobody_is_not_checked(h):
    _root, parent = _parent(h)
    with as_service_account("api"):
        made = h.iam.create_policy(
            "moved", _agents("market/pricer"), scope=WS1, parent=parent.id
        )
    assert made.parent_id == parent.id


def test_a_name_the_parent_stopped_allowing_never_blocks_an_edit(h):
    """(a) The parent is narrowed below a sub-policy: narrowing the sub-policy, or
    any edit that adds nothing new, goes through."""
    root, parent = _parent(h)
    with h.as_(root):
        child = h.iam.create_policy(
            "Alpha access",
            _agents("people/recruiter", "people/scout"),
            scope=WS1,
            parent=parent.id,
        )
        h.iam.update_policy(
            parent.id,
            expected_revision=1,
            document=document(
                statement("Allow", [USE], ["${scope}/module:agent/people/scout"])
            ),
        )
        h.iam.update_policy(
            child.id, expected_revision=1, document=_agents("people/recruiter")
        )
        # What the edit adds is still checked.
        with pytest.raises(ValueError, match="people/coach"):
            h.iam.update_policy(
                child.id,
                expected_revision=2,
                document=_agents("people/recruiter", "people/coach"),
            )


NOTHING = statement("Allow", [USE], ["${scope}/module:agent/%00"], sid="Nothing")


def test_the_nothing_sentinel_never_blocks_widening(h):
    """(b) A new access policy allows nothing (``%00``); the builder keeps that
    statement while it adds the first types, under a parent that allows specific
    agents only, or no agent at all."""
    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    root = h.user("root")
    h.attach("builtin.platform_admin", root.id)
    some = h.admin(
        "create_policy",
        "Acme access",
        document(statement("Allow", [USE], ["${scope}/module:agent/people/recruiter"])),
    )
    none = h.admin(
        "create_policy",
        "Beta access",
        document(statement("Allow", [OPEN], ["${scope}/module:app/market/prices"])),
    )
    for parent, added in (
        (some, statement("Allow", [USE], ["${scope}/module:agent/people/recruiter"])),
        (none, statement("Allow", [OPEN], ["${scope}/module:app/market/prices"])),
    ):
        with as_service_account("api"):
            access = h.iam.create_policy(
                "W access", document(NOTHING), scope=WS1, parent=parent.id
            )
        with h.as_(root):
            widened = h.iam.update_policy(
                access.id, expected_revision=1, document=document(NOTHING, added)
            )
        assert widened.revision == 2
        # Created by hand with it, the sentinel is not checked either.
        with h.as_(root):
            h.iam.create_policy(
                "by hand", document(NOTHING), scope=WS1, parent=parent.id
            )


def test_a_new_parent_is_checked_against_the_whole_document(h):
    """Re-parenting with the same document is checked as a create is."""
    root, parent = _parent(h)
    with h.as_(root):
        other = h.iam.create_policy(
            "Market access",
            document(statement("Allow", [USE], ["${scope}/module:agent/market/*"])),
        )
        child = h.iam.create_policy(
            "Alpha access", _agents("people/recruiter"), scope=WS1, parent=parent.id
        )
        with pytest.raises(ValueError, match="people/recruiter"):
            h.iam.update_policy(child.id, expected_revision=1, parent=other.id)


def test_a_name_its_parent_allows_only_in_a_container_under_the_owner_is_kept(h):
    """A sub-policy of an organization attached below it names its resources at each
    container under it (the evaluator fills ``${scope}`` with each): a platform
    parent naming one workspace's agents allows Recruiter there, so the sub-policy
    naming Recruiter grants something and is kept. One it allows nowhere is still
    refused."""
    from naas_abi_core.services.iam.tests.iam_harness import org

    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    root = h.user("root")
    h.attach("builtin.platform_admin", root.id)
    org1 = org("org-1")
    parent = h.admin(
        "create_policy",
        "ws-1's people",
        document(statement("Allow", [USE], [f"{WS1}/module:agent/people/*"])),
    )
    with h.as_(root):
        child = h.iam.create_policy(
            "Recruiter", _agents("people/recruiter"), scope=org1, parent=parent.id
        )
        with pytest.raises(ValueError, match="grant nothing"):
            h.iam.create_policy(
                "Pricer", _agents("market/pricer"), scope=org1, parent=parent.id
            )
    bob = h.user("bob")
    h.attach(child.id, bob.id, f"{org1}/*")
    recruiter = f"{WS1}/module:agent/people/recruiter"
    assert h.allowed(USE, recruiter, bob)
    assert not h.allowed(USE, f"{org1}/module:agent/people/recruiter", bob)
