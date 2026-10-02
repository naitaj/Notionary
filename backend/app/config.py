from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Notionary"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./notionary.db"
    
    # Notion
    NOTION_API_KEY: str = ""
    NOTION_PAGE_ID: str = ""
    
    # LLMs
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    class Config:
        env_file = str(ENV_PATH)
        extra = "ignore"

settings = Settings()
