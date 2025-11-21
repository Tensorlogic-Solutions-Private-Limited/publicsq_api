"""
User context service for loading organizational scope and user information.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.user import User, Role
from app.models.permission import Permission, RolePermission
from app.models.organization import Organization, Block, School
from app.middleware.rbac import UserContext, rbac_middleware


class UserContextService:
    """Service for managing user context and organizational scope."""
    
    @staticmethod
    async def get_user_context(db, user: User) -> UserContext:
        """Get complete user context with permissions and organizational scope."""
        return await rbac_middleware.load_user_context(db, user)
    
    @staticmethod
    async def get_user_permissions(db, user: User) -> List[str]:
        """Get list of permission codes for the user."""
        user_context = await rbac_middleware.load_user_context(db, user)
        return user_context.permissions
    
    @staticmethod
    async def get_user_organizational_scope(db, user: User) -> Dict[str, Any]:
        """Get user's organizational scope information."""
        user_context = await rbac_middleware.load_user_context(db, user)
        return user_context.organizational_scope
    
    @staticmethod
    async def get_user_role_info(db, user: User) -> Dict[str, Any]:
        """Get detailed role information for the user."""
        query = (
            select(User)
            .options(joinedload(User.role))
            .filter(User.id == user.id)
        )
        
        if hasattr(db, 'execute') and hasattr(db.execute, '__await__'):
            result = await db.execute(query)
        else:
            result = db.execute(query)
        full_user = result.scalar_one_or_none()
        
        if not full_user or not full_user.role:
            return {}
        
        return {
            "role_id": full_user.role.id,
            "role_code": full_user.role.role_code,
            "role_name": full_user.role.role_name,
            "created_at": full_user.role.created_at,
            "updated_at": full_user.role.updated_at
        }
    
    @staticmethod
    async def get_user_hierarchy_details(db, user: User) -> Dict[str, Any]:
        """Get detailed organizational hierarchy information for the user."""
        query = (
            select(User)
            .options(
                joinedload(User.organization),
                joinedload(User.block),
                joinedload(User.school)
            )
            .filter(User.id == user.id)
        )
        
        if hasattr(db, 'execute') and hasattr(db.execute, '__await__'):
            result = await db.execute(query)
        else:
            result = db.execute(query)
        full_user = result.scalar_one_or_none()
        
        if not full_user:
            return {}
        
        hierarchy_details = {
            "organization": None,
            "block": None,
            "school": None
        }
        
        if full_user.organization:
            hierarchy_details["organization"] = {
                "id": full_user.organization.id,
                "org_code": full_user.organization.org_code,
                "org_name": full_user.organization.org_name,
                "org_description": full_user.organization.org_description,
                "is_active": full_user.organization.is_active
            }
        
        if full_user.block:
            hierarchy_details["block"] = {
                "id": full_user.block.id,
                "block_code": full_user.block.block_code,
                "block_name": full_user.block.block_name,
                "block_description": full_user.block.block_description,
                "organization_id": full_user.block.organization_id,
                "is_active": full_user.block.is_active
            }
        
        if full_user.school:
            hierarchy_details["school"] = {
                "id": full_user.school.id,
                "udise_code": full_user.school.udise_code,
                "school_name": full_user.school.school_name,
                "school_description": full_user.school.school_description,
                "block_id": full_user.school.block_id,
                "organization_id": full_user.school.organization_id,
                "is_active": full_user.school.is_active
            }
        
        return hierarchy_details
    
    @staticmethod
    async def get_user_full_profile(db, user: User) -> Dict[str, Any]:
        """Get complete user profile including role, permissions, and hierarchy."""
        user_context = await rbac_middleware.load_user_context(db, user)
        role_info = await UserContextService.get_user_role_info(db, user)
        hierarchy_details = await UserContextService.get_user_hierarchy_details(db, user)
        
        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "phone": user.phone,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at
            },
            "role": role_info,
            "permissions": user_context.permissions,
            "organizational_scope": user_context.organizational_scope,
            "hierarchy_details": hierarchy_details
        }
    
    @staticmethod
    async def check_user_permission(db, user: User, permission_code: str) -> bool:
        """Check if user has a specific permission."""
        try:
            await rbac_middleware.check_permission(db, user, permission_code)
            return True
        except Exception:
            return False
    
    @staticmethod
    async def get_user_accessible_resources(db, user: User) -> Dict[str, List[int]]:
        """Get IDs of all resources accessible to the user."""
        from app.services.scope_service import ScopeFilterService
        
        return {
            "organization_ids": await ScopeFilterService.get_accessible_organization_ids(db, user),
            "block_ids": await ScopeFilterService.get_accessible_block_ids(db, user),
            "school_ids": await ScopeFilterService.get_accessible_school_ids(db, user)
        }
    
    @staticmethod
    async def validate_user_scope_access(
        db, 
        user: User, 
        organization_id: Optional[int] = None,
        block_id: Optional[int] = None,
        school_id: Optional[int] = None
    ) -> bool:
        """Validate if user can access the specified scope."""
        try:
            await rbac_middleware.validate_hierarchical_scope(
                db=db,
                user=user,
                target_organization_id=organization_id,
                target_block_id=block_id,
                target_school_id=school_id
            )
            return True
        except Exception:
            return False
    
    @staticmethod
    def clear_user_cache(user_id: int):
        """Clear cached user context."""
        rbac_middleware.clear_user_cache(user_id)
    
    @staticmethod
    async def refresh_user_context(db, user: User) -> UserContext:
        """Refresh user context by clearing cache and reloading."""
        rbac_middleware.clear_user_cache(user.id)
        return await rbac_middleware.load_user_context(db, user)