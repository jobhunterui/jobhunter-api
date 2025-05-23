from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager # Import this

from app.api.routes import api_router
from app.core.config import settings
from app.core.firebase_admin_setup import initialize_firebase_admin # Ensure this path is correct

# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Code to run on startup
    print("INFO: Application lifespan startup: Initializing Firebase Admin SDK...")
    initialize_firebase_admin() # Call your initialization function
    print("INFO: Application lifespan startup: Firebase Admin SDK initialization attempt complete.")
    yield
    # Code to run on shutdown (if any)
    print("INFO: Application lifespan shutdown.")

def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        debug=settings.DEBUG_MODE,
        lifespan=lifespan  # Add the lifespan manager here
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