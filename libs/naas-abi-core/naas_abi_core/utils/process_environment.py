"""The environment of a process the engine starts for someone else.

A workspace runtime or a coding harness gets an allow-list of the engine's
variables (where to find programs, the locale, the terminal, the network's
proxies and certificate authorities), never the engine's whole environment:
its keys, database URLs and service credentials stay with the engine.

Proxy URLs pass without their user information: a proxy that needs
credentials gets them for that process through ``extra``, never the engine's.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

PASSED_VARIABLES = (
    "PATH",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "TZ",
    # Certificate authorities (a private CA): paths, no secret.
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "NO_PROXY",
    "no_proxy",
)

# Proxies: passed without their user information.
PROXY_VARIABLES = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def without_userinfo(url: str) -> str:
    """``url`` without a ``user:password@`` before its host."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        scheme, rest = "", url
    authority, slash, path = rest.partition("/")
    if "@" in authority:
        authority = authority.rsplit("@", 1)[1]
    return f"{scheme}{sep}{authority}{slash}{path}"


def allowed_environment(
    *, home: str | None = None, extra: Mapping[str, str] | None = None
) -> dict[str, str]:
    """The allow-listed variables, then ``extra``.

    With ``home``, the process gets its own home and XDG directories under it,
    so what it reads and writes there (configuration, credentials, caches) is
    its own; without, it keeps the engine's ``HOME``.
    """
    env = {name: os.environ[name] for name in PASSED_VARIABLES if name in os.environ}
    for name in PROXY_VARIABLES:
        if os.environ.get(name):
            env[name] = without_userinfo(os.environ[name])
    env.setdefault("PATH", os.defpath)
    if home is not None:
        env["HOME"] = home
        env["XDG_CONFIG_HOME"] = os.path.join(home, ".config")
        env["XDG_DATA_HOME"] = os.path.join(home, ".local", "share")
        env["XDG_STATE_HOME"] = os.path.join(home, ".local", "state")
        env["XDG_CACHE_HOME"] = os.path.join(home, ".cache")
    elif "HOME" in os.environ:
        env["HOME"] = os.environ["HOME"]
    env.update(extra or {})
    return env
