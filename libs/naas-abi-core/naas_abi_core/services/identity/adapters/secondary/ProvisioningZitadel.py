"""``provisioning: zitadel``: Zitadel's user API (v2), with a service user's token.

``admin.token`` is the personal access token of a machine user allowed to create
users (the ``ORG_USER_MANAGER`` role in the organization, or ``IAM_USER_MANAGER``);
``admin.url`` defaults to the issuer and ``admin.org_id`` picks the organization
users are made in when the token's own is not the one. A new user has an email
Zitadel mails a verification code to (``sendCode``), so only whoever controls
the mailbox verifies it: the ID token's ``email_verified`` is what lets an
invitation attach.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from naas_abi_core.services.identity.adapters.secondary.AdminHttp import AdminHttp
from naas_abi_core.services.identity.IdentityPorts import (
    ProvisionedUser,
    ProvisioningError,
    ProvisioningPort,
)


class ProvisioningZitadel(ProvisioningPort):
    def __init__(
        self, provider: str, http: AdminHttp, *, org_id: str | None = None
    ) -> None:
        self._provider = provider
        self._http = http
        self._org = {"x-zitadel-orgid": org_id} if org_id else {}

    def find_user(self, email: str) -> ProvisionedUser | None:
        status, body, _ = self._http.request(
            "POST",
            "/v2/users",
            headers=self._org,
            json_body={
                "queries": [
                    {
                        "emailQuery": {
                            "emailAddress": email,
                            "method": "TEXT_QUERY_METHOD_EQUALS_IGNORE_CASE",
                        }
                    },
                    {"typeQuery": {"type": "TYPE_HUMAN"}},
                ],
                "query": {"limit": 1},
            },
        )
        if status != 200 or not isinstance(body, dict):
            raise self._failure("search users", status, body)
        found = body.get("result") or []
        return self._user(found[0], email, created=False) if found else None

    def ensure_user(self, email: str, *, name: str | None = None) -> ProvisionedUser:
        existing = self.find_user(email)
        if existing is not None:
            return existing
        given, family = _names(email, name)
        status, body, _ = self._http.request(
            "POST",
            "/v2/users/human",
            headers=self._org,
            json_body={
                "username": email,
                "profile": {"givenName": given, "familyName": family},
                "email": {"email": email, "sendCode": {}},
            },
        )
        if status == 409:
            # Created meanwhile, or the username is taken by another email.
            found = self.find_user(email)
            if found is not None:
                return found
        if (
            status not in (200, 201)
            or not isinstance(body, dict)
            or "userId" not in body
        ):
            raise self._failure("create the user", status, body)
        return ProvisionedUser(
            provider=self._provider,
            email=email,
            subject=str(body["userId"]),
            name=name or f"{given} {family}".strip(),
            created=True,
        )

    def update_user(
        self,
        subject: str,
        *,
        name: str | None = None,
        disabled: bool | None = None,
    ) -> ProvisionedUser | None:
        found = self._get(subject)
        if found is None:
            return None
        path = f"/v2/users/{quote(subject, safe='')}"
        if name:
            given, family = _names("", name)
            status, body, _ = self._http.request(
                "PUT",
                f"/v2/users/human/{quote(subject, safe='')}",
                headers=self._org,
                json_body={
                    # Zitadel keeps the display name unless it is sent too.
                    "profile": {
                        "givenName": given,
                        "familyName": family,
                        "displayName": name,
                    }
                },
            )
            if status == 404:
                return None
            if status >= 300:
                raise self._failure("rename the user", status, body)
        if disabled is not None and disabled != _inactive(found):
            # Zitadel refuses deactivating an inactive user (and the reverse), so
            # only a change is sent. A deactivated user cannot sign in.
            status, body, _ = self._http.request(
                "POST",
                f"{path}/{'deactivate' if disabled else 'reactivate'}",
                headers=self._org,
                json_body={},
            )
            if status == 404:
                return None
            if status >= 300:
                raise self._failure(
                    "deactivate the user" if disabled else "reactivate the user",
                    status,
                    body,
                )
        updated = self._get(subject)
        return (
            None
            if updated is None
            else self._user(updated, _email_of(updated), created=False)
        )

    def delete_user(self, subject: str) -> bool:
        status, body, _ = self._http.request(
            "DELETE", f"/v2/users/{quote(subject, safe='')}", headers=self._org
        )
        if status == 404:
            return False
        if status >= 300:
            raise self._failure("delete the user", status, body)
        return True

    # -- plumbing ---------------------------------------------------------------------

    def _get(self, subject: str) -> dict[str, Any] | None:
        status, body, _ = self._http.request(
            "GET", f"/v2/users/{quote(subject, safe='')}", headers=self._org
        )
        if status == 404:
            return None
        if (
            status != 200
            or not isinstance(body, dict)
            or not isinstance(body.get("user"), dict)
        ):
            raise self._failure("read the user", status, body)
        return body["user"]

    def _user(
        self, found: dict[str, Any], email: str, *, created: bool
    ) -> ProvisionedUser:
        profile = (found.get("human") or {}).get("profile") or {}
        return ProvisionedUser(
            provider=self._provider,
            email=email,
            subject=found.get("userId"),
            name=profile.get("displayName"),
            created=created,
            disabled=_inactive(found),
        )

    @staticmethod
    def _failure(what: str, status: int, body: Any) -> Exception:
        message = body.get("message") if isinstance(body, dict) else None
        if status == 400:
            return ValueError(f"Zitadel refused to {what}: {message or 'bad request'}")
        return ProvisioningError(
            f"Zitadel could not {what} (HTTP {status}{': ' + message if message else ''})"
        )


def _inactive(found: dict[str, Any]) -> bool:
    return found.get("state") in ("USER_STATE_INACTIVE", "USER_STATE_LOCKED")


def _email_of(found: dict[str, Any]) -> str:
    return str(((found.get("human") or {}).get("email") or {}).get("email") or "")


def _names(email: str, name: str | None) -> tuple[str, str]:
    """A given and a family name: Zitadel requires both."""
    text = (name or "").strip() or email.split("@", 1)[0].replace(".", " ").replace(
        "_", " "
    )
    parts = text.title().split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    return (parts[0] if parts else "User"), "-"
