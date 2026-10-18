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

Security note: callers are authenticated (an engine token, verified against
the JWKS) but not yet authorized per secret: whoever holds a valid token can
read/write/list the secrets this process's ``Secret`` service exposes, until
the secret service enforces IAM. The exception is ``RESERVED_NAMES``: IAM's
signing keys, the engine's service key and the IdP's secrets are open only to
the account that owns them, whatever a policy says. A known, temporary gap for
every other secret.

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

# Secrets sealed to one first-party account (RFC §11.3): name prefix -> the
# service account that owns it. Compared case-insensitively, after trimming,
# so no spelling of the name reaches an adapter that normalises it.
RESERVED_NAMES: dict[str, str] = {
    "iam/": "engine",
    "idp/": "idp",
}


def reserved_owner(key: str) -> str | None:
    """The account that owns secret ``key``, or None when it is not reserved."""
    folded = key.strip().casefold()
    for prefix, owner in RESERVED_NAMES.items():
        if folded.startswith(prefix):
            return owner
    return None
