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
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"

    # Redis Settings
    REDIS_URL: str = ""

    # Tier-based Rate Limiting Quotas
    FREE_DAILY_QUOTA: int = 5
    PREMIUM_DAILY_QUOTA: int = 50

    # Environment Settings
    ENVIRONMENT: str = "development"

    # Paystack Keys - NO DEFAULTS, must come from environment
    PAYSTACK_LIVE_SECRET_KEY: str
    PAYSTACK_LIVE_PUBLIC_KEY: str
    PAYSTACK_TEST_SECRET_KEY: str
    PAYSTACK_TEST_PUBLIC_KEY: str
    
    # These will be dynamically set based on ENVIRONMENT
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    
    # Paystack Plan Codes (same for both test and live)
    PAYSTACK_ACTUAL_PLAN_CODES: Dict[str, str] = {
        "monthly": "PLN_y6ssj3yx0t392cz",
        "yearly": "PLN_uqktx3mjkn0skcx"
    }
    PAYSTACK_PLAN_CODES: Optional[Dict[str, str]] = None

    PREMIUM_FEATURES: List[str] = [
        "gemini_cv_generation",
        "gemini_cover_letter_generation",
        "cv_upload_and_parse"
    ]

    @model_validator(mode="after")
    def set_active_paystack_keys_and_defaults(self) -> 'Settings':
        env = self.ENVIRONMENT.lower().strip()
        print(f"INFO: [Config.Validator] Environment set to: '{env}'")
        
        # Debug logging - show what we actually got from environment
        print(f"DEBUG: [Config.Validator] Raw values loaded:")
        print(f"  PAYSTACK_LIVE_SECRET_KEY starts with: {self.PAYSTACK_LIVE_SECRET_KEY[:20] if self.PAYSTACK_LIVE_SECRET_KEY else 'NONE'}...")
        print(f"  PAYSTACK_LIVE_PUBLIC_KEY starts with: {self.PAYSTACK_LIVE_PUBLIC_KEY[:20] if self.PAYSTACK_LIVE_PUBLIC_KEY else 'NONE'}...")
        print(f"  PAYSTACK_TEST_SECRET_KEY starts with: {self.PAYSTACK_TEST_SECRET_KEY[:20] if self.PAYSTACK_TEST_SECRET_KEY else 'NONE'}...")
        print(f"  PAYSTACK_TEST_PUBLIC_KEY starts with: {self.PAYSTACK_TEST_PUBLIC_KEY[:20] if self.PAYSTACK_TEST_PUBLIC_KEY else 'NONE'}...")
        
        if env == "production":
            # Validate live keys are present and not placeholder values
            if not self.PAYSTACK_LIVE_SECRET_KEY or self.PAYSTACK_LIVE_SECRET_KEY.startswith("your_"):
                raise ValueError(f"PAYSTACK_LIVE_SECRET_KEY must be set in environment variables for production. Got: {self.PAYSTACK_LIVE_SECRET_KEY[:30] if self.PAYSTACK_LIVE_SECRET_KEY else 'None'}")
            
            if not self.PAYSTACK_LIVE_PUBLIC_KEY or self.PAYSTACK_LIVE_PUBLIC_KEY.startswith("your_"):
                raise ValueError(f"PAYSTACK_LIVE_PUBLIC_KEY must be set in environment variables for production. Got: {self.PAYSTACK_LIVE_PUBLIC_KEY[:30] if self.PAYSTACK_LIVE_PUBLIC_KEY else 'None'}")
            
            self.PAYSTACK_SECRET_KEY = self.PAYSTACK_LIVE_SECRET_KEY
            self.PAYSTACK_PUBLIC_KEY = self.PAYSTACK_LIVE_PUBLIC_KEY
            print("SUCCESS: [Config.Validator] Using LIVE Paystack keys for PRODUCTION environment")
            print(f"  Active SECRET_KEY starts with: {self.PAYSTACK_SECRET_KEY[:15]}...")
            print(f"  Active PUBLIC_KEY starts with: {self.PAYSTACK_PUBLIC_KEY[:15]}...")
            
        else:  # development or any other value defaults to test mode
            self.PAYSTACK_SECRET_KEY = self.PAYSTACK_TEST_SECRET_KEY
            self.PAYSTACK_PUBLIC_KEY = self.PAYSTACK_TEST_PUBLIC_KEY
            print("INFO: [Config.Validator] Using TEST Paystack keys for DEVELOPMENT environment")
            
            if self.PAYSTACK_TEST_SECRET_KEY and self.PAYSTACK_TEST_SECRET_KEY.startswith("your_"):
                print("WARNING: [Config.Validator] TEST Paystack keys appear to be placeholders.")

        # Set plan codes (same for both environments)
        self.PAYSTACK_PLAN_CODES = self.PAYSTACK_ACTUAL_PLAN_CODES
        print(f"INFO: [Config.Validator] Active Paystack Plan Codes: {self.PAYSTACK_PLAN_CODES}")
        
        # Handle ALLOWED_ORIGINS
        if not self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS = [
                "https://jobhunterui.github.io",
                "http://localhost:8000",
                "http://localhost:3000",
                "http://127.0.0.1:5500",
                "moz-extension://*",
                "chrome-extension://*"
            ]
            print(f"INFO: [Config.Validator] Defaulting ALLOWED_ORIGINS: {self.ALLOWED_ORIGINS}")
        else:
            print(f"INFO: [Config.Validator] Using ALLOWED_ORIGINS from environment: {self.ALLOWED_ORIGINS}")
            
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'

# Create settings instance
try:
    settings = Settings()
    print("SUCCESS: [Config] Settings loaded successfully")
except Exception as e:
    print(f"CRITICAL ERROR: [Config] Failed to load settings: {e}")
    print("Available environment variables:")
    for key in os.environ:
        if 'PAYSTACK' in key:
            value = os.environ[key]
            print(f"  {key} = {value[:20]}..." if len(value) > 20 else f"  {key} = {value}")
    raise

# Final validation
print(f"FINAL CHECK: Environment={settings.ENVIRONMENT}")
print(f"FINAL CHECK: Active secret key starts with: {settings.PAYSTACK_SECRET_KEY[:15] if settings.PAYSTACK_SECRET_KEY else 'NONE'}...")
print(f"FINAL CHECK: Active public key starts with: {settings.PAYSTACK_PUBLIC_KEY[:15] if settings.PAYSTACK_PUBLIC_KEY else 'NONE'}...")