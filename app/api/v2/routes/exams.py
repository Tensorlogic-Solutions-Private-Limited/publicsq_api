"""
V2 Exam Routes - Hierarchical exam container management.

This module provides endpoints for managing exam containers that can hold
multiple subject designs, implementing the exam hierarchy structure.
"""
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.decorators.permissions import require_permission
from app.services import exam_service
from app.schemas.exams import ExamCreate, ExamResponse, DesignBase, ExamListResponse, ExamUpdate
from app.services.state_resolution_service import StateResolutionService

router = APIRouter(tags=["Exams (Revised)"])


@router.post("/v2/exams", response_model=ExamResponse, status_code=status.HTTP_201_CREATED)
@require_permission("quiz.create")
async def create_exam(
    exam_data: ExamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new exam container.
    
    This endpoint creates an empty exam container that can hold multiple subject designs.
    The exam is initialized with status "draft".
    
    **Organizational Hierarchy:**
    - If organization_id, block_id, or school_id are not provided, they will be automatically
      populated from the current user's profile.
    - Role-based permissions apply when explicitly providing these values.

    """
    result = await exam_service.create_exam(
        db=db,
        exam_name=exam_data.exam_name,
        current_user=current_user,
        total_time=exam_data.total_time,
        exam_mode=exam_data.exam_mode,
        organization_id=exam_data.organization_id,
        block_id=exam_data.block_id,
        school_id=exam_data.school_id
    )
    
    return result


@router.post("/v2/exams/{exam_code}/designs", status_code=status.HTTP_201_CREATED)
@require_permission("quiz.create")
async def create_design_within_exam(
    exam_code: str,
    payload: DesignBase,
    state_id: Optional[int] = Query(None, description="State ID for question filtering (required for admin roles)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a design within an exam container.
    
    This endpoint creates a subject design and associates it with the specified exam container.
    The design creation uses the same logic as v1/exams but links the design to the parent exam.
    
    **Design Status:**
    - Design status is ALWAYS set to 1 (draft) when created within an exam
    - The status field in the request body is IGNORED
    - Design status is controlled by the parent exam's status:
      - When exam is "draft" or "saved": design status = 1 (draft)
      - When exam is "started": design status = 2 (closed)
      - Design status cannot be changed directly, only through exam status changes
    
    **State Resolution:**
    - For super_admin, admin, and admin_user roles: state_id can be explicitly provided
    - For other roles (block_admin, teacher): state_id is validated against user's scope
    
    **Request Body:** Same as POST /v1/exams (DesignBase schema), but status field is ignored
    
    **Response:** Same response structure as v1/exams design creation
    """
    try:
        # Resolve state_id based on user role
        user_role = current_user.role.role_code if current_user.role else None
        
        # Use state_id from query parameter, or fall back to state_id from payload
        effective_state_id = state_id if state_id is not None else payload.state_id
        
        if user_role in ["super_admin", "admin", "admin_user"]:
            # Admin roles can use any state_id they provide, no validation needed
            resolved_state_id = effective_state_id
        else:
            # For other roles (block_admin, teacher), use StateResolutionService for validation
            resolved_state_id = await StateResolutionService.resolve_state_for_user(
                db=db, 
                user=current_user, 
                explicit_state_id=effective_state_id
            )
        
        # Call exam_service.create_design_within_exam()
        result = await exam_service.create_design_within_exam(
            db=db,
            exam_code=exam_code,
            payload=payload,
            current_user=current_user,
            state_id=resolved_state_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create design within exam: {str(e)}"
        )


@router.get("/v2/exams", response_model=ExamListResponse)
@require_permission("quiz.view")
async def list_exams(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    status: Optional[str] = Query(None, description="Filter by exam status (draft, saved, started, completed)"),
    standard: Optional[str] = Query(None, description="Filter by standard (from designs)"),
    subject_code: Optional[str] = Query(None, description="Filter by subject code (from designs)"),
    exam_name: Optional[str] = Query(None, description="Search by exam name (partial match)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List exam containers with pagination and filters.
    
    This endpoint returns a paginated list of exam containers with design counts.
    Results are filtered based on user's role and organizational hierarchy.
    
    **Query Parameters:**
    - page: Page number (default: 1)
    - page_size: Number of items per page (default: 10, max: 100)
    - status: Filter by exam status (draft, saved, started, completed)
    - standard: Filter by standard (from associated designs)
    - subject_code: Filter by subject code (from associated designs)
    - exam_name: Search by exam name (partial match, case-insensitive)
    """
    result = await exam_service.list_exams(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status_filter=status,
        standard=standard,
        subject_code=subject_code,
        exam_name=exam_name
    )
    
    return result


@router.get("/v2/exams/{exam_code}", response_model=ExamResponse)
@require_permission("quiz.view")
async def get_exam_by_code(
    exam_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get exam container with all its designs.
    
    This endpoint retrieves a specific exam container by its exam code and includes
    all associated designs in the response. Access is controlled based on user's
    role and organizational hierarchy.
    
    **Response:**
    - Returns exam details with designs array
    - Each design includes full details (same structure as v1/designs response)
    - Designs array contains design objects without wrapper keys
    """
    result = await exam_service.get_exam_by_code(
        db=db,
        exam_code=exam_code,
        current_user=current_user
    )
    
    return result


@router.put("/v2/exams/{exam_code}", response_model=ExamResponse)
@require_permission("quiz.edit_properties")
async def update_exam(
    exam_code: str,
    exam_data: ExamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update exam container details.
    
    This endpoint allows updating exam container fields. All fields are optional
    for partial updates. Role-based permissions apply for organizational field updates.
    
    **Immutability:**
    - Exams with status 'started' or 'completed' cannot be updated
    - Only 'draft' or 'saved' exams can be modified
    
    **Status Synchronization:**
    - When status changes to 'started', all associated designs are automatically
      updated to status 2 (closed)
    
    **Role-Based Permissions:**
    - super_admin: Can update organization_id, block_id, school_id
    - admin/admin_user: Can update block_id, school_id
    - block_admin: Can update school_id
    - teacher: Cannot update organizational fields
    """
    result = await exam_service.update_exam(
        db=db,
        exam_code=exam_code,
        current_user=current_user,
        exam_name=exam_data.exam_name,
        total_time=exam_data.total_time,
        exam_mode=exam_data.exam_mode,
        status_update=exam_data.status,
        organization_id=exam_data.organization_id,
        block_id=exam_data.block_id,
        school_id=exam_data.school_id
    )
    
    return result


@router.delete("/v2/exams/{exam_code}", status_code=status.HTTP_204_NO_CONTENT)
@require_permission("quiz.edit_properties")
async def delete_exam(
    exam_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete exam container.
    
    This endpoint deletes an exam container. All associated designs are automatically
    deleted via database cascade (foreign key constraint).
    
    **Cascade Deletion:**
    - Deleting an exam automatically deletes all associated designs
    - Designs cascade delete their question papers
    - Database foreign key constraints enforce cascade deletion
    
    **Permissions:**
    - Access is controlled based on user's role and organizational hierarchy
    - Teachers can only delete their own exams within their school
    - Block admins can delete exams within their block
    - Admins can delete exams within their organization
    - Super admins can delete all exams
    """
    await exam_service.delete_exam(
        db=db,
        exam_code=exam_code,
        current_user=current_user
    )
    
    return None
