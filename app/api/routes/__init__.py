from fastapi import APIRouter

from app.api.routes.cv_generator import router as cv_router

api_router = APIRouter()

api_router.include_router(cv_router, prefix="/cv", tags=["CV Generator"])