from naas_abi_core.engine.nats_connection_warden import (
    Admissions,
    Admitted,
    Connection,
    stale,
    unknown,
)
from naas_abi_core.services.iam.broker import BrokerPermissions
from naas_abi_core.services.iam.IAMPorts import KeyRefusedError


def _permissions(*publish: str) -> BrokerPermissions:
    return BrokerPermissions(publish=publish, subscribe=(), inbox_prefix="_INBOX.k.m")


KV = _permissions("abi.svc.keyvalue.v1.>")
DOCS = _permissions("abi.svc.document.v1.>")


def test_only_the_connections_whose_permissions_changed_are_stale():
    admitted = {
        Connection("S", 1): Admitted("sa_a", "ka", KV),
        Connection("S", 2): Admitted("sa_b", "kb", KV),
    }
    now = {("sa_a", "ka"): KV, ("sa_b", "kb"): DOCS}
    assert stale(admitted, lambda p, k: now[(p, k)]) == [Connection("S", 2)]


def test_a_refused_key_or_an_undecided_check_ends_the_connection():
    admitted = {
        Connection("S", 1): Admitted("sa_a", "ka", KV),
        Connection("S", 2): Admitted("sa_b", "kb", KV),
    }

    def permissions(principal, key):
        if principal == "sa_a":
            raise KeyRefusedError()
        raise RuntimeError("the store is down")  # fail closed

    assert stale(admitted, permissions) == [Connection("S", 1), Connection("S", 2)]


def test_each_key_is_checked_once_however_many_connections_use_it():
    admitted = {Connection("S", n): Admitted("sa_a", "ka", KV) for n in range(5)}
    calls = []

    def permissions(principal, key):
        calls.append((principal, key))
        return KV

    assert stale(admitted, permissions) == []
    assert calls == [("sa_a", "ka")]


def _connz(server: str, *clients: dict) -> dict:
    return {"server": {"id": server}, "data": {"connections": list(clients)}}


def test_a_callout_connection_this_engine_did_not_admit_is_unknown():
    admitted = {Connection("S", 7): Admitted("sa_a", "ka", KV)}
    answers = [
        _connz(
            "S",
            {"cid": 6, "authorized_user": "auth"},  # a static user: never kicked
            {"cid": 7, "authorized_user": "module/x/a", "issuer_key": "$G"},
            {"cid": 9, "authorized_user": "module/x/b", "issuer_key": "$G"},
            {"cid": 10, "authorized_user": "sys", "account": "SYS"},
        )
    ]
    foreign, gone = unknown(answers, admitted)
    assert foreign == [Connection("S", 9)]
    assert gone == []


def test_a_recorded_connection_the_broker_no_longer_lists_is_gone():
    admitted = {
        Connection("S", 7): Admitted("sa_a", "ka", KV),
        Connection("OTHER", 3): Admitted("sa_b", "kb", KV),
    }
    foreign, gone = unknown([_connz("S")], admitted)
    assert foreign == []
    # A server that did not answer says nothing about its connections.
    assert gone == [Connection("S", 7)]


def test_admissions_record_and_forget():
    admissions = Admissions()
    admissions.admit(Connection("S", 1), Admitted("sa_a", "ka", KV))
    assert admissions.get(Connection("S", 1)) == Admitted("sa_a", "ka", KV)
    admissions.forget(Connection("S", 1))
    admissions.forget(Connection("S", 1))  # twice is fine
    assert len(admissions) == 0
