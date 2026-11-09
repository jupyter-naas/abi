"""``provisioning: builtin``: the built-in IdP's admin app, over NATS.

The IdP module serves a second app, ``admin`` (``libs/naas-abi-idp``), JSON
over ``abi.app.v1``. Discovery lets only the engine's own accounts through
(``naas_abi_idp.admin``); this adapter is called as one of them, after the
caller's own rights were checked (``IdentityService.provision_user``).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote, urlencode

from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
    AppAnswer,
    IdPApp,
)
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisionedUser,
    ProvisioningError,
    ProvisioningPort,
)

JSON = {"content-type": "application/json", "accept": "application/json"}


class ProvisioningBuiltinIdP(ProvisioningPort):
    def __init__(self, provider: str) -> None:
        self._provider = provider
        self._app: IdPApp | None = None

    def attach(self, app: IdPApp | None) -> None:
        """Where admin calls go: the module's ``admin`` app. Attached by the
        serving engine once its NATS runtime is up."""
        self._app = app

    def ensure_user(self, email: str, *, name: str | None = None) -> ProvisionedUser:
        body: dict[str, Any] = {"email": email}
        if name:
            body["name"] = name
        answer = self._ask("POST", "/users", body=json.dumps(body).encode())
        if answer.status == 201:
            return self._user(answer, created=True)
        if answer.status == 409:
            # Registered already (it may have signed itself up): not an error.
            found = self.find_user(email)
            if found is not None:
                return found
        raise self._failure(answer)

    def find_user(self, email: str) -> ProvisionedUser | None:
        answer = self._ask("GET", "/users/by-email", query=urlencode({"email": email}))
        if answer.status == 200:
            return self._user(answer, created=False)
        if answer.status == 404:
            return None
        raise self._failure(answer)

    def update_user(
        self,
        subject: str,
        *,
        name: str | None = None,
        disabled: bool | None = None,
    ) -> ProvisionedUser | None:
        path = f"/users/{quote(subject, safe='')}"
        answer = self._ask("GET", path)
        if answer.status == 404:
            return None
        if answer.status != 200:
            raise self._failure(answer)
        if name:
            answer = self._ask("PATCH", path, body=json.dumps({"name": name}).encode())
            if answer.status != 200:
                raise self._404_or_failure(answer)
        if disabled is not None:
            # Disabling ends the person's sessions and refresh tokens at the IdP.
            answer = self._ask("POST", f"{path}/{'disable' if disabled else 'enable'}")
            if answer.status != 200:
                raise self._404_or_failure(answer)
        return self._user(answer, created=False)

    def delete_user(self, subject: str) -> bool:
        answer = self._ask("DELETE", f"/users/{quote(subject, safe='')}")
        if answer.status in (200, 204):
            return True
        if answer.status == 404:
            return False
        raise self._failure(answer)

    # -- plumbing ---------------------------------------------------------------------

    def _404_or_failure(self, answer: AppAnswer) -> Exception:
        if answer.status == 404:
            return ProvisioningError(
                "The user was deleted at the built-in IdP meanwhile"
            )
        return self._failure(answer)

    def _ask(
        self, method: str, path: str, *, query: str = "", body: bytes = b""
    ) -> AppAnswer:
        if self._app is None:
            raise ProviderUnavailableError(
                "The built-in identity provider is not reachable yet: it runs as a "
                "module over NATS (nats.discovery must be configured)"
            )
        return self._app.request(
            method, path, query=query, body=body, headers=JSON if body else {}
        )

    def _user(self, answer: AppAnswer, *, created: bool) -> ProvisionedUser:
        try:
            data = json.loads(answer.body)
            return ProvisionedUser(
                provider=self._provider,
                email=str(data["email"]),
                subject=str(data["id"]),
                name=data.get("name"),
                created=created,
                disabled=bool(data.get("disabled", False)),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise ProvisioningError("The built-in IdP answered no user") from exc

    @staticmethod
    def _failure(answer: AppAnswer) -> Exception:
        message = "The built-in IdP refused the call"
        try:
            message = str(json.loads(answer.body).get("message") or message)
        except (ValueError, AttributeError):
            pass
        if answer.status == 400:
            return ValueError(message)
        if answer.status == 403:
            return ProvisioningError(f"{message} (the admin app refused this account)")
        return ProvisioningError(f"{message} (HTTP {answer.status})")
