"""The secret service passes the authorization contract."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.iam.enforcement import internal_call
from naas_abi_core.services.iam.tests.data_service_contract import (
    ANY_OK,
    DENY,
    HIDDEN,
    SECRET,
    Case,
    DataServiceContract,
    Expect,
    ok,
)
from naas_abi_core.services.secret.adaptors.primary.secret__primary_adapter__NATS import (
    SecretPrimaryAdapterNATS,
)
from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
    SecretSecondaryAdapterNATSClient,
)
from naas_abi_core.services.secret.iam_catalog import CATALOG
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import InvalidSecretKey, ISecretAdapter


class MemorySecrets(ISecretAdapter):
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def list(self):
        return dict(self.values)


def _keys(listed: dict) -> list[tuple[str, str | None]]:
    return sorted(listed.items())


@pytest.fixture
def iam_layer_only(monkeypatch):
    """The endpoint's allowlist (``may_use``: a caller reaches only the names
    under its own prefix) is a layer before IAM, tested with the endpoint. The
    contract checks the other one: the per-key IAM check, whatever the key."""
    from naas_abi_core.services.secret.adaptors.primary import (
        secret__primary_adapter__NATS as primary,
    )

    monkeypatch.setattr(primary, "_may_use", lambda _key: True)


@pytest.mark.usefixtures("iam_layer_only")
class TestSecretAuthorization(DataServiceContract):
    catalog = CATALOG

    def build_owner(self, tmp_path):
        return Secret([MemorySecrets()])

    def seed(self, owner):
        for key in ("shared/a", "frozen/f", "private/p", "iam/k"):
            owner.set(key, f"value of {key}")
        with internal_call("idp"):  # sealed to the built-in IdP
            owner.set("idp/signing", "value of idp/signing")

    def build_primary(self, owner):
        return SecretPrimaryAdapterNATS(owner, SECRET)

    def build_remote(self, url, identity):
        return Secret(
            [SecretSecondaryAdapterNATSClient(url, TEST_TOKENS.source(identity))]
        )

    def close_remote(self, remote):
        for adapter in remote.adapters:
            adapter.close()

    def granted_resources(self):
        return ["abi:-:-:secret:secret/shared%2F*"]

    def denied_resources(self):
        return ["abi:-:-:secret:secret/private%2F*"]

    def read_only_resources(self):
        return ["abi:-:-:secret:secret/frozen%2F*"]

    def outcome_of(self, exc):
        return "invalid" if isinstance(exc, InvalidSecretKey) else None

    def cases(self):
        return [*self.hostile_key_cases(), *self.key_cases()]

    @staticmethod
    def hostile_key_cases():
        """A key the granted pattern (``shared/*``) would match, but that is
        written to a ``.env`` as more than one line or is no name: refused
        before the check, for everyone."""
        invalid = Expect("invalid")
        keys = [
            "shared/x\nINJECTED=1",
            "shared/x\r\nINJECTED=1",
            "shared/x=1",
            "shared/x y",
            "shared/#x",
            "",
        ]
        cases = []
        for number, key in enumerate(keys):
            for name, call in (
                ("set", lambda s, k=key: s.set(k, "v")),
                ("remove", lambda s, k=key: s.remove(k)),
            ):
                cases.append(
                    Case(
                        f"{name}, hostile key {number}",
                        call,
                        nobody=invalid,
                        granted=invalid,
                        denied=invalid,
                    )
                )
            # Reading one is reading nothing: no such key can exist.
            cases.append(
                Case(
                    f"get, hostile key {number}",
                    lambda s, k=key: s.get(k, "default"),
                    nobody=ok("default"),
                    granted=ok("default"),
                    denied=ok("default"),
                )
            )
        return cases

    def key_cases(self):
        absent = ok(None)
        return [
            Case(
                "get a granted key",
                lambda s: s.get("shared/a"),
                nobody=absent,
                granted=ok("value of shared/a"),
                denied=ok("value of shared/a"),
            ),
            Case(
                "get a denied key",
                lambda s: s.get("private/p", "default"),
                nobody=ok("default"),
                granted=ok("default"),
                denied=ok("default"),
            ),
            Case(
                "get a sealed key",
                lambda s: s.get("idp/signing"),
                nobody=absent,
                granted=absent,
                denied=absent,
            ),
            Case(
                "set a granted key",
                lambda s: s.set("shared/b", "b"),
                nobody=HIDDEN,
                granted=ANY_OK,
                denied=ANY_OK,
            ),
            Case(
                "list",
                lambda s: s.list(),
                nobody=ok([]),
                granted=ok([("shared/a", "value of shared/a"), ("shared/b", "b")]),
                # iam/ and idp/ are sealed
                denied=ok(
                    [
                        ("frozen/f", "value of frozen/f"),
                        ("shared/a", "value of shared/a"),
                        ("shared/b", "b"),
                    ]
                ),
                view=_keys,
            ),
            Case(
                "set a read-only key",
                lambda s: s.set("frozen/f", "changed"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=DENY,
            ),
            Case(
                "remove a denied key",
                lambda s: s.remove("private/p"),
                nobody=HIDDEN,
                granted=HIDDEN,
                denied=HIDDEN,
            ),
        ]


def test_a_dotenv_secret_is_one_line_per_key(tmp_path):
    """The adapter refuses a key that would write a second line."""
    import pytest
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        DotenvSecretSecondaryAdaptor,
    )

    path = tmp_path / ".env"
    path.write_text("A=1\n")
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    for key in ("x\nINJECTED=1", "x y", "x=1", ""):
        with pytest.raises(InvalidSecretKey):
            adapter.set(key, "v")
        with pytest.raises(InvalidSecretKey):
            adapter.remove(key)
    assert path.read_text() == "A=1\n"
    adapter.set("shared/ok", "v")
    assert "shared/ok" in path.read_text()
