import importlib
import json

import pytest
from click.testing import CliRunner
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
    IAMStoreMemory,
)
from naas_abi_core.services.iam.IAMPorts import KeyRefusedError
from naas_abi_core.services.iam.IAMService import IAMService

from naas_abi_cli.cli.iam import iam, provision_dev_modules

MANIFEST = {
    "version": "2026-10-13",
    "statements": [{"effect": "Allow", "actions": ["document:*"], "resources": ["*"]}],
}


class Unclosable(IAMService):
    def close(self) -> None:  # the store outlives each command in these tests
        pass


@pytest.fixture
def service():
    found = Unclosable(IAMStoreMemory())
    found.bootstrap()
    return found


@pytest.fixture
def cli(service):
    notified = []

    def invoke(*args):
        result = CliRunner().invoke(
            iam,
            list(args),
            obj={"iam_opener": lambda: (service, lambda: notified.append(True))},
            catch_exceptions=False,
        )
        result.notified = list(notified)
        notified.clear()
        return result

    return invoke


def key_in(result) -> str:
    return next(
        line for line in result.stdout.splitlines() if line.startswith("abi_sk_")
    )


def submit(service, name="module/acme/people", document=MANIFEST):
    record = service.store.find_service_account(name)
    with use_call_context(
        CallContext(principal=Principal(record.id, "service_account", name))
    ):
        return service.submit_manifest(name.split("/")[2], name.split("/")[1], document)


def test_service_accounts_are_created_listed_and_deleted(cli, service):
    created = cli("service-account", "create", "ci/nightly", "--key")
    account_id, name = created.stdout.splitlines()[0].split("\t")
    key = key_in(created)
    assert name == "ci/nightly" and key.startswith("abi_sk_")
    assert created.notified
    assert service.exchange_key(key).name == "ci/nightly"
    listed = cli("service-account", "list").stdout
    assert f"{account_id}\tactive\tci/nightly" in listed
    cli("service-account", "delete", "ci/nightly")
    with pytest.raises(KeyRefusedError):
        service.exchange_key(key)


def test_keys_are_shown_once_listed_rotated_and_revoked(cli, service):
    cli("service-account", "create", "module/acme/people")
    first = cli("key", "create", "module/acme/people", "--description", "prod")
    value = key_in(first)
    key_id = value.split("_")[2]
    listed = cli("key", "list", "module/acme/people").stdout
    assert key_id in listed and "prod" in listed and value not in listed
    rotated = key_in(cli("key", "rotate", "module/acme/people", key_id))
    assert service.exchange_key(rotated)
    with pytest.raises(KeyRefusedError):
        service.exchange_key(value)
    rotated_id = rotated.split("_")[2]
    cli("key", "revoke", "module/acme/people", rotated_id)
    with pytest.raises(KeyRefusedError):
        service.exchange_key(rotated)


def test_a_manifest_is_listed_shown_approved_or_narrowed(cli, service, tmp_path):
    cli("service-account", "create", "module/acme/people")
    submit(service)
    assert (
        "pending\tmodule/acme/people"
        in cli("module", "list", "--status", "pending").stdout
    )
    assert json.loads(cli("module", "show", "module/acme/people").stdout) == MANIFEST
    narrowed = tmp_path / "narrowed.yaml"
    narrowed.write_text(
        "version: 2026-10-13\n"
        "statements:\n"
        "  - effect: Allow\n"
        "    actions: [document:Get]\n"
        "    resources: ['abi:-:-:document:document/people/*']\n"
    )
    approved = cli(
        "module", "approve", "module/acme/people", "--document", str(narrowed)
    )
    assert "approved module/acme/people" in approved.stdout and approved.notified
    policy = service.store.get_policy("module.acme.people")
    assert policy.document.statements[0].actions == ("document:Get",)


def test_a_manifest_is_rejected_with_its_reason(cli, service):
    cli("service-account", "create", "module/acme/people")
    submit(service)
    assert (
        "rejected"
        in cli("module", "reject", "module/acme/people", "--reason", "wide").stdout
    )
    assert submit(service).manifest.reason == "wide"


def test_errors_are_reported_not_raised(service):
    result = CliRunner().invoke(
        iam,
        ["key", "create", "module/acme/missing"],
        obj={"iam_opener": lambda: (service, lambda: None)},
    )
    assert result.exit_code != 0 and "not found" in result.output


def test_dev_up_hands_each_module_a_fresh_key(service):
    with as_service_account("engine"):
        first = provision_dev_modules(service, "acme", {"people": "acme.people"})
        second = provision_dev_modules(service, "acme", {"people": "acme.people"})
    assert service.exchange_key(second["people"]).name == "module/acme/acme.people"
    with pytest.raises(KeyRefusedError):
        service.exchange_key(first["people"])


def test_a_project_missing_other_secrets_still_opens_its_iam(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.delenv("SOME_PROVIDER_KEY", raising=False)
    (tmp_path / ".env").write_text("")
    (tmp_path / "config.yaml").write_text(
        "modules:\n"
        "  - module: some.provider\n"
        "    enabled: true\n"
        "    config:\n"
        '      api_key: "{{ secret.SOME_PROVIDER_KEY }}"\n'
        "services:\n"
        "  iam:\n"
        "    store:\n"
        "      adapter: sqlite\n"
        f"      path: {tmp_path / 'iam.sqlite'}\n"
        "  secret:\n"
        "    secret_adapters:\n"
        "      - adapter: dotenv\n"
        "        config: {}\n"
    )
    from naas_abi_cli.cli.iam import open_project_iam

    service, notify = open_project_iam()
    try:
        service.bootstrap()
        with as_service_account("engine"):
            assert service.store.find_service_account("engine") is not None
        notify()  # no broker login without the secrets: nothing to tell
    finally:
        service.close()


# -- invitations and IdP groups --------------------------------------------------------


class FakeIdentity:
    default_provider = "builtin"

    def __init__(self, provisioning: str = "builtin") -> None:
        self.provisioning = provisioning
        self.provisioned: list[tuple[str, str, str | None]] = []
        self.fail: Exception | None = None

    def list_providers(self):
        from types import SimpleNamespace

        return [SimpleNamespace(name="builtin"), SimpleNamespace(name="okta")]

    def provision_user(self, provider, email, *, name=None):
        from types import SimpleNamespace

        if self.fail is not None:
            raise self.fail
        if self.provisioning == "none":
            raise NotImplementedError(
                f"Users of {provider!r} are managed in the identity provider"
            )
        self.provisioned.append((provider, email, name))
        return SimpleNamespace(email=email, created=True, subject="u_1")


@pytest.fixture
def identity():
    return FakeIdentity()


@pytest.fixture
def engine(service, identity):
    from types import SimpleNamespace

    closed = []
    opened = (
        SimpleNamespace(iam=service, identity=identity),
        lambda: closed.append(True),
    )
    return opened, closed


@pytest.fixture
def run(engine):
    opened, closed = engine

    def invoke(*args):
        result = CliRunner().invoke(
            iam,
            list(args),
            obj={"services_opener": lambda: opened},
            catch_exceptions=False,
        )
        result.closed = bool(closed)
        return result

    return invoke


def test_inviting_keeps_the_roles_and_creates_the_person(run, service, identity):
    result = run(
        "invite",
        "Bob@Example.com",
        "--org",
        "acme",
        "--org-role",
        "member",
        "--workspace",
        "ws1",
        "--role",
        "viewer",
        "--name",
        "Bob",
    )
    assert result.exit_code == 0, result.output
    assert result.closed
    grants = service.store.list_pending_grants()
    assert {(g.provider, g.email, g.policy_id, g.scope) for g in grants} == {
        ("builtin", "bob@example.com", "builtin.member", "abi:acme:-"),
        ("builtin", "bob@example.com", "builtin.viewer", "abi:acme:ws1"),
    }
    assert identity.provisioned == [("builtin", "Bob@Example.com", "Bob")]
    assert "created" in result.output


def test_a_provider_managed_in_the_provider_keeps_the_grants_only(
    run, service, identity
):
    identity.provisioning = "none"
    result = run(
        "invite",
        "bob@example.com",
        "--workspace",
        "ws1",
        "--org",
        "acme",
        "--role",
        "member",
    )
    assert result.exit_code == 0, result.output
    assert len(service.store.list_pending_grants()) == 1
    assert "managed in the identity provider" in result.output


def test_no_provision_keeps_the_grants_only(run, service, identity):
    result = run(
        "invite",
        "bob@example.com",
        "--org",
        "acme",
        "--org-role",
        "admin",
        "--no-provision",
    )
    assert result.exit_code == 0 and identity.provisioned == []
    assert len(service.store.list_pending_grants()) == 1


def test_a_provider_that_fails_takes_the_grants_back(run, service, identity):
    identity.fail = RuntimeError("the provider is down")
    result = CliRunner().invoke(
        iam,
        ["invite", "bob@example.com", "--org", "acme", "--org-role", "member"],
        obj={
            "services_opener": lambda: run.__closure__ and (_opened(service, identity))
        },
    )
    assert result.exit_code != 0
    assert service.store.list_pending_grants() == []


def _opened(service, identity):
    from types import SimpleNamespace

    return SimpleNamespace(iam=service, identity=identity), lambda: None


@pytest.mark.parametrize(
    "args",
    [
        ("invite", "bob@example.com"),
        ("invite", "bob@example.com", "--org-role", "member"),
        ("invite", "bob@example.com", "--role", "member"),
        ("invite", "bob@example.com", "--workspace", "ws1", "--role", "member"),
    ],
)
def test_an_invitation_must_say_where(run, service, args):
    assert run(*args).exit_code != 0
    assert service.store.list_pending_grants() == []


def test_a_workspace_iam_knows_needs_no_org(run, service):
    with as_service_account("engine"):
        service.put_scope("acme", "ws1")
    result = run("invite", "bob@example.com", "--workspace", "ws1", "--role", "member")
    assert result.exit_code == 0, result.output
    assert [g.scope for g in service.store.list_pending_grants()] == ["abi:acme:ws1"]


def test_pending_grants_are_listed_and_revoked(run, service):
    run(
        "invite",
        "bob@example.com",
        "--org",
        "acme",
        "--org-role",
        "member",
        "--no-provision",
    )
    listed = run("invitation", "list", "--email", "BOB@example.com").output.split("\t")
    grant_id = listed[0]
    assert grant_id.startswith("pgr_") and "builtin.member" in listed
    assert run("invitation", "list", "--provider", "okta").output == ""
    assert run("invitation", "revoke", grant_id).exit_code == 0
    assert run("invitation", "revoke", grant_id).exit_code != 0
    assert service.store.list_pending_grants() == []


def test_idp_groups_are_bound_listed_and_unbound(run, service):
    bound = run(
        "group",
        "bind",
        "acme",
        "Data readers",
        "--org",
        "o",
        "--workspace",
        "w",
        "--role",
        "viewer",
    )
    assert bound.exit_code == 0, bound.output
    assert bound.output.split("\t")[:2] == ["acme", "Data readers"]
    assert service.resolve_idp_groups("acme", ["Data readers"])
    assert "abi:o:w" in run("group", "list").output
    assert run("group", "list", "--provider", "other").output == ""
    org_level = run("group", "bind", "acme", "Admins", "--org", "o", "--role", "admin")
    assert "abi:o:-" in org_level.output
    assert (
        run(
            "group",
            "unbind",
            "acme",
            "Data readers",
            "--org",
            "o",
            "--workspace",
            "w",
            "--role",
            "viewer",
        ).exit_code
        == 0
    )
    assert (
        run(
            "group",
            "unbind",
            "acme",
            "Data readers",
            "--org",
            "o",
            "--workspace",
            "w",
            "--role",
            "viewer",
        ).exit_code
        != 0
    )
    assert "Data readers" not in run("group", "list").output


def test_a_failing_provider_takes_back_only_the_grants_this_command_made(
    service, identity
):
    first = CliRunner().invoke(
        iam,
        [
            "invite",
            "bob@example.com",
            "--org",
            "acme",
            "--org-role",
            "member",
            "--no-provision",
        ],
        obj={"services_opener": lambda: _opened(service, identity)},
        catch_exceptions=False,
    )
    assert first.exit_code == 0
    identity.fail = RuntimeError("the provider is down")
    again = CliRunner().invoke(
        iam,
        [
            "invite",
            "bob@example.com",
            "--org",
            "acme",
            "--org-role",
            "member",
            "--workspace",
            "ws1",
            "--role",
            "viewer",
        ],
        obj={"services_opener": lambda: _opened(service, identity)},
    )
    assert again.exit_code != 0
    # The org grant of the earlier invitation stays; the workspace one is gone.
    assert [(g.policy_id, g.scope) for g in service.store.list_pending_grants()] == [
        ("builtin.member", "abi:acme:-")
    ]


def test_a_provider_warning_is_shown(run, identity):
    from types import SimpleNamespace

    identity.provision_user = lambda provider, email, *, name=None: SimpleNamespace(
        email=email, created=True, subject="u", warning="no mail server"
    )
    result = run("invite", "bob@example.com", "--org", "acme", "--org-role", "member")
    assert "warning: no mail server" in result.output


# -- the change notice --------------------------------------------------------------------


def test_the_change_notice_gives_up_when_no_broker_listens(monkeypatch) -> None:
    # The NATS client retries an unreachable server for as long as it is let: a
    # notice with no deadline held `abi dev up` for ever.
    import socket
    import time

    iam_cli = importlib.import_module("naas_abi_cli.cli.iam")

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]  # nothing listens here once it is closed
    monkeypatch.setattr(iam_cli, "NOTIFY_TIMEOUT_SECONDS", 1.0)

    started = time.monotonic()
    iam_cli.notify_engine(f"nats://127.0.0.1:{port}", revision=1)

    assert time.monotonic() - started < 10


def test_a_dev_module_key_tells_the_broker_of_the_dev_run(monkeypatch) -> None:
    # `abi dev up` runs its own broker on another port than the config names.
    from types import SimpleNamespace

    dev = importlib.import_module("naas_abi_cli.cli.dev")

    iam_cli = importlib.import_module("naas_abi_cli.cli.iam")

    told: list[str | None] = []

    def opener(nats_url=None):
        told.append(nats_url)
        service = IAMService(IAMStoreMemory())
        service.bootstrap()
        return service, lambda: None

    monkeypatch.setattr(iam_cli, "open_project_iam", opener)
    overlay = {
        "nats": {
            "nats_url": "nats://engine:pw@127.0.0.1:13136",
            "discovery": {"project": "demo"},
        }
    }

    key = dev._module_key(
        SimpleNamespace(name="research", identity="acme.research"), overlay
    )

    assert key.startswith("abi_sk_")
    assert told == ["nats://engine:pw@127.0.0.1:13136"]
