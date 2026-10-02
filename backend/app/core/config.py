from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Notionary"
    ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./notionary.db"
    # For Postgres/Supabase: "postgresql+asyncpg://user:pass@host:5432/dbname"
    DB_ECHO: bool = False

    # Notion Integration
    NOTION_API_KEY: str = ""
    NOTION_PARENT_PAGE_ID: str = ""
    NOTION_API_VERSION: str = "2022-06-28"

    # LLM & Embedding Settings
    DEFAULT_LLM_PROVIDER: str = "anthropic"  # anthropic, gemini, openai, mock
    DEFAULT_EMBEDDING_PROVIDER: str = "local"  # local, openai, gemini, mock

    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    CLAUDE_SONNET_MODEL: str = "claude-3-5-sonnet-20241022"
    CLAUDE_HAIKU_MODEL: str = "claude-3-5-haiku-20241022"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENAI_MODEL: str = "gpt-4o"

    # Auth & Security
    JWT_SECRET: str = "notionary-super-secret-dev-jwt-key-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
