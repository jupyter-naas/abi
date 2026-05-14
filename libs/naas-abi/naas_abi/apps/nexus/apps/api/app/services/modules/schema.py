from pydantic import BaseModel


class ModuleInfo(BaseModel):
    module_path: str
    name: str
    description: str
    logo_url: str | None = None
    category: str  # "core" | "ai" | "application" | "domain"
    installed: bool
    model: str | None = None
    slug: str | None = None
    agent_type: str | None = None
    system_prompt_preview: str | None = None
    functional: bool = True


class ModulesResponse(BaseModel):
    installed: list[ModuleInfo]
    available: list[ModuleInfo]
