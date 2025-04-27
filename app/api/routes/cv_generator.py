from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.cv import CVRequest, CVResponse, CoverLetterRequest, CoverLetterResponse
from app.services.gemini_service import GeminiService
from app.services.rate_limiter import RateLimiter

router = APIRouter()
rate_limiter = RateLimiter()


@router.post("/generate", response_model=CVResponse)
async def generate_cv(
    request: CVRequest, gemini_service: GeminiService = Depends(GeminiService)
):
    """
    Generate a CV based on job description and resume.
    """
    # Check rate limits
    remaining, limit_reached = await rate_limiter.check_limit()
    if limit_reached:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily limit reached. Please try again tomorrow.",
        )

    try:
        # Generate CV using Gemini
        cv_data = await gemini_service.generate_cv(request.job_description, request.resume)

        # Update rate limit counter
        await rate_limiter.increment()

        # Return the CV data with quota information
        return {
            "cv_data": cv_data,
            "quota": {
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
    request: CoverLetterRequest, gemini_service: GeminiService = Depends(GeminiService)
):
    """
    Generate a cover letter based on job description and resume.
    """
    # Check rate limits
    remaining, limit_reached = await rate_limiter.check_limit()
    if limit_reached:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily limit reached. Please try again tomorrow.",
        )

    try:
        # Generate cover letter using Gemini
        cover_letter = await gemini_service.generate_cover_letter(
            request.job_description, request.resume, request.feedback
        )

        # Update rate limit counter
        await rate_limiter.increment()

        # Return the cover letter with quota information
        return {
            "cover_letter": cover_letter,
            "quota": {
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