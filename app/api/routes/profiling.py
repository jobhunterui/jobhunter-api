from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from app.schemas.profiling import ProfilingRequest, ProfilingResponse, ProfessionalProfile
from app.schemas.user import UserSubscription
from app.services.gemini_service import GeminiService
from app.services.profiling_service import profiling_service, ProfilingService
from app.services.rate_limiter import RateLimiter
from app.api.dependencies import get_current_active_user_uid, get_current_admin_user_uid
from app.services.user_service import get_user_subscription_object
from app.core.config import settings

router = APIRouter()
rate_limiter = RateLimiter()

def check_profiling_access(user_subscription: Optional[UserSubscription], feature_name: str) -> bool:
    """
    Check if user has access to profiling features.
    Currently profiling is free for all users, but this allows future premium gating.
    """
    # TEMPORARILY DISABLED: Premium feature checks - profiling now free
    # Original premium logic preserved for re-enabling later:
    # if feature_name in settings.PREMIUM_FEATURES:
    #     if not user_subscription or user_subscription.tier == "free":
    #         return False
    #     if user_subscription.status != "active":
    #         return False
    #     if user_subscription.current_period_ends_at:
    #         if datetime.now(timezone.utc) > user_subscription.current_period_ends_at:
    #             return False
    
    return True  # Always allow access - profiling is free

@router.post("/generate_profile", response_model=ProfilingResponse)
async def generate_professional_profile(
    request: ProfilingRequest,
    gemini_service: GeminiService = Depends(GeminiService),
    profiling_svc: ProfilingService = Depends(lambda: profiling_service),
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Generate a comprehensive professional profile using AI analysis.
    Analyzes CV, non-professional experience, and profiling questions.
    """
    print(f"Professional profiling request for user UID: {current_user_uid}")

    # 1. Fetch user subscription details
    user_subscription: Optional[UserSubscription] = await get_user_subscription_object(current_user_uid)
    current_tier = user_subscription.tier if user_subscription and user_subscription.tier else "free"
    print(f"User {current_user_uid} is on tier: {current_tier}")

    # 2. Check if user has access to profiling features
    feature_name = "professional_profiling"
    if not check_profiling_access(user_subscription, feature_name):
        print(f"Access denied for user {current_user_uid} to feature '{feature_name}'.")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Professional profiling is a premium feature. Please upgrade your plan to access."
        )
    print(f"Access granted for user {current_user_uid} to feature '{feature_name}'.")

    # 3. Check rate limits
    remaining, limit_reached = await rate_limiter.check_limit(user_uid=current_user_uid, subscription_tier=current_tier)
    if limit_reached:
        print(f"Rate limit reached for user {current_user_uid} on tier {current_tier}.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily API quota for your '{current_tier}' plan reached. Please try again tomorrow or upgrade for a higher quota.",
        )
    print(f"User {current_user_uid} (Tier: {current_tier}) has {remaining} requests remaining before this one (profiling).")

    # 4. Generate professional profile using Gemini
    try:
        # Convert profiling questions to dict for Gemini service
        questions_dict = {
            "work_approach": request.profiling_questions.work_approach,
            "problem_solving": request.profiling_questions.problem_solving,
            "work_values": request.profiling_questions.work_values
        }
        
        profile_data = await gemini_service.generate_professional_profile(
            cv_text=request.cv_text,
            non_professional_experience=request.non_professional_experience,
            profiling_questions=questions_dict
        )

        # Increment rate limit counter
        await rate_limiter.increment(user_uid=current_user_uid, subscription_tier=current_tier)

        # 5. Save profile to database
        save_success = await profiling_svc.save_user_profile(current_user_uid, profile_data)
        if not save_success:
            print(f"WARNING: Failed to save profile to database for user {current_user_uid}")
            # Continue anyway - the profile generation was successful

        # 6. Create response
        try:
            professional_profile = ProfessionalProfile(**profile_data)
        except Exception as validation_error:
            print(f"Profile validation error for user {current_user_uid}: {validation_error}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Generated profile data validation failed: {str(validation_error)}"
            )

        return ProfilingResponse(
            profile=professional_profile,
            quota={
                "remaining": remaining - 1,
                "total": rate_limiter._get_quota_for_tier(current_tier),
            }
        )

    except ValueError as ve:
        print(f"ValueError during profiling for user {current_user_uid}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error generating professional profile: {str(ve)}"
        )
    except Exception as e:
        print(f"Unexpected error during profiling for user {current_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while generating your professional profile: {str(e)}"
        )
        
@router.post("/save_profile")
async def save_my_profile(
    # The request body from the frontend will be validated against this Pydantic model
    request_data: dict, 
    # This dependency gives us access to the ProfilingService (the "engine")
    profiling_svc: ProfilingService = Depends(lambda: profiling_service),
    # This dependency gets the user's UID from their token
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Saves or updates a user's professional profile from the cloud sync.
    The frontend sends the profile data in the request body.
    """
    print(f"Profile save request for user UID: {current_user_uid}")
    
    # Extract the actual profile data from the request
    profile_data_to_save = request_data.get("profile_data")
    if not profile_data_to_save:
        raise HTTPException(status_code=400, detail="Missing 'profile_data' in request.")

    try:
        # HERE IS THE KEY: We are calling the EXISTING service method you pointed out.
        # This new endpoint acts as the bridge from the internet to your service logic.
        success = await profiling_svc.save_user_profile(current_user_uid, profile_data_to_save)
        
        if success:
            return {"status": "success", "message": "Profile saved successfully."}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save profile in the service."
            )
    except Exception as e:
        print(f"Error in /save_profile endpoint for user {current_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while saving your profile: {str(e)}"
        )

@router.get("/my_profile")
async def get_my_profile(
    profiling_svc: ProfilingService = Depends(lambda: profiling_service),
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Retrieve the current user's saved professional profile.
    """
    print(f"Profile retrieval request for user UID: {current_user_uid}")
    
    try:
        profile_data = await profiling_svc.get_user_profile(current_user_uid)
        
        if not profile_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No professional profile found. Please generate a profile first."
            )
        
        return {
            "uid": profile_data["uid"],
            "profile": profile_data["profile_data"],
            "created_at": profile_data["created_at"],
            "updated_at": profile_data["updated_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving profile for user {current_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving your professional profile: {str(e)}"
        )

@router.get("/admin/all_profiles")
async def get_all_profiles_admin(
    limit: Optional[int] = 50,
    profiling_svc: ProfilingService = Depends(lambda: profiling_service),
    admin_user_uid: str = Depends(get_current_admin_user_uid)
):
    """
    Admin endpoint to retrieve all user profiles.
    """
    print(f"Admin profile retrieval request from user UID: {admin_user_uid}")

    try:
        profiles = await profiling_svc.list_all_profiles(limit=limit)
        
        return {
            "profiles": profiles,
            "total_count": len(profiles),
            "limit_applied": limit
        }
        
    except Exception as e:
        print(f"Error retrieving profiles for admin {admin_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user profiles: {str(e)}"
        )