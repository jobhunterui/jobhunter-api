from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings


def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        debug=settings.DEBUG_MODE,
    )

    # Set up CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    application.include_router(api_router, prefix=settings.API_V1_STR)

    return application


app = get_application()


@app.get("/")
async def root():
    return {
        "message": "Welcome to the JobHunter CV Generator API",
        "version": settings.VERSION,
        "docs_url": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}