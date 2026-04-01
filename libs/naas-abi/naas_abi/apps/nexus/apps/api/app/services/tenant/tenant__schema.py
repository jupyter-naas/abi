from pydantic import BaseModel, Field


class TenantResponse(BaseModel):
    class ExternalAppResponse(BaseModel):
        name: str
        url: str
        description: str | None = None
        icon_emoji: str | None = None

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
    apps: list[ExternalAppResponse] = Field(default_factory=list)
