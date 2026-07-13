# Central settings — loaded from env vars / .env, with defaults for local dev
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Read backend/.env if present; ignore unknown env keys
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://taskuser:taskpass@localhost:5432/taskdb"
    SECRET_KEY: str = "change-me-in-production"  # used to sign JWTs — change in prod
    ALGORITHM: str = "HS256"  # JWT signing algorithm
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # how long a login token stays valid
    # Comma-separated frontend URLs allowed to call the API (CORS)
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        # FastAPI needs a list, not a comma-separated string
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Single shared instance imported across the app: `from app.core.config import settings`
settings = Settings()
