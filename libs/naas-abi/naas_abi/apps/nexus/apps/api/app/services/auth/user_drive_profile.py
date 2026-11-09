"""Keep a user's profile files in their own drive in step with the database.

``naas_abi/my-drive/<user_id>/``:

- ``.settings/user/user.json``: the account (Account Settings > Profile), as stored.
- ``.settings/user/org_member.json``: their organization memberships (the role IAM
  holds, and the member profile set by org admins in Organization Settings > Users).
- ``.USER.md``: a readable summary built from the two files and the picture URL,
  with account values filled from member profiles where the account has none
  (``account_fallbacks``, org -> account only).

The JSON files keep previous versions in ``.settings/user/archives/``
(``drive_settings``); ``.USER.md`` is rebuilt in place. The database is the
source of truth: callers run ``sync_user_drive_profile`` after a change, and a
storage failure is logged, never raised (``sync_user_drive_profile_safely``).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import drive_settings, user_settings_store
from naas_abi.apps.nexus.apps.api.app.services.auth.account_fallbacks import (
    FALLBACK_FIELDS,
    effective_account_values,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    my_drive_root,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions as StorageExceptions,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

ORG_MEMBER_KEY = "org_member.json"
USER_MD_KEY = ".USER.md"
SCHEMA_VERSION = 1

ROLE_LABELS = {"owner": "Owner", "admin": "Admin", "member": "Member"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def load_memberships(db: AsyncSession, user_id: str) -> list[dict[str, Any]]:
    """The user's organizations with their member profile, oldest first. The role is
    the one IAM holds (``services/iam/memberships``); the profile is what the
    organization set, if anything."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

    roles = await MEMBERSHIPS.scopes_of(user_id, level="org")
    if not roles:
        return []
    organizations = {
        org.id: org
        for org in (
            await db.execute(select(OrganizationModel).where(OrganizationModel.id.in_(roles)))
        )
        .scalars()
        .all()
    }
    profiles = {
        member.organization_id: member
        for member in (
            await db.execute(
                select(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user_id)
            )
        )
        .scalars()
        .all()
    }
    found = []
    for org_id, role in roles.items():
        organization = organizations.get(org_id)
        if organization is None:
            continue
        member = profiles.get(org_id)
        found.append(
            (
                member.created_at if member is not None else None,
                {
                    "organization_id": org_id,
                    "organization_name": organization.name,
                    "organization_slug": organization.slug,
                    "role": role,
                    "member_since": _iso(member.created_at) if member is not None else None,
                    "profile": {
                        "avatar": member.avatar if member else None,
                        "organization": member.organization_name if member else None,
                        "job_title": member.job_title if member else None,
                        "service_line": member.service_line if member else None,
                        "country": member.country if member else None,
                        "interest": member.interest if member else None,
                        "bio": member.bio if member else None,
                    },
                },
            )
        )
    found.sort(
        key=lambda item: (item[0] is None, item[0] or datetime.min, item[1]["organization_id"])
    )
    return [membership for _, membership in found]


def org_member_document(user_id: str, memberships: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "user_id": user_id, "memberships": memberships}


def _line(label: str, value: Any) -> str | None:
    return f"- **{label}:** {value}" if value not in (None, "") else None


def build_user_md(user_doc: dict[str, Any], org_doc: dict[str, Any]) -> str:
    """Readable profile: the account (with org fallbacks) and each membership."""
    account = user_doc["user"]
    memberships = org_doc["memberships"]
    effective = effective_account_values(account, [m["profile"] for m in memberships])
    sources = {
        field: "organization" if not account.get(field) and effective.get(field) else "account"
        for field in FALLBACK_FIELDS
    }

    def shown(field: str) -> Any:
        value = effective.get(field)
        if value and sources[field] == "organization":
            return f"{value} (from organization profile)"
        return value

    lines = [f"# {account.get('name') or account.get('email')}", ""]
    lines += [
        line
        for line in (
            _line("Email", account.get("email")),
            _line("Organization", shown("organization")),
            _line("Job title", shown("job_title")),
            _line("Avatar", shown("avatar")),
            _line("Platform superadmin", "yes" if account.get("is_superadmin") else None),
            _line("Account created", account.get("created_at")),
        )
        if line
    ]
    if account.get("bio"):
        lines += ["", "## Bio", "", account["bio"]]

    lines += ["", "## Organizations", ""]
    if not memberships:
        lines.append("_No organization._")
    for membership in memberships:
        profile = membership["profile"]
        role = ROLE_LABELS.get(membership["role"], membership["role"])
        lines += [f"### {membership['organization_name']} ({role})", ""]
        lines += [
            line
            for line in (
                _line("Organization", profile.get("organization")),
                _line("Job title", profile.get("job_title")),
                _line("Service line", profile.get("service_line")),
                _line("Country", profile.get("country")),
                _line("Interest", profile.get("interest")),
                _line("Avatar", profile.get("avatar")),
                _line("Member since", membership.get("member_since")),
            )
            if line
        ]
        if profile.get("bio"):
            lines += ["", profile["bio"]]
        lines.append("")
    lines += [
        "",
        "_Generated from .settings/user/user.json and .settings/user/org_member.json._",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _write_if_changed(storage: ObjectStorageService, prefix: str, key: str, content: bytes) -> bool:
    try:
        if storage.get_object(prefix, key) == content:
            return False
    except StorageExceptions.ObjectNotFound:
        pass
    storage.put_object(prefix, key, content)
    return True


async def sync_user_drive_profile(
    db: AsyncSession, storage: ObjectStorageService, user_id: str, now: datetime
) -> bool:
    """Rewrite user.json, org_member.json and .USER.md; False if the user is gone."""
    user = (await db.execute(select(UserModel).where(UserModel.id == user_id))).scalar_one_or_none()
    if user is None:
        return False
    user_doc = user_settings_store.user_settings_document(user)  # type: ignore[arg-type]
    org_doc = org_member_document(user_id, await load_memberships(db, user_id))
    user_settings_store.save_user_settings(storage, user, now)  # type: ignore[arg-type]
    drive_settings.save_versioned(
        storage,
        user_id,
        user_settings_store.SECTION,
        ORG_MEMBER_KEY,
        drive_settings.encode_json(org_doc),
        now,
    )
    _write_if_changed(
        storage, my_drive_root(user_id), USER_MD_KEY, build_user_md(user_doc, org_doc).encode()
    )
    return True


async def sync_user_drive_profile_safely(
    db: AsyncSession, storage: ObjectStorageService, user_id: str, now: datetime
) -> None:
    try:
        await sync_user_drive_profile(db, storage, user_id, now)
    except Exception as exc:  # noqa: BLE001 - the database change already succeeded
        logger.warning("Could not write profile files to the drive of %s: %s", user_id, exc)
