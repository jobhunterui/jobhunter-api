from typing import Dict, Any, Optional

from pydantic import BaseModel, Field


class CVRequest(BaseModel):
    job_description: str = Field(..., description="The full job description")
    resume: str = Field(..., description="User's current resume/CV")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_description": "We are looking for a Software Engineer with experience in Python and FastAPI...",
                "resume": "John Doe\nExperienced Software Engineer\n...",
            }
        }


class QuotaInfo(BaseModel):
    remaining: int = Field(..., description="Remaining requests for the day")
    total: int = Field(..., description="Total daily quota")


class CVResponse(BaseModel):
    cv_data: Dict[str, Any] = Field(..., description="Generated CV data in JSON format")
    quota: QuotaInfo