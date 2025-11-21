"""
Service layer for organizational hierarchy operations.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.orm import selectinload, joinedload
from fastapi import HTTPException, status
import uuid

from app.models.organization import Organization, Block, School, SchoolBoard, SchoolBoardClass
from app.models.master import Board, State
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreate, OrganizationUpdate, OrganizationResponse,
    BlockCreate, BlockUpdate, BlockResponse,
    SchoolCreate, SchoolUpdate, SchoolResponse,
    OrganizationListResponse, BlockListResponse, SchoolListResponse,
    OrganizationDetailResponse, BlockDetailResponse, SchoolDetailResponse
)
from app.services.scope_service import ScopeFilterService
from app.services.response_helpers import OrganizationResponseHelper, BlockResponseHelper, SchoolResponseHelper


class OrganizationService:
    """Service for organization operations."""
    
    @staticmethod
    async def get_organization_by_uuid(
        db: AsyncSession,
        organization_uuid: uuid.UUID,
        current_user: User,
        include_relationships: bool = False
    ) -> OrganizationDetailResponse:
        """Get organization by UUID with scope validation."""
        
        # First, get the organization by UUID
        query = select(Organization).filter(
            Organization.uuid == organization_uuid,
            Organization.is_active == True
)

        if include_relationships:
            query = query.options(
                selectinload(Organization.blocks).selectinload(Block.active_schools).selectinload(School.created_by_user).selectinload(School.updated_by_user),
                selectinload(Organization.blocks).selectinload(Block.state),
                selectinload(Organization.active_schools).selectinload(School.created_by_user).selectinload(School.updated_by_user),
                selectinload(Organization.blocks).selectinload(Block.created_by_user).selectinload(Block.updated_by_user),
                joinedload(Organization.created_by_user),
                joinedload(Organization.updated_by_user)
            )
        else:
            query = query.options(
                joinedload(Organization.created_by_user),
                joinedload(Organization.updated_by_user)
            )
        
        result = await db.execute(query)
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Use OrganizationResponseHelper to build response data
        response_data = OrganizationResponseHelper.build_response_data(organization)
        
        # Handle relationships if requested
        if include_relationships:
            # Filter active blocks and build their responses
            response_data['blocks'] = [
                BlockResponse(
                    id=block.id,
                    uuid=block.uuid,
                    block_code=block.block_code,
                    block_name=block.block_name,
                    block_description=block.block_description,
                    organization_uuid=organization.uuid,
                    is_active=block.is_active,
                    created_at=block.created_at,
                    updated_at=block.updated_at,
                    created_by=block.created_by_user.username if block.created_by_user else None,
                    updated_by=block.updated_by_user.username if block.updated_by_user else None
                ) for block in organization.blocks if block.is_active
            ] if organization.blocks else []
            
            # Filter active schools and build their responses
            response_data['schools'] = [
                SchoolResponse(
                    id=school.id,
                    uuid=school.uuid,
                    udise_code=school.udise_code,
                    school_name=school.school_name,
                    school_description=school.school_description,
                    organization_uuid=organization.uuid,
                    block_uuid=school.block.uuid if school.block else None,
                    is_active=school.is_active,
                    created_at=school.created_at,
                    updated_at=school.updated_at,
                    created_by=school.created_by_user.username if school.created_by_user else None,
                    updated_by=school.updated_by_user.username if school.updated_by_user else None,
                ) for school in organization.active_schools
            ] if organization.schools else []
        else:
            # Clear relationship data if not requested
            response_data['blocks'] = []
            response_data['schools'] = []
        
        # Return the response using the helper data
        return OrganizationDetailResponse(**response_data)
    
    @staticmethod
    async def update_organization_by_uuid(
        db: AsyncSession,
        organization_uuid: uuid.UUID,
        organization_data: OrganizationUpdate,
        current_user: User
    ) -> OrganizationResponse:
        """Update organization by UUID."""
        
        # Get organization by UUID (only active ones can be updated)
        result = await db.execute(
            select(Organization)
            .options(
                selectinload(Organization.created_by_user),
                selectinload(Organization.updated_by_user)
            )
            .filter(
                Organization.uuid == organization_uuid,
                Organization.is_active == True
            )
        )
        organization = result.scalar_one_or_none()

        
        if not organization or not organization.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or already deleted"
            )

        
        # Use integer ID for scope validation and updates
        if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check for duplicates if updating code or name
        if organization_data.org_code and organization_data.org_code != organization.org_code:
            existing = await db.execute(
                select(Organization).filter(
                    and_(
                        Organization.org_code == organization_data.org_code,
                        Organization.id != organization.id
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Organization with code '{organization_data.org_code}' already exists"
                )
        
        if organization_data.org_name and organization_data.org_name != organization.org_name:
            existing = await db.execute(
                select(Organization).filter(
                    and_(
                        Organization.org_name == organization_data.org_name,
                        Organization.id != organization.id
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Organization with name '{organization_data.org_name}' already exists"
                )
        
        # Update fields
        for field, value in organization_data.model_dump(exclude_unset=True).items():
            setattr(organization, field, value)
        
        organization.updated_by = current_user.id
        
        try:
            await db.commit()
            await db.refresh(organization)
            
            # Use OrganizationResponseHelper to build response data
            response_data = OrganizationResponseHelper.build_response_data(organization)
            return OrganizationResponse(**response_data)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update organization"
            )
    
    @staticmethod
    async def delete_organization_by_uuid(
        db: AsyncSession,
        organization_uuid: uuid.UUID,
        current_user: User
    ) -> Dict[str, str]:
        """Soft delete organization by UUID (sets is_active=False)."""

        # Get organization by UUID (only active ones considered for deletion)
        result = await db.execute(
            select(Organization).filter(Organization.uuid == organization_uuid)
        )
        organization = result.scalar_one_or_none()

        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        # Use integer ID for scope validation and deletion permission
        if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )

        # Check if organization has associated active records (blocks/schools)
        blocks_count = await db.execute(
            select(func.count(Block.id)).filter(Block.organization_id == organization.id, Block.is_active == True)
        )
        if blocks_count.scalar() > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete organization with existing active blocks"
            )

        schools_count = await db.execute(
            select(func.count(School.id)).filter(School.organization_id == organization.id, School.is_active == True)
        )
        if schools_count.scalar() > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete organization with existing active schools"
            )

        try:
            # Soft delete: mark inactive and record who did it
            organization.is_active = False
            organization.updated_by = current_user.id

            # persist
            await db.commit()
            return {"message": "Organization soft deleted successfully"}
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete organization"
            )

    
    @staticmethod
    async def create_organization(
        db: AsyncSession,
        organization_data: OrganizationCreate,
        current_user: User
    ) -> OrganizationResponse:
        """Create a new organization."""
        
        # Check if organization code already exists
        existing_org = await db.execute(
            select(Organization).filter(Organization.org_code == organization_data.org_code)
        )
        if existing_org.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Organization with code '{organization_data.org_code}' already exists"
            )
        
        # Check if organization name already exists
        existing_name = await db.execute(
            select(Organization).filter(Organization.org_name == organization_data.org_name)
        )
        if existing_name.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Organization with name '{organization_data.org_name}' already exists"
            )
        
        # Create organization
        organization = Organization(
            org_code=organization_data.org_code,
            org_name=organization_data.org_name,
            org_description=organization_data.org_description,
            is_active=organization_data.is_active,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        
        try:
            db.add(organization)
            await db.commit()
            await db.refresh(organization)
        except Exception as e:
            await db.rollback()
            from app.utils.database_error_handler import DatabaseErrorHandler
            from sqlalchemy.exc import IntegrityError, SQLAlchemyError
            
            if isinstance(e, (IntegrityError, SQLAlchemyError)):
                DatabaseErrorHandler.handle_sqlalchemy_error(
                    e, 
                    table_name="organizations", 
                    operation="create",
                    context={"org_code": organization_data.org_code, "org_name": organization_data.org_name}
                )
            
            # Re-raise other exceptions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create organization"
            )
        
        # Load user relationships for response
        org_with_users = await db.execute(
            select(Organization)
            .options(
                selectinload(Organization.created_by_user),
                selectinload(Organization.updated_by_user)
            )
            .filter(Organization.id == organization.id)
        )
        org_with_users = org_with_users.scalar_one()
        
        # Use OrganizationResponseHelper to build response data
        response_data = OrganizationResponseHelper.build_response_data(org_with_users)
        return OrganizationResponse(**response_data)
    
    @staticmethod
    async def get_organizations(
        db: AsyncSession,
        current_user: User,
        page: int = 1,
        page_size: int = 50,
        include_inactive: bool = False,
        org_name: Optional[str] = None
    ) -> OrganizationListResponse:
        """Get list of organizations with scope filtering."""
        
        # Build base query with user relationships
        query = select(Organization).options(
            joinedload(Organization.created_by_user),
            joinedload(Organization.updated_by_user)
        )
        
        # Apply scope filtering
        query = await ScopeFilterService.filter_organizations_query(db, current_user, query)
        
        # Filter active/inactive
        if not include_inactive:
            query = query.filter(Organization.is_active == True)
        
        # Filter by organization name if provided
        if org_name:
            # Validate single word (no spaces allowed)
            if ' ' in org_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization name search must be a single word"
                )
            
            # Apply case-insensitive partial matching
            search_term = org_name.strip()
            query = query.filter(Organization.org_name.ilike(f'%{search_term}%'))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        organizations = result.scalars().all()
        
        return OrganizationListResponse(
            data=[OrganizationResponse(**OrganizationResponseHelper.build_response_data(org)) for org in organizations],
            total=total,
            page=page,
            page_size=page_size,
            grandTotal=total
        )
    
    @staticmethod
    async def get_organization_by_id(
        db: AsyncSession,
        organization_id: int,
        current_user: User,
        include_relationships: bool = False
    ) -> OrganizationDetailResponse:
        """Get organization by ID with scope validation."""
        
        # Check if user can access this organization
        if not await ScopeFilterService.can_access_organization(db, current_user, organization_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Build query with optional relationships and user relationships
        query = select(Organization).filter(Organization.id == organization_id, Organization.is_active == True)
        
        # Always load user relationships for audit fields
        query = query.options(
            selectinload(Organization.created_by_user),
            selectinload(Organization.updated_by_user)
        )
        
        if include_relationships:
            query = query.options(
                selectinload(Organization.blocks).selectinload(Block.state),
                selectinload(Organization.active_schools)
            )
        
        result = await db.execute(query)
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Use OrganizationResponseHelper to build response data
        response_data = OrganizationResponseHelper.build_response_data(organization)
        
        # Handle relationships if requested
        if not include_relationships:
            # Clear relationship data if not requested
            response_data['blocks'] = []
            response_data['schools'] = []
        
        return OrganizationDetailResponse(**response_data)
    
    @staticmethod
    async def update_organization(
        db: AsyncSession,
        organization_id: int,
        organization_data: OrganizationUpdate,
        current_user: User
    ) -> OrganizationResponse:
        """Update organization."""
        
        # Check if user can access this organization
        if not await ScopeFilterService.can_access_organization(db, current_user, organization_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Get organization
        result = await db.execute(
            select(Organization).filter(Organization.id == organization_id, Organization.is_active == True)
        )
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check for duplicate code if updating
        if organization_data.org_code and organization_data.org_code != organization.org_code:
            existing_code = await db.execute(
                select(Organization).filter(
                    and_(
                        Organization.org_code == organization_data.org_code,
                        Organization.id != organization_id
                    )
                )
            )
            if existing_code.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Organization with code '{organization_data.org_code}' already exists"
                )
        
        # Check for duplicate name if updating
        if organization_data.org_name and organization_data.org_name != organization.org_name:
            existing_name = await db.execute(
                select(Organization).filter(
                    and_(
                        Organization.org_name == organization_data.org_name,
                        Organization.id != organization_id
                    )
                )
            )
            if existing_name.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Organization with name '{organization_data.org_name}' already exists"
                )
        
        # Update fields
        update_data = organization_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(organization, field, value)
        
        organization.updated_by = current_user.id
        
        await db.commit()
        await db.refresh(organization)
        
        # Load user relationships for response
        org_with_users = await db.execute(
            select(Organization)
            .options(
                selectinload(Organization.created_by_user),
                selectinload(Organization.updated_by_user)
            )
            .filter(Organization.id == organization.id)
        )
        org_with_users = org_with_users.scalar_one()
        
        # Use OrganizationResponseHelper to build response data
        response_data = OrganizationResponseHelper.build_response_data(org_with_users)
        return OrganizationResponse(**response_data)
    
    @staticmethod
    async def delete_organization(
        db: AsyncSession,
        organization_id: int,
        current_user: User
    ) -> Dict[str, str]:
        """Soft delete organization."""
        
        # Check if user can access this organization
        if not await ScopeFilterService.can_access_organization(db, current_user, organization_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Get organization
        result = await db.execute(
            select(Organization).filter(Organization.id == organization_id, Organization.is_active == True)
        )
        organization = result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Soft delete by setting is_active to False
        organization.is_active = False
        organization.updated_by = current_user.id
        
        await db.commit()
        
        return {"message": "Organization deleted successfully"}


class BlockService:
    """Service for block operations."""
    
    @staticmethod
    async def create_block(
        db: AsyncSession,
        block_data: BlockCreate,
        current_user: User
    ) -> BlockResponse:
        """Create a new block."""
        
        # First, get the organization by UUID to get its integer ID
        org_query = select(Organization).filter(Organization.uuid == block_data.organization_uuid, Organization.is_active == True)
        org_result = await db.execute(org_query)
        organization = org_result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization or insufficient permissions"
            )
        
        # Validate state_id exists in state_master table
        from app.exceptions.state_exceptions import InvalidStateError
        state_query = select(State).filter(State.id == block_data.state_id)
        state_result = await db.execute(state_query)
        state = state_result.scalar_one_or_none()
        
        if not state:
            raise InvalidStateError(state_id=block_data.state_id)
        
        # Check if block code already exists
        existing_block = await db.execute(
            select(Block).filter(Block.block_code == block_data.block_code)
        )
        if existing_block.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Block with code '{block_data.block_code}' already exists"
            )
        
        # Check if block name already exists within the organization
        existing_name = await db.execute(
            select(Block).filter(
                and_(
                    Block.block_name == block_data.block_name,
                    Block.organization_id == organization.id
                )
            )
        )
        if existing_name.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Block with name '{block_data.block_name}' already exists in this organization"
            )
        
        # Create block with state_id
        block = Block(
            block_code=block_data.block_code,
            block_name=block_data.block_name,
            block_description=block_data.block_description,
            organization_id=organization.id,
            state_id=block_data.state_id,
            is_active=block_data.is_active,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        
        try:
            db.add(block)
            await db.commit()
            await db.refresh(block)
        except Exception as e:
            await db.rollback()
            from app.utils.database_error_handler import DatabaseErrorHandler
            from sqlalchemy.exc import IntegrityError, SQLAlchemyError
            
            if isinstance(e, (IntegrityError, SQLAlchemyError)):
                DatabaseErrorHandler.handle_sqlalchemy_error(
                    e, 
                    table_name="blocks", 
                    operation="create",
                    context={"block_code": block_data.block_code, "state_id": block_data.state_id}
                )
            
            # Re-raise other exceptions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create block"
            )
        
        # Load organization, state, and user relationships for response
        from sqlalchemy.orm import selectinload, joinedload
        block_with_org = await db.execute(
            select(Block)
            .options(
                selectinload(Block.organization).selectinload(Organization.created_by_user),
                selectinload(Block.organization).selectinload(Organization.updated_by_user),
                selectinload(Block.state),
                selectinload(Block.created_by_user),
                selectinload(Block.updated_by_user)
            )
            .filter(Block.id == block.id)
        )
        block_with_org = block_with_org.scalar_one()
        
        # Use BlockResponseHelper to build response data
        response_data = BlockResponseHelper.build_response_data(block_with_org)
        return BlockResponse(**response_data)
    
    @staticmethod
    async def get_blocks(
        db: AsyncSession,
        current_user: User,
        organization_uuid: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 50,
        include_inactive: bool = False,
        block_name: Optional[str] = None
    ) -> BlockListResponse:
        """Get list of blocks with scope filtering."""
        
        # Build base query
        query = select(Block).options(
            selectinload(Block.organization).selectinload(Organization.created_by_user),
            selectinload(Block.organization).selectinload(Organization.updated_by_user),
            selectinload(Block.state),
            selectinload(Block.active_schools).selectinload(School.created_by_user),
            selectinload(Block.active_schools).selectinload(School.updated_by_user),
            selectinload(Block.created_by_user),
            selectinload(Block.updated_by_user)
        )
        
        # Apply scope filtering
        query = await ScopeFilterService.filter_blocks_query(db, current_user, query)
        
        # Filter by organization if specified
        if organization_uuid:
            # Convert UUID to integer ID
            org_result = await db.execute(
                select(Organization).filter(Organization.uuid == organization_uuid)
            )
            organization = org_result.scalar_one_or_none()
            if not organization:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization not found"
                )
            
            if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
            query = query.filter(Block.organization_id == organization.id)
        
        # Filter active/inactive
        if not include_inactive:
            query = query.filter(Block.is_active == True)
        
        # Filter by block name if provided
        if block_name:
            # Validate single word (no spaces allowed)
            if ' ' in block_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block name search must be a single word"
                )
            
            # Apply case-insensitive partial matching
            search_term = block_name.strip()
            query = query.filter(Block.block_name.ilike(f'%{search_term}%'))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        blocks = result.scalars().all()
        
        # Use BlockResponseHelper to build response data
        block_responses = []
        for block in blocks:
            response_data = BlockResponseHelper.build_response_data(block)
            block_response = BlockResponse(**response_data)
            block_responses.append(block_response)
        
        return BlockListResponse(
            data=block_responses,
            total=total,
            page=page,
            page_size=page_size,
            grandTotal=total
        )
    
    @staticmethod
    async def get_block_by_id(
        db: AsyncSession,
        block_id: int,
        current_user: User,
        include_relationships: bool = False
    ) -> BlockDetailResponse:
        """Get block by ID with scope validation."""
        
        # Check if user can access this block
        if not await ScopeFilterService.can_access_block(db, current_user, block_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Build query with optional relationships and user relationships
        query = select(Block).filter(Block.id == block_id, Block.is_active == True).options(
            selectinload(Block.organization).selectinload(Organization.created_by_user),
            selectinload(Block.organization).selectinload(Organization.updated_by_user),
            selectinload(Block.state),
            selectinload(Block.created_by_user),
            selectinload(Block.updated_by_user)
        )
        
        if include_relationships:
            query = query.options(
                selectinload(Block.active_schools).selectinload(School.created_by_user),
                selectinload(Block.active_schools).selectinload(School.updated_by_user)
            )
        
        result = await db.execute(query)
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Use BlockResponseHelper to build response data
        response_data = BlockResponseHelper.build_response_data(block)
        response_data['schools'] = []  # Will be populated if include_relationships is True
        return BlockDetailResponse(**response_data)
    
    @staticmethod
    async def update_block(
        db: AsyncSession,
        block_id: int,
        block_data: BlockUpdate,
        current_user: User
    ) -> BlockResponse:
        """Update block."""
        
        # Check if user can access this block
        if not await ScopeFilterService.can_access_block(db, current_user, block_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Get block
        result = await db.execute(
            select(Block).filter(Block.id == block_id, Block.is_active == True)
        )
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Validate organization if updating
        if block_data.organization_id and block_data.organization_id != block.organization_id:
            if not await ScopeFilterService.can_access_organization(db, current_user, block_data.organization_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
        
        # Validate state_id if updating
        if hasattr(block_data, 'state_id') and block_data.state_id and block_data.state_id != block.state_id:
            from app.exceptions.state_exceptions import InvalidStateError
            state_query = select(State).filter(State.id == block_data.state_id)
            state_result = await db.execute(state_query)
            state = state_result.scalar_one_or_none()
            
            if not state:
                raise InvalidStateError(state_id=block_data.state_id)
        
        # Check for duplicate code if updating
        if block_data.block_code and block_data.block_code != block.block_code:
            existing_code = await db.execute(
                select(Block).filter(
                    and_(
                        Block.block_code == block_data.block_code,
                        Block.id != block_id
                    )
                )
            )
            if existing_code.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Block with code '{block_data.block_code}' already exists"
                )
        
        # Check for duplicate name within organization if updating
        org_id = block_data.organization_id or block.organization_id
        if block_data.block_name and block_data.block_name != block.block_name:
            existing_name = await db.execute(
                select(Block).filter(
                    and_(
                        Block.block_name == block_data.block_name,
                        Block.organization_id == org_id,
                        Block.id != block_id
                    )
                )
            )
            if existing_name.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Block with name '{block_data.block_name}' already exists in this organization"
                )
        
        # Update fields
        update_data = block_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(block, field, value)
        
        block.updated_by = current_user.id
        
        try:
            await db.commit()
            await db.refresh(block)
        except Exception as e:
            await db.rollback()
            from app.utils.database_error_handler import DatabaseErrorHandler
            from sqlalchemy.exc import IntegrityError, SQLAlchemyError
            
            if isinstance(e, (IntegrityError, SQLAlchemyError)):
                DatabaseErrorHandler.handle_sqlalchemy_error(
                    e, 
                    table_name="blocks", 
                    operation="update",
                    context={"block_id": block_id, "block_code": block_data.block_code}
                )
            
            # Re-raise other exceptions
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update block"
            )
        
        # Load organization relationship for response
        from sqlalchemy.orm import selectinload, joinedload
        block_with_org = await db.execute(
            select(Block)
            .options(
                selectinload(Block.organization).selectinload(Organization.created_by_user),
                selectinload(Block.organization).selectinload(Organization.updated_by_user),
                selectinload(Block.state),
                selectinload(Block.created_by_user),
                selectinload(Block.updated_by_user)
            )
            .filter(Block.id == block.id)
        )
        block_with_org = block_with_org.scalar_one()
        
        # Use OrganizationResponseHelper for organization data
        return BlockResponse(
            id=block_with_org.id,
            uuid=block_with_org.uuid,
            block_code=block_with_org.block_code,
            block_name=block_with_org.block_name,
            block_description=block_with_org.block_description,
            organization_uuid=block_with_org.organization.uuid if block_with_org.organization else None,
            is_active=block_with_org.is_active,
            created_at=block_with_org.created_at,
            updated_at=block_with_org.updated_at,
            created_by=block_with_org.created_by_user.username if block_with_org.created_by_user else None,
            updated_by=block_with_org.updated_by_user.username if block_with_org.updated_by_user else None,
            organization=OrganizationResponse(**OrganizationResponseHelper.build_response_data(block_with_org.organization)) if block_with_org.organization else None
        )
    
    @staticmethod
    async def delete_block(
        db: AsyncSession,
        block_id: int,
        current_user: User
    ) -> Dict[str, str]:
        """Soft delete block."""
        
        # Check if user can access this block
        if not await ScopeFilterService.can_access_block(db, current_user, block_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Get block
        result = await db.execute(
            select(Block).filter(Block.id == block_id, Block.is_active == True)
        )
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Soft delete by setting is_active to False
        block.is_active = False
        block.updated_by = current_user.id
        
        await db.commit()
        
        return {"message": "Block deleted successfully"}

    @staticmethod
    async def get_block_by_uuid(
        db: AsyncSession,
        block_uuid: uuid.UUID,
        current_user: User,
        include_relationships: bool = False
    ) -> BlockDetailResponse:
        """Get block by UUID with scope validation."""
        
        # First, get the block by UUID
        query = select(Block).filter(Block.uuid == block_uuid, Block.is_active == True).options(
            selectinload(Block.organization).selectinload(Organization.created_by_user),
            selectinload(Block.organization).selectinload(Organization.updated_by_user),
            selectinload(Block.state),
            selectinload(Block.created_by_user),
            selectinload(Block.updated_by_user)
        )
        
        if include_relationships:
            query = query.options(
                selectinload(Block.active_schools).selectinload(School.created_by_user),
                selectinload(Block.active_schools).selectinload(School.updated_by_user)
            )
        
        result = await db.execute(query)
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_block(db, current_user, block.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Use BlockResponseHelper to build response data
        response_data = BlockResponseHelper.build_response_data(block)
        
        # Handle schools relationship if requested
        if include_relationships:
            response_data['schools'] = [
                SchoolResponseHelper.build_response_data(school)
                for school in block.active_schools
            ]
        else:
            response_data['schools'] = []
        
        return BlockDetailResponse(**response_data)

    @staticmethod
    async def update_block_by_uuid(
        db: AsyncSession,
        block_uuid: uuid.UUID,
        block_data: BlockUpdate,
        current_user: User
    ) -> BlockResponse:
        """Update block by UUID."""
        
        # First, get the block by UUID
        query = select(Block).filter(Block.uuid == block_uuid, Block.is_active == True)
        result = await db.execute(query)
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_block(db, current_user, block.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Continue with the same logic as update_block but use the found block
        update_data = block_data.model_dump(exclude_unset=True)
        
        # Validate state_id if being updated
        if "state_id" in update_data:
            state_query = select(State).filter(State.id == update_data["state_id"])
            state_result = await db.execute(state_query)
            state = state_result.scalar_one_or_none()
            
            if not state:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid state_id: {update_data['state_id']}"
                )
        
        # Validate organization if being updated
        if "organization_id" in update_data:
            if not await ScopeFilterService.can_access_organization(db, current_user, update_data["organization_id"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
        
        # Check for duplicate block code if being updated
        if "block_code" in update_data:
            existing_block = await db.execute(
                select(Block).filter(
                    Block.block_code == update_data["block_code"].upper(),
                    Block.id != block.id,
                    Block.is_active == True
                )
            )
            if existing_block.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block code already exists"
                )
            update_data["block_code"] = update_data["block_code"].upper()
        
        # Check for duplicate block name if being updated
        if "block_name" in update_data:
            org_id = update_data.get("organization_id", block.organization_id)
            existing_block = await db.execute(
                select(Block).filter(
                    Block.block_name == update_data["block_name"],
                    Block.organization_id == org_id,
                    Block.id != block.id,
                    Block.is_active == True
                )
            )
            if existing_block.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block name already exists in this organization"
                )
        
        # Update block
        for key, value in update_data.items():
            setattr(block, key, value)
        
        block.updated_by = current_user.id
        
        await db.commit()
        await db.refresh(block)
        
        # Load organization, state, and user relationships for response
        from sqlalchemy.orm import selectinload, joinedload
        block_with_org = await db.execute(
            select(Block)
            .options(
                selectinload(Block.organization).selectinload(Organization.created_by_user),
                selectinload(Block.organization).selectinload(Organization.updated_by_user),
                selectinload(Block.state),
                selectinload(Block.created_by_user),
                selectinload(Block.updated_by_user)
            )
            .filter(Block.id == block.id)
        )
        block_with_org = block_with_org.scalar_one()
        
        # Use BlockResponseHelper to build response data
        response_data = BlockResponseHelper.build_response_data(block_with_org)
        return BlockResponse(**response_data)

    @staticmethod
    async def delete_block_by_uuid(
        db: AsyncSession,
        block_uuid: uuid.UUID,
        current_user: User
    ):
        """Delete block by UUID (soft delete)."""
        
        # First, get the block by UUID
        query = select(Block).filter(Block.uuid == block_uuid, Block.is_active == True)
        result = await db.execute(query)
        block = result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_block(db, current_user, block.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Block not found"
            )
        
        # Soft delete
        block.is_active = False
        block.updated_by = current_user.id
        
        await db.commit()


class SchoolService:
    """Service for school operations."""
    
    @staticmethod
    async def create_school(
        db: AsyncSession,
        school_data: SchoolCreate,
        current_user: User
    ) -> SchoolResponse:
        """Create a new school."""
        
        # First, get the block by UUID to get its integer ID
        block_query = select(Block).filter(Block.uuid == school_data.block_uuid, Block.is_active == True)
        block_result = await db.execute(block_query)
        block = block_result.scalar_one_or_none()
        
        if not block:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Block not found"
            )
        
        # Get the organization by UUID to get its integer ID
        org_query = select(Organization).filter(Organization.uuid == school_data.organization_uuid, Organization.is_active == True)
        org_result = await db.execute(org_query)
        organization = org_result.scalar_one_or_none()
        
        if not organization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization not found"
            )
        
        # Validate that block belongs to the specified organization
        if block.organization_id != organization.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Block does not belong to the specified organization"
            )
        
        # Use integer IDs for scope validation (internal operations)
        if not await ScopeFilterService.can_access_block(db, current_user, block.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid block or insufficient permissions"
            )
        
        # Validate state if provided
        state_id = None
        if school_data.state_id:
            state_query = select(State).filter(State.id == school_data.state_id)
            state_result = await db.execute(state_query)
            state = state_result.scalar_one_or_none()
            if not state:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="State not found"
                )
            state_id = state.id
        
        # Validate boards exist
        board_query = select(Board).filter(Board.id.in_(school_data.boards))
        board_result = await db.execute(board_query)
        boards = board_result.scalars().all()
        if len(boards) != len(school_data.boards):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more boards not found"
            )
        
        # Check if UDISE code already exists
        existing_school = await db.execute(
            select(School).filter(School.udise_code == school_data.udise_code)
        )
        if existing_school.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"School with UDISE code '{school_data.udise_code}' already exists"
            )
        
        # Check if school name already exists within the block
        existing_name = await db.execute(
            select(School).filter(
                and_(
                    School.school_name == school_data.school_name,
                    School.block_id == block.id
                )
            )
        )
        if existing_name.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"School with name '{school_data.school_name}' already exists in this block"
            )
        
        # Create school
        school = School(
            udise_code=school_data.udise_code,
            school_name=school_data.school_name,
            school_description=school_data.school_description,
            address=school_data.address,
            local_govt_body_id=school_data.local_govt_body_id,
            state_id=state_id,
            block_id=block.id,
            organization_id=organization.id,
            is_active=school_data.is_active,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        
        db.add(school)
        await db.commit()
        await db.refresh(school)
        
        # Create school-board relationships
        for board in boards:
            school_board = SchoolBoard(
                school_id=school.id,
                board_id=board.id,
                is_active=True,
                created_by=current_user.id,
                updated_by=current_user.id
            )
            db.add(school_board)
            await db.flush()  # Flush to get the school_board.id
            
            # Create class levels for this school-board combination
            if school_data.class_levels:
                for class_level in school_data.class_levels:
                    school_board_class = SchoolBoardClass(
                        school_board_id=school_board.id,
                        class_level=class_level,
                        is_active=True,
                        created_by=current_user.id,
                        updated_by=current_user.id
                    )
                    db.add(school_board_class)
        
        await db.commit()
        
        # Load the school with relationships for response
        school_with_relationships = await db.scalar(
            select(School)
            .options(
                selectinload(School.school_boards).selectinload(SchoolBoard.board),
                selectinload(School.school_boards).selectinload(SchoolBoard.school_board_classes),
                selectinload(School.state),
                selectinload(School.organization).selectinload(Organization.created_by_user),
                selectinload(School.organization).selectinload(Organization.updated_by_user),
                selectinload(School.block).selectinload(Block.created_by_user),
                selectinload(School.block).selectinload(Block.updated_by_user),
                selectinload(School.block).selectinload(Block.organization).selectinload(Organization.created_by_user),
                selectinload(School.block).selectinload(Block.organization).selectinload(Organization.updated_by_user),
                selectinload(School.created_by_user),
                selectinload(School.updated_by_user)
            )
            .filter(School.id == school.id)
        )
        
        # Use SchoolResponseHelper to build response data
        response_data = SchoolResponseHelper.build_response_data(school_with_relationships)
        return SchoolResponse(**response_data)
    
    @staticmethod
    async def get_schools(
        db: AsyncSession,
        current_user: User,
        organization_uuid: Optional[uuid.UUID] = None,
        block_uuid: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 50,
        include_inactive: bool = False,
        school_name: Optional[str] = None,
        udise_code: Optional[str] = None,
        board_id: Optional[int] = None,
        state_id: Optional[int] = None
    ) -> SchoolListResponse:
        """Get list of schools with scope filtering."""
        
        # Build base query
        query = select(School).options(
            selectinload(School.organization).selectinload(Organization.created_by_user),
            selectinload(School.organization).selectinload(Organization.updated_by_user),
            selectinload(School.block).selectinload(Block.created_by_user),
            selectinload(School.block).selectinload(Block.updated_by_user),
            selectinload(School.state),
            selectinload(School.school_boards).selectinload(SchoolBoard.board),
            selectinload(School.school_boards).selectinload(SchoolBoard.school_board_classes),
            selectinload(School.created_by_user),
            selectinload(School.updated_by_user)
        )
        
        # Apply scope filtering
        query = await ScopeFilterService.filter_schools_query(db, current_user, query)
        
        # Filter by organization if specified
        if organization_uuid:
            # Convert UUID to integer ID
            org_result = await db.execute(
                select(Organization).filter(Organization.uuid == organization_uuid)
            )
            organization = org_result.scalar_one_or_none()
            if not organization:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization not found"
                )
            
            if not await ScopeFilterService.can_access_organization(db, current_user, organization.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
            query = query.filter(School.organization_id == organization.id)
        
        # Filter by block if specified
        if block_uuid:
            # Convert UUID to integer ID
            block_result = await db.execute(
                select(Block).filter(Block.uuid == block_uuid)
            )
            block = block_result.scalar_one_or_none()
            if not block:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block not found"
                )
            
            if not await ScopeFilterService.can_access_block(db, current_user, block.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid block or insufficient permissions"
                )
            query = query.filter(School.block_id == block.id)
        
        # Filter active/inactive
        if not include_inactive:
            query = query.filter(School.is_active == True)


        # Filter by exact UDISE code if provided
        if udise_code:
            normalized = udise_code.strip().upper()
            query = query.filter(School.udise_code == normalized)
            # If both udise_code and school_name are provided, udise_code takes precedence
            school_name = None
        
        # Filter by school name if provided
        if school_name:
            # Validate single word (no spaces allowed)
            if ' ' in school_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="School name search must be a single word"
                )
            
            # Apply case-insensitive partial matching
            search_term = school_name.strip()
            query = query.filter(School.school_name.ilike(f'%{search_term}%'))
        
        # Filter by state_id if provided (always via block relationship)
        if state_id:
            # Use subquery to find schools in blocks with this state
            state_subquery = select(Block.id).where(Block.state_id == state_id)
            query = query.filter(School.block_id.in_(state_subquery))
        
        # Filter by board_id if provided
        if board_id:
            # Use subquery to find schools with this board
            board_subquery = select(SchoolBoard.school_id).where(
                and_(
                    SchoolBoard.board_id == board_id,
                    SchoolBoard.is_active == True
                )
            )
            query = query.filter(School.id.in_(board_subquery))
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Apply sorting - when searching by name, sort by creation date (newest first)
        if school_name:
            query = query.order_by(School.created_at.desc())
        else:
            # Default sorting by school name for consistent results
            query = query.order_by(School.school_name)
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute query
        result = await db.execute(query)
        schools = result.scalars().all()
        
        # Use SchoolResponseHelper to build response data
        school_responses = []
        for school in schools:
            response_data = SchoolResponseHelper.build_response_data(school)
            school_response = SchoolResponse(**response_data)
            school_responses.append(school_response)
        
        return SchoolListResponse(
            data=school_responses,
            total=total,
            page=page,
            page_size=page_size,
            grandTotal=total
        )
    
    @staticmethod
    async def get_school_by_id(
        db: AsyncSession,
        school_id: int,
        current_user: User
    ) -> SchoolDetailResponse:
        """Get school by ID with scope validation."""
        
        # Check if user can access this school
        if not await ScopeFilterService.can_access_school(db, current_user, school_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Build query with relationships
        query = select(School).filter(School.id == school_id, School.is_active == True).options(
            selectinload(School.organization),
            selectinload(School.block)
        )
        
        result = await db.execute(query)
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Use SchoolResponseHelper to build response data
        response_data = SchoolResponseHelper.build_response_data(school)
        return SchoolDetailResponse(**response_data)
    
    @staticmethod
    async def update_school(
        db: AsyncSession,
        school_id: int,
        school_data: SchoolUpdate,
        current_user: User
    ) -> SchoolResponse:
        """Update school."""
        
        # Check if user can access this school
        if not await ScopeFilterService.can_access_school(db, current_user, school_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Get school
        result = await db.execute(
            select(School).filter(School.id == school_id, School.is_active == True)
        )
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Validate block if updating
        if school_data.block_id and school_data.block_id != school.block_id:
            if not await ScopeFilterService.can_access_block(db, current_user, school_data.block_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid block or insufficient permissions"
                )
            
            # Validate organization matches block
            block_result = await db.execute(
                select(Block).filter(Block.id == school_data.block_id)
            )
            block = block_result.scalar_one_or_none()
            
            if not block:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block not found"
                )
            
            org_id = school_data.organization_id or school.organization_id
            if block.organization_id != org_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization ID does not match block's organization"
                )
        
        # Check for duplicate code if updating
        if school_data.udise_code and school_data.udise_code != school.udise_code:
            existing_code = await db.execute(
                select(School).filter(
                    and_(
                        School.udise_code == school_data.udise_code,
                        School.id != school_id
                    )
                )
            )
            if existing_code.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"School with UDISE code '{school_data.udise_code}' already exists"
                )
        
        # Check for duplicate name within block if updating
        block_id = school_data.block_id or school.block_id
        if school_data.school_name and school_data.school_name != school.school_name:
            existing_name = await db.execute(
                select(School).filter(
                    and_(
                        School.school_name == school_data.school_name,
                        School.block_id == block_id,
                        School.id != school_id
                    )
                )
            )
            if existing_name.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"School with name '{school_data.school_name}' already exists in this block"
                )
        
        # Update fields
        update_data = school_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(school, field, value)
        
        school.updated_by = current_user.id
        
        await db.commit()
        await db.refresh(school)
        
        # Use SchoolResponseHelper to build response data
        response_data = SchoolResponseHelper.build_response_data(school)
        return SchoolResponse(**response_data)
    
    @staticmethod
    async def delete_school(
        db: AsyncSession,
        school_id: int,
        current_user: User
    ) -> Dict[str, str]:
        """Soft delete school."""
        
        # Check if user can access this school
        if not await ScopeFilterService.can_access_school(db, current_user, school_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Get school
        result = await db.execute(
            select(School).filter(School.id == school_id, School.is_active == True)
        )
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Soft delete by setting is_active to False
        school.is_active = False
        school.updated_by = current_user.id
        
        await db.commit()
        
        return {"message": "School deleted successfully"}

    @staticmethod
    async def get_school_by_uuid(
        db: AsyncSession,
        school_uuid: uuid.UUID,
        current_user: User
    ) -> SchoolResponse:
        """Get school by UUID with scope validation."""
        
        # First, get the school by UUID
        query = select(School).filter(School.uuid == school_uuid, School.is_active == True).options(
            selectinload(School.organization).selectinload(Organization.created_by_user),
            selectinload(School.organization).selectinload(Organization.updated_by_user),
            selectinload(School.block).selectinload(Block.created_by_user),
            selectinload(School.block).selectinload(Block.updated_by_user),
            selectinload(School.state),
            selectinload(School.school_boards).selectinload(SchoolBoard.board),
            selectinload(School.school_boards).selectinload(SchoolBoard.school_board_classes),
            selectinload(School.created_by_user),
            selectinload(School.updated_by_user)
        )
        
        result = await db.execute(query)
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_school(db, current_user, school.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Use SchoolResponseHelper to build response data
        response_data = SchoolResponseHelper.build_response_data(school)
        return SchoolResponse(**response_data)

    @staticmethod
    async def update_school_by_uuid(
        db: AsyncSession,
        school_uuid: uuid.UUID,
        school_data: SchoolUpdate,
        current_user: User
    ) -> SchoolResponse:
        """Update school by UUID."""
        
        # First, get the school by UUID
        query = select(School).filter(School.uuid == school_uuid, School.is_active == True)
        result = await db.execute(query)
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_school(db, current_user, school.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Continue with the same logic as update_school but use the found school
        update_data = school_data.model_dump(exclude_unset=True)
        
        # Validate block and organization if being updated
        if "block_id" in update_data:
            if not await ScopeFilterService.can_access_block(db, current_user, update_data["block_id"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid block or insufficient permissions"
                )
        
        if "organization_id" in update_data:
            if not await ScopeFilterService.can_access_organization(db, current_user, update_data["organization_id"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
        
        # Validate organization-block relationship if both are being updated
        if "organization_id" in update_data and "block_id" in update_data:
            block_query = select(Block).filter(Block.id == update_data["block_id"], Block.is_active == True)
            block_result = await db.execute(block_query)
            block = block_result.scalar_one_or_none()
            
            if not block or block.organization_id != update_data["organization_id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block must belong to the specified organization"
                )
        
        # Check for duplicate UDISE code if being updated
        if "udise_code" in update_data:
            existing_school = await db.execute(
                select(School).filter(
                    School.udise_code == update_data["udise_code"].upper(),
                    School.id != school.id,
                    School.is_active == True
                )
            )
            if existing_school.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="UDISE code already exists"
                )
            update_data["udise_code"] = update_data["udise_code"].upper()
        
        # Check for duplicate school name if being updated
        if "school_name" in update_data:
            block_id = update_data.get("block_id", school.block_id)
            existing_school = await db.execute(
                select(School).filter(
                    School.school_name == update_data["school_name"],
                    School.block_id == block_id,
                    School.id != school.id,
                    School.is_active == True
                )
            )
            if existing_school.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="School name already exists in this block"
                )
        
        boards_to_update = update_data.pop("boards", None)
        class_levels_to_update = update_data.pop("class_levels", None)
        block_uuid = update_data.pop("block_uuid", None)
        organization_uuid = update_data.pop("organization_uuid", None)
        
        for key, value in update_data.items():
            setattr(school, key, value)
        
        school.updated_by = current_user.id
        
        if block_uuid is not None:
            block_query = select(Block).filter(Block.uuid == block_uuid, Block.is_active == True)
            block_result = await db.execute(block_query)
            new_block = block_result.scalar_one_or_none()
            
            if not new_block:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Block not found"
                )
            
            if not await ScopeFilterService.can_access_block(db, current_user, new_block.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid block or insufficient permissions"
                )
            
            school.block_id = new_block.id
            school.organization_id = new_block.organization_id
        
        if organization_uuid is not None:
            org_query = select(Organization).filter(Organization.uuid == organization_uuid, Organization.is_active == True)
            org_result = await db.execute(org_query)
            new_organization = org_result.scalar_one_or_none()
            
            if not new_organization:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization not found"
                )
            
            if not await ScopeFilterService.can_access_organization(db, current_user, new_organization.id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization or insufficient permissions"
                )
            
            school.organization_id = new_organization.id
        
        if boards_to_update is not None or class_levels_to_update is not None:
            await db.execute(delete(SchoolBoard).filter(SchoolBoard.school_id == school.id))
            
            school_board_ids = await db.execute(select(SchoolBoard.id).filter(SchoolBoard.school_id == school.id))
            school_board_ids = [row[0] for row in school_board_ids.fetchall()]
            if school_board_ids:
                await db.execute(delete(SchoolBoardClass).filter(SchoolBoardClass.school_board_id.in_(school_board_ids)))
            
            if boards_to_update:
                board_query = select(Board).filter(Board.id.in_(boards_to_update))
                board_result = await db.execute(board_query)
                existing_boards = {board.id for board in board_result.scalars()}
                
                if len(existing_boards) != len(boards_to_update):
                    missing_boards = set(boards_to_update) - existing_boards
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid board IDs: {missing_boards}"
                    )
                
                for board_id in boards_to_update:
                    school_board = SchoolBoard(
                        school_id=school.id,
                        board_id=board_id,
                        created_by=current_user.id,
                        updated_by=current_user.id
                    )
                    db.add(school_board)
                    await db.flush()
                    
                    if class_levels_to_update:
                        for class_level in class_levels_to_update:
                            school_board_class = SchoolBoardClass(
                                school_board_id=school_board.id,
                                class_level=class_level,
                                created_by=current_user.id,
                                updated_by=current_user.id
                            )
                            db.add(school_board_class)
        
        await db.commit()
        await db.refresh(school)
        
        school_with_relationships = await db.execute(
            select(School)
            .options(
                selectinload(School.organization), 
                selectinload(School.block),
                selectinload(School.school_boards).selectinload(SchoolBoard.board),
                selectinload(School.state)
            )
            .filter(School.id == school.id)
        )
        school_with_relationships = school_with_relationships.scalar_one()
        
        # Use SchoolResponseHelper to build response data
        response_data = SchoolResponseHelper.build_response_data(school_with_relationships)
        return SchoolResponse(**response_data)

    @staticmethod
    async def delete_school_by_uuid(
        db: AsyncSession,
        school_uuid: uuid.UUID,
        current_user: User
    ):
        """Delete school by UUID (soft delete)."""
        
        # First, get the school by UUID
        query = select(School).filter(School.uuid == school_uuid, School.is_active == True)
        result = await db.execute(query)
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Use the integer ID for scope validation (internal operations)
        if not await ScopeFilterService.can_access_school(db, current_user, school.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Soft delete
        school.is_active = False
        school.updated_by = current_user.id
        
        await db.commit()
    
    @staticmethod
    async def get_school_codes(
        db: AsyncSession,
        current_user: User
    ):
        """Get simple list of schools with just uuid, school_name, and udise_code."""
        from app.schemas.organization import SchoolCodesListResponse, SchoolCodeResponse
        from app.services.response_helpers import SchoolResponseHelper
        
        # Build base query - only load essential fields
        query = select(School).filter(School.is_active == True)
        
        # Apply scope filtering
        query = await ScopeFilterService.filter_schools_query(db, current_user, query)
        
        # Sort by school name alphabetically
        query = query.order_by(School.school_name)
        
        # Execute query
        result = await db.execute(query)
        schools = result.scalars().all()
        
        # Build simple response data
        school_data = []
        for school in schools:
            school_dict = SchoolResponseHelper.build_simple_response_data(school)
            school_data.append(SchoolCodeResponse(**school_dict))
        
        return SchoolCodesListResponse(data=school_data)
    
    @staticmethod
    async def remove_boards_from_school(
        db: AsyncSession,
        school_uuid: uuid.UUID,
        board_ids: List[int],
        current_user: User
    ):
        """Remove specific boards from a school."""
        from app.models.organization import SchoolBoard
        from app.schemas.organization import RemoveBoardsResponse
        
        # Get school and validate access - use internal method to get database model
        school_query = select(School).filter(
            School.uuid == school_uuid,
            School.is_active == True
        )
        result = await db.execute(school_query)
        school = result.scalar_one_or_none()
        
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found"
            )
        
        # Validate user has access to this school (reuse existing scope validation)
        from app.services.scope_service import ScopeFilterService
        accessible_school_ids = await ScopeFilterService.get_accessible_school_ids(db, current_user)
        if school.id not in accessible_school_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="School not found or not accessible"
            )
        
        # Get current school boards with their classes
        current_boards_query = select(SchoolBoard).options(
            selectinload(SchoolBoard.school_board_classes)
        ).filter(
            SchoolBoard.school_id == school.id,
            SchoolBoard.is_active == True
        )
        result = await db.execute(current_boards_query)
        current_school_boards = result.scalars().all()
        
        current_board_ids = [sb.board_id for sb in current_school_boards]
        
        # Validate that boards to remove exist in the school
        invalid_board_ids = [bid for bid in board_ids if bid not in current_board_ids]
        if invalid_board_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Boards {invalid_board_ids} are not associated with this school"
            )
        
        # Check that we're not removing all boards (at least one must remain)
        remaining_board_ids = [bid for bid in current_board_ids if bid not in board_ids]
        if not remaining_board_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove all boards from school. At least one board must remain."
            )
        
        # Remove the specified boards (soft delete)
        for school_board in current_school_boards:
            if school_board.board_id in board_ids:
                school_board.is_active = False
                school_board.updated_by = current_user.id
                
                # Also soft delete all related school_board_classes
                for school_board_class in school_board.school_board_classes:
                    if school_board_class.is_active:
                        school_board_class.is_active = False
                        school_board_class.updated_by = current_user.id
        
        # Update school's updated_at timestamp
        school.updated_by = current_user.id
        
        await db.commit()
        
        return RemoveBoardsResponse(
            message=f"Successfully removed {len(board_ids)} board(s) from school",
            school_uuid=school_uuid,
            removed_board_ids=board_ids,
            remaining_board_ids=remaining_board_ids
        )