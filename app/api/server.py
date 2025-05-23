# app/api/server.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api.routes import api_router # This should be the main router aggregating others
from app.api.routes import users as users_router # Import the new users router
from app.core.config import settings
from app.core.firebase_admin_setup import initialize_firebase_admin

# Lifespan event to initialize Firebase Admin SDK
# This is a context manager that runs on application startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO: Application lifespan startup: Initializing Firebase Admin SDK...")
    initialize_firebase_admin() #
    print("INFO: Application lifespan startup: Firebase Admin SDK initialization attempt complete.")
    yield
    print("INFO: Application lifespan shutdown.")

# This function creates and configures the FastAPI application instance
# It includes middleware, routers, and other configurations.
def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
        debug=settings.DEBUG_MODE,
        lifespan=lifespan
    )

    # Middleware for CORS
    # This allows cross-origin requests from specified origins
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS, #
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include the main API router (which might include cv_generator, etc.)
    application.include_router(api_router, prefix=settings.API_V1_STR) #

    # Include the new users router
    application.include_router(
        users_router.router, # Make sure to use users_router.router
        prefix=f"{settings.API_V1_STR}/users", #
        tags=["Users"] # Add a tag for API docs
    )


    return application

# Create the FastAPI application instance
# This is the main entry point for the application
app = get_application()

# Define a root endpoint for the API
# This is a simple health check or welcome message
@app.get("/")
async def root():
    return {
        "message": "Welcome to the JobHunter CV Generator API",
        "version": settings.VERSION, #
        "docs_url": "/docs",
    }

# Define a health check endpoint
# This is useful for monitoring and ensuring the service is running
@app.get("/health")
async def health_check():
    return {"status": "healthy"}