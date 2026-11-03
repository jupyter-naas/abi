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
