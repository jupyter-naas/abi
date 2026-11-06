"""What a view answers: one workspace, read-only.

During a view every request of the session is judged here, before any route runs:

* **Read-only.** Every method but GET, HEAD and OPTIONS is refused, apart from the
  two that end the view (Stop, and the sign-out) and the reads sent by POST that
  ``reads_by_post.READS_BY_POST`` allows in a view.
* **Confined.** A request is answered only when it names the viewed workspace (the
  ``workspace_id`` of its path, or the ``workspace_id`` query parameter of a route
  that takes one), or when its route is on ``ANSWERED_WITHOUT_A_WORKSPACE``: a route
  that names no workspace and that the workspace's pages need, each with its reason.
  Anything else is outside the view.

A read sent by POST names its workspace in its body: the guard reads the (bounded) JSON
body and holds ``workspace_id`` to the viewed one, as a GET's query is.

A route is classified by the route the request reaches (its template and its
declared parameters), never by the raw text of the request: a ``workspace_id`` in
the query of a route that does not take one names nothing.

Routes of ``/api`` only: a link into an app (``/app-html``, ``/app-remote``,
``/app-preview``) carries its own credential, not the session.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from urllib.parse import parse_qs

from fastapi.dependencies.utils import get_flat_dependant
from fastapi.routing import APIRoute
from naas_abi.apps.nexus.apps.api.app.services.view_as.reads_by_post import (
    BODY,
    BY_ROUTE,
    QUERY,
    ReadByPost,
)
from starlette.routing import Match

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
API_PREFIX = "/api/"

# Writes that end the view, or the session it runs on: (method, route template).
STOP_ROUTE = ("DELETE", "/api/iam/view-as")
SIGN_OUT_ROUTE = ("POST", "/api/auth/oidc/logout")
ENDING_ROUTES = frozenset({STOP_ROUTE, SIGN_OUT_ROUTE})

# Routes that name no workspace and that the workspace's pages need: (method, route
# template) -> why. Each answers as the person (the credential is theirs), and a
# route that lists or finds workspaces shows the viewed one only.
# A route is added here with its reason, never to make a refusal go away.
ANSWERED_WITHOUT_A_WORKSPACE: dict[tuple[str, str], str] = {
    ("GET", "/api/auth/me"): "the shell shows the person: their name and avatar",
    ("GET", "/api/auth/oidc/session"): (
        "the web app's session answer: the viewer's, with the view the banner shows"
    ),
    ("GET", "/api/workspaces"): "the workspace list of the shell: the viewed workspace only",
    ("GET", "/api/workspaces/slug/{slug}"): (
        "the web app finds the workspace of its address by slug: the viewed workspace only"
    ),
    ("GET", "/api/chat/conversations/{conversation_id}"): (
        "a conversation is opened by its id: in a view it is the person's and private to them, "
        "so it is never found (404)"
    ),
    ("GET", "/api/chat/ingestion-jobs/{job_id}"): (
        "a file of a conversation is followed by its job's id: private to the person, "
        "never found (404) in a view"
    ),
    ("GET", "/api/iam/api-keys"): (
        "the account's keys page opens: the person's personal keys are private to them, "
        "answered empty in a view"
    ),
    ("GET", "/api/tenant"): "branding of the shell; public, the same for everyone",
    ("GET", "/api/auth/avatar/{filename}"): "avatar images in <img> tags; public",
    ("GET", "/api/auth/avatar/user/{user_id}"): "account pictures in <img> tags; public",
    ("GET", "/api/auth/avatar/user/{user_id}/org"): "member pictures in <img> tags; public",
    (
        "GET",
        "/api/auth/avatar/user/{user_id}/org/{org_id}",
    ): "member pictures in <img> tags; public",
}


# The largest body the guard reads to find the workspace a POST read names (a sheet draft is
# at most 2 MB of text: its JSON form is a little more).
MAX_BODY = 8 * 1024 * 1024


class Verdict(Enum):
    """How a view treats a request."""

    NAMED = "names the viewed workspace"
    LISTED = "answered without a workspace"
    OUTSIDE = "outside the view"


@dataclass(frozen=True)
class Refusal:
    status: int
    detail: str


def read_only_detail(person: str) -> str:
    return f"Read-only: you are viewing as {person}"


def outside_detail(person: str, workspace: str) -> str:
    return f"Outside this view: you are viewing as {person} in {workspace}"


def declared_workspace_query(route: APIRoute) -> bool:
    """Whether the route takes a ``workspace_id`` query parameter (worked out once per
    route: it is asked on every request of a view)."""
    known = route.__dict__.get("_view_as_workspace_query")
    if known is None:
        known = any(
            p.alias == "workspace_id" for p in get_flat_dependant(route.dependant).query_params
        )
        route.__dict__["_view_as_workspace_query"] = known
    return known


def route_names_workspace(route: APIRoute) -> bool:
    """Whether the route can name a workspace: a path parameter or a query
    parameter called ``workspace_id``."""
    return "workspace_id" in route.param_convertors or declared_workspace_query(route)


def classify(
    method: str,
    route: APIRoute,
    path_params: dict[str, object],
    query_string: bytes,
    viewed_workspace: str,
) -> Verdict:
    """How a view treats a GET, HEAD or OPTIONS request that reached ``route``."""
    if (method, route.path) in ANSWERED_WITHOUT_A_WORKSPACE or (
        method == "HEAD" and ("GET", route.path) in ANSWERED_WITHOUT_A_WORKSPACE
    ):
        return Verdict.LISTED
    named: list[str] = []
    if "workspace_id" in route.param_convertors:
        named.append(str(path_params.get("workspace_id", "")))
    if declared_workspace_query(route):
        # Blank values count: ``?workspace_id=viewed&workspace_id=`` reaches the handler
        # as "" (the last value), which a handler may read as "no workspace given".
        given = parse_qs(query_string.decode("latin-1"), keep_blank_values=True)
        named.extend(given.get("workspace_id", []))
    if named and all(value == viewed_workspace for value in named):
        return Verdict.NAMED
    return Verdict.OUTSIDE


def find_route(routes: list, scope: dict) -> tuple[APIRoute, dict[str, object]] | None:
    """The API route a request reaches (a method that route does not take counts: it
    is answered 405 and names the same workspace), with its path parameters."""
    partial: tuple[APIRoute, dict[str, object]] | None = None
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        match, child = route.matches(scope)
        if match == Match.FULL:
            return route, child.get("path_params", {})
        if match == Match.PARTIAL and partial is None:
            partial = (route, child.get("path_params", {}))
    return partial


def is_ending(scope: dict) -> bool:
    """Whether the request is Stop or the sign-out: they only give access up."""
    found = find_route(scope["app"].router.routes, scope)
    method = str(scope.get("method", "GET")).upper()
    return found is not None and (method, found[0].path) in ENDING_ROUTES


def post_read(scope: dict) -> ReadByPost | None:
    """The entry of ``READS_BY_POST`` the request reaches, None for any other write."""
    if str(scope.get("method", "")).upper() != "POST":
        return None
    found = find_route(scope["app"].router.routes, scope)
    return BY_ROUTE.get(("POST", found[0].path)) if found is not None else None


def needs_body(scope: dict) -> bool:
    """Whether judging the request means reading its body: an allowed read sent by POST
    that names its workspace there."""
    if not str(scope.get("path", "")).startswith(API_PREFIX):
        return False
    entry = post_read(scope)
    return entry is not None and entry.allowed and entry.workspace == BODY


def body_names_workspace(body: bytes, viewed_workspace: str) -> bool:
    """Whether the JSON object the body carries names the viewed workspace, and only it
    (``workspace_id`` at its top level, as every read sent by POST takes it)."""
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return isinstance(data, dict) and data.get("workspace_id") == viewed_workspace


def judge(
    scope: dict,
    *,
    person: str,
    workspace_id: str,
    workspace_name: str,
    body: bytes | None = None,
) -> Refusal | None:
    """The refusal a view gives the request, or None to answer it. ``body`` is the
    request's body when ``needs_body(scope)``."""
    path = scope.get("path", "")
    if not path.startswith(API_PREFIX):
        return None
    method = str(scope.get("method", "GET")).upper()
    routes = scope["app"].router.routes
    if method not in READ_METHODS:
        if is_ending(scope):
            return None
        entry = post_read(scope)
        if entry is None or not entry.allowed:
            return Refusal(403, read_only_detail(person))
        if entry.workspace == BODY:
            if body is None or not body_names_workspace(body, workspace_id):
                return Refusal(403, outside_detail(person, workspace_name))
        elif entry.workspace == QUERY:
            found = find_route(routes, scope)
            if found is None:
                return Refusal(403, outside_detail(person, workspace_name))
            route, path_params = found
            query = scope.get("query_string", b"")
            if classify(method, route, path_params, query, workspace_id) is Verdict.OUTSIDE:
                return Refusal(403, outside_detail(person, workspace_name))
        return None
    found = find_route(routes, scope)
    if found is None:
        return Refusal(403, outside_detail(person, workspace_name))
    route, path_params = found
    verdict = classify(method, route, path_params, scope.get("query_string", b""), workspace_id)
    if verdict is Verdict.OUTSIDE:
        return Refusal(403, outside_detail(person, workspace_name))
    return None
