from pydantic import BaseModel, Field


class GitHubConnectStatusResponse(BaseModel):
    module_installed: bool
    connected: bool
    oauth_available: bool


class GitHubDeviceStartResponse(BaseModel):
    session_id: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int


class GitHubDevicePollResponse(BaseModel):
    status: str
    connected: bool
    interval: int | None = None
    github_login: str | None = None
    restart_required: bool | None = None
    message: str | None = None
    detail: str | None = None


class GitHubTokenInput(BaseModel):
    token: str = Field(min_length=1)
