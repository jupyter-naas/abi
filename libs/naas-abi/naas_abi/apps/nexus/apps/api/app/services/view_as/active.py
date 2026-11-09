"""The view a request runs in, for the code that must behave differently during one.

``RequestIdentityMiddleware`` sets it for the request (a ``ContextVar``, copied into the
threadpool with the call context), so a handler or a service asks ``viewing()`` without the
request being passed down to it. Outside a request, or for a request of the viewer
themselves, there is none.

Three things ask it (``services/view_as/AGENTS.md``): the private content a view blanks
(``private``), the page loads that write something and do nothing in a view
(``viewing()``), and the activity log, which names the viewer (``viewer_id``).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from naas_abi.apps.nexus.apps.api.app.services.view_as.port import ViewRecord

_VIEW: ContextVar[ViewRecord | None] = ContextVar("nexus_view_as", default=None)


def current_view() -> ViewRecord | None:
    """The view of the request being served, None when it runs as the viewer."""
    return _VIEW.get()


def viewing() -> bool:
    """Whether the request being served is a view of someone."""
    return _VIEW.get() is not None


@contextmanager
def use_view(view: ViewRecord | None) -> Iterator[None]:
    token = _VIEW.set(view)
    try:
        yield
    finally:
        _VIEW.reset(token)
