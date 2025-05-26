# app/api/routes/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserProfileResponse, UserSubscription
from app.services import user_service
from app.api.dependencies import get_current_user
from typing import Dict
from datetime import datetime, timezone

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

    try:
        # Get or create user from Firestore
        user_data_from_db = await user_service.get_or_create_user(uid=uid, email=email)
        
        print(f"DEBUG: Raw user data from DB for UID {uid}: {user_data_from_db}")
        
        # Validate required fields exist
        if not user_data_from_db.get("uid"):
            raise ValueError("Missing UID in user data")
        if not user_data_from_db.get("email"):
            raise ValueError("Missing email in user data")
            
        # Handle created_at field - ensure it's a datetime object
        created_at = user_data_from_db.get("created_at")
        if created_at is None:
            # Fallback to current time if missing
            created_at = datetime.now(timezone.utc)
            print(f"WARNING: No created_at found for user {uid}, using current time")
        elif hasattr(created_at, 'ToDatetime'):
            # Firestore Timestamp object
            created_at = created_at.ToDatetime()
        elif isinstance(created_at, str):
            # ISO string, parse it
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except Exception as e:
                print(f"ERROR: Failed to parse created_at string '{created_at}': {e}")
                created_at = datetime.now(timezone.utc)
        elif not isinstance(created_at, datetime):
            # Unknown type, fallback
            print(f"WARNING: Unknown created_at type {type(created_at)}: {created_at}")
            created_at = datetime.now(timezone.utc)
            
        # Ensure timezone info
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        # Handle subscription data
        subscription_data = user_data_from_db.get("subscription", {})
        print(f"DEBUG: Raw subscription data: {subscription_data}")
        
        # Clean and validate subscription data
        clean_subscription_data = {}
        
        # Handle basic subscription fields with defaults
        clean_subscription_data["tier"] = subscription_data.get("tier", "free")
        clean_subscription_data["status"] = subscription_data.get("status", "active")
        clean_subscription_data["paystack_customer_id"] = subscription_data.get("paystack_customer_id")
        clean_subscription_data["paystack_subscription_id"] = subscription_data.get("paystack_subscription_id")
        
        # Handle datetime fields in subscription
        datetime_fields = [
            "current_period_starts_at",
            "current_period_ends_at", 
            "cancellation_effective_date"
        ]
        
        for field_name in datetime_fields:
            field_value = subscription_data.get(field_name)
            if field_value is None:
                clean_subscription_data[field_name] = None
            elif hasattr(field_value, 'ToDatetime'):
                # Firestore Timestamp
                clean_subscription_data[field_name] = field_value.ToDatetime()
            elif isinstance(field_value, str):
                # ISO string
                try:
                    parsed_dt = datetime.fromisoformat(field_value.replace('Z', '+00:00'))
                    clean_subscription_data[field_name] = parsed_dt
                except Exception as e:
                    print(f"ERROR: Failed to parse {field_name} string '{field_value}': {e}")
                    clean_subscription_data[field_name] = None
            elif isinstance(field_value, datetime):
                # Already datetime, ensure timezone
                if field_value.tzinfo is None:
                    field_value = field_value.replace(tzinfo=timezone.utc)
                clean_subscription_data[field_name] = field_value
            else:
                print(f"WARNING: Unknown {field_name} type {type(field_value)}: {field_value}")
                clean_subscription_data[field_name] = None
        
        print(f"DEBUG: Cleaned subscription data: {clean_subscription_data}")
        
        # Create UserSubscription object
        try:
            subscription_details = UserSubscription(**clean_subscription_data)
        except Exception as e:
            print(f"ERROR: Failed to create UserSubscription object: {e}")
            print(f"Problematic data: {clean_subscription_data}")
            # Fallback to minimal subscription
            subscription_details = UserSubscription(
                tier="free",
                status="active"
            )
        
        # Create the response object
        try:
            response_data = UserProfileResponse(
                uid=user_data_from_db["uid"],
                email=user_data_from_db["email"],
                created_at=created_at,
                subscription=subscription_details
            )
            
            print(f"DEBUG: Successfully created UserProfileResponse for UID {uid}")
            return response_data
            
        except Exception as e:
            print(f"ERROR: Failed to create UserProfileResponse: {e}")
            raise ValueError(f"Failed to construct response object: {e}")
            
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"ERROR: Exception in read_users_me for UID {uid}: {e}")
        print(f"Exception type: {type(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Also log the user data if available
        try:
            if 'user_data_from_db' in locals():
                print(f"User data when error occurred: {user_data_from_db}")
        except:
            pass
            
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing user profile data: {str(e)}",
        )