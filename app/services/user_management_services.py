from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc, func, and_, or_
from fastapi import HTTPException, status
from sqlalchemy.orm import joinedload
from typing import Optional, Dict, Any
import math

from app.models.user import User, Role
from app.models.organization import Organization, Block, School
from app.utils.get_user_role import get_user_role
from app.utils.auth import get_password_hash
from app.schemas.auth import UserCreate, UserUpdate, UserUpdateRequest
from app.services.scope_service import ScopeFilterService
from app.middleware.rbac import rbac_middleware, PermissionDeniedError, ScopeViolationError

async def list_users_service(
    db: AsyncSession, 
    current_user: User,
    page: int = 1, 
    per_page: int = 10,
    search: Optional[str] = None,
    role_code: Optional[str] = None,
    is_active: Optional[bool] = None,
    school_udise: Optional[str] = None
):
    """
    List users with hierarchical scope filtering and pagination.
    """
    # Build base query with all relationships
    query = (
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
    )
    
    # Apply scope filtering
    query = await ScopeFilterService.filter_users_query(db, current_user, query)
    
    # Exclude current user from the results
    query = query.filter(User.id != current_user.id)
    
    # Apply additional filters
    if search:
        search_filter = or_(
            User.username.ilike(f"%{search}%"),
            User.full_name.ilike(f"%{search}%"),
            User.email.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    if role_code:
        # Use the existing role relationship instead of adding another join
        query = query.filter(User.role.has(Role.role_code == role_code))
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if school_udise:
        # Filter users by school's UDISE+ code
        query = query.filter(User.school.has(School.udise_code == school_udise.strip()))
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    
    # Execute query
    result = await db.execute(query)
    users = result.unique().scalars().all()
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page) if total > 0 else 1
    
    return {
        "users": users,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "grandTotal": total
    }

async def count_active_users(db: AsyncSession, current_user: User):
    """Count active users within the current user's scope (excluding current user)."""
    query = select(func.count(User.id)).filter(User.is_active == True)
    query = await ScopeFilterService.filter_users_query(db, current_user, query)
    # Exclude current user from count
    query = query.filter(User.id != current_user.id)
    result = await db.execute(query)
    return result.scalar()

async def create_user_service(
    db: AsyncSession,
    user_data: UserCreate,
    current_user: User
):
    """
    Create a new user with hierarchical scope validation.
    """
    # Convert UUIDs to integer IDs first for scope validation
    organization_id = None
    block_id = None
    school_id = None
    
    if user_data.school_uuid:
        school_result = await db.execute(
            select(School).filter(School.uuid == user_data.school_uuid)
        )
        school = school_result.scalar_one_or_none()
        if school:
            school_id = school.id
            block_id = school.block_id
            organization_id = school.organization_id
    
    elif user_data.block_uuid:
        block_result = await db.execute(
            select(Block).filter(Block.uuid == user_data.block_uuid)
        )
        block = block_result.scalar_one_or_none()
        if block:
            block_id = block.id
            organization_id = block.organization_id
    
    elif user_data.organization_uuid:
        org_result = await db.execute(
            select(Organization).filter(Organization.uuid == user_data.organization_uuid)
        )
        org = org_result.scalar_one_or_none()
        if org:
            organization_id = org.id
    
    # Validate organizational assignment is within current user's scope
    if organization_id or block_id or school_id:
        await rbac_middleware.validate_hierarchical_scope(
            db=db,
            user=current_user,
            target_organization_id=organization_id,
            target_block_id=block_id,
            target_school_id=school_id
        )
    
    # Check if username already exists
    existing_user = await db.execute(
        select(User).filter(User.username == user_data.username)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = await db.execute(
            select(User).filter(User.email == user_data.email)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Validate role exists
    role_result = await db.execute(
        select(Role).filter(Role.role_code == user_data.role_code)
    )
    role = role_result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role code"
        )
    
    # Validate UUIDs exist (already converted to IDs above)
    if user_data.school_uuid and not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid school UUID"
        )
    
    if user_data.block_uuid and not block_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid block UUID"
        )
    
    if user_data.organization_uuid and not organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid organization UUID"
        )
    
    # Create new user
    new_user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        email=user_data.email,
        phone=user_data.phone,
        role_id=role.id,
        organization_id=organization_id,
        block_id=block_id,
        school_id=school_id,
        staff_id=user_data.staff_id,
        boards=user_data.boards,
        is_active=True,
        created_by=current_user.id
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    # Load relationships for response
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
        .filter(User.id == new_user.id)
    )
    
    return result.unique().scalar_one()

async def update_user_service(
    db: AsyncSession,
    user_id: int,
    new_password: str,
    current_user: User
):
    # Fetch target user
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Check role of current user
    role_obj = await get_user_role(db, current_user.role_id)
    is_admin = role_obj.role_code in ["super_admin", "admin", "admin_user"]

    # Only allow user to change their own password, or admin
    if not is_admin and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this password")

    # Update and save password
    target_user.hashed_password = get_password_hash(new_password)
    await db.commit()

    return {"message": f"Password updated successfully for user: {target_user.username}"}

async def get_user_by_id_service(user_id: int, db: AsyncSession, current_user: User) -> User:
    """Get user by ID with scope validation."""
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
        .filter(User.id == user_id)
    )
    user_obj = result.unique().scalar_one_or_none()

    if not user_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Validate user is within current user's scope
    await rbac_middleware.validate_hierarchical_scope(
        db=db,
        user=current_user,
        target_organization_id=user_obj.organization_id,
        target_block_id=user_obj.block_id,
        target_school_id=user_obj.school_id
    )

    return user_obj

async def get_user_by_uuid_service(user_uuid: str, db: AsyncSession, current_user: User) -> User:
    """Get user by UUID with scope validation."""
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
        .filter(User.uuid == user_uuid)
    )
    user_obj = result.unique().scalar_one_or_none()

    if not user_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Validate user is within current user's scope
    await rbac_middleware.validate_hierarchical_scope(
        db=db,
        user=current_user,
        target_organization_id=user_obj.organization_id,
        target_block_id=user_obj.block_id,
        target_school_id=user_obj.school_id
    )

    return user_obj

async def update_user_info_service(
    db: AsyncSession,
    user_id: int,
    user_data: UserUpdate,
    current_user: User
):
    """
    Update user information with scope validation.
    """
    # Fetch target user with scope validation
    target_user = await get_user_by_id_service(user_id, db, current_user)
    
    # Validate new organizational assignment is within current user's scope
    if (user_data.organization_id is not None or 
        user_data.block_id is not None or 
        user_data.school_id is not None):
        
        await rbac_middleware.validate_hierarchical_scope(
            db=db,
            user=current_user,
            target_organization_id=user_data.organization_id,
            target_block_id=user_data.block_id,
            target_school_id=user_data.school_id
        )
    
    # Check if username already exists (if being changed)
    if user_data.username and user_data.username != target_user.username:
        existing_user = await db.execute(
            select(User).filter(
                and_(User.username == user_data.username, User.id != user_id)
            )
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    # Check if email already exists (if being changed)
    if user_data.email and user_data.email != target_user.email:
        existing_email = await db.execute(
            select(User).filter(
                and_(User.email == user_data.email, User.id != user_id)
            )
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Validate role exists (if being changed)
    if user_data.role_code:
        role_result = await db.execute(
            select(Role).filter(Role.role_code == user_data.role_code)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role code"
            )
        target_user.role_id = role.id
    
    # Validate organizational hierarchy consistency
    new_org_id = user_data.organization_id if user_data.organization_id is not None else target_user.organization_id
    new_block_id = user_data.block_id if user_data.block_id is not None else target_user.block_id
    new_school_id = user_data.school_id if user_data.school_id is not None else target_user.school_id
    
    if new_school_id:
        school_result = await db.execute(
            select(School).filter(School.id == new_school_id)
        )
        school = school_result.scalar_one_or_none()
        if not school:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid school ID"
            )
        
        # Auto-assign block and organization from school
        new_block_id = school.block_id
        new_org_id = school.organization_id
    
    elif new_block_id:
        block_result = await db.execute(
            select(Block).filter(Block.id == new_block_id)
        )
        block = block_result.scalar_one_or_none()
        if not block:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid block ID"
            )
        
        # Auto-assign organization from block
        new_org_id = block.organization_id
    
    elif new_org_id:
        org_result = await db.execute(
            select(Organization).filter(Organization.id == new_org_id)
        )
        org = org_result.scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid organization ID"
            )
    
    # Update user fields
    if user_data.username is not None:
        target_user.username = user_data.username
    if user_data.full_name is not None:
        target_user.full_name = user_data.full_name
    if user_data.email is not None:
        target_user.email = user_data.email
    if user_data.phone is not None:
        target_user.phone = user_data.phone
    if user_data.is_active is not None:
        target_user.is_active = user_data.is_active
    
    # Update organizational assignments
    target_user.organization_id = new_org_id
    target_user.block_id = new_block_id
    target_user.school_id = new_school_id
    target_user.updated_by = current_user.id

    await db.commit()
    await db.refresh(target_user)
    
    # Load relationships for response
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
        .filter(User.id == target_user.id)
    )
    
    return result.unique().scalar_one()

async def delete_user_service(
    db: AsyncSession,
    user_id: int,
    current_user: User
):
    """
    Delete (deactivate) user with scope validation.
    """
    # Fetch target user with scope validation
    target_user = await get_user_by_id_service(user_id, db, current_user)
    
    # Prevent self-deletion
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete by deactivating
    target_user.is_active = False
    target_user.updated_by = current_user.id
    
    await db.commit()
    
    return {"message": f"User '{target_user.username}' has been deactivated successfully"}

async def update_user_password_by_uuid_service(
    db: AsyncSession,
    user_uuid: str,
    new_password: str,
    current_user: User
):
    """Update user password by UUID with scope validation."""
    # Fetch target user with scope validation
    target_user = await get_user_by_uuid_service(user_uuid, db, current_user)
    
    # Update password
    target_user.hashed_password = get_password_hash(new_password)
    target_user.updated_by = current_user.id
    
    await db.commit()
    
    return {"message": f"Password updated successfully for user: {target_user.username}"}

async def update_user_info_by_uuid_service(
    db: AsyncSession,
    user_uuid: str,
    user_data: UserUpdate,
    current_user: User
):
    """
    Update user information by UUID with scope validation.
    """
    # Fetch target user with scope validation
    target_user = await get_user_by_uuid_service(user_uuid, db, current_user)
    
    # Convert UUIDs to integer IDs and validate new organizational assignment is within current user's scope
    organization_id = None
    block_id = None
    school_id = None
    
    if user_data.organization_uuid is not None or user_data.block_uuid is not None or user_data.school_uuid is not None:
        if user_data.school_uuid:
            school_result = await db.execute(
                select(School).filter(School.uuid == user_data.school_uuid)
            )
            school = school_result.scalar_one_or_none()
            if not school:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid school UUID"
                )
            school_id = school.id
            block_id = school.block_id
            organization_id = school.organization_id
        
        elif user_data.block_uuid:
            block_result = await db.execute(
                select(Block).filter(Block.uuid == user_data.block_uuid)
            )
            block = block_result.scalar_one_or_none()
            if not block:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid block UUID"
                )
            block_id = block.id
            organization_id = block.organization_id
        
        elif user_data.organization_uuid:
            org_result = await db.execute(
                select(Organization).filter(Organization.uuid == user_data.organization_uuid)
            )
            org = org_result.scalar_one_or_none()
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid organization UUID"
                )
            organization_id = org.id
        
        await rbac_middleware.validate_hierarchical_scope(
            db=db,
            user=current_user,
            target_organization_id=organization_id,
            target_block_id=block_id,
            target_school_id=school_id
        )
    
    # Check if username already exists (if being changed)
    if user_data.username and user_data.username != target_user.username:
        existing_user = await db.execute(
            select(User).filter(
                and_(User.username == user_data.username, User.id != target_user.id)
            )
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    # Check if email already exists (if being changed)
    if user_data.email and user_data.email != target_user.email:
        existing_email = await db.execute(
            select(User).filter(
                and_(User.email == user_data.email, User.id != target_user.id)
            )
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Validate role exists (if being changed)
    if user_data.role_code:
        role_result = await db.execute(
            select(Role).filter(Role.role_code == user_data.role_code)
        )
        role = role_result.scalar_one_or_none()
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{user_data.role_code}' not found"
            )
        target_user.role_id = role.id
    
    # Update user fields
    update_data = user_data.dict(exclude_unset=True, exclude={'role_code', 'organization_uuid', 'block_uuid', 'school_uuid'})
    for field, value in update_data.items():
        if hasattr(target_user, field):
            setattr(target_user, field, value)
    
    # Update organizational fields with converted integer IDs
    if organization_id is not None:
        target_user.organization_id = organization_id
    if block_id is not None:
        target_user.block_id = block_id
    if school_id is not None:
        target_user.school_id = school_id
    
    target_user.updated_by = current_user.id
    
    await db.commit()
    
    # Return updated user with relationships
    result = await db.execute(
        select(User)
        .options(
            joinedload(User.role),
            joinedload(User.organization),
            joinedload(User.block),
            joinedload(User.school)
        )
        .filter(User.id == target_user.id)
    )
    
    return result.unique().scalar_one()

async def delete_user_by_uuid_service(
    db: AsyncSession,
    user_uuid: str,
    current_user: User
):
    """
    Delete (deactivate) user by UUID with scope validation.
    """
    # Fetch target user with scope validation
    target_user = await get_user_by_uuid_service(user_uuid, db, current_user)
    
    # Prevent self-deletion
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete by deactivating
    target_user.is_active = False
    target_user.updated_by = current_user.id
    
    await db.commit()
    
    return {"message": f"User '{target_user.username}' has been deactivated successfully"}

async def update_user_password_by_uuid_service(
    db: AsyncSession,
    user_uuid: str,
    new_password: str,
    current_user: User
):
    """Update user password by UUID with scope validation."""
    # Fetch target user with scope validation
    target_user = await get_user_by_uuid_service(user_uuid, db, current_user)
    
    # Update password
    target_user.hashed_password = get_password_hash(new_password)
    target_user.updated_by = current_user.id
    
    await db.commit()
    
    return {"message": f"Password updated successfully for user: {target_user.username}"}

