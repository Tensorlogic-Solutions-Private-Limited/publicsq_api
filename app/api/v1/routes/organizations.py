"""
API routes for organizational hierarchy management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.decorators.permissions import require_permission, validate_scope
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    BlockCreate, BlockUpdate, BlockResponse,
    SchoolCreate, SchoolUpdate, SchoolResponse,
    OrganizationListResponse, BlockListResponse, SchoolListResponse,
    OrganizationDetailResponse, BlockDetailResponse, SchoolDetailResponse,
    SchoolCodesListResponse, RemoveBoardsRequest, RemoveBoardsResponse
)
from app.services.organization_service import OrganizationService, BlockService, SchoolService

router = APIRouter()

# Organization endpoints
@router.post("/v1/organizations", tags=["Organizations"], response_model=OrganizationResponse)
@require_permission("school.create")  # Using school.create as proxy for org creation permission
async def create_organization(
    organization_data: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new organization.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Request Body:
    - **org_code** (str): Unique organization code
    - **org_name** (str): Organization name
    - **org_description** (str, optional): Organization description
    - **is_active** (bool, optional): Whether the organization is active (default: true)
    
    ### Response:
    - **201 Created**: Organization created successfully
    - **400 Bad Request**: Validation error or duplicate code/name
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Only Super Admin and VidyaShakthi Admin can create organizations
    - Organization codes are automatically converted to uppercase
    """
    return await OrganizationService.create_organization(db, organization_data, current_user)


@router.get("/v1/organizations", tags=["Organizations"], response_model=OrganizationListResponse)
@require_permission("school.list")  # Using school.list as proxy for org listing permission
async def get_organizations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive organizations"),
    org_name: Optional[str] = Query(None, min_length=3, description="Search by organization name (partial match, minimum 3 characters)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of organizations with hierarchical scope filtering.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Query Parameters:
    - **page** (int, optional): Page number (default: 1)
    - **page_size** (int, optional): Items per page (default: 50, max: 100)
    - **include_inactive** (bool, optional): Include inactive organizations (default: false)
    - **org_name** (str, optional): Search by organization name (partial match, minimum 3 characters)
    
    ### Response:
    - **200 OK**: List of organizations accessible to the user
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Results are filtered based on user's hierarchical scope
    - Super Admin sees all organizations
    - VidyaShakthi Admin sees their organization
    - Lower-level users see their organization only
    - Organization name search is case-insensitive and matches partial names
    """
    return await OrganizationService.get_organizations(db, current_user, page, page_size, include_inactive, org_name)


@router.get("/v1/organizations/{organization_uuid}", tags=["Organizations"], response_model=OrganizationDetailResponse)
@require_permission("school.view")  # Using school.view as proxy for org viewing permission
async def get_organization(
    organization_uuid: uuid.UUID = Path(..., description="Organization UUID"),
    include_relationships: bool = Query(False, description="Include blocks and schools"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get organization details by ID.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **organization_uuid** (UUID): Organization UUID
    
    ### Query Parameters:
    - **include_relationships** (bool, optional): Include related blocks and schools (default: false)
    
    ### Response:
    - **200 OK**: Organization details
    - **404 Not Found**: Organization not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Access is validated based on user's hierarchical scope
    """
    return await OrganizationService.get_organization_by_uuid(db, organization_uuid, current_user, include_relationships)


@router.put("/v1/organizations/{organization_uuid}", tags=["Organizations"], response_model=OrganizationResponse)
@require_permission("school.edit")  # Using school.edit as proxy for org editing permission
async def update_organization(
    organization_uuid: uuid.UUID = Path(..., description="Organization UUID"),
    organization_data: OrganizationUpdate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update organization details.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **organization_uuid** (UUID): Organization UUID
    
    ### Request Body:
    - **org_code** (str, optional): Updated organization code
    - **org_name** (str, optional): Updated organization name
    - **org_description** (str, optional): Updated organization description
    - **is_active** (bool, optional): Updated active status
    
    ### Response:
    - **200 OK**: Organization updated successfully
    - **400 Bad Request**: Validation error or duplicate code/name
    - **404 Not Found**: Organization not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    """
    return await OrganizationService.update_organization_by_uuid(db, organization_uuid, organization_data, current_user)


@router.delete("/v1/organizations/{organization_uuid}", tags=["Organizations"])
@require_permission("school.delete")  # Using school.delete as proxy for org deletion permission
async def delete_organization(
    organization_uuid: uuid.UUID = Path(..., description="Organization UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete organization (soft delete).
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **organization_uuid** (UUID): Organization UUID
    
    ### Response:
    - **200 OK**: Organization deleted successfully
    - **404 Not Found**: Organization not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Performs soft delete by setting is_active to False
    - Related records will have their foreign keys set to NULL
    - Soft-deleted organizations are filtered out from all queries
    """
    return await OrganizationService.delete_organization_by_uuid(db, organization_uuid, current_user)


# Block endpoints
@router.post("/v1/blocks", tags=["Blocks"], response_model=BlockResponse)
@require_permission("school.create")  # Using school.create as proxy for block creation permission
async def create_block(
    block_data: BlockCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new block.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Request Body:
    - **block_code** (str): Unique block code
    - **block_name** (str): Block name
    - **block_description** (str, optional): Block description
    - **organization_uuid** (UUID): Organization UUID this block belongs to
    - **state_id** (int): State ID this block belongs to (mandatory)
    - **is_active** (bool, optional): Whether the block is active (default: true)
    
    ### Response:
    - **201 Created**: Block created successfully
    - **400 Bad Request**: Validation error, duplicate code/name, or invalid organization
    - **403 Forbidden**: Insufficient permissions or scope violation
    
    ### Notes:
    - Block codes are automatically converted to uppercase
    - Block names must be unique within the organization
    - User must have access to the specified organization
    """
    return await BlockService.create_block(db, block_data, current_user)


@router.get("/v1/blocks", tags=["Blocks"], response_model=BlockListResponse)
@require_permission("school.list")  # Using school.list as proxy for block listing permission
async def get_blocks(
    organization_uuid: Optional[uuid.UUID] = Query(None, description="Filter by organization UUID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive blocks"),
    block_name: Optional[str] = Query(None, min_length=3, description="Search by block name (partial match, minimum 3 characters)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of blocks with hierarchical scope filtering.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Query Parameters:
    - **organization_uuid** (UUID, optional): Filter by organization UUID
    - **page** (int, optional): Page number (default: 1)
    - **page_size** (int, optional): Items per page (default: 50, max: 100)
    - **include_inactive** (bool, optional): Include inactive blocks (default: false)
    - **block_name** (str, optional): Search by block name (partial match, minimum 3 characters)
    
    ### Response:
    - **200 OK**: List of blocks accessible to the user with state information
    - **400 Bad Request**: Invalid organization ID or insufficient permissions
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Results are filtered based on user's hierarchical scope
    - Super Admin sees all blocks
    - VidyaShakthi Admin sees blocks in their organization
    - Block Admin sees their block only
    - Block name search is case-insensitive and matches partial names
    - Response includes state_id and state_name for each block
    """
    return await BlockService.get_blocks(db, current_user, organization_uuid, page, page_size, include_inactive, block_name)


@router.get("/v1/blocks/{block_uuid}", tags=["Blocks"], response_model=BlockDetailResponse)
@require_permission("school.view")  # Using school.view as proxy for block viewing permission
async def get_block(
    block_uuid: uuid.UUID = Path(..., description="Block UUID"),
    include_relationships: bool = Query(False, description="Include schools"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get block details by UUID.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **block_uuid** (uuid): Block UUID
    
    ### Query Parameters:
    - **include_relationships** (bool, optional): Include related schools (default: false)
    
    ### Response:
    - **200 OK**: Block details with organization and state information
    - **404 Not Found**: Block not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Access is validated based on user's hierarchical scope
    - Always includes organization and state information
    """
    return await BlockService.get_block_by_uuid(db, block_uuid, current_user, include_relationships)


@router.put("/v1/blocks/{block_uuid}", tags=["Blocks"], response_model=BlockResponse)
@require_permission("school.edit")  # Using school.edit as proxy for block editing permission
async def update_block(
    block_uuid: uuid.UUID = Path(..., description="Block UUID"),
    block_data: BlockUpdate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update block details by UUID.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **block_uuid** (uuid): Block UUID
    
    ### Request Body:
    - **block_code** (str, optional): Updated block code
    - **block_name** (str, optional): Updated block name
    - **block_description** (str, optional): Updated block description
    - **organization_id** (int, optional): Updated organization ID
    - **state_id** (int, optional): Updated state ID this block belongs to
    - **is_active** (bool, optional): Updated active status
    
    ### Response:
    - **200 OK**: Block updated successfully
    - **400 Bad Request**: Validation error, duplicate code/name, or invalid organization
    - **404 Not Found**: Block not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    """
    return await BlockService.update_block_by_uuid(db, block_uuid, block_data, current_user)


@router.delete("/v1/blocks/{block_uuid}", tags=["Blocks"])
@require_permission("school.delete")  # Using school.delete as proxy for block deletion permission
async def delete_block(
    block_uuid: uuid.UUID = Path(..., description="Block UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete block by UUID (soft delete).
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **block_uuid** (uuid): Block UUID
    
    ### Response:
    - **200 OK**: Block deleted successfully
    - **404 Not Found**: Block not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Performs soft delete by setting is_active to False
    - Related records will have their foreign keys set to NULL
    - Soft-deleted blocks are filtered out from all queries
    """
    await BlockService.delete_block_by_uuid(db, block_uuid, current_user)
    return {"message": "Block deleted successfully"}








# School endpoints
@router.post("/v1/schools", tags=["Schools"], response_model=SchoolResponse)
@require_permission("school.create")
@validate_scope(organization_param="organization_uuid", block_param="block_uuid")
async def create_school(
    school_data: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new school.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Request Body:
    - **udise_code** (str): Unique UDISE code (mandatory)
    - **school_name** (str): School name
    - **school_description** (str, optional): School description
    - **address** (str, optional): School address
    - **local_govt_body_id** (str, optional): Local government body ID
    - **state_id** (int, optional): State ID
    - **boards** (List[int]): List of board IDs (mandatory, at least 1)
    - **class_levels** (List[int], optional): List of class levels for each board
    - **block_uuid** (UUID): Block UUID this school belongs to
    - **organization_uuid** (UUID): Organization UUID this school belongs to
    - **is_active** (bool, optional): Whether the school is active (default: true)
    
    ### Response:
    - **201 Created**: School created successfully
    - **400 Bad Request**: Validation error, duplicate UDISE code/name, or invalid block/organization
    - **403 Forbidden**: Insufficient permissions or scope violation
    
    ### Notes:
    - UDISE codes must be unique across all schools
    - School names must be unique within the block
    - At least one board must be specified
    - Organization UUID must match the block's organization
    - User must have access to the specified block and organization
    """
    return await SchoolService.create_school(db, school_data, current_user)


@router.get("/v1/schools", tags=["Schools"], response_model=SchoolListResponse)
@require_permission("school.list")
async def get_schools(
    organization_uuid: Optional[uuid.UUID] = Query(None, description="Filter by organization UUID"),
    block_uuid: Optional[uuid.UUID] = Query(None, description="Filter by block UUID"),
    school_name: Optional[str] = Query(None, min_length=3, description="Search by school name (partial match, minimum 3 characters)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    include_inactive: bool = Query(False, description="Include inactive schools"),
    # exact UDISE+ code filter
    udise_code: Optional[str] = Query(None, min_length=1, description="Exact UDISE+ code"),
    # board and state filters
    board_id: Optional[int] = Query(None, gt=0, description="Filter by board ID"),
    state_id: Optional[int] = Query(None, gt=0, description="Filter by state ID (via block relationship)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of schools with hierarchical scope filtering.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Query Parameters:
    - **organization_uuid** (UUID, optional): Filter by organization UUID
    - **block_uuid** (UUID, optional): Filter by block UUID
    - **school_name** (str, optional): Search by school name (partial match, minimum 3 characters, single word)
    - **udise_code** (str, optional): Filter by exact UDISE+ code
    - **board_id** (int, optional): Filter by board ID
    - **state_id** (int, optional): Filter by state ID (via block relationship)
    - **page** (int, optional): Page number (default: 1)
    - **page_size** (int, optional): Items per page (default: 50, max: 100)
    - **include_inactive** (bool, optional): Include inactive schools (default: false)
    
    ### Response:
    - **200 OK**: List of schools accessible to the user
    - **400 Bad Request**: Invalid organization/block UUID or insufficient permissions
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Results are filtered based on user's hierarchical scope
    - Super Admin sees all schools
    - VidyaShakthi Admin sees schools in their organization
    - Block Admin sees schools in their block
    - School Admin and Teachers see their school only
    - When school_name is provided, results are sorted by creation date (newest first)
    - School name search is case-insensitive and matches partial names
    - Response includes school boards and state information
    """
    return await SchoolService.get_schools(db, current_user, organization_uuid, block_uuid, page, page_size, include_inactive, school_name, udise_code=udise_code, board_id=board_id, state_id=state_id)


@router.get("/v1/schools/codes", tags=["Schools"], response_model=SchoolCodesListResponse)
@require_permission("school.list")
async def get_school_codes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get simple list of schools with UUID, name, and UDISE code.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Response:
    - **200 OK**: List of schools with basic information
    - **403 Forbidden**: Insufficient permissions
    
    ### Response Format:
    ```json
    {
        "data": [
            {
                "uuid": "123e4567-e89b-12d3-a456-426614174000",
                "school_name": "ABC Primary School", 
                "udise_code": "12345678901"
            }
        ]
    }
    ```
    
    ### Notes:
    - Returns only active schools accessible to the user based on hierarchical scope
    - Results are sorted alphabetically by school name
    - Lightweight response for dropdown/selection purposes
    - Super Admin sees all schools
    - VidyaShakthi Admin sees schools in their organization
    - Block Admin sees schools in their block
    - Teachers see their school only
    """
    return await SchoolService.get_school_codes(db, current_user)


@router.get("/v1/schools/{school_uuid}", tags=["Schools"], response_model=SchoolDetailResponse)
@require_permission("school.view")
async def get_school(
    school_uuid: uuid.UUID = Path(..., description="School UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get school details by UUID.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **school_uuid** (uuid): School UUID
    
    ### Response:
    - **200 OK**: School details with organization and block information
    - **404 Not Found**: School not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Access is validated based on user's hierarchical scope
    - Always includes organization and block information
    """
    return await SchoolService.get_school_by_uuid(db, school_uuid, current_user)


@router.put("/v1/schools/{school_uuid}", tags=["Schools"], response_model=SchoolResponse)
@require_permission("school.edit")
async def update_school(
    school_uuid: uuid.UUID = Path(..., description="School UUID"),
    school_data: SchoolUpdate = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update school details by UUID.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **school_uuid** (uuid): School UUID
    
    ### Request Body:
    - **udise_code** (str, optional): Updated UDISE code
    - **school_name** (str, optional): Updated school name
    - **school_description** (str, optional): Updated school description
    - **address** (str, optional): Updated school address
    - **local_govt_body_id** (str, optional): Updated local government body ID
    - **state_id** (int, optional): Updated state ID
    - **boards** (List[int], optional): Updated list of board IDs
    - **class_levels** (List[int], optional): Updated list of class levels
    - **block_uuid** (UUID, optional): Updated block UUID
    - **organization_uuid** (UUID, optional): Updated organization UUID
    - **is_active** (bool, optional): Updated active status
    
    ### Response:
    - **200 OK**: School updated successfully
    - **400 Bad Request**: Validation error, duplicate UDISE code/name, or invalid block/organization
    - **404 Not Found**: School not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Organization UUID must match the block's organization if both are updated
    - UDISE codes must remain unique across all schools
    - At least one board must be specified if boards are updated
    """
    return await SchoolService.update_school_by_uuid(db, school_uuid, school_data, current_user)


@router.delete("/v1/schools/{school_uuid}", tags=["Schools"])
@require_permission("school.delete")
async def delete_school(
    school_uuid: uuid.UUID = Path(..., description="School UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete school by UUID (soft delete).
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **school_uuid** (uuid): School UUID
    
    ### Response:
    - **200 OK**: School deleted successfully
    - **404 Not Found**: School not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Notes:
    - Performs soft delete by setting is_active to False
    - Related records will have their foreign keys set to NULL
    - Soft-deleted schools are filtered out from all queries
    """
    await SchoolService.delete_school_by_uuid(db, school_uuid, current_user)
    return {"message": "School deleted successfully"}


@router.delete("/v1/schools/{school_uuid}/boards", tags=["Schools"], response_model=RemoveBoardsResponse)
@require_permission("school.edit")
async def remove_boards_from_school(
    school_uuid: uuid.UUID = Path(..., description="School UUID"),
    remove_request: RemoveBoardsRequest = ...,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove specific boards from a school.
    
    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **school_uuid** (uuid): School UUID
    
    ### Request Body:
    - **board_ids** (List[int]): List of board IDs to remove from the school (minimum 1)
    
    ### Response:
    - **200 OK**: Boards removed successfully
    - **400 Bad Request**: Invalid board IDs, boards not associated with school, or trying to remove all boards
    - **404 Not Found**: School not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    
    ### Example Request:
    ```json
    {
        "board_ids": [2, 4, 6]
    }
    ```
    
    ### Example Response:
    ```json
    {
        "message": "Successfully removed 3 board(s) from school",
        "school_uuid": "123e4567-e89b-12d3-a456-426614174000",
        "removed_board_ids": [2, 4, 6],
        "remaining_board_ids": [1, 3, 5]
    }
    ```
    
    ### Notes:
    - At least one board must remain associated with the school
    - Only boards currently associated with the school can be removed
    - Performs soft delete by setting is_active to False on SchoolBoard records
    - Duplicate board IDs in the request are not allowed
    - Board IDs must be positive integers
    """
    return await SchoolService.remove_boards_from_school(db, school_uuid, remove_request.board_ids, current_user)





