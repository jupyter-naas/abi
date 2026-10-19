"""The cache service passes the authorization contract (RFC §6.4, "cache")."""

from __future__ import annotations

from typing import cast

from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.proto.cache.v1 import cache_pb2
from naas_abi_core.services.cache.adapters.cache_nats_contract import SUBJECT_PREFIX
from naas_abi_core.services.cache.adapters.primary.cache__primary_adapter__NATS import (
    CachePrimaryAdapterNATS,
)
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)
from naas_abi_core.services.cache.adapters.secondary.CacheSecondaryAdapterNATSClient import (
    CacheSecondaryAdapterNATSClient,
    _raise_for_error,
)
from naas_abi_core.services.cache.CachePort import CacheNotFoundError
from naas_abi_core.services.cache.CacheService import CacheService
from naas_abi_core.services.cache.iam_catalog import CATALOG
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    NOT_FOUND,
    SECRET,
    Case,
    DataServiceContract,
    ok,
)


def _describe(cache: CacheService):
    """``cache:Describe``: in process the view's check, over NATS the endpoint."""
    if cache.services_wired:
        return cache.cold.require_describe()
    client = cast(CacheSecondaryAdapterNATSClient, cache.cold.adapter)
    response = client._call(
        f"{SUBJECT_PREFIX}.describe",
        cache_pb2.DescribeRequest(context=client._context()),
        cache_pb2.DescribeResponse,
    )
    if response.HasField("error"):
        _raise_for_error(response.error)
    return None


class TestCacheAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return CacheService([("cold", CacheFSAdapter(str(tmp_path / "cache")))])

    def seed(self, owner):
        for key in ("shared:a", "shared:b", "frozen:f", "private:p"):
            owner.set_text(key, f"value of {key}")

    def build_primary(self, owner):
        return CachePrimaryAdapterNATS(owner.cold, SECRET, tiers=owner.tier_names)

    def build_remote(self, url, identity):
        return CacheService(
            [("cold", CacheSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity)))]
        )

    def close_remote(self, remote):
        for _, adapter in remote.adapters:
            adapter.close()

    def granted_resources(self):
        return ["abi:-:-:cache:key/shared%3A*"]

    def denied_resources(self):
        return ["abi:-:-:cache:key/private%3A*"]

    def read_only_resources(self):
        return ["abi:-:-:cache:key/frozen%3A*"]

    def outcome_of(self, exc):
        return NOT_FOUND if isinstance(exc, CacheNotFoundError) else None

    def cases(self):
        def page(listed):
            return list(listed.keys), listed.next_after

        return [
            Case(
                "get a granted key",
                lambda c: c.get("shared:a"),
                nobody=HIDDEN,
                granted=ok("value of shared:a"),
                denied=ok("value of shared:a"),
            ),
            Case(
                "get a denied key",
                lambda c: c.get("private:p"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "exists on a denied key",
                lambda c: c.exists("private:p"),
                nobody=ok(False),
                granted=ok(False),
                denied=ok(False),
            ),
            Case(
                "list the cold tier",
                lambda c: c.cold.list_keys(),
                nobody=ok(([], None)),
                granted=ok((["shared:a", "shared:b"], None)),
                denied=ok((["frozen:f", "shared:a", "shared:b"], None)),
                view=page,
            ),
            Case(
                "list a page of the cold tier",
                lambda c: c.cold.list_keys(limit=1),
                nobody=ok(([], None)),
                granted=ok((["shared:a"], "shared:a")),
                denied=ok((["frozen:f"], "frozen:f")),
                view=page,
            ),
            Case(
                "set a read-only key",
                lambda c: c.set_text("frozen:f", "changed"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "delete a denied key from the cold tier",
                lambda c: c.cold.delete("private:p"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "set if absent on a granted key",
                lambda c: c.cold.set_json_if_absent("shared:new", {"n": 1}),
                nobody=HIDDEN,
                granted=ok(True),
                denied=ok(True),
            ),
            Case(
                "describe the service",
                _describe,
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=ANY_OK,
            ),
        ]


def test_the_decorator_computes_for_a_caller_who_may_not_use_the_cache(tmp_path):
    """A caller allowed to write but not read a key, or to read but not write
    it, still gets its result: computed, and cached only when it may."""
    from loguru import logger
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
    )
    from naas_abi_core.engine.IEngine import IEngine
    from naas_abi_core.services.cache.CachePort import DataType
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
        IAMStoreMemory,
    )
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.IAMService import IAMService
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with internal_call():
        iam.register_catalog(CATALOG)
        for name, actions in (("writer", ["cache:Set"]), ("reader", ["cache:Get"])):
            account = iam.create_service_account(name)
            policy = iam.create_policy(
                name, document(statement("Allow", actions, ["abi:-:-:cache:key/*"]))
            )
            iam.attach_policy(policy.id, account.id)
    cache = CacheService([("cold", CacheFSAdapter(str(tmp_path / "cache")))])
    cache.set_services(IEngine.Services(iam=iam))
    calls: list[str] = []

    @cache(lambda x: f"square:{x}", DataType.TEXT)
    def square(x: str) -> str:
        calls.append(x)
        return str(int(x) ** 2)

    warnings: list[str] = []
    sink = logger.add(lambda m: warnings.append(str(m)), level="WARNING")
    try:
        with use_call_context(CallContext(principal=service_account("writer"))):
            assert square("3") == "9"  # Get denied: computed, not read
        with use_call_context(CallContext(principal=service_account("reader"))):
            assert square("4") == "16"  # Set denied: computed, not cached
    finally:
        logger.remove(sink)
    assert calls == ["3", "4"]
    assert any("square:3" in w for w in warnings)
    assert any("square:4" in w for w in warnings)
    assert not any("%r" in w for w in warnings)
