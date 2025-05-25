from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.schemas.cv import CVResponse # Reusing CVResponse
from app.schemas.user import UserSubscription
from app.services.cv_parser_service import cv_parser_service, CVParserService
from app.services.gemini_service import GeminiService
from app.services.rate_limiter import RateLimiter
from app.api.dependencies import get_current_active_user_uid
from app.services.user_service import get_user_subscription_object
from app.core.config import settings
from app.api.routes.cv_generator import check_premium_access # Reusing the helper from cv_generator

router = APIRouter()
rate_limiter = RateLimiter() # Assuming RateLimiter is a singleton or configured globally

@router.post("/upload_and_parse_cv", response_model=CVResponse)
async def upload_and_parse_cv(
    file: UploadFile = File(...),
    gemini_service: GeminiService = Depends(GeminiService),
    parser_service: CVParserService = Depends(lambda: cv_parser_service), # Dependency injection for the service
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Uploads a CV file (PDF or DOCX), extracts text, structures it using AI,
    and returns the structured CV JSON.
    Requires authentication and premium subscription status.
    """
    print(f"CV upload and parse request for user UID: {current_user_uid}")

    # 1. Fetch user subscription details
    user_subscription: Optional[UserSubscription] = await get_user_subscription_object(current_user_uid)
    current_tier = user_subscription.tier if user_subscription and user_subscription.tier else "free"
    print(f"User {current_user_uid} is on tier: {current_tier}")

    # 2. Check if this feature is premium and if the user has access
    feature_name = "cv_upload_and_parse" # Matches settings.PREMIUM_FEATURES
    if feature_name in settings.PREMIUM_FEATURES:
        if not check_premium_access(user_subscription, feature_name): # Using helper from cv_generator.py
            print(f"Access denied for user {current_user_uid} to premium feature '{feature_name}'.")
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"CV Upload & Parse is a premium feature. Please upgrade your plan to access."
            )
        print(f"Access granted for user {current_user_uid} to premium feature '{feature_name}'.")

    # 3. Check rate limits (if this feature should also be rate-limited like generation)
    # For now, let's assume it shares the same general API quota.
    remaining, limit_reached = await rate_limiter.check_limit(user_uid=current_user_uid, subscription_tier=current_tier)
    if limit_reached:
        print(f"Rate limit reached for user {current_user_uid} on tier {current_tier}.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily API quota for your '{current_tier}' plan reached. Please try again tomorrow or upgrade for a higher quota.",
        )
    print(f"User {current_user_uid} (Tier: {current_tier}) has {remaining} requests remaining before this one (upload/parse).")

    # 4. Extract text from the uploaded file
    try:
        extracted_text = await parser_service.extract_text_from_file(file)
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not extract any text from the uploaded CV. The file might be empty, an image, or corrupted."
            )
    except ValueError as ve: # Catch errors from parser_service (e.g., unsupported format)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        print(f"Error during file processing for user {current_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the file: {str(e)}"
        )

    # 5. Structure the extracted text using GeminiService
    try:
        structured_cv_data = await gemini_service.structure_cv_from_text(extracted_text)

        # Increment rate limit counter
        await rate_limiter.increment(user_uid=current_user_uid, subscription_tier=current_tier)

        return CVResponse(
            cv_data=structured_cv_data,
            quota= {
                "remaining": remaining - 1, # Quota after this request
                "total": rate_limiter._get_quota_for_tier(current_tier),
            }
        )
    except ValueError as ve: # Errors from Gemini service (e.g., JSON parsing or API call failure)
        print(f"ValueError during CV structuring for user {current_user_uid}: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, # Could be 500 if it's Gemini's fault
            detail=f"Error structuring CV data: {str(ve)}"
        )
    except Exception as e:
        print(f"Unexpected error during CV structuring for user {current_user_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while structuring the CV: {str(e)}"
        )