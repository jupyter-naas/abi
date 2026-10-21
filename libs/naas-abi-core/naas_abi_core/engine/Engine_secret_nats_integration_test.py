"""The engine's secret service is closed to SDK modules, on a real broker
(docs/adr/20261024_secret-service-closed-to-sdk-modules.md).

The engine holds secrets in its ``.env``, among them ``NATS_JWT_SECRET``, and serves
``abi.svc.secret.v1``. An SDK module, logged in as the broker's ``module`` user, reads,
lists, writes and removes only the names ``nats.secret.modules`` grants its identity; the
engine's own processes keep every secret.
"""

import asyncio
import json

import pytest
from naas_abi_core.engine.nats_auth import module_key
from naas_abi_core.engine.nats_test_server import (
    login,
    native_nats_server,
    nats_server_binary,
)

SECRET = "secret-closed-engine-test-secret-at-least-32-bytes"
PASSWORDS = {"abi": "secret-closed-abi-password", "module": "secret-closed-module-pw"}
GRANTED = "partner"
UNGRANTED = "stranger"
ENGINE_SECRETS = {
    "NATS_JWT_SECRET": SECRET,
    "OPENAI_API_KEY": "sk-engine-provider-key",
    "GITHUB_ACCESS_TOKEN": "ghp_engine_github_token",
    "PARTNER_TOKEN": "partner-own-credential",
    "PARTNER_STATE": "partner-state-v1",
}


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True, users=PASSWORDS) as url:
        yield url


@pytest.fixture
def serving(tmp_path, broker, monkeypatch):
    from naas_abi_core.engine.Engine import Engine

    work = tmp_path / "engine"
    work.mkdir()
    (work / ".env").write_text(
        "".join(f"{name}={value}\n" for name, value in ENGINE_SECRETS.items())
    )
    monkeypatch.chdir(work)
    grants = {
        GRANTED: {
            "read": ["PARTNER_TOKEN", "PARTNER_STATE"],
            "write": ["PARTNER_STATE"],
        }
    }
    config = (
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: []\n"
        "services:\n"
        "  secret: {secret_adapters: [{adapter: dotenv, config: {path: .env}}]}\n"
        f"nats: {{nats_url: '{login(broker, 'abi', PASSWORDS['abi'])}', jwt_secret: {SECRET}, "
        f"secret: {{modules: {json.dumps(grants)}}}}}\n"
    )
    engine = Engine(config)
    engine.load()
    yield work
    engine.shutdown()


def as_module(url, identity, scenario):
    """``scenario(ABIClient)`` as the SDK module ``identity``."""
    from naas_abi_sdk.client import ABIClient
    from naas_abi_sdk.service_token import ModuleToken

    async def run():
        client = ABIClient(
            login(url, "module", PASSWORDS["module"]),
            ModuleToken(identity, module_key(SECRET, identity)),
            timeout=30,
        )
        try:
            return await scenario(client)
        finally:
            await client.close()

    return asyncio.run(run())


def secret_calls(client):
    from naas_abi_proto.secret.v1 import secret_pb2 as pb

    async def get(key):
        response = await client.secret.get(pb.GetRequest(key=key))
        return response.found.value if response.found.HasField("value") else None

    async def names():
        return {
            e.key for e in (await client.secret.list(pb.ListRequest())).found.entries
        }

    async def set_(key, value):
        await client.secret.set(pb.SetRequest(key=key, value=value))

    async def remove(key):
        await client.secret.remove(pb.RemoveRequest(key=key))

    return get, names, set_, remove


def test_a_module_cannot_read_the_engines_secrets(serving, broker):
    async def scenario(client):
        get, names, _, _ = secret_calls(client)
        return (
            [await get(name) for name in ENGINE_SECRETS],
            await get("NO_SUCH_SECRET"),
            await names(),
        )

    values, missing, listed = as_module(broker, UNGRANTED, scenario)

    assert values == [None] * len(ENGINE_SECRETS) and missing is None
    assert listed == set()


def test_a_module_reads_lists_and_writes_only_what_it_was_granted(serving, broker):
    from naas_abi_sdk import RPCError

    async def scenario(client):
        get, names, set_, remove = secret_calls(client)
        seen = {
            "own": await get("PARTNER_TOKEN"),
            "jwt": await get("NATS_JWT_SECRET"),
            "openai": await get("OPENAI_API_KEY"),
            "listed": await names(),
        }
        await set_("PARTNER_STATE", "partner-state-v2")
        refused = {}
        for label, call in {
            "set jwt": lambda: set_("NATS_JWT_SECRET", "overwritten"),
            "set new": lambda: set_("BRAND_NEW", "x"),
            "set read-only grant": lambda: set_("PARTNER_TOKEN", "x"),
            "remove github": lambda: remove("GITHUB_ACCESS_TOKEN"),
            "remove missing": lambda: remove("NO_SUCH_SECRET"),
        }.items():
            try:
                await call()
            except RPCError as exc:
                refused[label] = exc.code
        seen["refused"] = refused
        seen["state"] = await get("PARTNER_STATE")
        return seen

    seen = as_module(broker, GRANTED, scenario)

    assert seen["own"] == ENGINE_SECRETS["PARTNER_TOKEN"]
    assert seen["jwt"] is None and seen["openai"] is None
    assert seen["listed"] == {"PARTNER_TOKEN", "PARTNER_STATE"}
    assert seen["state"] == "partner-state-v2"
    assert seen["refused"] == {
        label: "PERMISSION_DENIED"
        for label in (
            "set jwt",
            "set new",
            "set read-only grant",
            "remove github",
            "remove missing",
        )
    }
    env = (serving / ".env").read_text()
    assert f"NATS_JWT_SECRET={SECRET}" in env
    assert "GITHUB_ACCESS_TOKEN=ghp_engine_github_token" in env
    assert "BRAND_NEW" not in env


def test_a_granted_module_removes_what_it_may_write(serving, broker):
    async def scenario(client):
        get, _, _, remove = secret_calls(client)
        await remove("PARTNER_STATE")
        return await get("PARTNER_STATE")

    assert as_module(broker, GRANTED, scenario) is None
    assert "PARTNER_STATE" not in (serving / ".env").read_text()


def test_one_modules_grant_is_not_anothers(serving, broker):
    async def scenario(client):
        get, names, _, _ = secret_calls(client)
        return await get("PARTNER_TOKEN"), await names()

    assert as_module(broker, UNGRANTED, scenario) == (None, set())


def test_a_module_cannot_pose_as_an_engine_process(serving, broker):
    """It holds a key for its own identity only: a token asserting ``api`` made with
    it is refused, and the module key of a first-party identity cannot be derived."""
    import jwt
    from naas_abi_sdk import RPCError
    from naas_abi_sdk.client import ABIClient

    with pytest.raises(ValueError):
        module_key(SECRET, "api")

    class Forged:
        def __call__(self):
            # signed with the module's own key, but claiming a first-party identity
            return jwt.encode(
                {"sub": "api"},
                module_key(SECRET, GRANTED),
                algorithm="HS256",
                headers={"kid": "module"},
            )

    async def scenario():
        client = ABIClient(
            login(broker, "module", PASSWORDS["module"]), Forged(), timeout=30
        )
        try:
            _, names, _, _ = secret_calls(client)
            return await names()
        finally:
            await client.close()

    with pytest.raises(RPCError) as refused:
        asyncio.run(scenario())
    assert refused.value.code == "UNAUTHENTICATED"


def test_the_engines_own_processes_keep_every_secret(serving, broker):
    from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
        SecretSecondaryAdapterNATSClient,
    )

    for identity in ("api", "engine", "dagster"):
        client = SecretSecondaryAdapterNATSClient(
            login(broker, "abi", PASSWORDS["abi"]), SECRET, identity
        )
        try:
            assert client.get("NATS_JWT_SECRET") == SECRET
            assert set(ENGINE_SECRETS) <= set(client.list())
        finally:
            client.close()


SYNTAX_VALUES = [
    "${NATS_JWT_SECRET}",
    "$OPENAI_API_KEY",
    'a"\nNATS_JWT_SECRET="attacker',
    "it's",
    "back\\slash",
]


def test_a_module_cannot_reach_another_secret_through_a_value_it_writes(
    serving, broker
):
    """The backend parses what it stored, expanding ``${NAME}`` from the file and the
    environment when the engine next loads its ``.env``: the value is refused instead."""
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        DotenvSecretSecondaryAdaptor,
    )
    from naas_abi_sdk import RPCError

    async def scenario(client):
        get, _, set_, _ = secret_calls(client)
        refused = {}
        for value in SYNTAX_VALUES:
            try:
                await set_("PARTNER_STATE", value)
            except RPCError as exc:
                refused[value] = exc.code
        await set_("PARTNER_STATE", "plain-new-state")
        return refused, await get("PARTNER_STATE")

    refused, state = as_module(broker, GRANTED, scenario)

    assert refused == {value: "INVALID_ARGUMENT" for value in SYNTAX_VALUES}
    assert state == "plain-new-state"
    # what an engine restart reads back from the file
    reloaded = DotenvSecretSecondaryAdaptor(str(serving / ".env"))
    assert reloaded.get("PARTNER_STATE") == "plain-new-state"
    assert reloaded.get("NATS_JWT_SECRET") == SECRET
    assert "${" not in (serving / ".env").read_text()


def test_the_engines_own_processes_may_still_write_any_value(serving, broker):
    from naas_abi_core.services.secret.adaptors.secondary.SecretSecondaryAdapterNATSClient import (
        SecretSecondaryAdapterNATSClient,
    )

    client = SecretSecondaryAdapterNATSClient(
        login(broker, "abi", PASSWORDS["abi"]), SECRET, "api"
    )
    try:
        client.set("ENGINE_NOTE", 'it\'s "quoted"')
        assert client.get("ENGINE_NOTE") == 'it\'s "quoted"'
    finally:
        client.close()
