import asyncio
import json
import httpx


async def test_basic_endpoints():
    """Test the basic API endpoints to verify the server is running correctly."""
    # Basic API test
    url = "http://127.0.0.1:8000"
    
    print("\n== Testing Basic Endpoints ==")
    
    async with httpx.AsyncClient() as client:
        # Test root endpoint
        try:
            response = await client.get(f"{url}/")
            print(f"Root endpoint: Status {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error testing root endpoint: {str(e)}")
        
        # Test health endpoint
        try:
            response = await client.get(f"{url}/health")
            print(f"Health endpoint: Status {response.status_code}")
            print(f"Response: {response.json()}")
        except Exception as e:
            print(f"Error testing health endpoint: {str(e)}")


async def test_generate_cv(max_retries=3):
    """Test the CV generation functionality with a sample job description and resume."""
    print("\n== Testing CV Generation ==")
    
    # Sample job description and resume
    job_description = """
    Senior Python Developer
    
    We're looking for an experienced Python developer with strong FastAPI knowledge
    and experience with cloud deployments. The ideal candidate has 3+ years of
    experience building RESTful APIs and working with database systems.
    
    Requirements:
    - 3+ years of Python development
    - Experience with FastAPI or Django
    - Familiarity with database design
    - Experience with cloud services (AWS, Azure, or GCP)
    """
    
    resume = """
    John Smith
    Email: john.smith@example.com
    Phone: +44 7123 456789
    London, UK
    LinkedIn: linkedin.com/in/johnsmith
    
    EXPERIENCE
    
    Senior Software Engineer
    ABC Tech, London
    2019 - Present
    - Developed and maintained Python-based microservices using FastAPI
    - Led a team of 3 developers for a major client project
    - Reduced API response times by 40% through optimization
    
    Backend Developer
    XYZ Solutions
    2017 - 2019
    - Built RESTful APIs using Django
    - Implemented database migrations and optimization
    
    EDUCATION
    
    BSc Computer Science
    University of London
    2013 - 2017
    
    SKILLS
    
    Python, FastAPI, Django, PostgreSQL, MongoDB, AWS, Docker, Git
    """
    
    # API request
    url = "http://localhost:8000/api/v1/cv/generate"
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Attempt {attempt} of {max_retries}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={
                        "job_description": job_description,
                        "resume": resume
                    },
                    timeout=120.0  # Increased timeout for AI processing
                )
                
                # Print status code
                print(f"Status Code: {response.status_code}")
                
                # Print response
                data = response.json()
                print(json.dumps(data, indent=2))
                
                # If successful, print some fields to verify the content
                if response.status_code == 200 and "cv_data" in data:
                    print("\nCV Generation Successful!")
                    print(f"Name: {data['cv_data'].get('fullName', 'N/A')}")
                    print(f"Job Title: {data['cv_data'].get('jobTitle', 'N/A')}")
                    print(f"Skills: {', '.join(data['cv_data'].get('skills', ['N/A']))}")
                    print(f"Overall Match: {data['cv_data'].get('skillGapAnalysis', {}).get('overallMatch', 'N/A')}%")
                    print(f"Remaining Quota: {data['quota']['remaining']} of {data['quota']['total']}")
                    return True  # Success
                else:
                    print(f"Request failed with status code {response.status_code}")
                    if attempt < max_retries:
                        print(f"Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        print("Maximum retries reached. Test failed.")
                        return False
        except Exception as e:
            print(f"Error during attempt {attempt}: {str(e)}")
            if attempt < max_retries:
                print(f"Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                print("Maximum retries reached. Test failed.")
                return False


async def run_all_tests():
    """Run all API tests in sequence."""
    await test_basic_endpoints()
    await test_generate_cv()


if __name__ == "__main__":
    asyncio.run(run_all_tests())