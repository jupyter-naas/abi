"""Wire-level NATS contract shared by event's primary and secondary
adapters -- the subject prefix and auth header name both sides must agree on.

Deliberately its own module, sibling to ``primary/`` and ``secondary/``, not
owned by either: a secondary adapter importing constants from a primary
adapter's module (or vice versa) would make one adapter depend on the other,
which defeats the point of the hexagonal split -- primary and secondary
adapters are independent implementations connected only through the domain,
never directly on each other. Both
``adapters/primary/event__primary_adapter__NATS.py`` and
``adapters/secondary/EventSecondaryAdapterNATSClient.py`` import from here
instead.

Scope note: this contract covers only ``IEventAdapter`` -- the durable-log
secondary port (``append``/``query``/``max_seq``/``get_cursor``/
``set_cursor``/``query_for_consumer``) -- not the domain-level
``IEventService``. ``EventService(adapter, bus)`` composes an
``IEventAdapter`` with a ``BusService``; a client built against this contract
is only a drop-in replacement for the ``adapter`` argument. ``publish``,
``subscribe`` (bus-backed, live, returns a ``Thread``), ``iter_query``,
``iter_query_for_consumer``, the domain-level ``query`` (which takes an
``event_class: type``, not this port's ``event_type: str``), and
``seek_consumer_to_end`` all keep running 100% locally in ``EventService``
wherever it is constructed, composed on top of whichever ``IEventAdapter``
this contract's client is plugged into -- none of that is remoted by this
contract, and ``subscribe``'s bus broadcasting in particular is entirely
untouched by this work.

See ``naas_abi_core/proto/event/v1/event.proto`` for the full wire contract
this pairs with.
"""

SERVICE_NAME = "event"
SERVICE_VERSION = "1.0.0"
SUBJECT_PREFIX = "abi.svc.event.v1"

# Header carrying the Stage 1 service JWT (see naas_abi_core.engine.nats_auth).
# The client attaches the token under this exact header name -- both sides
# of this contract must agree on it.
AUTH_HEADER = "Nats-Auth-Token"
