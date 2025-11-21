from fastapi import APIRouter

from .metadata import router as dropdowns_router
from .questions import router as questions_router
from .exams import router as exams_router
from .design import router as design_router
from .qn_papers import router as papers_router
from .qn_paper_views import router as papers_view_router
from .file_upload import router as file_upload_router
from .organizations import router as organizations_router
from .users import router as users_router
from .teacher_academic import router as teacher_academic_router
from .school_images import router as school_images_router
from .taxonomy import router as taxonomy_router



api_router = APIRouter()

api_router.include_router(dropdowns_router)
api_router.include_router(questions_router)
api_router.include_router(exams_router)
api_router.include_router(design_router)
api_router.include_router(papers_router)
api_router.include_router(papers_view_router)
api_router.include_router(file_upload_router)
api_router.include_router(organizations_router)
api_router.include_router(users_router)
api_router.include_router(teacher_academic_router)
api_router.include_router(school_images_router)
api_router.include_router(taxonomy_router)
