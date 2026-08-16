from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str
    mongodb_db_name: str = "trenddrop"

    jwt_secret: str
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"

    frontend_url: str = "http://localhost:5500"
    cookie_secure: bool = False

    seed_admin_email: str = ""
    seed_admin_password: str = ""
    seed_admin_nome: str = "Admin"

    anthropic_api_key: str = ""

    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/social/meta/callback"
    meta_graph_version: str = "v21.0"

    social_token_encryption_key: str = ""

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_full_price_id: str = ""

    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost:8000/api/social/tiktok/callback"


settings = Settings()
