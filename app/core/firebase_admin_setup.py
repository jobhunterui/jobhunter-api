import firebase_admin
from firebase_admin import credentials
from app.core.config import settings
import os
import json

def initialize_firebase_admin():
    if firebase_admin._apps:
        print("INFO: [Firebase] Admin SDK already initialized")
        return

    cred = None
    is_production = settings.ENVIRONMENT.lower().strip() == "production"
    
    # Priority:
    # 1. FIREBASE_CREDENTIALS_JSON (Render env var - direct JSON content)
    # 2. FIREBASE_SERVICE_ACCOUNT_PATH_RENDER (Render env var - path to secret file)
    # 3. FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL (Local .env file - path to local key)

    if settings.FIREBASE_CREDENTIALS_JSON:
        try:
            cred_json_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_json_dict)
            if is_production:
                print("INFO: [Firebase] Admin SDK configured from environment credentials")
            else:
                print("INFO: [Firebase] Initializing from JSON environment variable (FIREBASE_CREDENTIALS_JSON)")
        except Exception as e:
            print(f"ERROR: [Firebase] Failed to load credentials from JSON environment variable: {e}")
    
    if not cred and settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER:
        if os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER):
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER)
            if is_production:
                print("INFO: [Firebase] Admin SDK configured from secret file")
            else:
                print(f"INFO: [Firebase] Initializing from Render secret file: {settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER}")
        else:
            print(f"ERROR: [Firebase] Render secret file path specified but not found: {settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER}")

    if not cred and settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL:
        # Ensure backslashes are handled correctly if path comes from Windows
        local_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL.replace("\\", "/")
        if os.path.exists(local_path):
            cred = credentials.Certificate(local_path)
            print(f"INFO: [Firebase] Initializing from local development path: {local_path}")
        else:
            print(f"ERROR: [Firebase] Local Firebase key path specified but not found: {local_path}")
    
    if cred:
        try:
            firebase_admin.initialize_app(cred)
            print("INFO: [Firebase] Admin SDK initialized successfully")
        except Exception as e:
            print(f"CRITICAL: [Firebase] Failed to initialize Admin SDK: {e}")
            raise
    else:
        error_msg = "CRITICAL: [Firebase] No valid credentials found for Admin SDK initialization"
        print(error_msg)
        raise RuntimeError(error_msg)