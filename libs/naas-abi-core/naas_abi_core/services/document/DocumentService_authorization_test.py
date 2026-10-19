"""The document service passes the authorization contract (RFC §6.4, "document").

The built-in IdP's namespace is sealed to it: neither ``api`` nor ``engine``,
both allowed everything else, can read it, in process or over NATS.
"""

from __future__ import annotations

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    service_account,
    use_call_context,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient import (
    DocumentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    DocumentNotFound,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.document.iam_catalog import CATALOG
from naas_abi_core.services.iam.enforcement import internal_call
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

NAMESPACES = ("shared", "private", "frozen")


def _seed(root: DocumentService) -> None:
    for namespace in NAMESPACES:
        documents = root.for_namespace(namespace)
        documents.ensure_collection(CollectionSpec(name="c"))
        documents.put("c", "1", {"owner": namespace})
    with internal_call("idp"):  # sealed to the built-in IdP
        idp = root.for_namespace("idp")
        idp.ensure_collection(CollectionSpec(name="users"))
        idp.put("users", "bob", {"email": "bob@example.com"})


def _ns(documents: DocumentService, namespace: str) -> DocumentService:
    return documents.for_namespace(namespace)


class TestDocumentAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        return DocumentService._for_engine(
            DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        )

    def seed(self, owner):
        _seed(owner)

    def build_primary(self, owner):
        return DocumentPrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return DocumentService._for_engine(
            DocumentSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    @staticmethod
    def _namespace(namespace: str) -> list[str]:
        return [
            f"abi:-:-:document:namespace/{namespace}",
            f"abi:-:-:document:collection/{namespace}/*",
            f"abi:-:-:document:document/{namespace}/*",
        ]

    def granted_resources(self):
        return self._namespace("shared")

    def denied_resources(self):
        return self._namespace("private")

    def read_only_resources(self):
        return self._namespace("frozen")

    def outcome_of(self, exc):
        if isinstance(exc, (DocumentNotFound, CollectionNotFound)):
            return NOT_FOUND
        return None

    def cases(self):
        return [
            Case(
                "list namespaces",
                lambda d: d.namespaces(),
                nobody=ok([]),
                granted=ok(["shared"]),
                denied=ok(["frozen", "shared"]),
                view=sorted,
            ),
            Case(
                "list a granted namespace's collections",
                lambda d: _ns(d, "shared").collections(),
                nobody=ok([]),
                granted=ok(["c"]),
                denied=ok(["c"]),
            ),
            Case(
                "list a denied namespace's collections",
                lambda d: _ns(d, "private").collections(),
                nobody=ok([]),
                granted=ok([]),
                denied=ok([]),
            ),
            Case(
                "get a granted document",
                lambda d: _ns(d, "shared").get("c", "1"),
                nobody=HIDDEN,
                granted=ok({"owner": "shared"}),
                denied=ok({"owner": "shared"}),
                view=lambda document: document.data,
            ),
            Case(
                "get a sealed document",
                lambda d: _ns(d, "idp").get("users", "bob"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "find in a denied collection",
                lambda d: _ns(d, "private").find("c"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "count a read-only collection",
                lambda d: _ns(d, "frozen").count("c"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=ok(1),
            ),
            Case(
                "put into a read-only collection",
                lambda d: _ns(d, "frozen").put("c", "2", {"n": 2}),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "administer a read-only namespace",
                lambda d: _ns(d, "frozen").ensure_collection(CollectionSpec(name="x")),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "delete a denied document",
                lambda d: _ns(d, "private").delete("c", "1"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "put a granted document",
                lambda d: _ns(d, "shared").put("c", "2", {"n": 2}),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]


@pytest.mark.parametrize("identity", ["api", "engine"])
def test_api_and_engine_cannot_read_a_namespace_private_to_another_principal(
    tmp_path, identity
):
    contract = TestDocumentAuthorization()
    root, _ = contract._owner(tmp_path)
    with use_call_context(CallContext(principal=service_account(identity))):
        assert "idp" not in root.namespaces()
        idp = root.for_namespace("idp")
        assert idp.collections() == []
        with pytest.raises(DocumentNotFound):
            idp.get("users", "bob")
        with pytest.raises(CollectionNotFound):
            idp.find("users")
        with pytest.raises(DocumentNotFound):
            idp.put("users", "eve", {"email": "eve@example.com"})
    # Its owner reads it.
    with use_call_context(CallContext(principal=service_account("idp"))):
        assert root.for_namespace("idp").get("users", "bob").data == {
            "email": "bob@example.com"
        }


def test_a_module_reaches_its_own_namespace_not_another_modules(tmp_path):
    """A remote module's account, once its manifest is approved, holds its own
    namespace only (``${module.id}``). It cannot list, read or drop another
    module's."""
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    contract = TestDocumentAuthorization()
    root, iam = contract._owner(tmp_path)
    name = "module/acme/people"
    with internal_call():
        account = iam.create_service_account(name)
        for namespace in ("people", "billing"):
            root.for_namespace(namespace).ensure_collection(
                CollectionSpec(name="records")
            )
            root.for_namespace(namespace).put("records", "1", {"n": 1})
    module = CallContext(
        principal=Principal(id=account.id, kind="service_account", name=name)
    )
    with use_call_context(module):
        iam.submit_manifest(
            "people",
            "acme",
            document(
                statement(
                    "Allow",
                    ["document:*"],
                    [
                        "abi:-:-:document:namespace/${module.id}",
                        "abi:-:-:document:collection/${module.id}/*",
                        "abi:-:-:document:document/${module.id}/*",
                    ],
                )
            ),
        )
    with internal_call():
        iam.approve_manifest(account.id)
    with use_call_context(module):
        assert root.namespaces() == ["people"]
        assert root.for_namespace("people").get("records", "1").data == {"n": 1}
        billing = root.for_namespace("billing")
        assert billing.collections() == []
        with pytest.raises(DocumentNotFound):
            billing.get("records", "1")
        with pytest.raises(CollectionNotFound):
            billing.drop_collection("records")


def test_the_idp_module_account_owns_the_idp_namespace_and_no_manifest_opens_it(
    tmp_path,
):
    """The built-in IdP runs as ``module/<project>/idp``. Its namespace is its
    own through the seal and its approved manifest; another module (or
    ``api``, or ``engine``) cannot reach it, even with a manifest that grants
    every document action everywhere."""
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    contract = TestDocumentAuthorization()
    root, iam = contract._owner(tmp_path)
    everything = document(statement("Allow", ["document:*"], ["abi:*:*:document:*"]))
    contexts = {}
    with internal_call():
        for name in ("module/default/idp", "module/default/greedy"):
            account = iam.create_service_account(name)
            contexts[name] = CallContext(
                principal=Principal(id=account.id, kind="service_account", name=name)
            )
    for name, context in contexts.items():
        with use_call_context(context):
            # The IdP's own manifest is the default one; the other asks for the world.
            iam.submit_manifest(
                name.rsplit("/", 1)[1],
                "default",
                everything
                if name.endswith("greedy")
                else document(
                    statement(
                        "Allow",
                        ["document:*"],
                        [
                            "abi:-:-:document:namespace/${module.id}",
                            "abi:-:-:document:collection/${module.id}/*",
                            "abi:-:-:document:document/${module.id}/*",
                        ],
                    )
                ),
            )
    with internal_call():
        for context in contexts.values():
            iam.approve_manifest(context.principal.id)
    with use_call_context(contexts["module/default/idp"]):
        assert root.for_namespace("idp").get("users", "bob").data == {
            "email": "bob@example.com"
        }
    with use_call_context(contexts["module/default/greedy"]):
        idp = root.for_namespace("idp")
        assert idp.collections() == []
        with pytest.raises(DocumentNotFound):
            idp.get("users", "bob")
        with pytest.raises(DocumentNotFound):
            idp.put("users", "eve", {"email": "eve@example.com"})
