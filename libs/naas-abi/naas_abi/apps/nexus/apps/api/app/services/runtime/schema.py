from pydantic import BaseModel


class RestartOsResponse(BaseModel):
    scheduled: bool
    mode: str
    message: str


class OsStatusResponse(BaseModel):
    dev_runtime_available: bool
    restarting: bool
    requested_at: float | None = None
