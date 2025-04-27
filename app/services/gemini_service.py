import json
from typing import Dict, Any

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
      Create a streamlined prompt for the Gemini API to reduce token usage.
      """
      return f"""
  You are an expert CV tailor. Create a focused, professional CV for this specific job.

  JOB DESCRIPTION:
  {job_description}

  RESUME:
  {resume}

  Create a CV in JSON format with these fields:
  - fullName: From resume
  - jobTitle: Tailored professional title matching the job
  - summary: Compelling summary highlighting qualifications (4-5 lines)
  - email, linkedin, phone, location: From resume
  - experience: Array of relevant jobs with:
    * jobTitle, company, dates
    * description: Focused on MOST relevant responsibilities 
    * achievements: Array of 3 measurable achievements with numbers
    * relevanceScore: 0-100 indicating relevance to the job
  - education: Array with degree, institution, dates, relevanceScore
  - skills: Array of categorized skills (e.g., "Technical: skill1, skill2")
  - certifications: Any relevant certifications
  - skillGapAnalysis: matchingSkills, missingSkills, overallMatch

  GUIDELINES:
  - Focus on RELEVANCE to this specific job
  - Include measurable achievements with numbers
  - Use strong action verbs and job-specific terminology

  Return ONLY valid JSON - No explanation text:
  ```json
  {{
    "fullName": "",
    "jobTitle": "",
    "summary": "",
    "email": "",
    "linkedin": "",
    "phone": "",
    "location": "",
    "experience": [
      {{
        "jobTitle": "",
        "company": "",
        "dates": "",
        "description": "",
        "achievements": ["", "", ""],
        "relevanceScore": 95
      }}
    ],
    "education": [
      {{
        "degree": "",
        "institution": "",
        "dates": "",
        "relevanceScore": 80
      }}
    ],
    "skills": ["", ""],
    "certifications": ["", ""],
    "skillGapAnalysis": {{
      "matchingSkills": [""],
      "missingSkills": [""],
      "overallMatch": 85
    }}
  }}
  ```
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