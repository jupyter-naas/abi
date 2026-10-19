"""``provisioning: keycloak``: Keycloak's admin REST API of the provider's realm.

``admin.client_id`` and ``admin.client_secret`` are a confidential client of
that realm with the service account enabled and the ``realm-management`` roles
``manage-users`` and ``view-users``; its client credentials token is fetched
from the realm's token endpoint and kept until it expires. ``admin.url`` and
``admin.realm`` default to what the issuer (``https://<host>[/prefix]/realms/<realm>``)
says. A new user is made with an unverified email and, unless ``send_actions``
is off, Keycloak mails them its "verify email and update password" action link:
the ID token's ``email_verified`` is what lets an invitation attach.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from naas_abi_core.services.identity.adapters.secondary.AdminHttp import AdminHttp
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisionedUser,
    ProvisioningError,
    ProvisioningPort,
)

ACTIONS = ("VERIFY_EMAIL", "UPDATE_PASSWORD")


def admin_location(issuer: str, url: str | None, realm: str | None) -> tuple[str, str]:
    """``(server base URL, realm)`` of a Keycloak issuer."""
    base, marker, tail = issuer.partition("/realms/")
    if not marker and not (url and realm):
        raise ValueError(
            f"{issuer!r} is not a Keycloak issuer (https://<host>/realms/<realm>): "
            "name admin.url and admin.realm"
        )
    return (url or base).rstrip("/"), realm or tail.strip("/").split("/")[0]


class ProvisioningKeycloak(ProvisioningPort):
    def __init__(
        self,
        provider: str,
        http: AdminHttp,
        realm: str,
        *,
        send_actions: bool = True,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._provider = provider
        self._http = http
        self._realm = quote(realm, safe="")
        self._send_actions = send_actions
        self._clock = clock

    def find_user(self, email: str) -> ProvisionedUser | None:
        status, body, _ = self._http.request(
            "GET",
            f"/admin/realms/{self._realm}/users",
            params={"email": email, "exact": "true", "max": "1"},
        )
        if status != 200 or not isinstance(body, list):
            raise self._failure("search users", status, body)
        return self._user(body[0], email, created=False) if body else None

    def ensure_user(self, email: str, *, name: str | None = None) -> ProvisionedUser:
        existing = self.find_user(email)
        if existing is not None:
            return existing
        first, last = _names(email, name)
        status, body, headers = self._http.request(
            "POST",
            f"/admin/realms/{self._realm}/users",
            json_body={
                "username": email,
                "email": email,
                "emailVerified": False,
                "enabled": True,
                "firstName": first,
                "lastName": last,
            },
        )
        if status == 409:
            found = self.find_user(email)
            if found is not None:
                return found
        if status != 201:
            raise self._failure("create the user", status, body)
        user_id = _created_id(headers)
        if user_id is None:
            created = self.find_user(email)
            user_id = created.subject if created else None
        if user_id and self._send_actions:
            self._mail_actions(user_id)
        return ProvisionedUser(
            provider=self._provider,
            email=email,
            subject=user_id,
            name=f"{first} {last}".strip(),
            created=True,
        )

    # -- plumbing ---------------------------------------------------------------------

    def _mail_actions(self, user_id: str) -> None:
        """Keycloak's own invitation mail. The user exists and the invitation
        attaches whatever happens here, so a mail server that is not set up is
        not an error of the invitation."""
        try:
            self._http.request(
                "PUT",
                f"/admin/realms/{self._realm}/users/{quote(user_id, safe='')}"
                "/execute-actions-email",
                json_body=list(ACTIONS),
            )
        except ProviderUnavailableError:
            pass

    def _user(
        self, found: dict[str, Any], email: str, *, created: bool
    ) -> ProvisionedUser:
        name = " ".join(p for p in (found.get("firstName"), found.get("lastName")) if p)
        return ProvisionedUser(
            provider=self._provider,
            email=email,
            subject=found.get("id"),
            name=name or None,
            created=created,
            disabled=found.get("enabled") is False,
        )

    @staticmethod
    def _failure(what: str, status: int, body: Any) -> Exception:
        message = None
        if isinstance(body, dict):
            message = body.get("errorMessage") or body.get("error")
        if status == 400:
            return ValueError(f"Keycloak refused to {what}: {message or 'bad request'}")
        return ProvisioningError(
            f"Keycloak could not {what} (HTTP {status}{': ' + str(message) if message else ''})"
        )


def _created_id(headers: dict[str, str]) -> str | None:
    location = next((v for k, v in headers.items() if k.lower() == "location"), "")
    return location.rstrip("/").rsplit("/", 1)[-1] or None


def _names(email: str, name: str | None) -> tuple[str, str]:
    text = (name or "").strip() or email.split("@", 1)[0].replace(".", " ").replace(
        "_", " "
    )
    parts = text.title().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return (parts[0] if parts else "User"), ""
