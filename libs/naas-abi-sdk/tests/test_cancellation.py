import threading

import pytest

from naas_abi_sdk.cancellation import (
    ActiveCalls,
    CallIdInUse,
    ToolCancellation,
    ToolCancelled,
    bind_cancellation,
    current_cancellation,
    new_call_id,
    reset_cancellation,
    valid_call_id,
)


def test_call_ids_are_generated_valid_and_distinct():
    ids = {new_call_id() for _ in range(50)}
    assert len(ids) == 50 and all(valid_call_id(i) for i in ids)


@pytest.mark.parametrize("value", ["", "a b", "a/b", "é", "x" * 129, "a\n"])
def test_a_call_id_has_letters_digits_underscore_and_dash(value):
    assert not valid_call_id(value)


def test_a_call_id_of_128_characters_is_valid():
    assert valid_call_id("a" * 128) and valid_call_id("A_b-9")


def test_a_cancellation_is_set_once_and_seen_by_every_waiter():
    token = ToolCancellation()
    assert not token.cancelled and not token.wait(0.01)
    token.raise_if_cancelled()
    woken = []
    thread = threading.Thread(target=lambda: woken.append(token.wait(5)))
    thread.start()
    token.cancel()
    token.cancel()  # idempotent
    thread.join(5)
    assert woken == [True] and token.cancelled
    with pytest.raises(ToolCancelled):
        token.raise_if_cancelled()


def test_the_current_cancellation_is_the_calls_and_inert_outside_one():
    outside = current_cancellation()
    assert not outside.cancelled
    token = ToolCancellation()
    reset = bind_cancellation(token)
    try:
        assert current_cancellation() is token
    finally:
        reset_cancellation(reset)
    assert current_cancellation() is not token


class TestActiveCalls:
    def test_a_registered_call_is_cancelled_by_its_own_identity_only(self):
        calls, seen = ActiveCalls(), []
        registration = calls.register("engine", "c1")
        registration.on_cancel(lambda: seen.append("cancelled"))
        assert not calls.cancel("partner", "c1")
        assert not calls.cancel("engine", "other")
        assert seen == [] and not registration.cancelled
        assert calls.cancel("engine", "c1")
        assert seen == ["cancelled"] and registration.cancelled

    def test_a_finished_call_is_not_cancelled(self):
        calls = ActiveCalls()
        registration = calls.register("engine", "c1")
        registration.release()
        assert not calls.cancel("engine", "c1")
        # And its id is free again.
        calls.register("engine", "c1")

    def test_an_id_running_twice_for_one_identity_is_refused(self):
        calls = ActiveCalls()
        calls.register("engine", "c1")
        with pytest.raises(CallIdInUse):
            calls.register("engine", "c1")
        calls.register("partner", "c1")  # another identity's own namespace

    def test_a_cancel_that_comes_first_applies_when_the_call_registers(self):
        now = [100.0]
        calls = ActiveCalls(clock=lambda: now[0])
        assert not calls.cancel("engine", "c1")
        registration = calls.register("engine", "c1")
        assert registration.cancelled
        seen = []
        registration.on_cancel(lambda: seen.append(1))  # runs at once
        assert seen == [1]

    def test_an_early_cancel_is_for_its_identity_and_expires(self):
        now = [100.0]
        calls = ActiveCalls(clock=lambda: now[0], early_seconds=30)
        calls.cancel("engine", "c1")
        calls.cancel("engine", "c2")
        assert not calls.register("partner", "c1").cancelled
        now[0] += 31
        assert not calls.register("engine", "c2").cancelled

    def test_early_cancels_are_bounded(self):
        calls = ActiveCalls(max_early=3)
        for index in range(10):
            calls.cancel("engine", f"c{index}")
        assert calls.early_count == 3
        # The oldest were dropped, the newest kept.
        assert calls.register("engine", "c9").cancelled
        assert not calls.register("engine", "c0").cancelled

    def test_a_callback_that_fails_does_not_stop_the_others(self):
        calls, seen = ActiveCalls(), []
        registration = calls.register("engine", "c1")

        def boom():
            raise RuntimeError("x")

        registration.on_cancel(boom)
        registration.on_cancel(lambda: seen.append("ran"))
        assert calls.cancel("engine", "c1") and seen == ["ran"]
