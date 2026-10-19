"""The built-in IdP (``naas-abi-idp``) over real HTTP in this process, and its
harness for the generic identity suite.

The provider is the real one, on in-memory adapters, mounted at ``/idp`` of a
uvicorn server on 127.0.0.1, so its issuer has the shape of a deployed one
(``http://127.0.0.1:<port>/idp``). ``sign_in`` drives its pages as a browser
would: ask for a code, read it from the mail the provider sent, enter it.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Sequence
from typing import Any, Self

import httpx

from naas_abi_core.services.identity.tests.identity_contract import TestUser


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class BuiltinIdPHarness:
    provider_name = "builtin"
    groups_claim: str | None = "groups"
    scopes: tuple[str, ...] = ("openid", "email", "profile", "groups", "offline_access")
    client_id = "abi-contract"
    client_secret: str | None = "contract-secret-contract-secret"
    redirect_uri = "http://127.0.0.1:9/callback"

    def __init__(self, redirect_uri: str | None = None) -> None:
        if redirect_uri is not None:
            self.redirect_uri = redirect_uri
        self.port = free_port()
        self.issuer = f"http://127.0.0.1:{self.port}/idp"
        self._server: Any = None
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        import uvicorn
        from naas_abi_idp.adapters.memory import (
            MemoryDocumentStore,
            MemoryMailer,
            MemorySecretStore,
        )
        from naas_abi_idp.configuration import ClientConfiguration, IdPConfiguration
        from naas_abi_idp.service import IdPService
        from naas_abi_idp.web import IdPWeb
        from starlette.applications import Starlette
        from starlette.routing import Mount

        self.mailer = MemoryMailer()
        configuration = IdPConfiguration(
            issuer=self.issuer,
            clients=[
                ClientConfiguration(
                    client_id=self.client_id,
                    secret=self.client_secret,
                    redirect_uris=[self.redirect_uri],
                ),
                ClientConfiguration(
                    client_id="other-client",
                    secret="other-secret-other-secret",
                    redirect_uris=[self.redirect_uri],
                ),
            ],
        )
        self.service = IdPService(
            MemoryDocumentStore(), MemorySecretStore(), self.mailer, configuration
        )
        self.service.seed_clients(configuration.clients)
        app = Starlette(routes=[Mount("/idp", app=IdPWeb(self.service).app())])
        self._server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning",
                lifespan="off",
            )
        )
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        deadline = time.time() + 15
        while not self._server.started:
            if time.time() > deadline:
                raise RuntimeError("The built-in IdP did not start")
            time.sleep(0.02)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=10)

    # -- IdentityProviderHarness ----------------------------------------------------

    def create_user(self, email: str, *, groups: Sequence[str] = ()) -> TestUser:
        from naas_abi_idp.ports import Conflict

        for name in groups:
            try:
                self.service.create_group(name)
            except Conflict:
                pass
        user = self.service.create_user(email, groups=list(groups))
        return TestUser(subject=user.id, email=user.email, login=user.email)

    def sign_in(self, authorization_url: str, user: TestUser) -> str:
        with httpx.Client(follow_redirects=False, timeout=10) as browser:
            page = browser.get(authorization_url)
            assert page.status_code == 200, page.text
            csrf = re.search(r'name="csrf" value="([^"]+)"', page.text)
            assert csrf, page.text
            base = f"{self.issuer}/login"
            sent = browser.post(
                f"{base}/email", data={"csrf": csrf.group(1), "email": user.login}
            )
            assert sent.status_code == 200, sent.text
            self.service.flush_mail()  # the mail leaves in the background
            done = browser.post(
                f"{base}/code",
                data={
                    "csrf": csrf.group(1),
                    "email": user.login,
                    "code": self.mailer.last_code(user.login),
                },
            )
            assert done.status_code == 302, done.text
            return done.headers["location"]

    def rotate_signing_key(self) -> None:
        self.service.keys.rotate()

    def other_client(self) -> tuple[str, str | None]:
        return "other-client", "other-secret-other-secret"
