from pydantic import BaseModel, Field


class GitHubConnectStatusResponse(BaseModel):
    module_installed: bool
    connected: bool
    oauth_available: bool
    app_available: bool = False
    app_slug: str | None = None
    installation_id: str | None = None
    account_login: str | None = None
    auth_mode: str | None = None
    github_login: str | None = None
    agent_name: str = "GitHub"
    ready: bool = False


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


class GitHubAppInstallStartRequest(BaseModel):
    return_to: str | None = None
    workspace_id: str | None = None


class GitHubAppInstallStartResponse(BaseModel):
    install_url: str
    state: str
    app_slug: str | None = None
    expires_in: int
