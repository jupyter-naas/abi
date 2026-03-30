from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.tenant.tenant__schema import TenantResponse


class TenantService:
    @staticmethod
    async def get_tenant_config() -> TenantResponse:
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
            apps=[
                TenantResponse.ExternalAppResponse(
                    name=app.name,
                    url=app.url,
                    description=app.description,
                    icon_emoji=app.icon_emoji,
                )
                for app in settings.tenant.apps
            ],
        )
