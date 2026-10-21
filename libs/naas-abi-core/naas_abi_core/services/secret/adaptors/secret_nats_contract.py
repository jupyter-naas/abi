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

Security note: the primary authorizes per caller. The engine's own processes
(``api``, ``engine``, ``dagster``) keep full access; an SDK module reads, lists,
writes and removes only the names ``nats.secret.modules`` grants it, by its verified
service identity (docs/adr/20261024_secret-service-closed-to-sdk-modules.md).

See ``naas_abi_core/proto/secret/v1/secret.proto`` for the full wire
contract this pairs with.
"""

SERVICE_NAME = "secret"
SERVICE_VERSION = "1.0.0"
SUBJECT_PREFIX = "abi.svc.secret.v1"

# Header carrying the Stage 1 service JWT (see naas_abi_core.engine.nats_auth).
# The client attaches the token under this exact header name -- both sides
# of this contract must agree on it.
AUTH_HEADER = "Nats-Auth-Token"
