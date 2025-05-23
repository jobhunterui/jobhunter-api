# app/api/routes/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserProfileResponse, UserSubscription
from app.services import user_service
from app.api.dependencies import get_current_user #
from typing import Dict

router = APIRouter()

@router.get("/me", response_model=UserProfileResponse)
async def read_users_me(current_user_token: Dict = Depends(get_current_user)):
    """
    Get current authenticated user's profile.
    If the user doesn't exist in Firestore, they will be created.
    """
    uid = current_user_token.get("uid")
    email = current_user_token.get("email")

    if not uid or not email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User ID or email not found in token.",
        )

    # This will get or create the user in Firestore.
    # The get_or_create_user returns the raw user data dict from DB.
    user_data_from_db = await user_service.get_or_create_user(uid=uid, email=email)
    
    # We need to structure it into UserProfileResponse.
    # The created_at and subscription parts need to be correctly parsed.
    
    # user_data_from_db already contains 'created_at' and 'subscription' (as a dict)
    # from the get_or_create_user service function.
    
    try:
        # Ensure subscription is a UserSubscription object for the response model
        subscription_details = UserSubscription(**user_data_from_db.get("subscription", {}))
        
        response_data = UserProfileResponse(
            uid=user_data_from_db["uid"],
            email=user_data_from_db["email"],
            created_at=user_data_from_db["created_at"], # Ensure this is datetime
            subscription=subscription_details
        )
        return response_data
    except Exception as e:
        # Log the error
        print(f"Error constructing UserProfileResponse for UID {uid}: {e}")
        print(f"Data from DB: {user_data_from_db}")
        # This could happen if 'created_at' or 'subscription' parts are missing or malformed
        # despite get_or_create_user logic.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing user profile data."
        )