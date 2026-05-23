"""Branch propagation conventions for the four boundary crossings.

``BranchContext`` covers in-process propagation. When work crosses a
process boundary — incoming HTTP, outgoing HTTP, incoming bus message,
outgoing bus message — the active branch must travel along with it,
or the loud-failure policy degrades into silent reads against ``main``
on the receiving side.

This module is **documentation by way of constants**: it defines the
header / metadata-field names that consumers MUST use, and explains
the four conventions in the module docstring. The middleware that
actually plumbs these values lives in higher layers (the API package
for HTTP, the bus adapter for messages); shipping that middleware
from naas-abi-core would force a FastAPI / queue-vendor dependency on
every consumer.

The four boundaries
-------------------

1. **Incoming HTTP request.** Read ``X-Abi-Branch`` from the request.
   Wrap the handler in ``BranchContext.use(branch)``. If the header
   is absent, fall back to ``"main"`` — public endpoints stay
   backwards-compatible with non-branch-aware clients.

2. **Outgoing HTTP request.** Set ``X-Abi-Branch: <BranchContext.current()>``
   on every request emitted by ``naas_abi_core`` so the receiver can
   pick it up via convention 1. Skip the header when the branch is
   ``"main"`` to keep traffic clean.

3. **Outgoing bus message.** Stamp the active branch into the message
   metadata under the field ``BUS_BRANCH_FIELD`` (``branch``). Whether
   that is a Kafka header, a Pub/Sub attribute, or a JSON envelope key
   is the bus adapter's call; the field name is shared.

4. **Incoming bus message.** The consuming bus adapter reads the
   metadata field and wraps message processing in
   ``BranchContext.use(branch)``. Missing field → ``"main"``.

Bus subscribers are inherently branch-scoped (per spec #865 §6): a
subscriber on ``main`` does NOT see events emitted on ``feature-x``.
This is by design — events on a feature branch are part of that
feature's isolated experience and do not leak into production state.
The bus per-branch isolation work lives in spec issue #885.
"""

from __future__ import annotations


HTTP_BRANCH_HEADER = "X-Abi-Branch"
"""HTTP header name used to carry the active branch across requests.

The ``X-`` prefix marks it as application-defined (we are not
registering an IANA header). Title-case is canonical; HTTP header
names are case-insensitive on the wire so middleware should
normalize before comparison."""


BUS_BRANCH_FIELD = "branch"
"""Bus message metadata field name used to carry the active branch.

Whether this lands as a Kafka header, an SQS attribute, an AMQP
property, or a JSON envelope key is a per-adapter detail. The
*field name* is shared so cross-adapter routing and observability
tooling can look it up consistently."""
