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
      
      try:
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
                  timeout=60.0,  # Increased timeout
              )
              
              # Print response status for debugging
              print(f"Gemini API response status: {response.status_code}")
              
              try:
                  response.raise_for_status()
                  data = response.json()
                  
                  # Extract the response text from Gemini
                  result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                  
                  # Process the response to extract the JSON data
                  return self._extract_json(result_text)
              except Exception as e:
                  # Print more detailed error information
                  print(f"Error processing Gemini response: {str(e)}")
                  print(f"Response content: {response.text if response.text else 'No response content'}")
                  raise ValueError(f"Failed to process Gemini API response: {str(e)}")
      except Exception as e:
          print(f"Exception in Gemini API call: {str(e)}")
          raise ValueError(f"Gemini API error: {str(e)}")
    
    def _create_prompt(self, job_description: str, resume: str) -> str:
        """
        Create a structured prompt for the Gemini API.
        """
        return f"""
You are an expert CV tailor and professional career coach. Create a comprehensive CV tailored specifically for this job, focusing on relevance and professional presentation.

JOB DESCRIPTION:
{job_description}

CANDIDATE'S RESUME:
{resume}

1. Carefully analyze both the job description and resume to identify key matching skills, experience and qualifications.

2. Produce a structured, comprehensive CV in JSON format with these exact fields:
   - fullName: Full name from the resume
   - jobTitle: A tailored professional title that matches the target job
   - summary: A compelling, specific professional summary highlighting relevant qualifications (4-5 lines)
   - email, linkedin, phone, location: Contact details from resume
   
   - experience: An array of work experience entries, ordered by relevance to the job, with each containing:
     * jobTitle: Position title (keep original unless extremely relevant to modify)
     * company: Company name
     * dates: Employment period
     * description: Role description with responsibilities MOST relevant to target job
     * achievements: Array of 3+ measurable achievements with quantifiable results where possible
     * relevanceScore: A number 0-100 indicating how relevant this role is to the target job
   
   - education: Array of educational qualifications with:
     * degree: Degree/qualification name
     * institution: School/university name
     * dates: Study period
     * relevanceScore: Relevance to target job (0-100)
   
   - skills: Array of skills categorized by type (e.g., "Technical: skill1, skill2", "Soft Skills: skill1, skill2")
   - certifications: Array of relevant certifications with dates
   
   - skillGapAnalysis:
     * matchingSkills: Array of skills from resume that match job requirements
     * missingSkills: Array of skills mentioned in job that aren't clearly evident in resume
     * overallMatch: Overall match percentage (0-100)

3. Important Guidelines:
   - Focus on RELEVANCE above all else - ruthlessly prioritize content most relevant to this specific job
   - Include measurable achievements with numbers wherever possible
   - Use strong action verbs and industry-specific terminology from the job description
   - Be truthful but strategic in highlighting relevant experience
   - Ensure all JSON fields are properly formatted and complete
   - For each experience item, provide a relevanceScore that accurately reflects how relevant that position is to the target job

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