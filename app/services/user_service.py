# app/services/user_service.py
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone
from app.schemas.user import UserSubscription, UserDBCreate #
from typing import Dict, Optional
from fastapi.concurrency import run_in_threadpool #
from app.schemas.payment import PaystackWebhookPlan

USERS_COLLECTION = "users"

def get_firestore_db():
    """Initializes and returns a Firestore client instance."""
    if not firebase_admin._apps:
        # This should ideally be handled by the application startup lifespan event
        # but as a fallback, or if called independently.
        # Consider how firebase_admin_setup.py is invoked in your app lifecycle.
        # For now, assuming it's initialized at startup.
        pass # Assuming Firebase Admin is initialized via lifespan in server.py
    return firestore.client()

async def get_or_create_user(uid: str, email: str) -> Dict:
    """
    Retrieves a user document from Firestore by UID.
    If the user does not exist, it creates a new user document with default
    free subscription status and a createdAt timestamp.
    Returns the user document data as a dictionary.
    """
    db = get_firestore_db()
    user_ref = db.collection(USERS_COLLECTION).document(uid)
    
    user_doc = await run_in_threadpool(user_ref.get) #

    if user_doc.exists:
        user_data = user_doc.to_dict()
        if 'createdAt' in user_data and hasattr(user_data['createdAt'], 'ToDatetime'): #
            user_data['createdAt'] = user_data['createdAt'].ToDatetime() #
        elif 'created_at' in user_data and hasattr(user_data['created_at'], 'ToDatetime'): #
            user_data['created_at'] = user_data['created_at'].ToDatetime() #

        if 'subscription' in user_data: #
            for key in ['current_period_starts_at', 'current_period_ends_at', 'cancellation_effective_date']: #
                if key in user_data['subscription'] and user_data['subscription'][key] and \
                    hasattr(user_data['subscription'][key], 'ToDatetime'): #
                    user_data['subscription'][key] = user_data['subscription'][key].ToDatetime() #
        return user_data
    else:
        current_time_utc = datetime.now(timezone.utc) #
        default_subscription = UserSubscription( #
            tier="free", #
            status="active", #
        )
        
        new_user_data = UserDBCreate( #
            uid=uid,
            email=email,
            created_at=current_time_utc, #
            subscription=default_subscription #
        )
        
        user_data_to_set = new_user_data.model_dump() #
        await run_in_threadpool(user_ref.set, user_data_to_set) #
        return user_data_to_set

async def get_user_profile_data(uid: str) -> Optional[Dict]:
    """
    Fetches the user document from Firestore and returns it as a dictionary.
    Returns None if the user is not found.
    Handles conversion of Firestore Timestamps to Python datetime objects.
    """
    db = get_firestore_db()
    user_ref = db.collection(USERS_COLLECTION).document(uid)
    user_doc = await run_in_threadpool(user_ref.get) #

    if user_doc.exists:
        user_data = user_doc.to_dict()
        if 'created_at' in user_data and hasattr(user_data['created_at'], 'ToDatetime'): #
            user_data['created_at'] = user_data['created_at'].ToDatetime() #
        
        if 'subscription' in user_data and isinstance(user_data['subscription'], dict): #
            subscription_data = user_data['subscription']
            for field_name in ['current_period_starts_at', 'current_period_ends_at', 'cancellation_effective_date']: #
                if field_name in subscription_data and hasattr(subscription_data[field_name], 'ToDatetime'): #
                    subscription_data[field_name] = subscription_data[field_name].ToDatetime() #
        return user_data
    return None

async def get_user_subscription_object(uid: str) -> Optional[UserSubscription]:
    """
    Fetches the user's document, extracts the subscription map,
    and returns it as a UserSubscription Pydantic object.
    Returns None if the user or subscription data is not found.
    """
    user_data = await get_user_profile_data(uid) #
    if user_data and 'subscription' in user_data: #
        try:
            # Ensure timestamps are converted if they are still Firestore Timestamps
            sub_data = user_data['subscription']
            for key in ['current_period_starts_at', 'current_period_ends_at', 'cancellation_effective_date']:
                if key in sub_data and hasattr(sub_data[key], 'ToDatetime'):
                    sub_data[key] = sub_data[key].ToDatetime()
            return UserSubscription(**sub_data) #
        except Exception as e:
            print(f"Error parsing subscription data for user {uid}: {e}") #
            return None
    return None

async def update_user_subscription_from_paystack(
    uid: str,
    tier: str, # e.g., "pro_monthly", "pro_yearly", or just "pro"
    status: str, # e.g., "active", "cancelled", "past_due"
    paystack_subscription_id: Optional[str],
    paystack_customer_id: Optional[str],
    current_period_starts_at: Optional[datetime],
    current_period_ends_at: Optional[datetime],
    cancellation_effective_date: Optional[datetime] = None
) -> bool:
    """
    Updates a user's subscription details in Firestore based on Paystack webhook event.
    """
    db = get_firestore_db()
    user_ref = db.collection(USERS_COLLECTION).document(uid)

    try:
        user_profile = await get_user_profile_data(uid)
        if not user_profile:
            print(f"User {uid} not found. Cannot update subscription.")
            # Optionally, create the user here if webhook arrives before user record exists
            # For now, we assume user exists from initial signup/token verification.
            return False

        # Prepare the subscription data, ensuring all datetime are UTC and Firestore compatible
        subscription_data = {
            "tier": tier,
            "status": status, # "active", "inactive", "cancelled", "past_due" etc.
            "payment_gateway": "paystack",
            "paystack_subscription_id": paystack_subscription_id,
            "paystack_customer_id": paystack_customer_id,
            "current_period_starts_at": current_period_starts_at.astimezone(timezone.utc) if current_period_starts_at else None,
            "current_period_ends_at": current_period_ends_at.astimezone(timezone.utc) if current_period_ends_at else None,
            "cancellation_effective_date": cancellation_effective_date.astimezone(timezone.utc) if cancellation_effective_date else None,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Remove None values to avoid overwriting existing fields with None if not provided
        subscription_update_data = {k: v for k, v in subscription_data.items() if v is not None}

        update_payload = {"subscription": subscription_update_data}
        if status == "active" and tier != "free":
            update_payload["has_active_subscription"] = True
        elif tier == "free":
            update_payload["has_active_subscription"] = False


        await run_in_threadpool(user_ref.update, update_payload)
        print(f"Successfully updated subscription for user {uid} to tier {tier}, status {status}.")
        return True
    except Exception as e:
        print(f"Error updating subscription for user {uid}: {e}")
        return False

async def revert_user_to_free_tier(uid: str) -> bool:
    """
    Reverts a user to the default free tier, typically after a subscription ends or is cancelled.
    """
    db = get_firestore_db()
    user_ref = db.collection(USERS_COLLECTION).document(uid)
    try:
        free_subscription_data = UserSubscription(
            tier="free",
            status="active", # Or "cancelled" if coming from a paid plan
            payment_gateway=None,
            paystack_subscription_id=None,
            paystack_customer_id=None,
            current_period_starts_at=None,
            current_period_ends_at=None,
            cancellation_effective_date=None,
            updated_at=datetime.now(timezone.utc)
        ).model_dump(exclude_none=True)

        await run_in_threadpool(
            user_ref.update,
            {
                "subscription": free_subscription_data,
                "has_active_subscription": False
            }
        )
        print(f"Successfully reverted user {uid} to free tier.")
        return True
    except Exception as e:
        print(f"Error reverting user {uid} to free tier: {e}")
        return False