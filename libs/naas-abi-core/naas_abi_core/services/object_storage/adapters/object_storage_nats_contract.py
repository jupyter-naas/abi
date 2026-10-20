"""Wire-level NATS contract shared by object_storage's primary and secondary
adapters -- the subject prefix and auth header name both sides must agree on.

Deliberately its own module, sibling to ``primary/`` and ``secondary/``, not
owned by either: a secondary adapter importing constants from a primary
adapter's module (or vice versa) would make one adapter depend on the other,
which defeats the point of the hexagonal split -- primary and secondary
adapters are independent implementations connected only through the domain,
never directly on each other. Both
``adapters/primary/object_storage__primary_adapter__NATS.py`` and
``adapters/secondary/ObjectStorageSecondaryAdapterNATSClient.py`` import
from here instead.

See ``naas_abi_core/proto/object_storage/v1/object_storage.proto`` for the
full wire contract this pairs with.
"""

SERVICE_NAME = "object_storage"
SERVICE_VERSION = "1.0.0"
SUBJECT_PREFIX = "abi.svc.object_storage.v1"

# Header carrying the Stage 1 service JWT (see naas_abi_core.engine.nats_auth).
# The client attaches the token under this exact header name -- both sides
# of this contract must agree on it.
AUTH_HEADER = "Nats-Auth-Token"
