from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime

class NonProfessionalExperience(BaseModel):
    description: str = Field(..., description="Non-professional experiences and activities")

class ProfilingQuestions(BaseModel):
    work_approach: str = Field(..., description="How user approaches challenging projects")
    problem_solving: str = Field(..., description="Recent challenge and how they solved it")
    work_values: str = Field(..., description="What matters most in ideal work environment")

class ProfilingRequest(BaseModel):
    cv_text: str = Field(..., description="User's CV/resume text")
    non_professional_experience: str = Field(..., description="Non-professional experiences")
    profiling_questions: ProfilingQuestions
    
    class Config:
        json_schema_extra = {
            "example": {
                "cv_text": "John Doe\nSoftware Engineer with 5 years experience...",
                "non_professional_experience": "Organized community events, led church technology team...",
                "profiling_questions": {
                    "work_approach": "independent",
                    "problem_solving": "When our church website went down before a major event, I quickly diagnosed the server issue...",
                    "work_values": "learning"
                }
            }
        }

class PersonalityProfile(BaseModel):
    traits: Dict[str, Any] = Field(..., description="Big Five personality traits and scores")
    work_style: str = Field(..., description="Preferred work style description")
    leadership_potential: str = Field(..., description="Leadership style and potential")
    team_dynamics: str = Field(..., description="How they work in teams")

class SkillsAssessment(BaseModel):
    technical_skills: List[Dict[str, Any]] = Field(..., description="Technical skills with proficiency levels")
    soft_skills: List[Dict[str, Any]] = Field(..., description="Soft skills with proficiency levels")
    transferable_skills: List[Dict[str, Any]] = Field(..., description="Skills from non-professional experience")
    skill_gaps: List[str] = Field(..., description="Areas for improvement")

class RoleFitAnalysis(BaseModel):
    suitable_roles: List[Dict[str, Any]] = Field(..., description="Roles they would excel in")
    role_match_scores: Dict[str, float] = Field(..., description="Match scores for different role types")
    career_level_assessment: str = Field(..., description="Current career level and readiness")

class CareerDevelopment(BaseModel):
    recommended_next_steps: List[str] = Field(..., description="Specific career development actions")
    skill_development_priorities: List[str] = Field(..., description="Skills to develop first")
    career_progression_paths: List[Dict[str, Any]] = Field(..., description="Possible career paths")
    timeline_recommendations: Dict[str, str] = Field(..., description="Timeframes for different goals")

class BehavioralInsights(BaseModel):
    decision_making_style: str = Field(..., description="How they make decisions")
    communication_style: str = Field(..., description="Preferred communication approach")
    motivation_drivers: List[str] = Field(..., description="What motivates them professionally")
    potential_challenges: List[str] = Field(..., description="Areas that might be challenging")
    work_environment_preferences: List[str] = Field(..., description="Ideal work environment characteristics")

class ProfessionalProfile(BaseModel):
    personality_profile: PersonalityProfile
    skills_assessment: SkillsAssessment
    role_fit_analysis: RoleFitAnalysis
    career_development: CareerDevelopment
    behavioral_insights: BehavioralInsights
    confidence_score: float = Field(..., description="Overall confidence in the analysis (0-1)")
    generated_at: datetime = Field(..., description="When this profile was generated")

class ProfilingResponse(BaseModel):
    profile: ProfessionalProfile
    quota: Dict[str, int] = Field(..., description="Remaining API quota information")