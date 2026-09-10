"""Reads the running platform configuration for the identity graph.

Two sources: the naas_abi module configuration (``abi_agent_model``, ...) and
the resolved Nexus ``Settings`` (``nexus_config``). Sections that have their
own classes in the ontology (users, organizations, feature flags, tenant) are
typed; everything else becomes a ``nexus:ConfigurationSetting``.

Values here are already resolved from ``{{ secret.* }}`` templates, so secrets
are dropped by key and credentials are stripped from URLs before anything
leaves this adapter.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from naas_abi.apps.nexus.apps.api.app.services.identity_graph.port import (
    IdentityWorkspaceSeed,
    PlatformConfigurationSourcePort,
    PlatformSnapshot,
)
from naas_abi_core import logger

# Any key matching this is dropped, value unseen. Deliberately broad: a
# duration like access_token_expire_minutes is a fair price for never
# publishing a token.
_SECRET_KEY = re.compile(
    r"(secret|password|passwd|token|api_?key|credential|private|signing|database_url|dsn|smtp_pass)",
    re.IGNORECASE,
)
_URL_WITH_USERINFO = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@\s]+@")

# Modelled by dedicated ontology classes rather than as flat settings.
_TYPED_NEXUS_SECTIONS = {"users", "organizations", "feature_flags", "tenant"}


def _strip_userinfo(value: str) -> str:
    if not _URL_WITH_USERINFO.match(value):
        return value
    parts = urlsplit(value)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def _as_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def flatten_settings(values: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested dicts to dotted keys; lists become JSON. Secrets dropped."""
    out: dict[str, str] = {}
    for key, value in values.items():
        dotted = f"{prefix}{key}"
        if _SECRET_KEY.search(str(key)) or value is None:
            continue
        if isinstance(value, dict):
            out.update(flatten_settings(value, f"{dotted}."))
            continue
        text = _as_text(value)
        if isinstance(value, str):
            text = _strip_userinfo(text)
        out[dotted] = text
    return out


def _dump(model: Any) -> dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return dict(model)


def _host_of(url: str | None) -> str:
    if not url:
        return "unknown"
    return urlsplit(url).hostname or url


class PlatformConfigurationSourceSettings(PlatformConfigurationSourcePort):
    def __init__(
        self,
        settings_getter: Callable[[], Any],
        module_config_getter: Callable[[], Any],
        clock: Callable[[], datetime.datetime] = lambda: datetime.datetime.now(datetime.UTC),
    ):
        self._settings_getter = settings_getter
        self._module_config_getter = module_config_getter
        self._clock = clock

    def load_platform(self) -> PlatformSnapshot | None:
        try:
            settings = _dump(self._settings_getter())
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[identity-graph] Nexus settings unavailable: {exc}")
            return None
        try:
            module = _dump(self._module_config_getter())
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[identity-graph] naas_abi module configuration unavailable: {exc}")
            module = {}

        flags = settings.get("feature_flags") or {}
        nexus_flat = {k: v for k, v in settings.items() if k not in _TYPED_NEXUS_SECTIONS}
        module_flat = {k: v for k, v in module.items() if k != "nexus_config"}
        flat = flatten_settings(module_flat)
        flat.update(flatten_settings(nexus_flat, "nexus_config."))

        seeds: dict[str, IdentityWorkspaceSeed] = {}
        for organization in settings.get("organizations") or []:
            for workspace in organization.get("workspaces") or []:
                if workspace.get("slug"):
                    seeds[workspace["slug"]] = IdentityWorkspaceSeed(
                        default_agent=workspace.get("default_agent"),
                        agents=list(workspace.get("agents") or []),
                        apps=list(workspace.get("apps") or []),
                        ontologies=list(workspace.get("ontologies") or []),
                    )

        return PlatformSnapshot(
            host=_host_of(settings.get("frontend_url")),
            applied_at=self._clock(),
            enabled_features=list(flags.get("enabled_features") or []),
            role_baseline={k: list(v) for k, v in (flags.get("role_baseline") or {}).items()},
            workspace_overrides={
                k: dict(v) for k, v in (flags.get("workspace_overrides") or {}).items()
            },
            organization_overrides={
                org: {role: list(features) for role, features in roles.items()}
                for org, roles in (flags.get("organization_overrides") or {}).items()
            },
            tenant={
                k: v for k, v in (settings.get("tenant") or {}).items() if not _SECRET_KEY.search(k)
            },
            settings=flat,
            credential_storage_by_email={
                str(user["email"]).lower(): bool(user.get("store_credentials_in_secrets", True))
                for user in settings.get("users") or []
                if user.get("email")
            },
            workspace_seeds=seeds,
        )
