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

    # Paystack Keys - Match what's actually in Render environment
    PAYSTACK_SECRET_KEY: str  # This is the live secret key in Render
    PAYSTACK_PUBLIC_KEY: str  # This is the live public key in Render  
    PAYSTACK_TEST_SECRET_KEY: str
    PAYSTACK_TEST_PUBLIC_KEY: str
    
    # These will be set based on environment
    ACTIVE_PAYSTACK_SECRET_KEY: Optional[str] = None
    ACTIVE_PAYSTACK_PUBLIC_KEY: Optional[str] = None
    
    # These will be dynamically set based on ENVIRONMENT
    FINAL_PAYSTACK_SECRET_KEY: Optional[str] = None
    FINAL_PAYSTACK_PUBLIC_KEY: Optional[str] = None
    
    # Paystack Plan Codes (same for both test and live)
    PAYSTACK_ACTUAL_PLAN_CODES: Dict[str, str] = {
        "monthly": "PLN_y6ssj3yx0t392cz",
        "yearly": "PLN_uqktx3mjkn0skcx" 
    }
    PAYSTACK_PLAN_CODES: Optional[Dict[str, str]] = None

    # TEMPORARILY DISABLED: Premium features list - all features now free
    # Original list preserved for re-enabling later:
    # PREMIUM_FEATURES: List[str] = [
    #     "gemini_cv_generation",
    #     "gemini_cover_letter_generation", 
    #     "cv_upload_and_parse"
    # ]
    PREMIUM_FEATURES: List[str] = []  # Empty list = no premium restrictions

    def _mask_sensitive_data(self, value: str, show_chars: int = 8) -> str:
        """Mask sensitive data for logging, showing only first few characters"""
        if not value or len(value) <= show_chars:
            return "***MASKED***"
        return f"{value[:show_chars]}***"

    @model_validator(mode="after")
    def set_active_paystack_keys_and_defaults(self) -> 'Settings':
        env = self.ENVIRONMENT.lower().strip()
        is_production = env == "production"
        
        # Only show detailed config in development
        if not is_production:
            print(f"INFO: [Config.Validator] Environment set to: '{env}'")
            print(f"DEBUG: [Config.Validator] Raw values loaded:")
            print(f"  PAYSTACK_SECRET_KEY (live) starts with: {self._mask_sensitive_data(self.PAYSTACK_SECRET_KEY, 12)}")
            print(f"  PAYSTACK_PUBLIC_KEY (live) starts with: {self._mask_sensitive_data(self.PAYSTACK_PUBLIC_KEY, 12)}")
            print(f"  PAYSTACK_TEST_SECRET_KEY starts with: {self._mask_sensitive_data(self.PAYSTACK_TEST_SECRET_KEY, 12)}")
            print(f"  PAYSTACK_TEST_PUBLIC_KEY starts with: {self._mask_sensitive_data(self.PAYSTACK_TEST_PUBLIC_KEY, 12)}")
        else:
            print(f"INFO: [Config] Production environment initialized")
        
        if is_production:
            # Use the live keys that are already loaded
            if not self.PAYSTACK_SECRET_KEY or self.PAYSTACK_SECRET_KEY.startswith("your_"):
                raise ValueError("PAYSTACK_SECRET_KEY (live) must be set in environment variables for production")
            
            if not self.PAYSTACK_PUBLIC_KEY or self.PAYSTACK_PUBLIC_KEY.startswith("your_"):
                raise ValueError("PAYSTACK_PUBLIC_KEY (live) must be set in environment variables for production")
            
            self.FINAL_PAYSTACK_SECRET_KEY = self.PAYSTACK_SECRET_KEY
            self.FINAL_PAYSTACK_PUBLIC_KEY = self.PAYSTACK_PUBLIC_KEY
            print("INFO: [Config] Payment system configured for production")
            
        else:  # development or any other value defaults to test mode
            self.FINAL_PAYSTACK_SECRET_KEY = self.PAYSTACK_TEST_SECRET_KEY
            self.FINAL_PAYSTACK_PUBLIC_KEY = self.PAYSTACK_TEST_PUBLIC_KEY
            print("INFO: [Config.Validator] Using TEST Paystack keys for DEVELOPMENT environment")
            
            if self.PAYSTACK_TEST_SECRET_KEY and self.PAYSTACK_TEST_SECRET_KEY.startswith("your_"):
                print("WARNING: [Config.Validator] TEST Paystack keys appear to be placeholders.")

        # Set plan codes (same for both environments)
        self.PAYSTACK_PLAN_CODES = self.PAYSTACK_ACTUAL_PLAN_CODES
        
        if not is_production:
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
            if not is_production:
                print(f"INFO: [Config.Validator] Defaulting ALLOWED_ORIGINS: {self.ALLOWED_ORIGINS}")
        else:
            if not is_production:
                print(f"INFO: [Config.Validator] Using ALLOWED_ORIGINS from environment: {self.ALLOWED_ORIGINS}")
            
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = 'ignore'

# Create settings instance
try:
    settings = Settings()
    is_production = settings.ENVIRONMENT.lower().strip() == "production"
    
    if not is_production:
        print("SUCCESS: [Config] Settings loaded successfully")
    else:
        print("INFO: [Config] Production settings loaded")
        
except Exception as e:
    print(f"CRITICAL ERROR: [Config] Failed to load settings: {e}")
    # Only show environment variables in development
    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        print("Available environment variables:")
        for key in os.environ:
            if 'PAYSTACK' in key:
                value = os.environ[key]
                masked_value = f"{value[:8]}***" if len(value) > 8 else "***MASKED***"
                print(f"  {key} = {masked_value}")
    raise

# Final validation - only detailed info in development
is_production = settings.ENVIRONMENT.lower().strip() == "production"
if not is_production:
    print(f"FINAL CHECK: Environment={settings.ENVIRONMENT}")
    print(f"FINAL CHECK: Active secret key configured: {bool(settings.FINAL_PAYSTACK_SECRET_KEY)}")
    print(f"FINAL CHECK: Active public key configured: {bool(settings.FINAL_PAYSTACK_PUBLIC_KEY)}")
else:
    print(f"INFO: [Config] Production configuration validated successfully")