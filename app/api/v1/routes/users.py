"""
User management API routes with RBAC and hierarchical scoping.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.schemas.auth import (
    UserCreate, UserUpdate, UserResponse, UserListResponse, 
    PasswordUpdateRequest
)
from app.services.user_management_services import (
    create_user_service,
    list_users_service,
    get_user_by_id_service,
    get_user_by_uuid_service,
    update_user_info_service,
    update_user_info_by_uuid_service,
    delete_user_service,
    delete_user_by_uuid_service,
    update_user_service,
    update_user_password_by_uuid_service,
    count_active_users
)
from app.decorators.permissions import require_permission, scope_filter, validate_scope
from app.middleware.rbac import PermissionDeniedError, ScopeViolationError

router = APIRouter(prefix="/v1/users", tags=["User Management"])


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@require_permission("user.create")
@validate_scope(
    organization_param="organization_uuid",
    block_param="block_uuid", 
    school_param="school_uuid"
)
async def create_user(
    user_data: UserCreate,
    organization_id: Optional[int] = None,
    block_id: Optional[int] = None,
    school_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new user with hierarchical scope validation.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - None
    
    ### Query Parameters:
    - **organization_id** (int, optional): Override organization ID from request body
    - **block_id** (int, optional): Override block ID from request body  
    - **school_id** (int, optional): Override school ID from request body
    
    ### Request Body (application/json):
    - **username** (str): Unique username (3-50 characters)
    - **password** (str): Password (minimum 8 characters, must contain 1 lowercase, 1 uppercase, 1 special character)
    - **role_code** (str): Role code for the user
    - **full_name** (str, optional): Full name of the user
    - **email** (str, optional): Email address (must be unique)
    - **phone** (str, optional): Phone number
    - **organization_id** (int, optional): Organization ID
    - **block_id** (int, optional): Block ID
    - **school_id** (int, optional): School ID
    
    ### Response (application/json):
    - **201 Created**: Returns the created user with organizational context
    
    ### Error Responses:
    - **400 Bad Request**: Invalid data or constraints violation
    - **403 Forbidden**: Insufficient permissions or scope violation
    - **404 Not Found**: Referenced organizational entity not found
    
    ### Notes:
    The organizational hierarchy will be automatically validated and completed:
    - If school_id is provided, block_id and organization_id will be auto-assigned
    - If block_id is provided, organization_id will be auto-assigned
    - User can only create users within their own organizational scope
    - Query parameters override request body values if provided
    """
    try:
        # Override user_data with URL parameters if provided
        if organization_id is not None:
            user_data.organization_id = organization_id
        if block_id is not None:
            user_data.block_id = block_id
        if school_id is not None:
            user_data.school_id = school_id
            
        new_user = await create_user_service(db, user_data, current_user)
        return new_user
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/", response_model=UserListResponse)
@require_permission("user.list")
@scope_filter("hierarchical")
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by username, full name, or email"),
    role_code: Optional[str] = Query(None, description="Filter by role code"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: dict = None,  # Injected by scope_filter decorator
    school_udise: Optional[str] = Query(None, description="Filter users by school's UDISE+ code"),
):

    """
    List users with pagination and filtering.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - None
    
    ### Query Parameters:
    - **page** (int, optional): Page number (default: 1, minimum: 1)
    - **per_page** (int, optional): Items per page (default: 10, minimum: 1, maximum: 100)
    - **search** (str, optional): Search by username, full name, or email
    - **role_code** (str, optional): Filter by specific role code
    - **is_active** (bool, optional): Filter by active status (true/false)
    - **school_udise** (str, optional): Filter users by school's UDISE+ code
    
    ### Response (application/json):
    - **200 OK**: Returns paginated list of users within organizational scope
    
    ### Error Responses:
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    Results are automatically filtered based on the current user's organizational scope:
    - Super Admin: Can see all users (except themselves)
    - VidyaShakthi Admin: Can see users in their organization (except themselves)
    - Block Admin: Can see users in their block (except themselves)
    - School Admin/Teacher: Can see users in their school (except themselves)
    - The current user's own details are excluded from the results
    """
    try:
        result = await list_users_service(
            db=db,
            current_user=current_user,
            page=page,
            per_page=per_page,
            search=search,
            role_code=role_code,
            is_active=is_active,
            school_udise=school_udise
        )
        return result
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/{user_uuid}", response_model=UserResponse)
@require_permission("user.view")
async def get_user(
    user_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user details by UUID.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **user_uuid** (UUID): UUID of the user to retrieve
    
    ### Query Parameters:
    - None
    
    ### Response (application/json):
    - **200 OK**: Returns user details with organizational context
    
    ### Error Responses:
    - **403 Forbidden**: Insufficient permissions or scope violation
    - **404 Not Found**: User not found or outside current user's scope
    
    ### Notes:
    The user must be within the current user's organizational scope.
    """
    try:
        user = await get_user_by_uuid_service(str(user_uuid), db, current_user)
        return user
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.put("/{user_uuid}", response_model=UserResponse)
@require_permission("user.edit")
async def update_user(
    user_uuid: uuid.UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user information.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **user_uuid** (UUID): UUID of the user to update
    
    ### Query Parameters:
    - None
    
    ### Request Body (application/json):
    - **username** (str, optional): New username
    - **role_code** (str, optional): New role code
    - **full_name** (str, optional): New full name
    - **email** (str, optional): New email address
    - **phone** (str, optional): New phone number
    - **is_active** (bool, optional): Active status
    - **organization_uuid** (UUID, optional): New organization UUID
    - **block_uuid** (UUID, optional): New block UUID
    - **school_uuid** (UUID, optional): New school UUID
    
    ### Response (application/json):
    - **200 OK**: Returns updated user with organizational context
    
    ### Error Responses:
    - **400 Bad Request**: Invalid data or constraints violation
    - **403 Forbidden**: Insufficient permissions or scope violation
    - **404 Not Found**: User not found or outside current user's scope
    
    ### Notes:
    The user must be within the current user's organizational scope.
    Any new organizational assignments will be validated against the current user's scope.
    """
    try:
        updated_user = await update_user_info_by_uuid_service(db, str(user_uuid), user_data, current_user)
        return updated_user
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.delete("/{user_uuid}")
@require_permission("user.delete")
async def delete_user(
    user_uuid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete (deactivate) a user.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **user_uuid** (UUID): UUID of the user to delete
    
    ### Query Parameters:
    - None
    
    ### Request Body:
    - None
    
    ### Response (application/json):
    - **200 OK**: Returns success message
    
    ### Error Responses:
    - **403 Forbidden**: Insufficient permissions or scope violation
    - **404 Not Found**: User not found or outside current user's scope
    - **400 Bad Request**: Cannot delete own account
    
    ### Notes:
    The user will be soft-deleted by setting is_active to False.
    The user must be within the current user's organizational scope.
    Users cannot delete their own account.
    """
    try:
        result = await delete_user_by_uuid_service(db, str(user_uuid), current_user)
        return result
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.patch("/{user_uuid}/password")
@require_permission("user.edit")
async def update_user_password(
    user_uuid: uuid.UUID,
    password_data: PasswordUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update user password.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **user_uuid** (UUID): UUID of the user whose password to update
    
    ### Query Parameters:
    - None
    
    ### Request Body (application/json):
    - **new_password** (str): New password (minimum 8 characters, must contain 1 lowercase, 1 uppercase, 1 special character)
    
    ### Response (application/json):
    - **200 OK**: Returns success message
    
    ### Error Responses:
    - **400 Bad Request**: Invalid password format
    - **403 Forbidden**: Insufficient permissions or scope violation
    - **404 Not Found**: User not found or outside current user's scope
    
    ### Notes:
    Users can update their own password, or admins can update any user's password
    within their organizational scope.
    """
    try:
        result = await update_user_password_by_uuid_service(
            db=db,
            user_uuid=str(user_uuid),
            new_password=password_data.new_password,
            current_user=current_user
        )
        return result
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )


@router.get("/stats/count")
@require_permission("user.list")
async def get_user_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get count of active users within the current user's scope.
    
    This endpoint returns the total number of active users that the current user
    has permission to view based on their organizational scope and role.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - None
    
    ### Query Parameters:
    - None
    
    ### Request Body:
    - None (GET request does not require a body)
    
    ### Response (application/json):
    - **200 OK**: Returns the count of active users
    
    #### Example Response:
    ```json
    {
        "active_users": 25
    }
    ```
    
    ### Error Responses:
    - **403 Forbidden**: 
        ```json
        { "detail": "Insufficient permissions" }
        ```
    - **500 Internal Server Error**: 
        ```json
        { "detail": "Unexpected error occurred while counting users" }
        ```
    
    ### Notes:
    - Results are automatically filtered based on the current user's organizational scope
    - Super Admin: Counts all active users in the system
    - VidyaShakthi Admin: Counts active users in their organization
    - Block Admin: Counts active users in their block
    - School Admin/Teacher: Counts active users in their school
    - Only users with `user.list` permission can access this endpoint
    - The count includes only users with `is_active = true`
    - Useful for dashboard statistics and user management overviews
    """
    try:
        count = await count_active_users(db, current_user)
        return {"active_users": count}
    except (PermissionDeniedError, ScopeViolationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )