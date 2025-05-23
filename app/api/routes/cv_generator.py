from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.cv import CVRequest, CVResponse, CoverLetterRequest, CoverLetterResponse
from app.services.gemini_service import GeminiService
from app.services.rate_limiter import RateLimiter
from app.api.dependencies import get_current_active_user_uid

router = APIRouter()
rate_limiter = RateLimiter() # This might also need to be user-specific later


@router.post("/generate", response_model=CVResponse)
async def generate_cv(
    request: CVRequest,
    gemini_service: GeminiService = Depends(GeminiService),
    current_user_uid: str = Depends(get_current_active_user_uid)
):
    """
    Generate a CV based on job description and resume.
    Requires authentication.
    """
    print(f"CV generation request for user UID: {current_user_uid}") # For logging

    # Check rate limits (TODO: make rate limiter user-aware for Phase 4)
    # For now, the global rate limiter applies.
    # Later, you could pass current_user_uid to rate_limiter.check_limit(current_user_uid)
    remaining, limit_reached = await rate_limiter.check_limit()
    if limit_reached:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily limit reached. Please try again tomorrow or upgrade to pro plan.",
        )

    try:
        # Generate CV using Gemini
        cv_data = await gemini_service.generate_cv(request.job_description, request.resume)

        # Update rate limit counter (TODO: make this user-specific for Phase 4)
        await rate_limiter.increment()

        # Return the CV data with quota information
        return {
            "cv_data": cv_data,
            "quota": { # This quota is currently global, will be user-specific in Phase 4
                "remaining": remaining - 1,  # Decrement by 1 to account for this request
                "total": rate_limiter.daily_quota,
            },
        }
    except Exception as e:
        import traceback
        print(f"Error in generate_cv: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating CV: {str(e)}",
        )

@router.post("/generate-cover-letter", response_model=CoverLetterResponse)
async def generate_cover_letter(
    request: CoverLetterRequest,
    gemini_service: GeminiService = Depends(GeminiService),
    current_user_uid: str = Depends(get_current_active_user_uid) # Add dependency
):
    """
    Generate a cover letter based on job description and resume.
    Requires authentication.
    """
    print(f"Cover letter generation request for user UID: {current_user_uid}") # For logging
    
    # Check rate limits (TODO: Phase 4)
    remaining, limit_reached = await rate_limiter.check_limit()
    if limit_reached: # And user is not premium (Phase 4)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily limit reached. Please try again tomorrow or upgrade to pro plan.",
        )

    try:
        # Generate cover letter using Gemini
        cover_letter = await gemini_service.generate_cover_letter(
            request.job_description, request.resume, request.feedback
        )

        # Update rate limit counter (TODO: Phase 4)
        await rate_limiter.increment()

        # Return the cover letter with quota information
        return {
            "cover_letter": cover_letter,
            "quota": { # Global quota for now
                "remaining": remaining - 1,  # Decrement by 1 to account for this request
                "total": rate_limiter.daily_quota,
            },
        }
    except Exception as e:
        import traceback
        print(f"Error in generate_cover_letter: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating cover letter: {str(e)}",
        )