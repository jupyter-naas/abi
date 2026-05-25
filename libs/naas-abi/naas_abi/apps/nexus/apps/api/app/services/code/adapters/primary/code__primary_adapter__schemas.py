from __future__ import annotations

from pydantic import BaseModel


class FSEntry(BaseModel):
    name: str
    path: str
    type: str
    size: int
    modified: float
    writable: bool


class FSListResponse(BaseModel):
    files: list[FSEntry]
    path: str
    sandbox_root: str


class WriteBody(BaseModel):
    content: str = ""


class RenameBody(BaseModel):
    new_path: str


class OpencodeChatRequest(BaseModel):
    message: str
    session_id: str = ""
    model_provider_id: str = ""
    model_id: str = ""
    agent: str = ""


class OpencodeRevertRequest(BaseModel):
    message_id: str = ""
