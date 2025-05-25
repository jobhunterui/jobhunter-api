# app/core/config.py
import os
from typing import List, Union, Optional, Dict

from pydantic import field_validator, Field, model_validator
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
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_PATH_RENDER: Optional[str] = None
    FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL: Optional[str] = None

    # Gemini API Settings
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.0-flash" # User specified
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Redis Settings
    REDIS_URL: str = ""

    # Tier-based Rate Limiting Quotas
    FREE_DAILY_QUOTA: int = 5
    PREMIUM_DAILY_QUOTA: int = 50 # This is used for any "pro" tier

    # Paystack Live Keys (expected to be set in environment variables)
    PAYSTACK_LIVE_SECRET_KEY: str = Field(default="your_live_secret_key_placeholder")
    PAYSTACK_LIVE_PUBLIC_KEY: str = Field(default="your_live_public_key_placeholder")

    # Paystack Test Keys (expected to be set in environment variables)
    PAYSTACK_TEST_SECRET_KEY: str = Field(default="your_test_secret_key_placeholder")
    PAYSTACK_TEST_PUBLIC_KEY: str = Field(default="your_test_public_key_placeholder")
    
    # These will be dynamically set based on ENVIRONMENT
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    
    # Paystack Plan Codes - User confirmed these are the same for test/live.
    # These are effectively the 'default' or 'live' codes.
    PAYSTACK_ACTUAL_PLAN_CODES: Dict[str, str] = {
        "monthly": "PLN_y6ssj3yx0t392cz", # From user's original config
        "yearly": "PLN_uqktx3mjkn0skcx"   # From user's original config
    }
    # This will hold the active plan codes (assigned in the validator)
    PAYSTACK_PLAN_CODES: Optional[Dict[str, str]] = None

    PAYSTACK_WEBHOOK_SECRET: Optional[str] = Field(None)

    # Environment Settings
    ENVIRONMENT: str = "development" # Default to development if not set

    PREMIUM_FEATURES: List[str] = [
        "gemini_cv_generation",
        "gemini_cover_letter_generation",
        "cv_upload_and_parse"
        # Add other feature keys here like "career_insights_analysis" if they become API-gated
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'

settings = Settings()

if not settings.ALLOWED_ORIGINS:
    settings.ALLOWED_ORIGINS = [
        "https://jobhunterui.github.io",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "moz-extension://*",
        "chrome-extension://*"
    ]
    
if settings.ENVIRONMENT.lower() != "development" and not settings.PAYSTACK_WEBHOOK_SECRET:
    print("WARNING: PAYSTACK_WEBHOOK_SECRET is not set in a non-development environment!")