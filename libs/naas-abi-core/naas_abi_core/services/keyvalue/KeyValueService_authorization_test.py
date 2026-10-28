"""The key-value service passes the authorization contract."""

from __future__ import annotations

from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
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
from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
    KeyValuePrimaryAdapterNATS,
)
from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
    KeyValueSecondaryAdapterNATSClient,
)
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)
from naas_abi_core.services.keyvalue.iam_catalog import CATALOG
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


class TestKeyValueAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return KeyValueService(PythonAdapter())

    def seed(self, owner):
        for index in range(3):
            owner.set(f"shared:{index}", b"s")
        owner.set("frozen:f", b"f")
        owner.set("private:p", b"p")
        owner.set("zzz:other", b"o")

    def build_primary(self, owner):
        return KeyValuePrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return KeyValueService(
            KeyValueSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    def granted_resources(self):
        return ["abi:-:-:keyvalue:key/shared%3A*"]

    def denied_resources(self):
        return ["abi:-:-:keyvalue:key/private%3A*"]

    def read_only_resources(self):
        return ["abi:-:-:keyvalue:key/frozen%3A*"]

    def outcome_of(self, exc):
        return NOT_FOUND if isinstance(exc, KVNotFoundError) else None

    def cases(self):
        def page_keys(page):
            return list(page.keys), page.next_after

        everything = ["frozen:f", "shared:0", "shared:1", "shared:2", "zzz:other"]
        return [
            Case(
                "get a granted key",
                lambda kv: kv.get("shared:0"),
                nobody=HIDDEN,
                granted=ok(b"s"),
                denied=ok(b"s"),
            ),
            Case(
                "get a denied key",
                lambda kv: kv.get("private:p"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "exists on a denied key",
                lambda kv: kv.exists("private:p"),
                nobody=ok(False),
                granted=ok(False),
                denied=ok(False),
            ),
            Case(
                "ttl of a granted key",
                lambda kv: kv.get_ttl("shared:1"),
                nobody=HIDDEN,
                granted=ok(None),
                denied=ok(None),
            ),
            Case(
                "list every key",
                lambda kv: kv.list_keys(),
                nobody=ok(([], None)),
                granted=ok((["shared:0", "shared:1", "shared:2"], None)),
                denied=ok((everything, None)),
                view=page_keys,
            ),
            Case(
                "list a page, paged after filtering",
                lambda kv: kv.list_keys(limit=2),
                nobody=ok(([], None)),
                granted=ok((["shared:0", "shared:1"], "shared:1")),
                denied=ok((["frozen:f", "shared:0"], "shared:0")),
                view=page_keys,
            ),
            Case(
                "list the next page",
                lambda kv: kv.list_keys(limit=2, after="shared:1"),
                nobody=ok(([], None)),
                granted=ok((["shared:2"], None)),
                denied=ok((["shared:2", "zzz:other"], None)),
                view=page_keys,
            ),
            Case(
                "list under a denied prefix",
                lambda kv: kv.list_keys("private:"),
                nobody=ok(([], None)),
                granted=ok(([], None)),
                denied=ok(([], None)),
                view=page_keys,
            ),
            Case(
                "set a read-only key",
                lambda kv: kv.set("frozen:f", b"x"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "compare-and-delete a denied key",
                lambda kv: kv.delete_if_value_matches("private:p", b"p"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "set if absent, then delete, a granted key",
                lambda kv: (
                    kv.set_if_not_exists("shared:new", b"n"),
                    kv.delete("shared:new"),
                ),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]
