from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from typing import Optional
import traceback # For more detailed error logging

from app.schemas.cv import CVRequest, CVResponse, CoverLetterRequest, CoverLetterResponse
from app.services.gemini_service import GeminiService
from app.services.rate_limiter import RateLimiter
from app.api.dependencies import get_current_active_user_uid
from app.services.user_service import get_user_subscription_object # Added
from app.schemas.user import UserSubscription # Added
from app.core.config import settings # Added

router = APIRouter()
# The RateLimiter instance will be either in-memory or Redis-backed based on config.py and redis connection status
rate_limiter = RateLimiter() 


# Helper function to check premium access
def check_premium_access(subscription: Optional[UserSubscription], feature_name: str) -> bool:
    if feature_name not in settings.PREMIUM_FEATURES:
        return True # Not a premium feature, access granted

    if not subscription:
        return False # No subscription means no premium access for premium features

    # Check if the subscription tier is not 'free' and is 'active'
    # Also check if the subscription period is current
    is_active_premium = (
        subscription.tier and subscription.tier.lower() != "free" and
        subscription.status == "active" and
        (subscription.current_period_ends_at is None or 
         (isinstance(subscription.current_period_ends_at, datetime) and 
          subscription.current_period_ends_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)))
    )
    return is_active_premium

@router.post("/generate", response_model=CVResponse)
async def generate_cv(
    request: CVRequest,
    gemini_service: GeminiService = Depends(GeminiService),
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Generate a CV based on job description and resume.
    Requires authentication. Access to this feature may depend on subscription status.
    """
    print(f"CV generation request for user UID: {current_user_uid}")

    # 1. Fetch user subscription details
    user_subscription: Optional[UserSubscription] = await get_user_subscription_object(current_user_uid)
    current_tier = user_subscription.tier if user_subscription and user_subscription.tier else "free"
    print(f"User {current_user_uid} is on tier: {current_tier}")
    if user_subscription:
        print(f"Subscription details: Status='{user_subscription.status}', EndsAt='{user_subscription.current_period_ends_at}'")


    # 2. Check if this feature is premium and if the user has access
    feature_name = "gemini_cv_generation" # Matches settings.PREMIUM_FEATURES
    if feature_name in settings.PREMIUM_FEATURES:
        if not check_premium_access(user_subscription, feature_name):
            print(f"Access denied for user {current_user_uid} to premium feature '{feature_name}'.")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, # 402 Payment Required
                detail=f"CV Generation is a premium feature. Please upgrade your plan to access."
            )
        print(f"Access granted for user {current_user_uid} to premium feature '{feature_name}'.")

    # 3. Check rate limits based on user's UID and subscription tier
    remaining, limit_reached = await rate_limiter.check_limit(user_uid=current_user_uid, subscription_tier=current_tier)
    if limit_reached:
        print(f"Rate limit reached for user {current_user_uid} on tier {current_tier}.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily API quota for your '{current_tier}' plan reached. Please try again tomorrow or upgrade for a higher quota.",
        )
    print(f"User {current_user_uid} (Tier: {current_tier}) has {remaining} requests remaining before this one.")

    try:
        # Generate CV using Gemini
        cv_data = await gemini_service.generate_cv(request.job_description, request.resume)

        # Increment rate limit counter for the user
        await rate_limiter.increment(user_uid=current_user_uid, subscription_tier=current_tier)

        # Return the CV data with updated quota information
        return {
            "cv_data": cv_data,
            "quota": { 
                "remaining": remaining - 1, # Reflects quota after this request
                "total": rate_limiter._get_quota_for_tier(current_tier), # Gets the total based on tier
            },
        }
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except ValueError as ve: # Catch ValueErrors from Gemini service (e.g., JSON parsing)
        print(f"ValueError during CV generation for user {current_user_uid}: {str(ve)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # Or 500 if it's an unexpected internal error
            detail=f"Error processing request: {str(ve)}",
        )
    except Exception as e:
        print(f"Unexpected error in generate_cv for user {current_user_uid}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while generating the CV: {str(e)}",
        )

@router.post("/generate-cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter(
    request: CoverLetterRequest,
    gemini_service: GeminiService = Depends(GeminiService),
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Generate a cover letter based on job description and resume.
    Requires authentication. Access to this feature may depend on subscription status.
    """
    print(f"Cover letter generation request for user UID: {current_user_uid}")

    # 1. Fetch user subscription details
    user_subscription: Optional[UserSubscription] = await get_user_subscription_object(current_user_uid)
    current_tier = user_subscription.tier if user_subscription and user_subscription.tier else "free"
    print(f"User {current_user_uid} is on tier: {current_tier}")
    if user_subscription:
        print(f"Subscription details: Status='{user_subscription.status}', EndsAt='{user_subscription.current_period_ends_at}'")

    # 2. Check if this feature is premium and if the user has access
    feature_name = "gemini_cover_letter_generation" # Matches settings.PREMIUM_FEATURES
    if feature_name in settings.PREMIUM_FEATURES:
        if not check_premium_access(user_subscription, feature_name):
            print(f"Access denied for user {current_user_uid} to premium feature '{feature_name}'.")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED, # 402 Payment Required
                detail=f"Cover Letter Generation is a premium feature. Please upgrade your plan to access."
            )
        print(f"Access granted for user {current_user_uid} to premium feature '{feature_name}'.")

    # 3. Check rate limits based on user's UID and subscription tier
    remaining, limit_reached = await rate_limiter.check_limit(user_uid=current_user_uid, subscription_tier=current_tier)
    if limit_reached:
        print(f"Rate limit reached for user {current_user_uid} on tier {current_tier}.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily API quota for your '{current_tier}' plan reached. Please try again tomorrow or upgrade for a higher quota.",
        )
    print(f"User {current_user_uid} (Tier: {current_tier}) has {remaining} requests remaining before this one.")

    try:
        # Generate cover letter using Gemini
        cover_letter = await gemini_service.generate_cover_letter(
            request.job_description, request.resume, request.feedback
        )

        # Increment rate limit counter for the user
        await rate_limiter.increment(user_uid=current_user_uid, subscription_tier=current_tier)

        # Return the cover letter with updated quota information
        return {
            "cover_letter": cover_letter,
            "quota": { 
                "remaining": remaining - 1, # Reflects quota after this request
                "total": rate_limiter._get_quota_for_tier(current_tier), # Gets the total based on tier
            },
        }
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except ValueError as ve: # Catch ValueErrors from Gemini service
        print(f"ValueError during Cover Letter generation for user {current_user_uid}: {str(ve)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error processing request: {str(ve)}",
        )
    except Exception as e:
        print(f"Unexpected error in generate_cover_letter for user {current_user_uid}: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while generating the cover letter: {str(e)}",
        )