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
