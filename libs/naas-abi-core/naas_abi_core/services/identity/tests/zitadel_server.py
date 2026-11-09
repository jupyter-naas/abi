"""Zitadel, the external reference identity provider, from pinned native binaries.

No Docker: the helper downloads Zitadel's release binary and PostgreSQL's
(Zonky's embedded-postgres builds, which Zitadel needs), checks their SHA-256,
unpacks them once into ``$ABI_TEST_BINARIES_DIR`` (default
``~/.cache/naas-abi/test-binaries``), then runs PostgreSQL on a free port and
``zitadel start-from-init`` against it. A first instance comes with an admin
machine user and a login client, both with personal access tokens.

``ZitadelHarness`` implements ``IdentityProviderHarness`` on it: a project and
a confidential web app with PKCE, users with passwords, project roles as
groups (claim ``urn:zitadel:iam:org:project:roles``), sign-in through the
Session API as Zitadel's own login UI does it, and key rotation through the
web keys API.

    python -m naas_abi_core.services.identity.tests.zitadel_server --fetch

downloads the binaries ahead of a test run (CI caches the directory).
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import platform
import secrets
import shutil
import socket
import subprocess
import tarfile
import time
import zipfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Self
from urllib.parse import parse_qs, urlsplit

import httpx

from naas_abi_core.services.identity.tests.identity_contract import TestUser

ZITADEL_VERSION = "v4.19.4"
POSTGRES_VERSION = "17.6.0"

# platform -> SHA-256 of zitadel-<platform>.tar.gz
_ZITADEL_SHA256 = {
    "linux-amd64": "d61fab2133c546261ea90cd43d2f7b4a5890bc4f9b5407930da1973626c47423",
    "linux-arm64": "ef7d1ff1f2632cd0cadb9c6d4cb0c2b19045f4599261a5d0df4a654f5175e989",
    "darwin-arm64": "25e01928885d4a4a64a1157902809528337a78374ba94f390fd0ef8892149f3f",
    "darwin-amd64": "5e0bc417311c118e5d78fad150388916edd7f95d506ffb6e24f7f481b9b6dc69",
}
# platform -> (Zonky artifact suffix, SHA-256 of the jar)
_POSTGRES = {
    "linux-amd64": (
        "linux-amd64",
        "23da5a044b4fb7a5a081a45008c95749c873305328d73f86aefd56922ce1d29d",
    ),
    "linux-arm64": (
        "linux-arm64v8",
        "84427ea54a5238247924ef3b0f940e7d027e58760f19d7325242e50d22fa014a",
    ),
    "darwin-arm64": (
        "darwin-arm64v8",
        "e87ee36767dee4f00f829d7a52e4a216e2fdebe5934c5683730940aabe570721",
    ),
    "darwin-amd64": (
        "darwin-amd64",
        "f1d6d39896ca48e65d6dbcb492d809df0d4952c65299de8af6e08d2208eae3e0",
    ),
}
_ZITADEL_URL = "https://github.com/zitadel/zitadel/releases/download/{version}/zitadel-{platform}.tar.gz"
_POSTGRES_URL = (
    "https://repo1.maven.org/maven2/io/zonky/test/postgres/"
    "embedded-postgres-binaries-{arch}/{version}/"
    "embedded-postgres-binaries-{arch}-{version}.jar"
)
ROLES_CLAIM = "urn:zitadel:iam:org:project:roles"


class BinariesUnavailable(RuntimeError):
    """The pinned binaries cannot be had here (platform, network)."""


def cache_dir() -> Path:
    configured = os.environ.get("ABI_TEST_BINARIES_DIR")
    root = (
        Path(configured)
        if configured
        else Path.home() / ".cache/naas-abi/test-binaries"
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "arm64": "arm64",
        "aarch64": "arm64",
    }.get(machine)
    key = f"{system}-{arch}"
    if key not in _ZITADEL_SHA256:
        raise BinariesUnavailable(f"No pinned Zitadel build for {system} {machine}")
    return key


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """One process unpacks at a time (pytest-xdist workers, parallel jobs)."""
    with path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _download(url: str, sha256: str, target: Path) -> None:
    partial = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
            response.raise_for_status()
            with partial.open("wb") as out:
                for chunk in response.iter_bytes(1 << 20):
                    digest.update(chunk)
                    out.write(chunk)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise BinariesUnavailable(f"Cannot download {url}: {exc}") from exc
    if digest.hexdigest() != sha256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"{url}: SHA-256 {digest.hexdigest()} is not the pinned {sha256}"
        )
    partial.rename(target)


def _checked_members(
    archive: tarfile.TarFile, destination: Path
) -> list[tarfile.TarInfo]:
    """Every member, once none escapes ``destination`` (by path or by link)."""
    root = destination.resolve()
    members = archive.getmembers()
    for member in members:
        target = (root / member.name).resolve()
        if not target.is_relative_to(root):
            raise RuntimeError(f"Archive member escapes its directory: {member.name}")
        if member.issym() or member.islnk():
            linked = (target.parent / member.linkname).resolve()
            if not linked.is_relative_to(root):
                raise RuntimeError(f"Archive link escapes its directory: {member.name}")
        if member.isdev():
            raise RuntimeError(f"Archive holds a device file: {member.name}")
    return members


def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    archive.extractall(destination, members=_checked_members(archive, destination))


def fetch_zitadel() -> Path:
    """The pinned Zitadel binary, downloaded and checked on first use."""
    key = platform_key()
    root = cache_dir() / f"zitadel-{ZITADEL_VERSION}-{key}"
    binary = root / f"zitadel-{key}" / "zitadel"
    if binary.exists():
        return binary
    with _locked(cache_dir() / ".zitadel.lock"):
        if binary.exists():
            return binary
        archive = cache_dir() / f"zitadel-{ZITADEL_VERSION}-{key}.tar.gz"
        if not archive.exists():
            _download(
                _ZITADEL_URL.format(version=ZITADEL_VERSION, platform=key),
                _ZITADEL_SHA256[key],
                archive,
            )
        staging = root.with_name(root.name + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        with tarfile.open(archive) as tar:
            _safe_extract(tar, staging)
        staging.rename(root)
        archive.unlink()
    return binary


def fetch_postgres() -> Path:
    """The pinned PostgreSQL install (``bin/initdb``, ``bin/pg_ctl``...)."""
    key = platform_key()
    arch, sha256 = _POSTGRES[key]
    root = cache_dir() / f"postgres-{POSTGRES_VERSION}-{key}"
    if (root / "bin" / "pg_ctl").exists():
        return root
    with _locked(cache_dir() / ".postgres.lock"):
        if (root / "bin" / "pg_ctl").exists():
            return root
        jar = cache_dir() / f"postgres-{POSTGRES_VERSION}-{key}.jar"
        if not jar.exists():
            _download(
                _POSTGRES_URL.format(arch=arch, version=POSTGRES_VERSION), sha256, jar
            )
        staging = root.with_name(root.name + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        with zipfile.ZipFile(jar) as archive:
            (name,) = [n for n in archive.namelist() if n.endswith(".txz")]
            with (
                archive.open(name) as packed,
                tarfile.open(fileobj=packed, mode="r:xz") as tar,
            ):
                _safe_extract(tar, staging)
        staging.rename(root)
        jar.unlink()
    return root


def fetch() -> tuple[Path, Path]:
    return fetch_zitadel(), fetch_postgres()


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(
    predicate, timeout: float, what: str, process: subprocess.Popen | None = None
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"{what}: the process exited with {process.returncode}")
        try:
            if predicate():
                return
        except Exception:  # noqa: BLE001, S110 - not up yet
            pass
        time.sleep(0.25)
    raise TimeoutError(f"{what} did not come up within {timeout:.0f}s")


class ZitadelServer:
    """PostgreSQL and Zitadel, in a work directory of their own."""

    admin_password = "Admin-Pass-1!"

    def __init__(self, workdir: Path | None = None) -> None:
        self.workdir = workdir or cache_dir() / "runs" / secrets.token_hex(6)
        self._owns_workdir = workdir is None
        self.port = _free_port()
        self.pg_port = _free_port()
        self._zitadel: subprocess.Popen | None = None
        self._pg_ctl: Path | None = None
        self.admin_token = ""
        self.login_token = ""

    @property
    def issuer(self) -> str:
        return f"http://localhost:{self.port}"

    def start(self) -> Self:
        binary, postgres = fetch()
        self.workdir.mkdir(parents=True, exist_ok=True)
        try:
            self._start_postgres(postgres)
            self._start_zitadel(binary)
        except BaseException:
            self.stop()
            raise
        return self

    def _start_postgres(self, postgres: Path) -> None:
        data = self.workdir / "pgdata"
        self._pg_ctl = postgres / "bin" / "pg_ctl"
        subprocess.run(
            [
                str(postgres / "bin" / "initdb"),
                "-D",
                str(data),
                "-U",
                "postgres",
                "-A",
                "trust",
                "-E",
                "UTF8",
                "--locale=C",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                str(self._pg_ctl),
                "-D",
                str(data),
                "-l",
                str(self.workdir / "postgres.log"),
                "-o",
                f"-p {self.pg_port} -c listen_addresses=127.0.0.1 -c unix_socket_directories=''",
                "-w",
                "start",
            ],
            check=True,
            capture_output=True,
        )

    def _start_zitadel(self, binary: Path) -> None:
        config = self.workdir / "zitadel.yaml"
        config.write_text(
            f"""Log:
  Level: warn
Port: {self.port}
ExternalDomain: localhost
ExternalPort: {self.port}
ExternalSecure: false
TLS:
  Enabled: false
Database:
  postgres:
    Host: 127.0.0.1
    Port: {self.pg_port}
    Database: zitadel
    MaxOpenConns: 10
    MaxIdleConns: 5
    User:
      Username: zitadel
      Password: zitadel
      SSL:
        Mode: disable
    Admin:
      Username: postgres
      Password: ""
      SSL:
        Mode: disable
"""
        )
        admin_pat = self.workdir / "admin.pat"
        login_pat = self.workdir / "login.pat"
        steps = self.workdir / "steps.yaml"
        steps.write_text(
            f"""FirstInstance:
  PatPath: {admin_pat}
  LoginClientPatPath: {login_pat}
  Org:
    Name: abi-test
    Human:
      UserName: zitadel-admin
      Email:
        Address: admin@abi.test
        Verified: true
      Password: {self.admin_password}
      PasswordChangeRequired: false
    Machine:
      Machine:
        Username: abi-admin
        Name: abi-admin
      Pat:
        ExpirationDate: 2099-01-01T00:00:00Z
    LoginClient:
      Machine:
        Username: login-client
        Name: login-client
      Pat:
        ExpirationDate: 2099-01-01T00:00:00Z
"""
        )
        log = (self.workdir / "zitadel.log").open("w")
        self._zitadel = subprocess.Popen(
            [
                str(binary),
                "start-from-init",
                "--config",
                str(config),
                "--steps",
                str(steps),
                "--masterkey",
                secrets.token_hex(16),
                "--tlsMode",
                "disabled",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            cwd=self.workdir,
        )
        _wait(
            lambda: (
                httpx.get(f"{self.issuer}/debug/ready", timeout=2).status_code == 200
            ),
            180,
            "Zitadel",
            self._zitadel,
        )
        _wait(lambda: admin_pat.exists() and login_pat.exists(), 30, "Zitadel tokens")
        self.admin_token = admin_pat.read_text().strip()
        self.login_token = login_pat.read_text().strip()
        # /debug/ready answers before the API behind the gateway does.
        _wait(
            lambda: (
                httpx.get(
                    f"{self.issuer}/admin/v1/settings/oidc",
                    headers={"Authorization": f"Bearer {self.admin_token}"},
                    timeout=5,
                ).status_code
                == 200
            ),
            60,
            "Zitadel's API",
            self._zitadel,
        )

    def stop(self) -> None:
        if self._zitadel is not None and self._zitadel.poll() is None:
            self._zitadel.terminate()
            try:
                self._zitadel.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self._zitadel.kill()
        self._zitadel = None
        data = self.workdir / "pgdata"
        if self._pg_ctl is not None and data.exists():
            subprocess.run(
                [str(self._pg_ctl), "-D", str(data), "-m", "fast", "-w", "stop"],
                check=False,
                capture_output=True,
            )
        if self._owns_workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    # -- APIs -------------------------------------------------------------------

    def api(
        self, method: str, path: str, body: Any = None, *, token: str | None = None
    ) -> Any:
        response = httpx.request(
            method,
            f"{self.issuer}{path}",
            json=body,
            headers={"Authorization": f"Bearer {token or self.admin_token}"},
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Zitadel {method} {path}: {response.status_code} {response.text}"
            )
        return response.json() if response.content else {}


class ZitadelHarness:
    """``IdentityProviderHarness`` on a running ``ZitadelServer``."""

    provider_name = "zitadel"
    groups_claim: str | None = ROLES_CLAIM
    scopes: tuple[str, ...] = ("openid", "email", "profile", "offline_access")
    password = "User-Pass-123!"

    def __init__(
        self, server: ZitadelServer, redirect_uri: str = "http://localhost:9/callback"
    ) -> None:
        self.server = server
        self.redirect_uri = redirect_uri
        self.issuer = server.issuer
        # Ten-minute tokens, as ABI expects of every provider.
        server.api(
            "PUT",
            "/admin/v1/settings/oidc",
            {
                "accessTokenLifetime": "600s",
                "idTokenLifetime": "600s",
                "refreshTokenIdleExpiration": "86400s",
                "refreshTokenExpiration": "604800s",
            },
        )
        self.project_id = self._project("abi")
        self.client_id, self.client_secret = self.add_client(
            self.project_id, [redirect_uri]
        )
        self._roles: set[str] = set()

    def _project(self, name: str) -> str:
        return self.server.api(
            "POST",
            "/management/v1/projects",
            {"name": f"{name}-{secrets.token_hex(3)}", "projectRoleAssertion": True},
        )["id"]

    def add_client(
        self, project_id: str, redirect_uris: Sequence[str]
    ) -> tuple[str, str]:
        app = self.server.api(
            "POST",
            f"/management/v1/projects/{project_id}/apps/oidc",
            {
                "name": f"nexus-{secrets.token_hex(3)}",
                "redirectUris": list(redirect_uris),
                "postLogoutRedirectUris": list(redirect_uris),
                "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
                "grantTypes": [
                    "OIDC_GRANT_TYPE_AUTHORIZATION_CODE",
                    "OIDC_GRANT_TYPE_REFRESH_TOKEN",
                ],
                "appType": "OIDC_APP_TYPE_WEB",
                "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
                "devMode": True,
                "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
                "idTokenUserinfoAssertion": True,
                "idTokenRoleAssertion": True,
                "accessTokenRoleAssertion": True,
            },
        )
        return app["clientId"], app["clientSecret"]

    def allow_redirect_uri(self, redirect_uri: str) -> None:
        """Add a redirect URI to the main client (a Nexus test server's)."""
        apps = self.server.api(
            "POST", f"/management/v1/projects/{self.project_id}/apps/_search", {}
        )["result"]
        (app,) = [
            a for a in apps if a.get("oidcConfig", {}).get("clientId") == self.client_id
        ]
        oidc = app["oidcConfig"]
        uris = sorted({*oidc.get("redirectUris", []), redirect_uri})
        self.server.api(
            "PUT",
            f"/management/v1/projects/{self.project_id}/apps/{app['id']}/oidc_config",
            {
                "redirectUris": uris,
                "postLogoutRedirectUris": uris,
                "responseTypes": oidc["responseTypes"],
                "grantTypes": oidc["grantTypes"],
                "appType": oidc["appType"],
                "authMethodType": oidc["authMethodType"],
                "devMode": True,
                "accessTokenType": oidc["accessTokenType"],
                "idTokenUserinfoAssertion": True,
                "idTokenRoleAssertion": True,
                "accessTokenRoleAssertion": True,
            },
        )

    # -- IdentityProviderHarness ------------------------------------------------

    def create_user(self, email: str, *, groups: Sequence[str] = ()) -> TestUser:
        local = email.split("@")[0]
        created = self.server.api(
            "POST",
            "/v2/users/human",
            {
                "username": email,
                "profile": {"givenName": local.title(), "familyName": "Test"},
                "email": {"email": email, "isVerified": True},
                "password": {"password": self.password, "changeRequired": False},
            },
        )
        user = TestUser(
            subject=created["userId"], email=email, login=email, password=self.password
        )
        if groups:
            self.set_groups(user, groups)
        return user

    def set_groups(self, user: TestUser, groups: Sequence[str]) -> None:
        for role in groups:
            if role not in self._roles:
                self.server.api(
                    "POST",
                    f"/management/v1/projects/{self.project_id}/roles",
                    {"roleKey": role, "displayName": role},
                )
                self._roles.add(role)
        self.server.api(
            "POST",
            f"/management/v1/users/{user.subject}/grants",
            {"projectId": self.project_id, "roleKeys": list(groups)},
        )

    def sign_in(self, authorization_url: str, user: TestUser) -> str:
        """What Zitadel's login UI does: a session checked with the user's
        password, then the authorization request finalized with it."""
        response = httpx.get(authorization_url, follow_redirects=False, timeout=30)
        if response.status_code != 302:
            raise AssertionError(
                f"authorize answered {response.status_code}: {response.text}"
            )
        query = parse_qs(urlsplit(response.headers["location"]).query)
        if "authRequest" not in query:
            # An error, or a callback straight away: hand it back.
            return response.headers["location"]
        auth_request = query["authRequest"][0]
        session = self.server.api(
            "POST",
            "/v2/sessions",
            {
                "checks": {
                    "user": {"loginName": user.login},
                    "password": {"password": user.password or self.password},
                }
            },
            token=self.server.login_token,
        )
        finalized = self.server.api(
            "POST",
            f"/v2/oidc/auth_requests/{auth_request}",
            {
                "session": {
                    "sessionId": session["sessionId"],
                    "sessionToken": session["sessionToken"],
                }
            },
            token=self.server.login_token,
        )
        return finalized["callbackUrl"]

    def rotate_signing_key(self) -> None:
        key = self.server.api(
            "POST", "/v2beta/web_keys", {"ecdsa": {"curve": "ECDSA_CURVE_P256"}}
        )
        self.server.api("POST", f"/v2beta/web_keys/{key['id']}/activate", {})

    def other_client(self) -> tuple[str, str | None]:
        return self.add_client(self._project("other"), [self.redirect_uri])


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fetch", action="store_true", help="download the pinned binaries"
    )
    if parser.parse_args().fetch:
        zitadel, postgres = fetch()
        print(f"zitadel: {zitadel}\npostgres: {postgres}")
