import firebase_admin
from firebase_admin import credentials
from app.core.config import settings
import os
import json # Make sure json is imported

print(f"DEBUG: FIREBASE_CREDENTIALS_JSON is set: {bool(settings.FIREBASE_CREDENTIALS_JSON)}")
print(f"DEBUG: FIREBASE_SERVICE_ACCOUNT_PATH_RENDER: {settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER}")
print(f"DEBUG: FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL: {settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL}")

def initialize_firebase_admin():
    if firebase_admin._apps:
        print("Firebase Admin SDK already initialized.")
        return

    cred = None
    # Priority:
    # 1. FIREBASE_CREDENTIALS_JSON (Render env var - direct JSON content)
    # 2. FIREBASE_SERVICE_ACCOUNT_PATH_RENDER (Render env var - path to secret file)
    # 3. FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL (Local .env file - path to local key)

    if settings.FIREBASE_CREDENTIALS_JSON:
        try:
            cred_json_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
            cred = credentials.Certificate(cred_json_dict)
            print("Initializing Firebase Admin SDK from JSON environment variable (FIREBASE_CREDENTIALS_JSON).")
        except Exception as e:
            print(f"Error loading Firebase credentials from JSON environment variable: {e}")
            # Potentially fallback or raise an error
    
    if not cred and settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER:
        if os.path.exists(settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER):
            cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER)
            print(f"Initializing Firebase Admin SDK from Render secret file path: {settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER}")
        else:
            print(f"Render secret file path specified but not found: {settings.FIREBASE_SERVICE_ACCOUNT_PATH_RENDER}")

    if not cred and settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL:
        # Ensure backslashes are handled correctly if path comes from Windows
        local_path = settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH_LOCAL.replace("\\", "/")
        if os.path.exists(local_path):
            cred = credentials.Certificate(local_path)
            print(f"Initializing Firebase Admin SDK from local path: {local_path}")
        else:
            print(f"Local Firebase key path specified but not found: {local_path}")
    
    if cred:
        try:
            firebase_admin.initialize_app(cred)
            print("Firebase Admin SDK initialized successfully.")
        except Exception as e:
            print(f"Failed to initialize Firebase Admin SDK: {e}")
    else:
        print("Firebase Admin SDK credentials not found or failed to load. Please check configuration.")
        # Depending on your app's needs, you might want to raise an exception here
        # if Firebase Admin is critical for the app to start.
        # For now, it will just print the error.