"""
RBAC Middleware for hierarchical permission checking and scope filtering.
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.user import User, Role
from app.models.permission import Permission, RolePermission
from app.models.organization import Organization, Block, School
from app.exceptions.rbac_exceptions import (
    PermissionDeniedError,
    ScopeViolationError,
    OwnershipViolationError,
    RoleNotFoundError,
    OrganizationalContextError,
    ResourceNotFoundError
)
from app.utils.rbac_logger import rbac_logger


class UserContext:
    """User context containing organizational scope and permissions."""
    
    # Role hierarchy levels (higher number = higher privilege)
    ROLE_HIERARCHY = {
        "super_admin": 5,
        "admin": 4,
        "admin_user": 3,
        "block_admin": 2,
        "teacher": 1
    }
    
    def __init__(self, user: User, permissions: List[str], organizational_scope: Dict[str, Any]):
        self.user = user
        self.permissions = permissions
        self.organizational_scope = organizational_scope
        self.role_code = user.role.role_code if user.role else None
    
    def has_permission(self, permission_code: str) -> bool:
        """Check if user has a specific permission."""
        return permission_code in self.permissions
    
    def is_super_admin(self) -> bool:
        """Check if user is a super admin."""
        return self.role_code == "super_admin"
    
    def is_admin(self) -> bool:
        """Check if user is an organization-level admin."""
        return self.role_code == "admin"
    
    def is_admin_user(self) -> bool:
        """Check if user is an organization-level admin-user."""
        return self.role_code == "admin_user"
    
    def is_block_admin(self) -> bool:
        """Check if user is a block admin."""
        return self.role_code == "block_admin"
    
    def is_teacher(self) -> bool:
        """Check if user is a teacher."""
        return self.role_code == "teacher"
    
    def get_role_level(self) -> int:
        """Get the hierarchy level of the user's role."""
        return self.ROLE_HIERARCHY.get(self.role_code, 0)
    
    def can_see_role(self, target_role_code: str) -> bool:
        """
        Check if user can see users with the target role based on hierarchy rules.
        
        Rules:
        - Org Admins: Can see their role and below (admin, admin_user, block_admin, teacher)
        - Admin Users: Can see only below their role (block_admin, teacher)
        - Block Admins: Can see only below their role (teacher)
        - Teachers: Can see only below their role (none)
        """
        if not target_role_code:
            return False
            
        target_level = self.ROLE_HIERARCHY.get(target_role_code, 0)
        user_level = self.get_role_level()
        
        # Super admin can see everyone
        if self.is_super_admin():
            return True
            
        # Org Admins can see their role and below
        if self.is_admin():
            return target_level <= user_level
            
        # Admin Users and Block Admins can see only below their role
        if self.is_admin_user() or self.is_block_admin():
            return target_level < user_level
            
        # Teachers can see only below their role (none)
        if self.is_teacher():
            return target_level < user_level
            
        return False


class RBACMiddleware:
    """RBAC Middleware for permission validation and scope filtering."""
    
    def __init__(self):
        self.permission_cache: Dict[int, UserContext] = {}
    
    async def load_user_context(self, db, user: User) -> UserContext:
        """Load user context with permissions and organizational scope."""
        
        # Check cache first
        if user.id in self.permission_cache:
            rbac_logger.log_cache_operation("hit", user_id=user.id, cache_key=f"user_context_{user.id}", hit=True)
            return self.permission_cache[user.id]
        
        rbac_logger.log_cache_operation("miss", user_id=user.id, cache_key=f"user_context_{user.id}", hit=False)
        
        # Load user with all relationships
        query = (
            select(User)
            .options(
                joinedload(User.role).joinedload(Role.role_permissions).joinedload(RolePermission.permission),
                joinedload(User.organization),
                joinedload(User.block),
                joinedload(User.school)
            )
            .filter(User.id == user.id)
        )
        
        # Handle both async and sync sessions
        if hasattr(db, '__class__') and 'AsyncSession' in str(db.__class__):
            # Async session
            result = await db.execute(query)
            # Use unique() for joined eager loads against collections
            full_user = result.unique().scalar_one_or_none()
        else:
            # Sync session
            result = db.execute(query)
            # For sync sessions, we need to handle the result differently
            full_user = result.scalar_one_or_none()
        
        if not full_user:
            rbac_logger.log_authentication_failure(
                reason="User not found during context loading",
                user_identifier=str(user.id)
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Validate user has a role
        if not full_user.role:
            raise RoleNotFoundError(user_id=full_user.id, role_id=full_user.role_id)
        
        # Extract permissions
        permissions = []
        if full_user.role and full_user.role.role_permissions:
            permissions = [rp.permission.permission_code for rp in full_user.role.role_permissions]
        
        # Build organizational scope
        organizational_scope = {
            "organization_id": full_user.organization_id,
            "block_id": full_user.block_id,
            "school_id": full_user.school_id
        }
        
        # Create user context
        user_context = UserContext(full_user, permissions, organizational_scope)
        
        # Cache the context
        self.permission_cache[user.id] = user_context
        rbac_logger.log_cache_operation("store", user_id=user.id, cache_key=f"user_context_{user.id}")
        
        # Log user context loaded
        rbac_logger.log_user_context_loaded(
            user_id=user.id,
            role_code=user_context.role_code,
            permissions_count=len(permissions),
            organizational_scope=organizational_scope,
            cached=False
        )
        
        return user_context
    
    async def check_permission(
        self, 
        db, 
        user: User, 
        permission_code: str, 
        resource_id: Optional[int] = None,
        resource_owner_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        target_user_uuid: Optional[str] = None
    ) -> bool:
        """
        Check if user has required permission for a resource.
        
        Args:
            db: Database session
            user: User object
            permission_code: Permission code to check
            resource_id: Optional resource ID for ownership checks
            resource_owner_id: Optional resource owner ID for ownership restrictions
            resource_type: Optional resource type for logging
            action: Optional action for logging
            target_user_uuid: Optional target user UUID for self-access checks
        
        Returns:
            bool: True if permission granted, False otherwise
        
        Raises:
            PermissionDeniedError: If permission is denied
            OwnershipViolationError: If ownership restriction violated
        """
        
        user_context = await self.load_user_context(db, user)
        
        # Super admin has all permissions
        if user_context.is_super_admin():
            rbac_logger.log_permission_check(
                user_id=user.id,
                permission=permission_code,
                granted=True,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action,
                reason="Super admin access"
            )
            return True
        
        # Special case: Allow self-access for user.view permission
        # Check if user is trying to view their own profile
        if (permission_code == "user.view" and 
            target_user_uuid and 
            str(user.uuid) == str(target_user_uuid)):
            rbac_logger.log_permission_check(
                user_id=user.id,
                permission=permission_code,
                granted=True,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action,
                reason="Self-access granted for user.view"
            )
            return True
        
        # Check if user has the permission
        if not user_context.has_permission(permission_code):
            rbac_logger.log_permission_check(
                user_id=user.id,
                permission=permission_code,
                granted=False,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action,
                reason="Permission not assigned to role"
            )
            raise PermissionDeniedError(
                user_id=user.id,
                permission=permission_code,
                resource_id=resource_id,
                resource_type=resource_type,
                action=action
            )
        
        # Check ownership restrictions if applicable
        if resource_owner_id is not None:
            # Get the role permission to check ownership restrictions
            ownership_query = (
                select(RolePermission)
                .join(Permission)
                .filter(
                    RolePermission.role_id == user.role_id,
                    Permission.permission_code == permission_code
                )
            )
            
            # Handle both async and sync sessions
            if hasattr(db, '__class__') and 'AsyncSession' in str(db.__class__):
                role_permission_result = await db.execute(ownership_query)
                role_permission = role_permission_result.scalar_one_or_none()
            else:
                role_permission_result = db.execute(ownership_query)
                role_permission = role_permission_result.scalar_one_or_none()
            
            if role_permission and role_permission.has_ownership_restriction:
                if resource_owner_id != user.id:
                    rbac_logger.log_ownership_check(
                        user_id=user.id,
                        resource_id=resource_id or 0,
                        resource_type=resource_type or "unknown",
                        resource_owner_id=resource_owner_id,
                        action=action or "access",
                        allowed=False,
                        reason="Ownership restriction violated"
                    )
                    raise OwnershipViolationError(
                        user_id=user.id,
                        resource_id=resource_id or 0,
                        resource_type=resource_type or "unknown",
                        resource_owner_id=resource_owner_id,
                        action=action or "access"
                    )
                else:
                    rbac_logger.log_ownership_check(
                        user_id=user.id,
                        resource_id=resource_id or 0,
                        resource_type=resource_type or "unknown",
                        resource_owner_id=resource_owner_id,
                        action=action or "access",
                        allowed=True,
                        reason="User owns the resource"
                    )
        
        rbac_logger.log_permission_check(
            user_id=user.id,
            permission=permission_code,
            granted=True,
            resource_id=resource_id,
            resource_type=resource_type,
            action=action,
            reason="Permission granted"
        )
        return True
    
    async def get_hierarchical_scope_filter(self, db, user: User) -> Dict[str, Any]:
        """
        Get hierarchical scope filter for the user.
        
        Returns:
            Dict containing filter conditions based on user's organizational scope
        """
        
        user_context = await self.load_user_context(db, user)
        
        # Super admin sees everything
        if user_context.is_super_admin():
            return {}
        
        # Admin and Admin-User see their organization
        if user_context.is_admin() or user_context.is_admin_user():
            if user_context.organizational_scope["organization_id"]:
                return {"organization_id": user_context.organizational_scope["organization_id"]}
            return {}
        
        # Block admin sees their block
        if user_context.is_block_admin():
            if user_context.organizational_scope["block_id"]:
                return {"block_id": user_context.organizational_scope["block_id"]}
            return {}
        
        # Teachers see their organization (only org-level filtering for teachers)
        if user_context.is_teacher():
            if user_context.organizational_scope["organization_id"]:
                return {"organization_id": user_context.organizational_scope["organization_id"]}
            return {}
        
        # Default: no access
        return {"id": -1}  # This will match no records
    
    async def get_user_scope_filter_with_role_hierarchy(self, db, user: User) -> Dict[str, Any]:
        """
        Get hierarchical scope filter for users with role hierarchy considerations.
        
        Returns:
            Dict containing filter conditions based on user's organizational scope AND role hierarchy
        """
        
        user_context = await self.load_user_context(db, user)
        
        # Super admin sees everything
        if user_context.is_super_admin():
            return {}
        
        # Get organizational scope filter
        org_scope_filter = await self.get_hierarchical_scope_filter(db, user)
        
        # Add role hierarchy filter
        if org_scope_filter and "id" not in org_scope_filter:  # Not the "no access" case
            # Get allowed role codes based on hierarchy
            allowed_roles = []
            for role_code in user_context.ROLE_HIERARCHY.keys():
                if user_context.can_see_role(role_code):
                    allowed_roles.append(role_code)
            
            if allowed_roles:
                org_scope_filter["allowed_roles"] = allowed_roles
            else:
                # No roles allowed, return no access
                return {"id": -1}
        
        return org_scope_filter
    
    async def get_question_scope_filter(self, db, user: User) -> Dict[str, Any]:
        """
        Get scope filter specifically for question-related endpoints.
        All authorized users can see all questions - no restrictions.
        Only unauthorized users are blocked.
        
        Returns:
            Dict containing filter conditions (empty dict means no restrictions)
        """
        
        # All authorized users can see all questions - no filtering
        return {}
    async def validate_hierarchical_scope(
        self, 
        db, 
        user: User, 
        target_organization_id: Optional[int] = None,
        target_block_id: Optional[int] = None,
        target_school_id: Optional[int] = None
    ) -> bool:
        """
        Validate if user can access resources in the target scope.
        
        Args:
            db: Database session
            user: User object
            target_organization_id: Target organization ID
            target_block_id: Target block ID
            target_school_id: Target school ID
        
        Returns:
            bool: True if access allowed, False otherwise
        
        Raises:
            ScopeViolationError: If scope validation fails
        """
        
        user_context = await self.load_user_context(db, user)
        
        # Build attempted scope for logging
        attempted_scope = {}
        if target_organization_id:
            attempted_scope["organization_id"] = target_organization_id
        if target_block_id:
            attempted_scope["block_id"] = target_block_id
        if target_school_id:
            attempted_scope["school_id"] = target_school_id
        
        # Super admin can access everything
        if user_context.is_super_admin():
            rbac_logger.log_scope_validation(
                user_id=user.id,
                valid=True,
                user_scope=user_context.organizational_scope,
                attempted_scope=attempted_scope,
                reason="Super admin access"
            )
            return True
        
        # VidyaShakthi admin can access their organization
        if user_context.is_admin() or user_context.is_admin_user():
            user_org_id = user_context.organizational_scope["organization_id"]
            if target_organization_id and target_organization_id != user_org_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="organization",
                    reason=f"Organization mismatch: user_org={user_org_id}, target_org={target_organization_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"organization_id={target_organization_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="organization"
                )
            return True
        
        # Block admin can access their block
        if user_context.is_block_admin():
            user_block_id = user_context.organizational_scope["block_id"]
            user_org_id = user_context.organizational_scope["organization_id"]
            
            if target_block_id and target_block_id != user_block_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="block",
                    reason=f"Block mismatch: user_block={user_block_id}, target_block={target_block_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"block_id={target_block_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="block"
                )
            
            if target_organization_id and target_organization_id != user_org_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="organization",
                    reason=f"Organization mismatch: user_org={user_org_id}, target_org={target_organization_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"organization_id={target_organization_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="organization"
                )
            
            return True
        
        # Teachers can access their school (School Admin role removed for MVP)
        if user_context.is_teacher():
            user_school_id = user_context.organizational_scope["school_id"]
            user_block_id = user_context.organizational_scope["block_id"]
            user_org_id = user_context.organizational_scope["organization_id"]
            
            if target_school_id and target_school_id != user_school_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="school",
                    reason=f"School mismatch: user_school={user_school_id}, target_school={target_school_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"school_id={target_school_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="school"
                )
            
            if target_block_id and target_block_id != user_block_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="block",
                    reason=f"Block mismatch: user_block={user_block_id}, target_block={target_block_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"block_id={target_block_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="block"
                )
            
            if target_organization_id and target_organization_id != user_org_id:
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=False,
                    user_scope=user_context.organizational_scope,
                    attempted_scope=attempted_scope,
                    violation_type="organization",
                    reason=f"Organization mismatch: user_org={user_org_id}, target_org={target_organization_id}"
                )
                raise ScopeViolationError(
                    user_id=user.id,
                    attempted_scope=f"organization_id={target_organization_id}",
                    user_scope=user_context.organizational_scope,
                    violation_type="organization"
                )
            
            return True
        
        # Default: deny access
        rbac_logger.log_scope_validation(
            user_id=user.id,
            valid=False,
            user_scope=user_context.organizational_scope,
            attempted_scope=attempted_scope,
            violation_type="role",
            reason=f"No role match for scope validation: role={user_context.role_code}"
        )
        raise ScopeViolationError(
            user_id=user.id,
            attempted_scope="unknown_role",
            user_scope=user_context.organizational_scope,
            violation_type="role"
        )
    
    def clear_user_cache(self, user_id: int):
        """Clear cached user context."""
        if user_id in self.permission_cache:
            del self.permission_cache[user_id]
            rbac_logger.log_cache_operation("clear", user_id=user_id, cache_key=f"user_context_{user_id}")
        
    def clear_all_cache(self):
        """Clear all cached user contexts."""
        cache_size = len(self.permission_cache)
        self.permission_cache.clear()
        rbac_logger.log_cache_operation("clear_all", additional_data={"cleared_entries": cache_size})

    async def get_question_scope_filter(self, db, user: User) -> Dict[str, Any]:
        """
        Get scope filter specifically for question-related endpoints.
        ALL users can see all questions - no organizational filtering for question bank.
        """
        # No filtering for questions - everyone can see all questions
        return {}


# Global RBAC middleware instance
rbac_middleware = RBACMiddleware()