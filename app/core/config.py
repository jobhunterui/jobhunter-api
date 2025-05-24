import os
from typing import List, Union, Optional, Dict

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "JobHunter CV Generator API"
    DEBUG_MODE: bool = False
    VERSION: str = "0.1.0"
    DESCRIPTION: str = """
    JobHunter CV Generator API.
    Creates tailored CVs using Google's Gemini AI model.
    """

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # CORS Settings
    ALLOWED_ORIGINS: Union[str, List[str]] = []

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Firebase Admin SDK settings
    # For Render, set FIREBASE_CREDENTIALS_JSON (as JSON string)
    # OR FIREBASE_SERVICE_ACCOUNT_PATH (as path to secret file) in Render's env vars.
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_PATH_RENDER: Optional[str] = None # Explicit for Render path
    
    # For local development, loaded from .env
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL: Optional[str] = None

    # Gemini API Settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Redis Settings (for rate limiting)
    REDIS_URL: str = ""  # Empty string instead of None
    DAILY_QUOTA: int = 100
    
    # Paystack Settings
    PAYSTACK_SECRET_KEY: str
    PAYSTACK_PUBLIC_KEY: str
    PAYSTACK_PLAN_CODES: Dict[str, str] = {
        "monthly": "PLN_y6ssj3yx0t392cz",
        "yearly": "PLN_uqktx3mjkn0skcx"
    }

    # Environment Settings
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'


settings = Settings()

# Initialize settings
if not settings.ALLOWED_ORIGINS:
    settings.ALLOWED_ORIGINS = [
        "https://jobhunterui.github.io",  # GitHub Pages
        "http://localhost:8000",  # Local development server
        "moz-extension://",  # Firefox extension
    ]