"""
Public tenant configuration endpoint.

Returns branding values (tab title, favicon) configured in config.yaml
so the frontend can apply them without authentication.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from naas_abi.apps.nexus.apps.api.app.core.config import settings

router = APIRouter()


class TenantResponse(BaseModel):
    tab_title: str
    favicon_url: str | None = None
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str
    accent_color: str
    background_color: str
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str
    login_card_padding: str
    login_card_color: str
    login_text_color: str | None = None
    login_input_color: str
    login_border_radius: str
    login_bg_image_url: str | None = None
    show_terms_footer: bool
    show_powered_by: bool
    login_footer_text: str | None = None


@router.get("", response_model=TenantResponse)
async def get_tenant_config() -> TenantResponse:
    """Public endpoint — no auth required."""
    return TenantResponse(
        tab_title=settings.tenant.tab_title,
        favicon_url=settings.tenant.favicon_url,
        logo_url=settings.tenant.logo_url,
        logo_rectangle_url=settings.tenant.logo_rectangle_url,
        logo_emoji=settings.tenant.logo_emoji,
        primary_color=settings.tenant.primary_color,
        accent_color=settings.tenant.accent_color,
        background_color=settings.tenant.background_color,
        font_family=settings.tenant.font_family,
        font_url=settings.tenant.font_url,
        login_card_max_width=settings.tenant.login_card_max_width,
        login_card_padding=settings.tenant.login_card_padding,
        login_card_color=settings.tenant.login_card_color,
        login_text_color=settings.tenant.login_text_color,
        login_input_color=settings.tenant.login_input_color,
        login_border_radius=settings.tenant.login_border_radius,
        login_bg_image_url=settings.tenant.login_bg_image_url,
        show_terms_footer=settings.tenant.show_terms_footer,
        show_powered_by=settings.tenant.show_powered_by,
        login_footer_text=settings.tenant.login_footer_text,
    )
