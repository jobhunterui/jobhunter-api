import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi.concurrency import run_in_threadpool
from app.core.config import settings

PROFILING_COLLECTION = "user_profiles"

class ProfilingService:
    def __init__(self):
        self.db = firestore.client()

    async def save_user_profile(self, uid: str, profile_data: Dict[str, Any]) -> bool:
        """
        Save user's professional profile to Firestore.
        """
        is_production = settings.ENVIRONMENT.lower().strip() == "production"
        
        try:
            profile_doc = {
                "uid": uid,
                "profile_data": profile_data,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "version": "1.0.0"
            }
            
            profile_ref = self.db.collection(PROFILING_COLLECTION).document(uid)
            await run_in_threadpool(profile_ref.set, profile_doc)
            
            if not is_production:
                print(f"INFO: Successfully saved professional profile for UID {uid}")
            else:
                print(f"INFO: [ProfilingService] Profile saved successfully")
            
            return True
            
        except Exception as e:
            if not is_production:
                print(f"ERROR: Failed to save professional profile for UID {uid}: {e}")
            else:
                print(f"ERROR: [ProfilingService] Profile save failed: {str(e)}")
            return False

    async def get_user_profile(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user's professional profile from Firestore.
        """
        is_production = settings.ENVIRONMENT.lower().strip() == "production"
        
        try:
            profile_ref = self.db.collection(PROFILING_COLLECTION).document(uid)
            profile_doc = await run_in_threadpool(profile_ref.get)
            
            if profile_doc.exists:
                profile_data = profile_doc.to_dict()
                
                # Convert Firestore timestamps if needed
                if 'created_at' in profile_data and hasattr(profile_data['created_at'], 'ToDatetime'):
                    profile_data['created_at'] = profile_data['created_at'].ToDatetime()
                if 'updated_at' in profile_data and hasattr(profile_data['updated_at'], 'ToDatetime'):
                    profile_data['updated_at'] = profile_data['updated_at'].ToDatetime()
                
                if not is_production:
                    print(f"INFO: Retrieved professional profile for UID {uid}")
                
                return profile_data
            else:
                if not is_production:
                    print(f"INFO: No professional profile found for UID {uid}")
                return None
                
        except Exception as e:
            if not is_production:
                print(f"ERROR: Failed to retrieve professional profile for UID {uid}: {e}")
            else:
                print(f"ERROR: [ProfilingService] Profile retrieval failed: {str(e)}")
            return None

    async def update_user_profile(self, uid: str, profile_data: Dict[str, Any]) -> bool:
        """
        Update existing user's professional profile in Firestore.
        """
        is_production = settings.ENVIRONMENT.lower().strip() == "production"
        
        try:
            update_data = {
                "profile_data": profile_data,
                "updated_at": datetime.now(timezone.utc),
                "version": "1.0.0"
            }
            
            profile_ref = self.db.collection(PROFILING_COLLECTION).document(uid)
            await run_in_threadpool(profile_ref.update, update_data)
            
            if not is_production:
                print(f"INFO: Successfully updated professional profile for UID {uid}")
            else:
                print(f"INFO: [ProfilingService] Profile updated successfully")
            
            return True
            
        except Exception as e:
            if not is_production:
                print(f"ERROR: Failed to update professional profile for UID {uid}: {e}")
            else:
                print(f"ERROR: [ProfilingService] Profile update failed: {str(e)}")
            return False

    async def list_all_profiles(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all user profiles for admin dashboard.
        """
        is_production = settings.ENVIRONMENT.lower().strip() == "production"
        
        try:
            profiles_ref = self.db.collection(PROFILING_COLLECTION)
            
            if limit:
                profiles_ref = profiles_ref.limit(limit)
            
            profiles_query = profiles_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
            profiles_docs = await run_in_threadpool(profiles_query.stream)
            
            profiles = []
            for doc in profiles_docs:
                profile_data = doc.to_dict()
                
                # Convert Firestore timestamps
                if 'created_at' in profile_data and hasattr(profile_data['created_at'], 'ToDatetime'):
                    profile_data['created_at'] = profile_data['created_at'].ToDatetime()
                if 'updated_at' in profile_data and hasattr(profile_data['updated_at'], 'ToDatetime'):
                    profile_data['updated_at'] = profile_data['updated_at'].ToDatetime()
                
                profiles.append(profile_data)
            
            if not is_production:
                print(f"INFO: Retrieved {len(profiles)} professional profiles for admin")
            else:
                print(f"INFO: [ProfilingService] Retrieved profiles for admin")
            
            return profiles
            
        except Exception as e:
            if not is_production:
                print(f"ERROR: Failed to retrieve profiles for admin: {e}")
            else:
                print(f"ERROR: [ProfilingService] Admin profile retrieval failed: {str(e)}")
            return []

# Create global instance
profiling_service = ProfilingService()