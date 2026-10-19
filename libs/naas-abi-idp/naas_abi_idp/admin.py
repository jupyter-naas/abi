"""The admin API: users, groups and clients, over NATS.

A second app of the module (``admin``), never on the public route: Nexus serves
only the ``idp`` app at ``/idp``. It is for services (the provisioning port, the
CLI), which reach it with ``abi.app.v1`` requests and are authorized by
discovery's ``OpenApp`` on ``abi:-:-:discovery:app/<project>/idp/admin``.

Discovery's ``OpenApp`` is a read-level action, so it is not enough: a service
account that holds a workspace role holds it too. The app therefore checks the
verified actor itself (``scope["abi"]["principal"]``, set by the app host from
discovery's answer): only the engine's own accounts (``ADMIN_ACCOUNTS``)
administer, never a module, a CI account or a user, whatever discovery allowed.
It also refuses a call made on behalf of a signed-in user: a user's reach into
apps is not an admin's (any user may open apps), so a service that acts for
someone calls as itself, after checking that person's rights on its own.

JSON in and out; errors are ``{"error": <code>, "message": ...}``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from naas_abi_idp.ports import Conflict, IdPError, InvalidArgument, NotFound
from naas_abi_idp.service import IdPService

log = logging.getLogger(__name__)

# The service accounts that administer: the engine's own, which check the rights
# of whoever they act for before they call (provisioning, ``abi iam``).
ADMIN_ACCOUNTS = frozenset({"api", "engine"})
MAX_BODY_BYTES = 64 * 1024
_STATUS = {NotFound: 404, Conflict: 409, InvalidArgument: 400}


class AdminAPI:
    def __init__(self, service: IdPService) -> None:
        self.service = service

    def app(self) -> Starlette:
        routes = [
            Route("/users", self.users, methods=["GET", "POST"]),
            Route("/users/by-email", self.user_by_email, methods=["GET"]),
            Route("/users/{user_id}", self.user, methods=["GET", "PATCH"]),
            Route("/users/{user_id}/disable", self.disable, methods=["POST"]),
            Route("/users/{user_id}/enable", self.enable, methods=["POST"]),
            Route("/groups", self.groups, methods=["GET", "POST"]),
            Route("/groups/{group}", self.group, methods=["DELETE"]),
            Route(
                "/groups/{group}/members/{user_id}",
                self.member,
                methods=["PUT", "DELETE"],
            ),
            Route("/clients", self.clients, methods=["GET", "POST"]),
            Route(
                "/clients/{client_id}/disable", self.disable_client, methods=["POST"]
            ),
            Route("/clients/{client_id}/enable", self.enable_client, methods=["POST"]),
            Route("/keys/rotate", self.rotate_key, methods=["POST"]),
        ]
        app = Starlette(routes=routes)
        app.add_middleware(_ServiceOnly)  # type: ignore[arg-type]
        return app

    # -- handlers ---------------------------------------------------------------------

    async def users(self, request: Request) -> Response:
        if request.method == "GET":
            return await self._run(
                request,
                lambda: self._page(
                    "users", self.service.list_users, request, lambda u: u.public()
                ),
            )
        return await self._run(
            request,
            lambda body: (
                201,
                self.service.create_user(
                    _text(body, "email"),
                    name=_optional_text(body, "name"),
                    groups=_list(body, "groups"),
                    password=_optional_text(body, "password"),
                ).public(),
            ),
            body=True,
        )

    async def user_by_email(self, request: Request) -> Response:
        def found() -> Any:
            user = self.service.find_user(request.query_params.get("email", ""))
            if user is None:
                raise NotFound("No user has that email")
            return user.public()

        return await self._run(request, found)

    async def user(self, request: Request) -> Response:
        user_id = request.path_params["user_id"]
        if request.method == "GET":
            return await self._run(
                request, lambda: self.service.get_user(user_id).public()
            )
        return await self._run(
            request,
            lambda body: self.service.update_user(
                user_id,
                name=_optional_text(body, "name"),
                email=_optional_text(body, "email"),
                password=_optional_text(body, "password"),
            ).public(),
            body=True,
        )

    async def disable(self, request: Request) -> Response:
        return await self._run(
            request,
            lambda: self.service.set_disabled(
                request.path_params["user_id"], True
            ).public(),
        )

    async def enable(self, request: Request) -> Response:
        return await self._run(
            request,
            lambda: self.service.set_disabled(
                request.path_params["user_id"], False
            ).public(),
        )

    async def groups(self, request: Request) -> Response:
        if request.method == "GET":
            return await self._run(
                request,
                lambda: self._page(
                    "groups", self.service.list_groups, request, lambda g: g.to_doc()
                ),
            )
        return await self._run(
            request,
            lambda body: (
                201,
                self.service.create_group(
                    _text(body, "name"), _optional_text(body, "description") or ""
                ).to_doc(),
            ),
            body=True,
        )

    async def group(self, request: Request) -> Response:
        def delete() -> Any:
            self.service.delete_group(request.path_params["group"])
            return {"deleted": True}

        return await self._run(request, delete)

    async def member(self, request: Request) -> Response:
        group, user_id = request.path_params["group"], request.path_params["user_id"]
        change = (
            self.service.add_member
            if request.method == "PUT"
            else self.service.remove_member
        )
        return await self._run(request, lambda: change(group, user_id).public())

    async def clients(self, request: Request) -> Response:
        if request.method == "GET":
            return await self._run(
                request,
                lambda: self._page(
                    "clients", self.service.list_clients, request, lambda c: c.public()
                ),
            )

        def create(body: dict[str, Any]) -> Any:
            client, secret = self.service.create_client(
                _text(body, "name"),
                redirect_uris=_list(body, "redirect_uris"),
                grant_types=_list(body, "grant_types") or ["client_credentials"],
                scopes=_list(body, "scopes"),
                confidential=_flag(body, "confidential", True),
            )
            # The secret is shown once: only its hash is kept.
            return 201, {**client.public(), "client_secret": secret}

        return await self._run(request, create, body=True)

    async def disable_client(self, request: Request) -> Response:
        return await self._run(
            request,
            lambda: self.service.set_client_disabled(
                request.path_params["client_id"], True
            ).public(),
        )

    async def enable_client(self, request: Request) -> Response:
        return await self._run(
            request,
            lambda: self.service.set_client_disabled(
                request.path_params["client_id"], False
            ).public(),
        )

    async def rotate_key(self, request: Request) -> Response:
        return await self._run(request, lambda: {"kid": self.service.keys.rotate().kid})

    # -- plumbing -----------------------------------------------------------------------

    @staticmethod
    def _page(
        name: str,
        lister: Callable[..., tuple[list[Any], str | None]],
        request: Request,
        show: Callable[[Any], Any],
    ) -> dict[str, Any]:
        raw = request.query_params.get("limit", "100")
        if not raw.isdigit():
            raise InvalidArgument("limit is a number")
        items, cursor = lister(limit=int(raw), after=request.query_params.get("after"))
        return {name: [show(i) for i in items], "next": cursor}

    @staticmethod
    async def _run(
        request: Request, work: Callable[..., Any], *, body: bool = False
    ) -> Response:
        try:
            args = (await _body(request),) if body else ()
            result = await run_in_threadpool(work, *args)
        except IdPError as error:
            status = next((s for t, s in _STATUS.items() if isinstance(error, t)), 400)
            return JSONResponse(
                {"error": error.code, "message": str(error)}, status_code=status
            )
        except Exception:
            log.exception("The admin API failed")
            return JSONResponse(
                {"error": "internal", "message": "Failed"}, status_code=500
            )
        status = 200
        if isinstance(result, tuple):
            status, result = result
        return JSONResponse(
            result, status_code=status, headers={"Cache-Control": "no-store"}
        )


class _ServiceOnly:
    """Refuse every caller but the engine's own accounts acting for nobody (see
    the module docstring)."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] == "http" and not _may_administer(scope.get("abi")):
            response = JSONResponse(
                {"error": "forbidden", "message": "The admin API is for services"},
                status_code=403,
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _may_administer(caller: Any) -> bool:
    if not isinstance(caller, dict) or caller.get("user_id"):
        return False
    principal = caller.get("principal")
    return (
        isinstance(principal, dict)
        and principal.get("kind") == "service_account"
        and principal.get("name") in ADMIN_ACCOUNTS
    )


async def _body(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise InvalidArgument("The request is too large")
    if not raw:
        return {}
    import json

    try:
        data = json.loads(raw)
    except ValueError:
        raise InvalidArgument("The body is not JSON") from None
    if not isinstance(data, dict):
        raise InvalidArgument("The body is a JSON object")
    return data


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidArgument(f"{key} is required")
    return value


def _optional_text(body: dict[str, Any], key: str) -> str | None:
    value = body.get(key)
    if value is not None and not isinstance(value, str):
        raise InvalidArgument(f"{key} is a string")
    return value


def _flag(body: dict[str, Any], key: str, default: bool) -> bool:
    value = body.get(key, default)
    if not isinstance(value, bool):
        raise InvalidArgument(f"{key} is true or false")
    return value


def _list(body: dict[str, Any], key: str) -> list[str]:
    value = body.get(key, [])
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise InvalidArgument(f"{key} is a list of strings")
    return value
