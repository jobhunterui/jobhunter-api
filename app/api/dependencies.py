# app/api/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer # Can be adapted for Bearer tokens
from firebase_admin import auth
from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token") # tokenUrl is not strictly used here but required

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        # The token comes from the Authorization: Bearer <ID_TOKEN> header
        # The frontend needs to send this Firebase ID token.
        decoded_token = auth.verify_id_token(token)
        return decoded_token # Contains uid, email, etc.
    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e: # Catch any other Firebase admin errors
        print(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user_uid(current_user: dict = Depends(get_current_user)) -> str:
    # This is a convenience dependency if you only need the UID
    if not current_user or "uid" not in current_user:
        raise HTTPException(status_code=400, detail="User not found in token")
    return current_user["uid"]

async def get_current_admin_user_uid(current_user: dict = Depends(get_current_user)) -> str:
    """
    This dependency checks if the authenticated user is in the admin list.
    It relies on get_current_user to first validate the token.
    """
    user_email = current_user.get("email")
    user_uid = current_user.get("uid")

    if not user_email or not user_uid:
        raise HTTPException(status_code=400, detail="User email or UID not found in token")

    # Check the user's email against the list of admins from your settings
    if user_email not in settings.ADMIN_EMAIL_ADDRESSES:
        print(f"SECURITY: Admin access DENIED for user {user_email} ({user_uid})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have administrative privileges."
        )

    print(f"SECURITY: Admin access GRANTED for user {user_email} ({user_uid})")
    return user_uid