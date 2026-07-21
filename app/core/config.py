from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "TeamFlow"
    environment: str = "development"
    database_url: str = "mysql+pymysql://teamflow:teamflow@localhost:3306/teamflow"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7
    lovable_api_key: Optional[str] = None
    storage_provider: str = "local"
    holiday_upload_dir: str = "uploads/holidays"
    max_holiday_file_size_mb: int = 10
    email_provider: str = "local"
    email_from_name: str = "WorkPilot"
    email_from_address: str = "noreply@example.com"
    resend_api_key: Optional[str] = None
    frontend_app_url: str = "https://teamflow-fe.vercel.app"
    invitation_token_expire_hours: int = 24
    run_migrations_on_startup: bool = True
    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "https://teamflow-fe.vercel.app"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
