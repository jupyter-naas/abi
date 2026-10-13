import socket

from naas_abi_core.engine.nats_naming import connection_name, rpc_client_role


def test_names_carry_the_role_and_the_host():
    assert connection_name("abi-engine") == f"abi-engine@{socket.gethostname()}"


def test_rpc_clients_are_named_after_their_domain():
    class ObjectStorageSecondaryAdapterNATSClient:
        pass

    class KeyValueSecondaryAdapterNATSClient:
        pass

    assert (
        rpc_client_role("engine", ObjectStorageSecondaryAdapterNATSClient)
        == "abi-engine:object_storage"
    )
    assert (
        rpc_client_role("api", KeyValueSecondaryAdapterNATSClient)
        == "abi-api:key_value"
    )
