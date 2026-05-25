from __future__ import annotations

from fastapi import HTTPException, status
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeDomainError,
    CodeFilesystemOSError,
    CodeOpencodeUnavailableError,
    CodePathAlreadyExistsError,
    CodePathNotDirectoryError,
    CodePathNotFileError,
    CodePathNotFoundError,
    CodePathOutsideRootError,
    CodeWriteForbiddenError,
)


def raise_http_for_code_error(exc: CodeDomainError) -> None:
    if isinstance(exc, CodePathOutsideRootError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, CodePathNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, (CodePathNotDirectoryError, CodePathNotFileError)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if isinstance(exc, CodeWriteForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, CodePathAlreadyExistsError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if isinstance(exc, CodeOpencodeUnavailableError):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if isinstance(exc, CodeFilesystemOSError):
        status_code = (
            status.HTTP_403_FORBIDDEN
            if "Permission" in str(exc)
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
