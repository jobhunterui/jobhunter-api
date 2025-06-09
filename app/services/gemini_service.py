import json
from typing import Dict, Any
from datetime import datetime

import httpx
import re

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
                            "maxOutputTokens": 4096,  # Increased from 2048 to 4096
                        }
                    },
                    timeout=120.0,  # Increased from 60 to 120 seconds
                )
                
                # Print response status for debugging
                print(f"Gemini API response status: {response.status_code}")
                
                try:
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract the response text from Gemini
                    result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    finish_reason = data["candidates"][0].get("finishReason", "UNKNOWN")
                    
                    if finish_reason == "MAX_TOKENS":
                        print("Warning: Gemini response was truncated due to MAX_TOKENS limit")
                    
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
        Create an ATS-optimized prompt for the Gemini API (gemini-2.0-flash) for CV generation.
        """
        # It's crucial to be very explicit with gemini-2.0-flash.
        # We will guide it step-by-step for each part of the CV.
        return f"""
You are an expert CV tailoring AI. Your task is to generate a highly ATS-optimized CV in JSON format.
You MUST strictly adhere to the instructions and the JSON output format.
Base all experience, skills, and education on the "USER'S RESUME" provided.
Tailor the content using keywords and requirements from the "TARGET JOB DESCRIPTION".

TARGET JOB DESCRIPTION:
---
{job_description}
---

USER'S RESUME (Source of Truth for user's experience):
---
{resume}
---

CRITICAL INSTRUCTIONS FOR ATS OPTIMIZATION (Follow these meticulously):

1.  **Keyword Extraction & Integration (MOST IMPORTANT):**
    * Identify ALL relevant keywords from the "TARGET JOB DESCRIPTION". This includes hard skills, soft skills, tools, technologies, industry terms, and action verbs.
    * Your primary goal is to incorporate these exact keywords naturally throughout the generated CV sections.
    * Use the *exact phrasing* from the job description. If it says "data analysis", use "data analysis".
    * If the job description uses an acronym (e.g., "CRM"), include it. If it uses the full term (e.g., "Customer Relationship Management"), use that. If both, use both if space permits or choose the one most prominent.

2.  **JSON Output Structure (MANDATORY):**
    * You MUST return ONLY a single, valid JSON object. No introductory text, no explanations, no markdown formatting around the JSON.
    * The JSON structure provided below under "EXPECTED JSON OUTPUT FORMAT" is the exact format you must follow. Do not deviate.

3.  **Field-Specific Instructions:**

    * `fullName`: Extract directly from "USER'S RESUME".
    * `jobTitle`: Use the EXACT job title from the "TARGET JOB DESCRIPTION". This is critical for ATS matching.
    * `summary`:
        * Create a compelling 3-4 line professional summary.
        * This summary MUST be heavily tailored to the "TARGET JOB DESCRIPTION".
        * Incorporate at least 3-5 of the MOST IMPORTANT keywords from the "TARGET JOB DESCRIPTION" into this summary naturally.
        * Clearly state the candidate's suitability for THIS SPECIFIC ROLE.
    * `email`, `linkedin`, `phone`, `location`: Extract directly from "USER'S RESUME". If LinkedIn is missing, provide an empty string.
    * `experience` (Array of objects):
        * For each role from "USER'S RESUME":
            * `jobTitle`: Use the job title from "USER'S RESUME".
            * `company`: Use the company name from "USER'S RESUME".
            * `dates`: Use the dates from "USER'S RESUME".
            * `description`: Write a brief (1-2 sentences) overview of the role. Infuse this description with relevant keywords from the "TARGET JOB DESCRIPTION" that align with the responsibilities of that past role.
            * `achievements`: (Array of strings) List 2-3 key achievements for this role, taken from "USER'S RESUME".
                * Rephrase these achievements to include keywords from the "TARGET JOB DESCRIPTION" where natural and truthful.
                * Start each achievement with a strong action verb (many can be found in the "TARGET JOB DESCRIPTION").
                * Quantify achievements with numbers/percentages from "USER'S RESUME" whenever possible.
            * `keywordsUsedInEntry`: (Array of strings) List the specific keywords from the "TARGET JOB DESCRIPTION" that you successfully incorporated into THIS experience entry (description and achievements). This is for verification.
    * `education` (Array of objects):
        * For each educational qualification from "USER'S RESUME":
            * `degree`: Degree name from "USER'S RESUME".
            * `institution`: Institution name from "USER'S RESUME".
            * `dates`: Graduation year or dates of study from "USER'S RESUME".
    * `skills` (Object with array values): THIS SECTION IS CRUCIAL FOR ATS.
        * `technicalSkills`: List all technical skills from "USER'S RESUME" that are ALSO mentioned or implied in the "TARGET JOB DESCRIPTION". Add any other key technical skills from "USER'S RESUME".
        * `softwareAndTools`: List all software/tools from "USER'S RESUME" that are ALSO mentioned in the "TARGET JOB DESCRIPTION". Add any other key software/tools from "USER'S RESUME".
        * `methodologiesAndFrameworks`: List relevant methodologies (Agile, Scrum, etc.) from "USER'S RESUME", especially if mentioned in "TARGET JOB DESCRIPTION".
        * `softSkills`: List key soft skills (communication, leadership, etc.) from "USER'S RESUME" that are relevant to the "TARGET JOB DESCRIPTION".
        * `otherSkills`: Any other relevant skills from "USER'S RESUME" that match keywords in "TARGET JOB DESCRIPTION".
        * **For all skill categories: Prioritize including skills that are explicitly mentioned in the "TARGET JOB DESCRIPTION" AND are present in the "USER'S RESUME".**
    * `certifications`: (Array of strings) List all certifications from "USER'S RESUME".
    * `atsAnalysis` (Object):
        * `jobDescriptionKeywords`: List up to 10-15 of the most important keywords you identified from the "TARGET JOB DESCRIPTION".
        * `integratedKeywords`: List the keywords from `jobDescriptionKeywords` that you successfully and naturally incorporated into the CV JSON.
        * `keywordCoverageNotes`: Briefly state how well keywords were covered. E.g., "Good coverage of core technical skills and responsibilities."

4.  **Truthfulness:**
    * All information regarding experience, skills, and education MUST be based on the "USER'S RESUME".
    * DO NOT invent or fabricate any information. Enhance and tailor, but stick to the facts in the user's resume.

EXPECTED JSON OUTPUT FORMAT (Strictly adhere to this structure):
```json
{{
  "fullName": "string",
  "jobTitle": "string (Exact from Target Job Description)",
  "summary": "string (3-4 lines, keyword-rich, tailored)",
  "email": "string",
  "linkedin": "string",
  "phone": "string",
  "location": "string",
  "experience": [
    {{
      "jobTitle": "string",
      "company": "string",
      "dates": "string",
      "description": "string (1-2 sentences, keyword-infused)",
      "achievements": [
        "string (quantified, keyword-infused achievement 1)",
        "string (quantified, keyword-infused achievement 2)"
      ],
      "keywordsUsedInEntry": ["keyword1", "keyword2"]
    }}
  ],
  "education": [
    {{
      "degree": "string",
      "institution": "string",
      "dates": "string"
    }}
  ],
  "skills": {{
    "technicalSkills": ["skill1", "skill2"],
    "softwareAndTools": ["tool1", "tool2"],
    "methodologiesAndFrameworks": ["methodology1"],
    "softSkills": ["soft_skill1"],
    "otherSkills": ["other_skill1"]
  }},
  "certifications": [
    "string (certification name 1)"
  ],
  "atsAnalysis": {{
    "jobDescriptionKeywords": ["jd_keyword1", "jd_keyword2"],
    "integratedKeywords": ["cv_integrated_keyword1", "cv_integrated_keyword2"],
    "keywordCoverageNotes": "string (Brief note on keyword integration)"
  }}
}}
```

Now, generate the CV based on the provided "TARGET JOB DESCRIPTION" and "USER'S RESUME", strictly following all instructions and the JSON format.
"""
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from Gemini's response text, handling truncated responses.
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
                # Check if this might be a truncated JSON response
                if text.strip().startswith("{") and not text.strip().endswith("}"):
                    # It's truncated - attempt to repair it
                    print(f"Detected truncated JSON response, attempting repair...")
                    
                    # Complete the JSON structure (basic attempt)
                    repaired_json = self._repair_truncated_json(text.strip())
                    return json.loads(repaired_json)
                
                return json.loads(text.strip())
                
        except (json.JSONDecodeError, IndexError) as e:
            # Try an aggressive repair on JSON parsing errors
            try:
                print(f"Attempting aggressive JSON repair for: {text[:100]}...")
                repaired_json = self._repair_truncated_json(text)
                return json.loads(repaired_json)
            except Exception as repair_error:
                print(f"Repair attempt failed: {str(repair_error)}")
                raise ValueError(f"Failed to extract valid JSON from Gemini response: {str(e)}")

    def _repair_truncated_json(self, text: str) -> str:
        """
        Attempts to repair truncated JSON responses by finding the structure
        and completing missing elements.
        """
        # Handle code blocks first
        if "```json" in text:
            # Extract content from code block
            content = text.split("```json", 1)[1]
            if "```" in content:
                content = content.split("```", 1)[0].strip()
            else:
                content = content.strip()
        else:
            content = text.strip()
        
        # Check if we have a valid JSON start
        if not content.startswith("{"):
            content = content[content.find("{"):] if "{" in content else "{}"
        
        # Basic structure completion
        brace_count = content.count("{") - content.count("}")
        bracket_count = content.count("[") - content.count("]")
        
        # If we have unclosed braces/brackets, close them
        if brace_count > 0 or bracket_count > 0:
            # Try to find the last complete object/element
            # This is a heuristic approach, not perfect
            lines = content.split("\n")
            cleaned_lines = []
            
            # Keep track of the structure
            in_array = False
            array_item_count = 0
            current_property = None
            
            for line in lines:
                # Skip obviously truncated lines
                if line.strip().endswith(",") and not line.strip().endswith("\","):
                    line = line.rstrip(",")
                
                # Track if we're in an array
                if "[" in line and "]" not in line:
                    in_array = True
                
                if in_array and "," in line:
                    array_item_count += 1
                
                if "]" in line:
                    in_array = False
                
                # Check for property names
                property_match = re.search(r'"(\w+)"\s*:', line)
                if property_match:
                    current_property = property_match.group(1)
                
                cleaned_lines.append(line)
            
            # Join the cleaned lines
            content = "\n".join(cleaned_lines)
            
            # Create a valid JSON structure to complete the truncated one
            if current_property and current_property == "relevanceScore":
                # We were in the middle of a relevance score (common truncation point)
                content += " 60"  # Add a default relevance score
            
            # Close any unclosed structures
            if in_array:
                content += "]"
            
            # Add closing braces/brackets
            content += "}" * brace_count + "]" * bracket_count
        
        # Make sure we have a complete JSON object
        if not content.endswith("}"):
            content += "}"
        
        # Double-check that we have valid JSON structure
        try:
            # Quick validation without full parsing
            if not (content.startswith("{") and content.endswith("}")):
                raise ValueError("Not a valid JSON object structure")
                
            # Remove any trailing commas before closing braces/brackets
            content = re.sub(r',\s*}', '}', content)
            content = re.sub(r',\s*]', ']', content)
            
            return content
            
        except Exception as e:
            print(f"Repair validation failed: {str(e)}")
            # If repair failed, return a minimal valid JSON
            return '{"fullName": "Repair Failed", "error": "Could not extract complete CV data"}'

    async def generate_cover_letter(self, job_description: str, resume: str, feedback: str = "") -> str:
        """
        Generate a cover letter using Gemini AI based on job description and resume.
        """
        prompt = self._create_cover_letter_prompt(job_description, resume, feedback)
        
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
                            "maxOutputTokens": 4096,
                        }
                    },
                    timeout=120.0,
                )
                
                # Print response status for debugging
                print(f"Gemini API response status for cover letter: {response.status_code}")
                
                try:
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract the response text from Gemini
                    result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    finish_reason = data["candidates"][0].get("finishReason", "UNKNOWN")
                    
                    if finish_reason == "MAX_TOKENS":
                        print("Warning: Gemini response was truncated due to MAX_TOKENS limit")
                    
                    # Return the cover letter text
                    return result_text.strip()
                except Exception as e:
                    print(f"Error processing Gemini response for cover letter: {str(e)}")
                    print(f"Response content: {response.text if response.text else 'No response content'}")
                    raise ValueError(f"Failed to process Gemini API response: {str(e)}")
        except Exception as e:
            print(f"Exception in Gemini API call for cover letter: {str(e)}")
            raise ValueError(f"Gemini API error: {str(e)}")

    def _create_cover_letter_prompt(self, job_description: str, resume: str, feedback: str = "") -> str:
        """
        Create an ATS-optimized prompt for the Gemini API (gemini-2.0-flash) for Cover Letter generation.
        This prompt emphasizes a structure that addresses job requirements directly.
        """
        feedback_section = ""
        if feedback:
            feedback_section = f"""
IMPORTANT FEEDBACK ON PREVIOUS ATTEMPT (Address this carefully):
---
{feedback}
---
"""

        # Inspired by the user's successful cover letter structure.
        # We need to guide gemini-2.0-flash very explicitly.
        return f"""
You are an expert cover letter writing AI. Your task is to generate a professional, highly ATS-optimized cover letter.
You MUST strictly adhere to all instructions.
The cover letter should be based on the "USER'S RESUME" and tailored to the "TARGET JOB DESCRIPTION".
The primary goal is to clearly show how the candidate's experience meets the key requirements of the job.

TARGET JOB DESCRIPTION:
---
{job_description}
---

USER'S RESUME (Source of Truth for user's experience):
---
{resume}
---

{feedback_section}

CRITICAL INSTRUCTIONS FOR COVER LETTER STRUCTURE & ATS OPTIMIZATION:

1.  **Overall Tone & Length:**
    * Professional, confident, and enthusiastic.
    * Concise: Aim for 3-4 main body paragraphs, under 400 words ideally.

2.  **Standard Formatting (MANDATORY):**
    * **Your Name & Contact Info:** (The AI should state that the user needs to add this manually at the top, as it cannot know it from the resume for a letter header)
        * Example: "[Your Name]\n[Your Phone]\n[Your Email]\n[Your LinkedIn Profile URL (Optional)]"
    * **Date:** (The AI should use a placeholder like "[Current Date]")
    * **Hiring Manager/Company Address:**
        * "Hiring Manager"
        * "{{"Company Name from Job Description"}}" (The AI should extract this)
        * "[Company Address - if known, otherwise skip]"
    * **Salutation:** "Dear Hiring Manager,"
    * **Closing:** "Sincerely,"
    * **Your Typed Name:** "[Your Name]"

3.  **Content - Paragraph by Paragraph Structure:**

    * **Paragraph 1: Introduction (Clear and Direct)**
        * State the EXACT job title you are applying for (from "TARGET JOB DESCRIPTION").
        * State the company name (from "TARGET JOB DESCRIPTION").
        * Briefly express strong interest in the role and the company.
        * Mention 1-2 key aspects of your experience or the company that make this a good fit.

    * **Paragraphs 2-3 (or 2-4): Requirement-Driven Body (THE CORE - MIMIC THIS STRUCTURE)**
        * **Identify Key Requirements:** From the "TARGET JOB DESCRIPTION", identify 2-3 of the MOST CRITICAL and distinct requirements, skills, or experience areas the job asks for.
        * **Address Each Requirement:** Dedicate a short paragraph (or a significant portion of a paragraph) to EACH key requirement identified.
        * **Structure for Each Requirement:**
            * Start by clearly referencing the requirement (e.g., "Regarding your need for X...", "My experience in Y aligns well with your requirements for...", "The job description highlights the importance of Z, an area where I have demonstrated success...").
            * Provide specific examples from the "USER'S RESUME" that demonstrate your proficiency or achievements related to THAT specific requirement.
            * Use keywords from the "TARGET JOB DESCRIPTION" naturally within these examples.
            * Quantify achievements (numbers, percentages) from the "USER'S RESUME" whenever possible.
        * **Do NOT use generic paragraphs.** Each body paragraph must be tied to a specific, identifiable requirement from the job description.

    * **Final Paragraph: Company Fit & Call to Action**
        * Briefly reiterate your enthusiasm for this specific role at this specific company.
        * Mention something specific about the company (its mission, a recent project, values, market position – if easily inferable or if the AI has general knowledge) that attracts you, and briefly connect it to your own values or goals.
        * State your confidence in your ability to contribute.
        * Politely express your desire for an interview ("I am eager to discuss my qualifications further in an interview.").

4.  **Keyword Integration (ATS CRITICAL):**
    * Naturally weave in keywords from the "TARGET JOB DESCRIPTION" (skills, technologies, responsibilities, industry terms) throughout the letter, especially in the requirement-driven body paragraphs.
    * Use the exact job title from the "TARGET JOB DESCRIPTION" at least once in the opening.

5.  **Truthfulness:**
    * All claims about experience and skills MUST be supported by the "USER'S RESUME". Do not invent.

RETURN ONLY THE FULL TEXT OF THE COVER LETTER. No extra explanations, no preambles, no JSON. Just the letter.
Start with "[Your Name]" placeholder for the header and end with "[Your Name]" placeholder for the signature.
Use "[Current Date]" as a placeholder for the date.
Use the actual company name from the job description in the recipient address block.
"""
    
    async def structure_cv_from_text(self, cv_text: str) -> Dict[str, Any]:
        """
        Structures raw CV text into JSON format using Gemini AI.
        """
        prompt = self._create_structure_cv_prompt(cv_text)

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
                                    {"text": prompt}
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.1,  # Lower temperature for more deterministic structuring
                            "topP": 0.8,
                            "topK": 40,
                            "maxOutputTokens": 4096,
                        }
                    },
                    timeout=120.0,
                )

                print(f"Gemini API response status for structuring CV: {response.status_code}")

                try:
                    response.raise_for_status()
                    data = response.json()

                    result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    finish_reason = data["candidates"][0].get("finishReason", "UNKNOWN")

                    if finish_reason == "MAX_TOKENS":
                        print("Warning: Gemini response for structuring CV was truncated due to MAX_TOKENS limit")

                    return self._extract_json(result_text)  # Reuse existing JSON extraction

                except Exception as e:
                    print(f"Error processing Gemini response for structuring CV: {str(e)}")
                    print(f"Response content: {response.text if response.text else 'No response content'}")
                    raise ValueError(f"Failed to process Gemini API response for structuring CV: {str(e)}")

        except Exception as e:
            print(f"Exception in Gemini API call for structuring CV: {str(e)}")
            raise ValueError(f"Gemini API error while structuring CV: {str(e)}")

    def _create_structure_cv_prompt(self, cv_text: str) -> str:
        """
        Creates a prompt for Gemini to structure raw CV text into JSON.
        """
        return f"""
    You are an expert CV parser and data extractor. Your task is to analyze the following raw CV text and structure it into a precise JSON format.

    RAW CV TEXT:
    ---
    {cv_text}
    ---

    Based on the text above, populate the following JSON structure. Ensure all fields are accurately extracted or inferred if not explicitly stated but strongly implied.
    If a field cannot be found or reasonably inferred, use an empty string "" for string fields, empty array [] for array fields, or a sensible default (e.g., 0 for relevanceScore if not applicable).

    JSON STRUCTURE TO POPULATE:
    ```json
    {{
    "fullName": "Full name of the candidate",
    "jobTitle": "Current or most recent job title, or a general professional title",
    "summary": "A concise professional summary. If not present, try to create a brief one (2-3 lines) based on the overall experience and skills.",
    "email": "Candidate's email address",
    "linkedin": "Candidate's LinkedIn profile URL (if present)",
    "phone": "Candidate's phone number",
    "location": "Candidate's general location (e.g., City, Country)",
    "experience": [
        {{
        "jobTitle": "Position title",
        "company": "Company name",
        "dates": "Employment dates (e.g., MM/YYYY - MM/YYYY or MM/YYYY - Present)",
        "description": "Key responsibilities and a brief overview of the role. Concisely summarize using bullet points or a short paragraph.",
        "achievements": [
            "Quantifiable achievement 1 (if listed)",
            "Quantifiable achievement 2 (if listed)"
        ],
        "relevanceScore": 0 
        }}
    ],
    "education": [
        {{
        "degree": "Degree name (e.g., Bachelor of Science in Computer Science)",
        "institution": "Name of the educational institution",
        "dates": "Graduation year or period of study (e.g., YYYY or MM/YYYY - MM/YYYY)",
        "relevanceScore": 0
        }}
    ],
    "skills": [
        "Categorized skill (e.g., Technical: Python, JavaScript, SQL)",
        "Categorized skill (e.g., Soft Skills: Communication, Teamwork)"
    ],
    "certifications": [
        "Certification name (if any)"
    ],
    "skillGapAnalysis": {{
        "matchingSkills": [],
        "missingSkills": [],
        "overallMatch": 0
    }}
    }}
    GUIDELINES FOR EXTRACTION:

    fullName: Extract the full name.
    jobTitle: Extract the most prominent or recent job title. If multiple, choose the most senior or relevant.
    summary: Extract if explicitly provided. If not, create a very brief (1-2 sentence) objective summary based on the content.
    contact details (email, linkedin, phone, location): Extract as found.
    experience:
    For each role, extract jobTitle, company, and dates.
    description: Summarize key responsibilities.
    achievements: List 2-3 key achievements, preferably quantifiable. If achievements are embedded in descriptions, extract them.
    relevanceScore: Leave as 0 for now, this field is not for you to calculate in this step.
    education:
    For each entry, extract degree, institution, and dates.
    relevanceScore: Leave as 0.
    skills: Attempt to categorize skills if possible (e.g., "Technical Skills", "Languages", "Tools"). If categories are not clear, list them as general skills. Combine related skills.
    certifications: List any certifications mentioned.
    skillGapAnalysis: Leave all fields (matchingSkills, missingSkills, overallMatch) as empty arrays or 0. This section is not for this parsing step.
    Return ONLY the valid JSON object. Do not include any explanatory text before or after the JSON.
    The entire output must be a single, valid JSON object.
    """
    
    async def generate_professional_profile(self, cv_text: str, non_professional_experience: str, profiling_questions: Dict[str, str]) -> Dict[str, Any]:
        """
        Generate a comprehensive professional profile using Gemini AI based on CV, 
        non-professional experience, and profiling questions.
        """
        prompt = self._create_profiling_prompt(cv_text, non_professional_experience, profiling_questions)
        
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
                            "temperature": 0.3,  # Slightly higher for personality analysis
                            "topP": 0.9,
                            "topK": 40,
                            "maxOutputTokens": 8192,  # Large response needed for comprehensive profile
                        }
                    },
                    timeout=180.0,  # Extended timeout for complex analysis
                )
                
                print(f"Gemini API response status for profiling: {response.status_code}")
                
                try:
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract the response text from Gemini
                    result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    finish_reason = data["candidates"][0].get("finishReason", "UNKNOWN")
                    
                    if finish_reason == "MAX_TOKENS":
                        print("Warning: Gemini profiling response was truncated due to MAX_TOKENS limit")
                    
                    # Process the response to extract the JSON data
                    return self._extract_json(result_text)
                except Exception as e:
                    print(f"Error processing Gemini profiling response: {str(e)}")
                    print(f"Response content: {response.text if response.text else 'No response content'}")
                    raise ValueError(f"Failed to process Gemini API profiling response: {str(e)}")
        except Exception as e:
            print(f"Exception in Gemini API call for profiling: {str(e)}")
            raise ValueError(f"Gemini API profiling error: {str(e)}")

    def _create_profiling_prompt(self, cv_text: str, non_professional_experience: str, profiling_questions: Dict[str, str]) -> str:
        """
        Create a comprehensive prompt for professional profiling using Gemini AI.
        This prompt combines CV analysis, personality assessment, and career guidance.
        """
        return f"""
    You are an expert career counselor, psychologist, and professional profiling specialist with deep expertise in:
    - Big Five personality assessment
    - Career development and role matching
    - Skills analysis and competency mapping
    - Professional behavioral analysis

    Your task is to create a comprehensive professional profile based on the provided information.
    You MUST return ONLY a valid JSON object following the exact structure specified below.

    PROFESSIONAL CV/RESUME:
    ---
    {cv_text}
    ---

    NON-PROFESSIONAL EXPERIENCES:
    ---
    {non_professional_experience}
    ---

    PROFILING QUESTIONS RESPONSES:
    Work Approach: {profiling_questions.get('work_approach', 'Not provided')}
    Problem Solving Example: {profiling_questions.get('problem_solving', 'Not provided')}
    Work Values: {profiling_questions.get('work_values', 'Not provided')}

    ANALYSIS INSTRUCTIONS:

    1. **Personality Profile Analysis:**
    - Assess Big Five traits (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
    - Rate each trait on a scale of 1-10 with explanations
    - Determine work style preferences (independent vs collaborative, detail-oriented vs big-picture, etc.)
    - Assess leadership potential and style
    - Analyze team dynamics and collaboration style

    2. **Skills Assessment:**
    - Extract technical skills from CV and rate proficiency (1-10)
    - Identify soft skills from all experiences and rate them (1-10)
    - Map transferable skills from non-professional experiences
    - Identify skill gaps for career advancement

    3. **Role Fit Analysis:**
    - Suggest 5-8 specific job roles they would excel in
    - Provide match scores (0-1) for different role categories
    - Assess current career level and readiness for advancement

    4. **Career Development Path:**
    - Recommend specific next steps for career growth
    - Prioritize skill development areas
    - Suggest 2-3 career progression paths with timelines
    - Provide actionable recommendations

    5. **Behavioral Insights:**
    - Analyze decision-making style from problem-solving example
    - Determine communication preferences
    - Identify key motivation drivers
    - Predict potential workplace challenges
    - Define ideal work environment characteristics

    CRITICAL JSON OUTPUT REQUIREMENTS:
    - Return ONLY valid JSON, no explanatory text
    - Follow the exact structure below
    - Use specific, actionable language
    - Base all assessments on provided information
    - Assign realistic confidence scores

    REQUIRED JSON STRUCTURE:
    ```json
    {{
    "personality_profile": {{
        "traits": {{
        "openness": {{"score": 7, "description": "Shows curiosity and willingness to try new approaches"}},
        "conscientiousness": {{"score": 8, "description": "Demonstrates strong attention to detail and reliability"}},
        "extraversion": {{"score": 6, "description": "Comfortable in both social and independent work settings"}},
        "agreeableness": {{"score": 7, "description": "Collaborative and considerate of others' perspectives"}},
        "neuroticism": {{"score": 3, "description": "Maintains composure under pressure and stress"}}
        }},
        "work_style": "Balanced approach combining independent analysis with collaborative execution",
        "leadership_potential": "Strong potential for technical leadership roles with natural mentoring abilities",
        "team_dynamics": "Effective team player who can bridge technical and non-technical stakeholders"
    }},
    "skills_assessment": {{
        "technical_skills": [
        {{"skill": "Python", "proficiency": 8, "source": "professional"}},
        {{"skill": "Project Management", "proficiency": 7, "source": "professional"}}
        ],
        "soft_skills": [
        {{"skill": "Communication", "proficiency": 8, "source": "both"}},
        {{"skill": "Problem Solving", "proficiency": 9, "source": "both"}}
        ],
        "transferable_skills": [
        {{"skill": "Event Organization", "proficiency": 7, "source": "non_professional"}},
        {{"skill": "Community Leadership", "proficiency": 8, "source": "non_professional"}}
        ],
        "skill_gaps": ["Advanced Data Analysis", "Strategic Planning", "Public Speaking"]
    }},
    "role_fit_analysis": {{
        "suitable_roles": [
        {{"title": "Senior Software Engineer", "match_score": 0.85, "reasoning": "Strong technical skills with leadership potential"}},
        {{"title": "Technical Project Manager", "match_score": 0.82, "reasoning": "Combines technical expertise with organizational abilities"}}
        ],
        "role_match_scores": {{
        "technical_individual_contributor": 0.88,
        "technical_leadership": 0.78,
        "project_management": 0.82,
        "consulting": 0.75
        }},
        "career_level_assessment": "Mid-level professional ready for senior roles with additional leadership development"
    }},
    "career_development": {{
        "recommended_next_steps": [
        "Seek technical leadership opportunities in current role",
        "Develop public speaking skills through professional presentations",
        "Pursue advanced certification in core technical area"
        ],
        "skill_development_priorities": [
        "Strategic thinking and planning",
        "Advanced technical expertise in specialization area",
        "Team leadership and mentoring"
        ],
        "career_progression_paths": [
        {{"path": "Technical Leadership Track", "timeline": "2-3 years", "next_role": "Technical Lead"}},
        {{"path": "Management Track", "timeline": "3-4 years", "next_role": "Engineering Manager"}}
        ],
        "timeline_recommendations": {{
        "short_term_6_months": "Focus on leadership skills and advanced technical training",
        "medium_term_2_years": "Target senior technical role with team responsibilities",
        "long_term_5_years": "Establish expertise in specialized area with industry recognition"
        }}
    }},
    "behavioral_insights": {{
        "decision_making_style": "Analytical approach with consideration of multiple perspectives before deciding",
        "communication_style": "Clear, direct communication with ability to adapt to technical and non-technical audiences",
        "motivation_drivers": ["Professional growth", "Technical challenges", "Positive team impact"],
        "potential_challenges": ["May need to develop comfort with ambiguous situations", "Could benefit from more assertiveness in leadership situations"],
        "work_environment_preferences": ["Collaborative but focused environment", "Access to learning opportunities", "Clear goal setting with autonomy in execution"]
    }},
    "confidence_score": 0.85,
    "generated_at": "{datetime.now().isoformat()}"
    }}
    ```

    Analyze all provided information thoroughly and generate a comprehensive, accurate professional profile in the exact JSON format specified above.
    """