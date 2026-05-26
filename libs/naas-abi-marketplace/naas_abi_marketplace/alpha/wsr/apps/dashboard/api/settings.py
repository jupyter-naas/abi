from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # OAuth2 client credentials — new OpenSky accounts (mid-March 2025+)
    opensky_client_id: str = ""
    opensky_client_secret: str = ""

    # Legacy basic auth — pre-March 2025 OpenSky accounts
    opensky_username: str = ""
    opensky_password: str = ""

    openwebcamdb_api_key: str = ""
    tfl_app_key: str = ""       # Optional: https://api-portal.tfl.gov.uk/ → higher rate limits
    allowed_origins: list[str] = ["*"]


settings = Settings()
