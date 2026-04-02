"""Backward-compatible secrets endpoint export."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.primary.secrets__primary_adapter__FastAPI import (  # noqa: E501
    SecretBulkImport,
    SecretCreate,
    SecretResponse,
    SecretUpdate,
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.secondary.postgres import (
    SecretsSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.service import (
    SecretsService,
    infer_secret_category,
    mask_secret_value,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import (
    decrypt_secret_value,
    encrypt_secret_value,
    try_decrypt_secret_value,
)
from sqlalchemy.ext.asyncio import AsyncSession


def deprecated_encrypt(value: str) -> str:
    return encrypt_secret_value(value)


def _encrypt(value: str) -> str:
    return deprecated_encrypt(value)


def _decrypt(encrypted_value: str) -> str:
    return decrypt_secret_value(encrypted_value)


def _try_decrypt(encrypted_value: str) -> str | None:
    return try_decrypt_secret_value(encrypted_value)


def _mask_value(value: str) -> str:
    return mask_secret_value(value)


def _infer_category(key: str) -> str:
    return infer_secret_category(key)


async def resolve_secret_async(db: AsyncSession, workspace_id: str, key: str) -> str | None:
    service = SecretsService(adapter=SecretsSecondaryAdapterPostgres(db=db))
    return await service.resolve_secret_value(
        context=RequestContext(
            token_data=TokenData(user_id="system", scopes={"*"}, is_authenticated=True)
        ),
        workspace_id=workspace_id,
        key=key,
    )


__all__ = [
    "router",
    "SecretCreate",
    "SecretUpdate",
    "SecretResponse",
    "SecretBulkImport",
    "deprecated_encrypt",
    "_encrypt",
    "_decrypt",
    "_try_decrypt",
    "_mask_value",
    "_infer_category",
    "resolve_secret_async",
]
