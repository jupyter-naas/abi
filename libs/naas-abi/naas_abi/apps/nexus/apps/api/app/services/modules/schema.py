from pydantic import BaseModel


class ModuleInfo(BaseModel):
    module_path: str
    name: str
    description: str
    logo_url: str | None = None
    category: str  # "core" | "ai" | "application" | "domain"
    installed: bool


class ModulesResponse(BaseModel):
    installed: list[ModuleInfo]
    available: list[ModuleInfo]
