"""A first-party module (the built-in IdP) is ready at engine boot (#1643).

``provision_first_party_module`` registers the key the deployment generated and
approves the manifest the engine computed from its own copy of the module:
no `abi iam` step after the stack is up, and nothing the running module sends
is approved without review.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from naas_abi_core.services.iam import keys, modules
from naas_abi_core.services.iam.IAMPorts import IAMConflictError
from naas_abi_core.services.iam.IAMService import (
    FIRST_PARTY_DECIDER,
    SEEDED_KEY_DESCRIPTION,
)

PROJECT = "demo"
ACCOUNT = "module/demo/idp"


def _manifest(services: tuple[str, ...] = ("document", "secret", "email")) -> dict:
    from naas_abi_sdk.module import ModuleDependencies
    from naas_abi_sdk.permissions import default_manifest

    return default_manifest(ModuleDependencies(services=services))


def _account(h):
    return h.iam.store.find_service_account(ACCOUNT)


def test_the_account_is_created_with_the_module_bootstrap(h) -> None:
    from naas_abi_core.services.iam import roles

    account = h.iam.provision_first_party_module(PROJECT, "idp")

    assert account.name == ACCOUNT
    attached = {a.policy_id for a in h.iam.store.list_attachments()}
    assert roles.MODULE_BOOTSTRAP in attached
    # Again: nothing new.
    assert h.iam.provision_first_party_module(PROJECT, "idp").id == account.id


def test_the_deployment_key_lets_the_module_log_in(h) -> None:
    value = keys.generate_key("service").value

    h.iam.provision_first_party_module(PROJECT, "idp", key=value)

    principal, key = h.iam.authenticate_key(value)
    assert principal.name == ACCOUNT
    assert key.description == SEEDED_KEY_DESCRIPTION
    # The same key again: registered once.
    h.iam.provision_first_party_module(PROJECT, "idp", key=value)
    assert len(h.iam.store.list_keys(principal.id)) == 1


def test_a_new_deployment_key_replaces_the_seeded_one(h) -> None:
    first = keys.generate_key("service").value
    second = keys.generate_key("service").value
    h.iam.provision_first_party_module(PROJECT, "idp", key=first)

    h.iam.provision_first_party_module(PROJECT, "idp", key=second)

    assert h.iam.authenticate_key(second)[0].name == ACCOUNT
    with pytest.raises(Exception):
        h.iam.authenticate_key(first)


def test_a_key_made_by_hand_is_kept(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp")
    by_hand = h.iam._create_key(account, description="abi iam")
    seeded = keys.generate_key("service").value

    h.iam.provision_first_party_module(PROJECT, "idp", key=seeded)

    assert h.iam.authenticate_key(by_hand.value)[0].id == account.id
    assert h.iam.authenticate_key(seeded)[0].id == account.id


@pytest.mark.parametrize("kind", ["personal", "grant"])
def test_only_a_service_key_is_registered(h, kind) -> None:
    with pytest.raises(ValueError):
        h.iam.provision_first_party_module(
            PROJECT, "idp", key=keys.generate_key(kind).value
        )


def test_a_key_of_another_principal_is_refused(h) -> None:
    other = h.service_account("module/demo/other")
    theirs = h.iam._create_key(other, description="theirs").value

    with pytest.raises(IAMConflictError, match="another principal"):
        h.iam.provision_first_party_module(PROJECT, "idp", key=theirs)


def test_a_forged_secret_for_a_known_key_id_is_refused(h) -> None:
    value = keys.generate_key("service").value
    h.iam.provision_first_party_module(PROJECT, "idp", key=value)
    key_id = keys.parse(value).key_id
    other_secret = keys.parse(keys.generate_key("service").value).secret
    forged = f"abi_sk_{key_id}_{other_secret}"

    with pytest.raises(IAMConflictError, match="does not match"):
        h.iam.provision_first_party_module(PROJECT, "idp", key=forged)


def test_a_revoked_key_is_not_brought_back(h) -> None:
    value = keys.generate_key("service").value
    account = h.iam.provision_first_party_module(PROJECT, "idp", key=value)
    h.iam.store.revoke_key(keys.parse(value).key_id, datetime.now(UTC))

    with pytest.raises(IAMConflictError, match="revoked"):
        h.iam.provision_first_party_module(PROJECT, "idp", key=value)
    assert account.id == _account(h).id


def test_the_engine_s_own_manifest_is_approved_before_the_module_submits(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())
    [approved] = h.iam.store.list_manifests(account.id, "approved")
    assert approved.decided_by == FIRST_PARTY_DECIDER
    assert modules.policy_id(PROJECT, "idp") in {
        a.policy_id for a in h.iam.store.list_attachments()
    }

    # The module submits the same document: in force at once, nothing pending.
    with h.as_(account):
        submitted = h.iam.submit_manifest("idp", PROJECT, _manifest())
    assert submitted.manifest.status == "approved" and submitted.in_force
    assert h.iam.store.list_manifests(account.id, "pending") == []


def test_another_version_from_the_module_waits_for_review(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())

    with h.as_(account):
        submitted = h.iam.submit_manifest(
            "idp", PROJECT, _manifest(("document", "secret", "email", "dataset"))
        )

    assert submitted.manifest.status == "pending"
    assert submitted.in_force  # the engine's version stays in force


def test_an_upgrade_approves_the_new_own_manifest(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())
    newer = _manifest(("document", "secret", "email", "kv"))

    h.iam.provision_first_party_module(PROJECT, "idp", manifest=newer)

    statuses = sorted(m.status for m in h.iam.store.list_manifests(account.id))
    assert statuses == ["approved", "superseded"]


def test_a_version_an_operator_rejected_stays_rejected(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp")
    with h.as_(account):
        h.iam.submit_manifest("idp", PROJECT, _manifest())
    h.admin("reject_manifest", account.id)

    h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())

    assert [m.status for m in h.iam.store.list_manifests(account.id)] == ["rejected"]


def test_a_pending_submission_of_the_same_version_is_approved(h) -> None:
    # The module started before the engine provisioned it (a restart).
    account = h.iam.provision_first_party_module(PROJECT, "idp")
    with h.as_(account):
        h.iam.submit_manifest("idp", PROJECT, _manifest())

    h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())

    assert [m.status for m in h.iam.store.list_manifests(account.id)] == ["approved"]


def test_a_suspended_account_is_left_alone(h) -> None:
    account = h.iam.provision_first_party_module(PROJECT, "idp")
    h.admin("suspend_principal", account.id)

    with pytest.raises(IAMConflictError, match="suspended"):
        h.iam.provision_first_party_module(PROJECT, "idp", manifest=_manifest())
