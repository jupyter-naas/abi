from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.secrets.port import (
    SecretRecord,
    SecretsPersistencePort,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import (
    SecretAlreadyExistsError,
    SecretBulkImportInput,
    SecretBulkImportResult,
    SecretCreateInput,
    SecretNotFoundError,
    SecretOutput,
    SecretUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import (
    decrypt_secret_value,
    encrypt_secret_value,
    try_decrypt_secret_value,
)


def mask_secret_value(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def infer_secret_category(key: str) -> str:
    key_upper = key.upper()
    if "API_KEY" in key_upper or "APIKEY" in key_upper:
        return "api_keys"
    if "TOKEN" in key_upper or "JWT" in key_upper:
        return "tokens"
    if "PASSWORD" in key_upper or "SECRET" in key_upper or "CREDENTIAL" in key_upper:
        return "credentials"
    return "other"


class SecretsService:
    def __init__(self, adapter: SecretsPersistencePort):
        self.adapter = adapter

    @staticmethod
    def encrypt(value: str) -> str:
        return encrypt_secret_value(value)

    @staticmethod
    def decrypt(encrypted_value: str) -> str:
        return decrypt_secret_value(encrypted_value)

    @staticmethod
    def try_decrypt(encrypted_value: str) -> str | None:
        return try_decrypt_secret_value(encrypted_value)

    def to_output(self, record: SecretRecord) -> SecretOutput:
        decrypted = self.try_decrypt(record.encrypted_value)
        masked = mask_secret_value(decrypted) if decrypted else "****"
        return SecretOutput(
            id=record.id,
            workspace_id=record.workspace_id,
            key=record.key,
            masked_value=masked,
            description=record.description or "",
            category=record.category,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    async def list_secrets(self, workspace_id: str) -> list[SecretOutput]:
        rows = await self.adapter.list_by_workspace(workspace_id=workspace_id)
        return [self.to_output(row) for row in rows]

    async def create_secret(self, secret: SecretCreateInput, now: datetime) -> SecretOutput:
        existing = await self.adapter.get_by_workspace_key(
            workspace_id=secret.workspace_id,
            key=secret.key,
        )
        if existing:
            raise SecretAlreadyExistsError(key=secret.key)

        row = await self.adapter.create(
            SecretRecord(
                id=str(uuid4()),
                workspace_id=secret.workspace_id,
                key=secret.key,
                encrypted_value=self.encrypt(secret.value),
                description=secret.description,
                category=secret.category or infer_secret_category(secret.key),
                created_at=now,
                updated_at=now,
            )
        )
        await self.adapter.commit()
        return SecretOutput(
            id=row.id,
            workspace_id=row.workspace_id,
            key=row.key,
            masked_value=mask_secret_value(secret.value),
            description=row.description or "",
            category=row.category,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def update_secret(
        self, secret_id: str, update: SecretUpdateInput, now: datetime
    ) -> SecretOutput:
        row = await self.adapter.get_by_id(secret_id=secret_id)
        if not row:
            raise SecretNotFoundError(secret_id=secret_id)

        row.updated_at = now
        if update.value is not None:
            row.encrypted_value = self.encrypt(update.value)
        if update.description is not None:
            row.description = update.description

        await self.adapter.save(row)
        await self.adapter.commit()
        return self.to_output(row)

    async def delete_secret(self, secret_id: str) -> None:
        deleted = await self.adapter.delete(secret_id=secret_id)
        if not deleted:
            raise SecretNotFoundError(secret_id=secret_id)
        await self.adapter.commit()

    async def bulk_import(
        self, data: SecretBulkImportInput, now: datetime
    ) -> SecretBulkImportResult:
        imported = 0
        updated = 0

        for line in data.env_content.split("\n"):
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#"):
                continue

            eq_idx = trimmed.find("=")
            if eq_idx == -1:
                continue

            key = trimmed[:eq_idx].strip()
            value = trimmed[eq_idx + 1 :].strip()

            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            if not key:
                continue

            existing = await self.adapter.get_by_workspace_key(data.workspace_id, key)
            encrypted = self.encrypt(value)

            if existing:
                existing.encrypted_value = encrypted
                existing.updated_at = now
                await self.adapter.save(existing)
                updated += 1
                continue

            await self.adapter.create(
                SecretRecord(
                    id=str(uuid4()),
                    workspace_id=data.workspace_id,
                    key=key,
                    encrypted_value=encrypted,
                    description="",
                    category=infer_secret_category(key),
                    created_at=now,
                    updated_at=now,
                )
            )
            imported += 1

        await self.adapter.commit()
        return SecretBulkImportResult(imported=imported, updated=updated)

    async def resolve_secret_value(self, workspace_id: str, key: str) -> str | None:
        row = await self.adapter.get_by_workspace_key(workspace_id=workspace_id, key=key)
        if not row:
            return None
        return self.try_decrypt(row.encrypted_value)
