# JobHunter CV Generator API

A FastAPI service that generates tailored CVs using Google's Gemini 2.0 Flash API.

## Features

- Generate tailored CVs based on job descriptions and resumes
- Rate limiting with daily quotas
- CORS support for web app and Firefox extension
- Designed for Render deployment

## Setup

### Prerequisites

- Python 3.9+
- [Optional] Redis for production rate limiting

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/jobhunterui/jobhunter-api.git
   cd jobhunter-api
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   .\venv\Scripts\Activate  # Windows
   source venv/bin/activate  # Linux/Mac
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your settings:
   ```
   GEMINI_API_KEY=your_api_key
   ALLOWED_ORIGINS=https://jobhunterui.github.io,moz-extension://
   DAILY_QUOTA=100
   ```

### Running Locally

```
uvicorn app.api.server:app --reload
```

The API will be available at http://localhost:8000 with interactive docs at http://localhost:8000/docs

## API Endpoints

### Generate CV

`POST /api/v1/cv/generate`

Generate a tailored CV based on a job description and resume.

**Request Body:**

```json
{
  "job_description": "Full job description text",
  "resume": "Candidate's resume/CV text"
}
```

**Response:**

```json
{
  "cv_data": {
    "fullName": "John Smith",
    "jobTitle": "Senior Python Developer",
    "summary": "Experienced Python developer with 5+ years...",
    ...
  },
  "quota": {
    "remaining": 99,
    "total": 100
  }
}
```

## Deployment

This API is designed to be deployed on Render.com.

## License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.