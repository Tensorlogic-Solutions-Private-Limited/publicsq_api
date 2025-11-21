from fastapi import APIRouter

from .exams import router as exams_router

api_router_v2 = APIRouter()

api_router_v2.include_router(exams_router)
