import json
from typing import Dict, Any

import httpx

from app.core.config import settings


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.api_url = f"{settings.GEMINI_API_URL}/{self.model}:generateContent"

    async def generate_cv(self, job_description: str, resume: str) -> Dict[str, Any]:
        """
        Generate a CV using Gemini AI based on job description and resume.
        """
        prompt = self._create_prompt(job_description, resume)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                headers={"Content-Type": "application/json"},
                params={"key": self.api_key},
                json={
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": prompt
                                }
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.2,
                        "topP": 0.8,
                        "topK": 40,
                        "maxOutputTokens": 2048,
                    }
                },
                timeout=30.0,
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract the response text from Gemini
            result_text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Process the response to extract the JSON data
            return self._extract_json(result_text)
    
    def _create_prompt(self, job_description: str, resume: str) -> str:
        """
        Create a structured prompt for the Gemini API.
        """
        return f"""
I need you to create a tailored CV in JSON format based on a candidate's resume and a job description.

JOB DESCRIPTION:
{job_description}

CANDIDATE'S RESUME:
{resume}

Please analyze the resume and the job description, then create a tailored CV that highlights the most relevant experiences, skills, and qualifications for this specific job.

Return ONLY the JSON data in the following format without any additional explanation or text:

```json
{{
  "fullName": "Candidate's full name from resume",
  "jobTitle": "A title that matches the job being applied for",
  "summary": "A concise professional summary tailored to this role",
  "email": "Email from resume",
  "linkedin": "LinkedIn URL from resume (or created based on name)",
  "phone": "Phone number from resume",
  "location": "Location from resume",
  
  "experience": [
    {{
      "jobTitle": "Position title",
      "company": "Company name",
      "dates": "Start date - End date (or Present)",
      "description": "Brief description focused on relevant responsibilities",
      "achievements": [
        "Achievement 1 with quantifiable results",
        "Achievement 2 with quantifiable results",
        "Achievement 3 with quantifiable results"
      ],
      "relevanceScore": 95
    }}
  ],
  
  "education": [
    {{
      "degree": "Degree name",
      "institution": "Institution name",
      "dates": "Start year - End year",
      "relevanceScore": 80
    }}
  ],
  
  "skills": [
    "Technical: Skill1, Skill2, Skill3",
    "Soft Skills: Communication, Leadership, Problem-solving"
  ],
  
  "certifications": [
    "Certification 1 with year if available",
    "Certification 2 with year if available"
  ],
  
  "skillGapAnalysis": {{
    "matchingSkills": ["List skills from resume that match job requirements"],
    "missingSkills": ["Important skills mentioned in job that candidate doesn't have"],
    "overallMatch": 85
  }}
}}
```

Prioritize skills and experience that are most relevant to the job description. For each experience and education item, add a relevanceScore from 0-100 indicating relevance to this job. Include the skillGapAnalysis section to help understand the fit for the role.
        """
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from Gemini's response text.
        """
        # Try to extract JSON from the response
        try:
            # Check if response contains a code block with JSON
            if "```json" in text and "```" in text.split("```json", 1)[1]:
                json_str = text.split("```json", 1)[1].split("```", 1)[0].strip()
                return json.loads(json_str)
            
            # Check if response contains any JSON block
            elif "```" in text and "```" in text.split("```", 1)[1]:
                json_str = text.split("```", 1)[1].split("```", 1)[0].strip()
                return json.loads(json_str)
            
            # Otherwise, try to parse the entire response as JSON
            else:
                return json.loads(text.strip())
                
        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"Failed to extract valid JSON from Gemini response: {str(e)}")