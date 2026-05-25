"""Code OpenCode FastAPI primary adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__dependencies import (
    get_code_opencode_service,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__exceptions import (
    raise_http_for_code_error,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__schemas import (
    OpencodeChatRequest,
    OpencodeRevertRequest,
)
from naas_abi.apps.nexus.apps.api.app.services.code.code__schema import (
    CodeDomainError,
    CodeOpencodeChatInput,
)
from naas_abi.apps.nexus.apps.api.app.services.code.opencode_service import CodeOpencodeService
from sse_starlette.sse import EventSourceResponse

opencode_router = APIRouter(dependencies=[Depends(get_current_user_required)])


def _translate_proxy_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    status_code = exc.response.status_code if exc.response is not None else 502
    detail = exc.response.text if exc.response is not None else str(exc)
    return HTTPException(status_code=status_code, detail=detail)


@opencode_router.get("/health")
async def health(service: CodeOpencodeService = Depends(get_code_opencode_service)):
    return await service.health()


@opencode_router.get("/providers")
async def providers(service: CodeOpencodeService = Depends(get_code_opencode_service)):
    try:
        return await service.list_providers()
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.get("/default-model")
async def default_model(service: CodeOpencodeService = Depends(get_code_opencode_service)):
    try:
        result = await service.default_model()
        return {
            "providerID": result.provider_id,
            "modelID": result.model_id,
            "name": result.name,
            "source": result.source,
        }
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.get("/sessions")
async def list_sessions(service: CodeOpencodeService = Depends(get_code_opencode_service)):
    try:
        return await service.list_sessions()
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.get("/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    service: CodeOpencodeService = Depends(get_code_opencode_service),
):
    try:
        return await service.session_messages(session_id)
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    service: CodeOpencodeService = Depends(get_code_opencode_service),
):
    try:
        return await service.delete_session(session_id)
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.post("/sessions/{session_id}/abort")
async def abort_session(
    session_id: str,
    service: CodeOpencodeService = Depends(get_code_opencode_service),
):
    try:
        return await service.abort_session(session_id)
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.post("/sessions/{session_id}/revert")
async def revert_session(
    session_id: str,
    body: OpencodeRevertRequest,
    service: CodeOpencodeService = Depends(get_code_opencode_service),
):
    try:
        return await service.revert_session(session_id, message_id=body.message_id)
    except httpx.HTTPStatusError as exc:
        raise _translate_proxy_http_error(exc) from exc
    except CodeDomainError as exc:
        raise_http_for_code_error(exc)


@opencode_router.post("/chat")
async def chat(
    body: OpencodeChatRequest,
    current_user: User = Depends(get_current_user_required),
    service: CodeOpencodeService = Depends(get_code_opencode_service),
):
    input_data = CodeOpencodeChatInput(
        message=body.message,
        user_id=current_user.id,
        session_id=body.session_id,
        model_provider_id=body.model_provider_id,
        model_id=body.model_id,
        agent=body.agent,
    )

    async def _stream() -> AsyncIterator[dict]:
        async for raw_event in service.stream_chat(input_data):
            yield {"data": raw_event}

    return EventSourceResponse(_stream(), media_type="text/event-stream; charset=utf-8")
