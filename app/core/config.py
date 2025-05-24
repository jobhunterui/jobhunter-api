import os
from typing import List, Union, Optional, Dict

from pydantic import field_validator, Field
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
    GEMINI_MODEL: str = "gemini-2.0-flash" # Consider if "gemini-1.5-flash" is intended based on typical naming
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Redis Settings (for rate limiting)
    REDIS_URL: str = ""  # Empty string instead of None
    
    # Tier-based Rate Limiting Quotas
    # DAILY_QUOTA is removed as FREE_DAILY_QUOTA and PREMIUM_DAILY_QUOTA are now primary.
    # If a general fallback is still needed, it can be added back or handled in logic.
    FREE_DAILY_QUOTA: int = 5
    PREMIUM_DAILY_QUOTA: int = 50
    
    # Paystack Settings
    PAYSTACK_SECRET_KEY: str
    PAYSTACK_PUBLIC_KEY: str
    PAYSTACK_PLAN_CODES: Dict[str, str] = {
        "monthly": "PLN_y6ssj3yx0t392cz",
        "yearly": "PLN_uqktx3mjkn0skcx"
    }
    PAYSTACK_WEBHOOK_SECRET: Optional[str] = Field(None) # Added for explicit declaration, can be set via env

    # Environment Settings
    ENVIRONMENT: str = "development"
    
    # Designate which features are premium
    # Use clear identifiers that can be checked in routes
    PREMIUM_FEATURES: List[str] = [
        "gemini_cv_generation",
        "gemini_cover_letter_generation"
        # Add other feature keys here like "career_insights_analysis" if they become API-gated
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore' # Changed from 'forbid' to 'ignore' as per user's original file

settings = Settings()

# Initialize settings
if not settings.ALLOWED_ORIGINS:
    settings.ALLOWED_ORIGINS = [
        "https://jobhunterui.github.io",  # GitHub Pages
        "http://localhost:8000",  # Local development server
        "http://localhost:3000",  # Common frontend dev port
        "http://127.0.0.1:5500", # For local frontend testing (Live Server)
        "moz-extension://*", # Firefox extension (using wildcard for UUIDs)
        "chrome-extension://*" # Chrome extension (using wildcard for IDs)
    ]
    
if settings.ENVIRONMENT == "production" and not settings.PAYSTACK_WEBHOOK_SECRET:
    print("WARNING: PAYSTACK_WEBHOOK_SECRET is not set in a production environment!")