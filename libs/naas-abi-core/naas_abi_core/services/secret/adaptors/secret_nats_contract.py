"""Wire-level NATS contract shared by secret's primary and secondary
adapters -- the subject prefix and auth header name both sides must agree
on.

Deliberately its own module, sibling to ``primary/`` and ``secondary/``,
not owned by either: a secondary adapter importing constants from a
primary adapter's module (or vice versa) would make one adapter depend on
the other, which defeats the point of the hexagonal split -- primary and
secondary adapters are independent implementations connected only through
the domain, never directly on each other. Both
``adaptors/primary/secret__primary_adapter__NATS.py`` and
``adaptors/secondary/SecretSecondaryAdapterNATSClient.py`` import from here
instead.

Authorization: whoever calls is checked per key by the ``Secret`` domain
service against IAM (RFC §6.4), as in process. Before IAM, any holder of a
service token could read every secret; that gap is closed.

The endpoint also stays an allowlist (``may_use``), a layer before IAM: the
``engine`` account reaches every secret but the IdP's, the IdP (the account
``idp`` or the module account of module ``idp``) its own (``idp/...``), and any
other caller only the names under its own prefix,
``<module id>/...`` for a module, ``<account name>/...`` for another service
account. Everything else the store serves (the broker's passwords, the callout
seed, IAM's signing keys, every provider key) is out of reach of a module,
whatever its policy grants.

See ``naas_abi_core/proto/secret/v1/secret.proto`` for the full wire
contract this pairs with.
"""

SERVICE_NAME = "secret"
SERVICE_VERSION = "1.0.0"
SUBJECT_PREFIX = "abi.svc.secret.v1"

# Header carrying the caller's engine token (see naas_abi_core.engine.nats_auth).
# The client attaches the token under this exact header name -- both sides
# of this contract must agree on it.
AUTH_HEADER = "Nats-Auth-Token"

# Names of the first-party accounts that own part of the store.
ENGINE = "engine"
IDP = "idp"
IDP_PREFIX = "idp/"


def _canonical(key: object) -> str | None:
    """``key`` when it is a plain ``a/b/c`` name: no dot segment, empty segment,
    backslash, percent escape, control character or surrounding space. A name
    an adapter might resolve differently (a path, a URL) is not one."""
    if not isinstance(key, str) or not key or key != key.strip():
        return None
    if any(c in key for c in "\\%\x00") or any(ord(c) < 32 for c in key):
        return None
    if any(part in ("", ".", "..") for part in key.split("/")):
        return None
    return key


def is_idp(name: str) -> bool:
    """The built-in IdP: the account named ``idp``, or the module account of
    the module ``idp`` (``module/<project>/idp``, how it runs by default)."""
    from naas_abi_core.services.iam.modules import parse_account

    account = parse_account(name)
    return name == IDP or (account is not None and account[1] == IDP)


def owned_prefix(name: str) -> str | None:
    """The prefix of the names a non-first-party account owns: ``<module
    id>/`` for ``module/<project>/<module id>``, ``<name>/`` for any other
    service account; None for a name that cannot own one."""
    from naas_abi_core.services.iam.modules import parse_account

    account = parse_account(name)
    owner = account[1] if account is not None else name
    return f"{owner}/" if _canonical(owner) is not None else None


def may_use(kind: str, name: str | None, key: object) -> bool:
    """Whether the verified caller (its kind and, for a service account, its
    name) may get, set, remove or list secret ``key``."""
    if kind != "service_account" or not name:
        return False
    if not isinstance(key, str):
        return False
    if name == ENGINE:
        return not key.strip().casefold().startswith(IDP_PREFIX)
    if is_idp(name):
        return _canonical(key) is not None and key.startswith(IDP_PREFIX)
    prefix = owned_prefix(name)
    if prefix is None or _canonical(key) is None:
        return False
    # Never another first party's, whatever the module is called.
    return key.startswith(prefix) and not key.casefold().startswith(
        (IDP_PREFIX, "iam/")
    )
