"""Object storage passes the authorization contract (RFC §6.4, "object_storage")."""

from __future__ import annotations

import io

import pytest
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    NOT_FOUND,
    SECRET,
    Case,
    DataServiceContract,
    Expect,
    ok,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_core.services.object_storage.iam_catalog import CATALOG
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

INVALID = "invalid_path"
BADPATH = Expect(INVALID)


def _read_stream(storage, prefix, key):
    with storage.get_object_stream(prefix, key) as stream:
        return stream.read()


class TestObjectStorageAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))

    def seed(self, owner):
        owner.put_object("workspaces/ws-1", "q3 report.pdf", b"report")
        owner.put_object("workspaces/ws-1", "notes.txt", b"notes")
        owner.put_object("workspaces/ws-2", "secret.txt", b"secret")
        owner.put_object("frozen", "f.txt", b"frozen")
        # Another object, which only the raw ``storage/`` path reaches: the
        # service strips that prefix, so IAM never names it.
        owner.adapter.put_object(
            "storage/workspaces/ws-1", "notes.txt", b"the object behind storage/"
        )

    def build_primary(self, owner):
        return ObjectStoragePrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return ObjectStorageService(
            ObjectStorageSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))
        )

    def close_remote(self, remote):
        remote.adapter.close()

    def granted_resources(self):
        return ["abi:-:-:object_storage:object/workspaces/ws-1/*"]

    def denied_resources(self):
        return ["abi:-:-:object_storage:object/workspaces/ws-2/*"]

    def read_only_resources(self):
        return ["abi:-:-:object_storage:object/frozen/*"]

    def outcome_of(self, exc):
        if isinstance(exc, Exceptions.InvalidObjectPath):
            return INVALID
        return NOT_FOUND if isinstance(exc, Exceptions.ObjectNotFound) else None

    def cases(self):
        return [*self.path_cases(), *self.object_cases()]

    @staticmethod
    def path_cases():
        """Names IAM would match under ``ws-1/*`` that a backend opens elsewhere
        (``../ws-2/secret.txt``) or outside the storage (``/abs``): refused for
        everyone, before any check, on every operation."""
        escapes = [
            ("workspaces/ws-1", "../ws-2/secret.txt"),
            ("workspaces/ws-1", "a/../../ws-2/secret.txt"),
            ("workspaces/ws-1", "/abs/secret.txt"),
            ("workspaces/ws-1", "a//b"),
            ("workspaces/ws-1/../ws-2", "secret.txt"),
            ("workspaces//ws-1", "notes.txt"),
            ("/workspaces/ws-1", "notes.txt"),
            ("workspaces/ws-1", "./notes.txt"),
        ]
        cases = []
        for prefix, key in escapes:
            label = f"{prefix!r} + {key!r}"
            operations = {
                "get": lambda s, p=prefix, k=key: s.get_object(p, k),
                "put": lambda s, p=prefix, k=key: s.put_object(p, k, b"x"),
                "delete": lambda s, p=prefix, k=key: s.delete_object(p, k),
                "metadata": lambda s, p=prefix, k=key: s.get_object_metadata(p, k),
                "stream": lambda s, p=prefix, k=key: _read_stream(s, p, k),
            }
            for name, call in operations.items():
                cases.append(
                    Case(
                        f"{name} {label}",
                        call,
                        nobody=BADPATH,
                        granted=BADPATH,
                        denied=BADPATH,
                    )
                )
        for prefix in (
            "../ws-2",
            "workspaces/ws-1/../ws-2",
            "workspaces//ws-1",
            "/abs",
        ):
            for name, call in (
                ("list", lambda s, p=prefix: s.list_objects(p)),
                ("list recursively", lambda s, p=prefix: s.list_objects_recursive(p)),
            ):
                cases.append(
                    Case(
                        f"{name} {prefix!r}",
                        call,
                        nobody=BADPATH,
                        granted=BADPATH,
                        denied=BADPATH,
                    )
                )
        return cases

    def object_cases(self):
        return [
            Case(
                "get a granted object",
                lambda s: s.get_object("workspaces/ws-1", "q3 report.pdf"),
                nobody=HIDDEN,
                granted=ok(b"report"),
                denied=ok(b"report"),
            ),
            Case(
                "stream a granted object",
                lambda s: _read_stream(s, "workspaces/ws-1", "notes.txt"),
                nobody=HIDDEN,
                granted=ok(b"notes"),
                denied=ok(b"notes"),
            ),
            Case(
                "stream a denied object",
                lambda s: _read_stream(s, "workspaces/ws-2", "secret.txt"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                # IAM checks ``workspaces/ws-1/notes.txt``: that object's
                # metadata is what comes back, not the one at the raw path.
                "metadata through the storage/ prefix",
                lambda s: s.get_object_metadata("storage/workspaces/ws-1", "notes.txt"),
                nobody=HIDDEN,
                granted=ok(5),
                denied=ok(5),
                view=lambda metadata: metadata.file_size_bytes,
            ),
            Case(
                "metadata of a denied object",
                lambda s: s.get_object_metadata("workspaces/ws-2", "secret.txt"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "list a granted prefix",
                lambda s: s.list_objects("workspaces/ws-1"),
                nobody=HIDDEN,
                granted=ok(
                    ["workspaces/ws-1/notes.txt", "workspaces/ws-1/q3 report.pdf"]
                ),
                denied=ok(
                    ["workspaces/ws-1/notes.txt", "workspaces/ws-1/q3 report.pdf"]
                ),
                view=sorted,
            ),
            Case(
                "list the folder above a granted prefix",
                lambda s: s.list_objects("workspaces"),
                nobody=HIDDEN,
                granted=ok(["workspaces/ws-1"]),
                # Its Deny (ws-2/*) hides everything inside, so the folder too.
                denied=ok(["workspaces/ws-1"]),
                view=sorted,
            ),
            Case(
                "list every object, recursively",
                lambda s: s.list_objects_recursive(""),
                nobody=HIDDEN,
                granted=ok(
                    ["workspaces/ws-1/notes.txt", "workspaces/ws-1/q3 report.pdf"]
                ),
                denied=ok(
                    [
                        "frozen/f.txt",
                        "storage/workspaces/ws-1/notes.txt",
                        "workspaces/ws-1/notes.txt",
                        "workspaces/ws-1/q3 report.pdf",
                    ]
                ),
                view=sorted,
            ),
            Case(
                "put into a read-only prefix",
                lambda s: s.put_object("frozen", "f.txt", b"changed"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "stream into a read-only prefix",
                lambda s: s.put_object_stream("frozen", "g.txt", io.BytesIO(b"g")),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "delete a denied object",
                lambda s: s.delete_object("workspaces/ws-2", "secret.txt"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
            Case(
                "put a granted object",
                lambda s: s.put_object("workspaces/ws-1", "new.txt", b"n"),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
        ]


def test_a_listing_hides_what_a_deny_names_and_a_folder_a_deny_empties(tmp_path):
    """Allowed everything but a file and a folder's contents: neither name is
    listed, though a name inside each would pass the folder probe."""
    from naas_abi_core.engine.call_context import use_call_context
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.tests.data_service_contract import caller
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    contract = TestObjectStorageAuthorization()
    owner, iam = contract._owner(tmp_path)
    with internal_call():
        iam.create_service_account("narrow")
        policy = iam.create_policy(
            "narrow",
            document(
                statement("Allow", ["object_storage:*"], ["*"]),
                statement(
                    "Deny",
                    ["object_storage:*"],
                    [
                        "abi:-:-:object_storage:object/workspaces/ws-1/notes.txt",
                        "abi:-:-:object_storage:object/workspaces/ws-2/*",
                    ],
                ),
            ),
        )
        iam.attach_policy(policy.id, contract._id(iam, "narrow"))
    with use_call_context(caller("narrow")):
        assert owner.list_objects("workspaces/ws-1") == [
            "workspaces/ws-1/q3 report.pdf"
        ]
        assert owner.list_objects("workspaces") == ["workspaces/ws-1"]


def _granted(iam, contract, name, *statements):
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.tests.iam_harness import document

    with internal_call():
        iam.create_service_account(name)
        policy = iam.create_policy(name, document(*statements))
        iam.attach_policy(policy.id, contract._id(iam, name))


def test_a_file_named_like_a_denied_folder_is_still_listed(tmp_path):
    """The ``<entry>/*`` Deny probe hides folders only: ``a/report`` is a
    file the caller may list, whatever ``a/report/*`` denies."""
    from naas_abi_core.engine.call_context import use_call_context
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.tests.data_service_contract import caller
    from naas_abi_core.services.iam.tests.iam_harness import statement

    contract = TestObjectStorageAuthorization()
    owner, iam = contract._owner(tmp_path)
    with internal_call():
        owner.put_object("a", "report", b"r")
        owner.put_object("a/reports", "q.txt", b"q")
    _granted(
        iam,
        contract,
        "reader",
        statement("Allow", ["object_storage:*"], ["abi:-:-:object_storage:object/a/*"]),
        statement(
            "Deny",
            ["object_storage:*"],
            [
                "abi:-:-:object_storage:object/a/report/*",
                "abi:-:-:object_storage:object/a/reports/*",
            ],
        ),
    )
    with use_call_context(caller("reader")):
        assert owner.list_objects("a") == ["a/report"]


def test_a_suspended_user_sees_no_folder_at_once(tmp_path):
    """Suspension takes effect immediately (#44): no folder above the user's
    prefixes, through a broad actor."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.services.iam.enforcement import internal_call
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    contract = TestObjectStorageAuthorization()
    owner, iam = contract._owner(tmp_path)
    with internal_call():
        bob = iam.ensure_user("https://idp.example", "bob")
        policy = iam.create_policy(
            "ws-1",
            document(
                statement(
                    "Allow",
                    ["object_storage:*"],
                    ["abi:-:-:object_storage:object/workspaces/ws-1/*"],
                )
            ),
        )
        iam.attach_policy(policy.id, bob.id)
    as_bob = CallContext(principal=service_account("api"), on_behalf_of=user(bob.id))
    with use_call_context(as_bob):
        assert owner.list_objects("workspaces") == ["workspaces/ws-1"]
    with internal_call():
        iam.suspend_principal(bob.id)
    with use_call_context(as_bob), pytest.raises(Exceptions.ObjectNotFound):
        owner.list_objects("workspaces")
