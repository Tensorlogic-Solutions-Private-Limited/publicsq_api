from fastapi import APIRouter
from .auth import router as auth_router

api_auth_router = APIRouter()

api_auth_router.include_router(auth_router)
