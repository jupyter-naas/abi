from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    CurrentPasswordInvalidError,
    EmailAlreadyRegisteredError,
    EmailAlreadyTakenError,
    ExpiredResetTokenError,
    InvalidCredentialsError,
    InvalidResetTokenError,
    UserNotFoundError,
)
from naas_abi.apps.nexus.apps.api.app.services.chat.chat__schema import (
    ChatForbidden,
    ChatNotFound,
    InvalidChatInput,
    ProviderUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.files.files__schema import (
    AlreadyExistsError,
    ArchiveTooLargeError,
    InvalidPathError,
    IsDirectoryError,
    NotFoundError,
    NotTextError,
    PreviewConversionError,
    PreviewUnavailableError,
    UnsupportedPreviewError,
    UploadTooLargeError,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.graph__schema import (
    GraphProtectedError,
    GraphServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMPermissionError
from naas_abi.apps.nexus.apps.api.app.services.ontology.ontology__schema import (
    OntologyFileNotFoundError,
    OntologyParseError,
    OntologyPathNotFoundError,
    OntologyServiceUnavailableError,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationDomainAlreadyExistsError,
    OrganizationMemberAlreadyExistsError,
    OrganizationPermissionError,
    OrganizationSlugAlreadyExistsError,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import (
    SecretAlreadyExistsError,
    SecretNotFoundError,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceMemberAlreadyExistsError,
    WorkspacePermissionError,
    WorkspaceSlugAlreadyExistsError,
)

DetailResolver = Callable[[Exception], str]


def _default_detail(exc: Exception) -> str:
    detail = str(exc)
    if detail:
        return detail
    return exc.__class__.__name__


EXCEPTION_TO_HTTP: dict[type[Exception], tuple[int, DetailResolver]] = {
    InvalidPathError: (400, _default_detail),
    AlreadyExistsError: (409, _default_detail),
    NotFoundError: (404, _default_detail),
    IsDirectoryError: (400, _default_detail),
    NotTextError: (400, _default_detail),
    UploadTooLargeError: (413, _default_detail),
    ArchiveTooLargeError: (413, _default_detail),
    UnsupportedPreviewError: (400, _default_detail),
    PreviewUnavailableError: (501, _default_detail),
    PreviewConversionError: (500, _default_detail),
    ChatNotFound: (404, _default_detail),
    ChatForbidden: (403, _default_detail),
    InvalidChatInput: (400, _default_detail),
    ProviderUnavailable: (503, _default_detail),
    OrganizationPermissionError: (403, lambda _exc: "You do not have access to this organization"),
    OrganizationSlugAlreadyExistsError: (400, lambda _exc: "Slug already exists"),
    OrganizationMemberAlreadyExistsError: (400, lambda _exc: "User is already a member"),
    OrganizationDomainAlreadyExistsError: (400, lambda _exc: "Domain already registered"),
    WorkspacePermissionError: (403, lambda _exc: "You do not have access to this workspace"),
    WorkspaceSlugAlreadyExistsError: (400, lambda _exc: "Slug already exists"),
    WorkspaceMemberAlreadyExistsError: (400, lambda _exc: "User is already a member"),
    GraphProtectedError: (400, _default_detail),
    GraphServiceUnavailableError: (500, _default_detail),
    OntologyPathNotFoundError: (404, _default_detail),
    OntologyServiceUnavailableError: (500, _default_detail),
    OntologyParseError: (500, lambda _: "Failed to parse ontology file"),
    OntologyFileNotFoundError: (404, lambda _: "Ontology file does not exist"),
    IAMPermissionError: (403, _default_detail),
    SecretAlreadyExistsError: (400, lambda _exc: "Secret with this key already exists"),
    SecretNotFoundError: (404, lambda _exc: "Secret not found"),
    EmailAlreadyRegisteredError: (400, lambda _exc: "Email already registered"),
    EmailAlreadyTakenError: (400, lambda _exc: "Email already taken"),
    UserNotFoundError: (404, lambda _exc: "User not found"),
    InvalidCredentialsError: (401, lambda _exc: "Invalid email or password"),
    CurrentPasswordInvalidError: (401, lambda _exc: "Current password is incorrect"),
    InvalidResetTokenError: (400, lambda _exc: "Invalid or expired reset token"),
    ExpiredResetTokenError: (400, lambda _exc: "Reset token has expired"),
}


def _resolve_exception_mapping(exc: Exception) -> tuple[int, str] | None:
    for exception_type, (status_code, detail_resolver) in EXCEPTION_TO_HTTP.items():
        if isinstance(exc, exception_type):
            return status_code, detail_resolver(exc)
    return None


async def service_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    mapping = _resolve_exception_mapping(exc)
    if mapping is None:
        raise exc
    status_code, detail = mapping
    return JSONResponse(status_code=status_code, content={"detail": detail})


def register_service_exception_handlers(app: FastAPI) -> None:
    for exception_type in EXCEPTION_TO_HTTP:
        app.add_exception_handler(exception_type, service_exception_handler)
