from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.schemas.teacher_academic import (
    TeacherAcademicCreate, 
    TeacherAcademicResponse, 
    TeacherAcademicListResponse
)
from app.services.teacher_academic_service import (
    create_teacher_academic_assignment,
    get_teacher_academic_assignments as get_teacher_academic_assignments_service
)

router = APIRouter()


@router.post(
    "/v1/users/{user_uuid}/teacher/acad",
    response_model=TeacherAcademicResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Teacher Academic Management"]
)
async def create_teacher_academic(
    user_uuid: str,
    assignment_data: TeacherAcademicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new academic assignment for a teacher.

    ### Path Parameters:
    - **user_uuid** (str, required): UUID of the teacher

    ### Request Body:
    - **academic_year** (str, required): Academic year (e.g., "2025")
    - **standard** (str, required): Standard/class (e.g., "10")
    - **division** (str, required): Division (e.g., "A", "B", "C")
    - **medium_code** (str, required): Medium code from medium_master_table
    - **subject_codes** (list[str], required): List of subject codes from subject_master_table

    ### Response:
    - **201 Created**: Academic assignment created successfully
    - **400 Bad Request**: Invalid data or duplicate assignment
    - **403 Forbidden**: Insufficient permissions
    - **404 Not Found**: Teacher not found

    ### Example Request:
    ```json
    {
        "academic_year": "2025",
        "standard": "10",
        "division": "A",
        "medium_code": "2000",
        "subject_codes": ["3000", "3001"]
    }
    ```

    ### Example Response:
    ```json
    {
        "id": 1,
        "academic_year": "2025",
        "standard": "10",
        "division": "A",
        "medium_id": 3,
        "medium_name": "English",
        "subjects": [
            {"id": 1, "name": "Math", "code": "3000"},
            {"id": 2, "name": "Science", "code": "3001"}
        ],
        "created_at": "2025-09-25T17:30:00Z",
        "updated_at": "2025-09-25T17:30:00Z"
    }
    ```
    """
    return await create_teacher_academic_assignment(
        db=db,
        user_uuid=user_uuid,
        assignment_data=assignment_data,
        current_user=current_user
    )


@router.get(
    "/v1/users/{user_uuid}/teacher/acad/",
    response_model=TeacherAcademicListResponse,
    tags=["Teacher Academic Management"]
)
async def get_teacher_academic_assignments(
    user_uuid: str,
    academic_year: Optional[str] = Query(None, description="Filter by academic year"),
    standard: Optional[str] = Query(None, description="Filter by standard/class"),
    division: Optional[str] = Query(None, description="Filter by division"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all academic assignments for a teacher.

    ### Path Parameters:
    - **user_uuid** (str, required): UUID of the teacher

    ### Query Parameters:
    - **academic_year** (str, optional): Filter by academic year
    - **standard** (str, optional): Filter by standard/class
    - **division** (str, optional): Filter by division

    ### Response:
    - **200 OK**: List of academic assignments
    - **403 Forbidden**: Insufficient permissions
    - **404 Not Found**: Teacher not found

    ### Example Response:
    ```json
    {
        "teacher_uuid": "123e4567-e89b-12d3-a456-426614174000",
        "teacher_name": "John Doe",
        "staff_id": "T001",
        "academic_assignments": [
            {
                "id": 1,
                "academic_year": "2025",
                "standard": "10",
                "division": "A",
                "medium_id": 3,
                "medium_name": "English",
                "subjects": [
                    {"id": 1, "name": "Math", "code": "3000"},
                    {"id": 2, "name": "Science", "code": "3001"}
                ],
                "created_at": "2025-09-25T17:30:00Z",
                "updated_at": "2025-09-25T17:30:00Z"
            }
        ]
    }
    ```
    """
    return await get_teacher_academic_assignments_service(
        db=db,
        user_uuid=user_uuid,
        current_user=current_user,
        academic_year=academic_year,
        standard=standard,
        division=division
    )
