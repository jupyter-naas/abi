"""Effective policies stay cached until the IAM store changes.

Every store write that changes who may do what bumps the store's revision. The
service compares it, at most every ``revision_check_seconds``, before it reads
a cached subject: a change made by another process (one this process never
heard of) applies within that interval, and a subject nothing changed is not
rebuilt every ``cache_ttl_seconds``. ``subject_ttl_seconds`` only bounds how long
an unchanged one is kept.
"""

from __future__ import annotations

import threading
import time

import pytest

from naas_abi_core.services.iam import IAMService as iam_service_module
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    document,
    graph,
    statement,
)

QUERY = "triple_store:Query"


def _other_process(h: IAMHarness, **kwargs) -> IAMHarness:
    """A second service on the same store: it hears of no change made by ``h``."""
    return IAMHarness(IAMService(h.iam.store, **kwargs))


def _counting_computes(monkeypatch, service: IAMService) -> list[int]:
    computed = [0]
    original = service._compute_subject

    def counting(*args, **kwargs):
        computed[0] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_compute_subject", counting)
    return computed


def test_another_process_s_change_applies_at_the_next_revision_check(h):
    other = _other_process(
        h, cache_ttl_seconds=60, subject_ttl_seconds=600, revision_check_seconds=0.05
    )
    bob = h.user()
    assert not other.allowed(QUERY, graph("a"), bob)
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))  # no notice reaches `other`
    time.sleep(0.1)
    assert other.allowed(QUERY, graph("a"), bob)


def test_an_unchanged_subject_outlives_the_cache_ttl(h, monkeypatch):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    # Started after those writes: the store has not changed since.
    other = _other_process(
        h, cache_ttl_seconds=0.05, subject_ttl_seconds=600, revision_check_seconds=0.01
    )
    computed = _counting_computes(monkeypatch, other.iam)
    assert other.allowed(QUERY, graph("a"), bob)
    first = computed[0]
    time.sleep(0.1)  # past cache_ttl_seconds, and past several revision checks
    assert other.allowed(QUERY, graph("a"), bob)
    assert computed[0] == first


def test_a_failed_revision_read_drops_the_cache(h, monkeypatch):
    other = _other_process(
        h, cache_ttl_seconds=60, subject_ttl_seconds=600, revision_check_seconds=0.01
    )
    bob = h.user()
    assert not other.allowed(QUERY, graph("a"), bob)
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))

    def unreadable() -> int:
        raise RuntimeError("store unreachable")

    with monkeypatch.context() as patched:
        patched.setattr(other.iam.store, "revision", unreadable)
        time.sleep(0.05)
        # The revision could not be read: nothing cached is trusted.
        assert other.allowed(QUERY, graph("a"), bob)


def _attach(h, bob):
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))


def _detach(h, bob):
    for attachment in h.iam.store.list_attachments(principal_id=bob.id):
        h.admin("detach_policy", attachment.policy_id, bob.id, scope=attachment.scope)


def _join_group(h, bob):
    sales = h.group()
    h.grant(sales.id, statement("Allow", [QUERY], ["*"]))
    h.admin("add_group_member", sales.id, bob.id)


def _leave_group(h, bob):
    for group_id in h.iam.store.groups_of(bob.id):
        h.admin("remove_group_member", group_id, bob.id)


def _suspend(h, bob):
    h.admin("suspend_principal", bob.id)


def _resume(h, bob):
    h.admin("resume_principal", bob.id)


def _edit_policy(h, bob):
    for attachment in h.iam.store.list_attachments(principal_id=bob.id):
        policy = h.iam.store.get_policy(attachment.policy_id)
        h.admin(
            "update_policy",
            policy.id,
            expected_revision=policy.revision,
            document=document(statement("Deny", [QUERY], ["*"])),
        )


# (setup, change, allowed before, allowed after)
CHANGES = {
    "attach a policy": (lambda h, bob: None, _attach, False, True),
    "detach a policy": (_attach, _detach, True, False),
    "join a group": (lambda h, bob: None, _join_group, False, True),
    "leave a group": (_join_group, _leave_group, True, False),
    "suspend the principal": (_attach, _suspend, True, False),
    "resume the principal": (
        lambda h, bob: (_attach(h, bob), _suspend(h, bob)),
        _resume,
        False,
        True,
    ),
    "edit an attached policy": (_attach, _edit_policy, True, False),
}


@pytest.mark.parametrize("change", list(CHANGES))
def test_every_change_through_the_service_applies_at_once(h, change):
    setup, act, before, after = CHANGES[change]
    bob = h.user()
    setup(h, bob)
    assert h.allowed(QUERY, graph("a"), bob) is before  # now cached
    act(h, bob)
    assert h.allowed(QUERY, graph("a"), bob) is after  # no wait


@pytest.mark.parametrize("change", list(CHANGES))
def test_every_change_reaches_another_process_without_a_notice(h, change):
    setup, act, before, after = CHANGES[change]
    other = _other_process(
        h, cache_ttl_seconds=60, subject_ttl_seconds=600, revision_check_seconds=0.02
    )
    bob = h.user()
    setup(h, bob)
    assert other.allowed(QUERY, graph("a"), bob) is before
    act(h, bob)
    time.sleep(0.05)
    assert other.allowed(QUERY, graph("a"), bob) is after


def test_the_defaults_keep_subjects_ten_minutes_and_check_every_two_seconds():
    assert iam_service_module.SUBJECT_TTL_SECONDS == 600
    assert iam_service_module.REVISION_CHECK_SECONDS == 2


@pytest.mark.parametrize("change", list(CHANGES))
def test_authorization_revision_refreshes_without_waiting_for_a_notice(h, change):
    setup, act, before, after = CHANGES[change]
    person = h.user("reader")
    setup(h, person)
    other = _other_process(h, revision_check_seconds=60)
    assert other.allowed(QUERY, graph("a"), person) is before
    revision = other.iam.authorization_revision()

    act(h, person)

    assert other.iam.authorization_revision() != revision
    assert other.allowed(QUERY, graph("a"), person) is after


def test_authorization_revision_does_not_trust_cached_grants_on_store_failure(
    h, monkeypatch
):
    person = h.user("reader")
    _attach(h, person)
    other = _other_process(h, revision_check_seconds=60)
    assert other.allowed(QUERY, graph("a"), person)

    def unreadable():
        raise RuntimeError("store unavailable")

    with monkeypatch.context() as patched:
        patched.setattr(other.iam.store, "revision", unreadable)
        with pytest.raises(RuntimeError, match="store unavailable"):
            other.iam.authorization_revision()

    _detach(h, person)
    # The failed check dropped its subjects, even before the periodic check runs.
    assert not other.allowed(QUERY, graph("a"), person)


def test_a_change_notice_cannot_publish_a_revision_before_discarding_old_grants(
    h, monkeypatch
):
    person = h.user("reader")
    _attach(h, person)
    other = _other_process(h, revision_check_seconds=60)
    assert other.allowed(QUERY, graph("a"), person)
    _detach(h, person)
    started, release = threading.Event(), threading.Event()
    original = other.iam.invalidate

    def delayed_notice():
        if threading.current_thread() is notice:
            started.set()
            assert release.wait(5)
        original()

    monkeypatch.setattr(other.iam, "invalidate", delayed_notice)
    notice = threading.Thread(target=other.iam.refresh_if_changed)
    notice.start()
    try:
        assert started.wait(5)
        other.iam.authorization_revision()
        assert not other.allowed(QUERY, graph("a"), person)
    finally:
        release.set()
        notice.join(5)
        assert not notice.is_alive()
