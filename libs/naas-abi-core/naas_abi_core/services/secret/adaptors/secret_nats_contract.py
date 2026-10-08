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

Security note (see the RFC / dev log for the fuller reasoning): Stage 1's
auth model is one shared JWT with no per-caller ARN/IAM authorization --
whoever holds a valid service token can read/write/list every secret this
process's ``Secret`` service exposes. Ported anyway, explicitly accepted
by Max as a known, temporary gap ("if it's adding security problems we
will have to fix that anyway") rather than left undone -- revisit once
Stage 2 per-caller authorization exists.

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
