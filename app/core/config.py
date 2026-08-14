from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/easymoney.db"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-me"
    JWT_SECRET: str = "change-me"
    JWT_EXPIRE_MINUTES: int = 720
    
    # Comma-separated string parsed to list, never * for CORS
    CORS_ORIGINS: str = "http://localhost:5173"
    
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_MB: int = 5
    CURRENCY: str = "لحوح"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
