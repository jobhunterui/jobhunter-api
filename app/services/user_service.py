# app/services/user_service.py
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone
from app.schemas.user import UserSubscription, UserDBCreate #
from typing import Dict, Optional
from fastapi.concurrency import run_in_threadpool # Import this

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
    
    # Wrap synchronous Firestore call in run_in_threadpool
    user_doc = await run_in_threadpool(user_ref.get) #

    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Ensure createdAt is a datetime object if stored as Firestore Timestamp
        if 'createdAt' in user_data and hasattr(user_data['createdAt'], 'ToDatetime'): # Firestore Timestamp #
            user_data['createdAt'] = user_data['createdAt'].ToDatetime() # Convert to Python datetime #
        elif 'created_at' in user_data and hasattr(user_data['created_at'], 'ToDatetime'): # Firestore Timestamp #
             user_data['created_at'] = user_data['created_at'].ToDatetime() # Convert to Python datetime #

        # Ensure subscription fields with timestamps are also converted
        if 'subscription' in user_data: #
            for key in ['current_period_starts_at', 'current_period_ends_at', 'cancellation_effective_date']: #
                if key in user_data['subscription'] and user_data['subscription'][key] and \
                   hasattr(user_data['subscription'][key], 'ToDatetime'): #
                    user_data['subscription'][key] = user_data['subscription'][key].ToDatetime() #
        return user_data
    else:
        # Create new user
        current_time_utc = datetime.now(timezone.utc) #
        default_subscription = UserSubscription( #
            tier="free", #
            status="active", #
        )
        
        new_user_data = UserDBCreate( #
            uid=uid,
            email=email,
            created_at=current_time_utc, # Store as 'created_at' for consistency #
            subscription=default_subscription #
        )
        
        user_data_to_set = new_user_data.model_dump() #

        # Wrap synchronous Firestore call in run_in_threadpool
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

    # Wrap synchronous Firestore call in run_in_threadpool
    user_doc = await run_in_threadpool(user_ref.get) #

    if user_doc.exists:
        user_data = user_doc.to_dict()
        # Convert Firestore Timestamps to Python datetime objects
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
            return UserSubscription(**user_data['subscription']) #
        except Exception as e:
            print(f"Error parsing subscription data for user {uid}: {e}") # Add logging #
            return None
    return None