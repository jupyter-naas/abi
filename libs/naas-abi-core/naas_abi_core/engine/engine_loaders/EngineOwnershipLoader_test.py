"""The engine's ownership loader, over an in-memory lease on its own loop."""

import threading
import time

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineOwnershipLoader import (
    EngineOwnershipLoader,
)
from naas_abi_core.engine.ownership.adapters.secondary.lease_memory import InMemoryLease
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
    EngineOwnership,
    LocalBackendsCannotHandOver,
    OwnershipState,
)
from naas_abi_core.engine.ownership.ownership_service_test import FlakyLease
from naas_abi_core.engine.ownership.tests.lease__secondary_adapter__generic_test import (
    holder,
)


def nats_config(**engine) -> NATSConfiguration:
    return NATSConfiguration(
        jwt_secret="test-only", engine={"lease_seconds": 1, **engine}
    )


class Store:
    """Builds the loader's ownership over an in-memory lease, seeded on its loop."""

    def __init__(self, *seed, flaky: bool = False):
        self.seed = seed
        self.flaky = flaky
        self.lease = None
        self.ownership = None

    async def __call__(self, settings, me):
        store = InMemoryLease()
        for seeded in self.seed:
            await store.create(seeded)
        self.lease = FlakyLease(store) if self.flaky else store
        self.ownership = EngineOwnership(self.lease, me, settings.timing())
        return self.ownership


def wait_until(predicate, timeout=5.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def test_a_client_engine_never_touches_the_lease():
    store = Store()
    loader = EngineOwnershipLoader(
        nats_config(role="client"), environ={}, ownership_factory=store
    )

    assert loader.claim() is None
    assert store.ownership is None
    loader.release()
    loader.close()


def test_the_environment_can_make_an_engine_a_client():
    store = Store()
    loader = EngineOwnershipLoader(
        nats_config(), environ={"ABI_ENGINE_ROLE": "client"}, ownership_factory=store
    )

    assert loader.claim() is None
    loader.close()


def test_a_serving_engine_holds_the_lease_until_it_releases():
    store = Store()
    loader = EngineOwnershipLoader(
        nats_config(), environ={"ABI_ROLLOUT_ID": "v2"}, ownership_factory=store
    )

    assert loader.claim() is Claim.SERVING
    record = loader.run(store.lease.read())
    assert record.holder.rollout_id == "v2"
    assert record.holder.instance_id == loader.instance_id

    loader.release()
    assert loader.run(store.lease.read()) is None
    loader.close()


def test_a_live_engine_makes_the_claim_fail():
    store = Store(holder("other"))
    done = threading.Event()
    loader = EngineOwnershipLoader(nats_config(), environ={}, ownership_factory=store)

    def renew_other():
        wait_until(lambda: store.lease is not None)
        while not done.is_set():
            record = loader.run(store.lease.read())
            loader.run(store.lease.update(holder("other"), record.revision))
            time.sleep(0.1)

    renewing = threading.Thread(target=renew_other, daemon=True)
    renewing.start()
    with pytest.raises(EngineAlreadyServing):
        loader.claim()
    done.set()
    renewing.join(timeout=2)
    loader.close()


def test_fencing_and_restoring_run_the_engine_callbacks_in_a_thread():
    store = Store(flaky=True)
    events: list[str] = []
    loader = EngineOwnershipLoader(nats_config(), environ={}, ownership_factory=store)
    assert loader.claim() is Claim.SERVING
    loader.keep(
        on_fenced=lambda: events.append(f"fenced:{threading.current_thread().name}"),
        on_restored=lambda: events.append("restored"),
    )

    store.lease.failing = True
    wait_until(lambda: len(events) == 1)
    assert events[0].startswith("fenced:")
    assert loader.loop_thread_name not in events[0]

    store.lease.failing = False
    wait_until(lambda: events[-1] == "restored")
    loader.release()
    loader.close()


def test_losing_the_lease_stops_the_process():
    store = Store()
    lost = threading.Event()
    loader = EngineOwnershipLoader(
        nats_config(), environ={}, ownership_factory=store, on_lost=lost.set
    )
    assert loader.claim() is Claim.SERVING
    loader.keep(on_fenced=lambda: None, on_restored=lambda: None)

    record = loader.run(store.lease.read())
    loader.run(store.lease.update(holder("thief"), record.revision))

    assert lost.wait(timeout=3)
    assert store.ownership.state is OwnershipState.LOST
    loader.close()


def test_a_standby_serves_once_the_engine_hands_over():
    store = Store(holder("old", "v1"))
    served = threading.Event()
    loader = EngineOwnershipLoader(
        nats_config(), environ={"ABI_ROLLOUT_ID": "v2"}, ownership_factory=store
    )
    assert loader.claim() is Claim.STANDBY

    loader.take_over_in_background(
        served.set, on_fenced=lambda: None, on_restored=lambda: None
    )
    time.sleep(0.2)
    assert not served.is_set()

    record = loader.run(store.lease.read())
    loader.run(store.lease.delete(record.revision))

    assert served.wait(timeout=2)
    wait_until(lambda: store.ownership.state is OwnershipState.SERVING)
    first = loader.run(store.lease.read()).revision
    wait_until(lambda: loader.run(store.lease.read()).revision > first)  # renewing
    loader.release()
    loader.close()


def test_a_standby_that_times_out_stops_the_process():
    store = Store(holder("old", "v1"))
    lost, served = threading.Event(), threading.Event()
    loader = EngineOwnershipLoader(
        nats_config(standby_timeout_seconds=0.3),
        environ={"ABI_ROLLOUT_ID": "v2"},
        ownership_factory=store,
        on_lost=lost.set,
    )
    assert loader.claim() is Claim.STANDBY

    def renew_old():
        while not lost.is_set():
            record = loader.run(store.lease.read())
            loader.run(store.lease.update(holder("old", "v1"), record.revision))
            time.sleep(0.1)

    threading.Thread(target=renew_old, daemon=True).start()
    loader.take_over_in_background(
        served.set, on_fenced=lambda: None, on_restored=lambda: None
    )

    assert lost.wait(timeout=3)
    assert not served.is_set()
    loader.close()


def test_releasing_a_standby_stops_its_wait():
    store = Store(holder("old", "v1"))
    served, lost = threading.Event(), threading.Event()
    loader = EngineOwnershipLoader(
        nats_config(),
        environ={"ABI_ROLLOUT_ID": "v2"},
        ownership_factory=store,
        on_lost=lost.set,
    )
    assert loader.claim() is Claim.STANDBY
    waiting = loader.take_over_in_background(
        served.set, on_fenced=lambda: None, on_restored=lambda: None
    )

    loader.release()
    waiting.join(timeout=2)

    assert not waiting.is_alive()
    assert not served.is_set()
    assert not lost.is_set()
    assert loader.run(store.lease.read()).holder == holder("old", "v1")
    loader.close()


def test_an_auto_engine_serves_when_no_engine_does():
    store = Store()
    loader = EngineOwnershipLoader(
        nats_config(role="auto"), environ={}, ownership_factory=store
    )

    assert loader.claim() is Claim.SERVING
    loader.release()
    loader.close()


def test_an_auto_engine_is_a_client_next_to_a_live_engine():
    store = Store(holder("api"))
    done = threading.Event()
    loader = EngineOwnershipLoader(
        nats_config(role="auto"),
        environ={"ABI_ROLLOUT_ID": "v9"},
        ownership_factory=store,
    )

    def renew_api():
        wait_until(lambda: store.lease is not None)
        while not done.is_set():
            record = loader.run(store.lease.read())
            loader.run(store.lease.update(holder("api"), record.revision))
            time.sleep(0.1)

    renewing = threading.Thread(target=renew_api, daemon=True)
    renewing.start()
    assert loader.claim() is None  # never a standby, even with a rollout id
    done.set()
    renewing.join(timeout=2)
    assert loader.run(store.lease.read()).holder == holder("api")
    loader.close()


LOCAL = {"document": "SQLite at storage/documents.sqlite"}


def test_a_rollout_with_local_backends_fails_before_touching_the_lease():
    store = Store()
    loader = EngineOwnershipLoader(
        nats_config(),
        environ={"ABI_ROLLOUT_ID": "v2"},
        ownership_factory=store,
        local_backends=LOCAL,
    )

    with pytest.raises(LocalBackendsCannotHandOver):
        loader.claim()
    assert store.ownership is None
    loader.close()


@pytest.mark.parametrize(
    "environ",
    [{}, {"ABI_ENGINE_ROLE": "auto", "ABI_ROLLOUT_ID": "v2"}],
    ids=["no rollout", "auto"],
)
def test_local_backends_are_fine_without_a_handover(environ):
    loader = EngineOwnershipLoader(
        nats_config(), environ=environ, ownership_factory=Store(), local_backends=LOCAL
    )

    assert loader.claim() is Claim.SERVING
    loader.close()
