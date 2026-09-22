"""Wire-level NATS contract shared by coding_environment's primary and
secondary adapters -- the subject prefix and auth header name both sides
must agree on.

Deliberately its own module, sibling to ``primary/`` and ``secondary/``, not
owned by either: a secondary adapter importing constants from a primary
adapter's module (or vice versa) would make one adapter depend on the other,
which defeats the point of the hexagonal split -- primary and secondary
adapters are independent implementations connected only through the domain,
never directly on each other. Both
``adapters/primary/coding_environment__primary_adapter__NATS.py`` and
``adapters/secondary/CodingEnvironmentSecondaryAdapterNATSClient.py`` import
from here instead.

See ``naas_abi_core/proto/coding_environment/v1/coding_environment.proto``
for the full wire contract this pairs with.
"""

SERVICE_NAME = "coding_environment"
SERVICE_VERSION = "1.0.0"
SUBJECT_PREFIX = "abi.svc.coding_environment.v1"

# Header carrying the Stage 1 service JWT (see naas_abi_core.engine.nats_auth).
# The client attaches the token under this exact header name -- both sides
# of this contract must agree on it.
AUTH_HEADER = "Nats-Auth-Token"
