"""
Permission validation service for RBAC system.
Handles permission checking, ownership validation, and hierarchical scope filtering.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.user import User, Role
from app.models.permission import Permission, RolePermission
from app.models.organization import Organization, Block, School
from app.models.master import Questions


class PermissionService:
    """Service class for handling permission validation and ownership restrictions."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def has_permission(self, user: User, permission_code: str, resource_id: Optional[int] = None) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            user: The user to check permissions for
            permission_code: The permission code to check (e.g., 'question_bank.edit')
            resource_id: Optional resource ID for ownership validation
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # Get the permission
        permission = self.db.query(Permission).filter(
            Permission.permission_code == permission_code
        ).first()
        
        if not permission:
            return False
        
        # Get the role permission mapping
        role_permission = self.db.query(RolePermission).filter(
            and_(
                RolePermission.role_id == user.role_id,
                RolePermission.permission_id == permission.id
            )
        ).first()
        
        if not role_permission:
            return False
        
        # If no ownership restriction, permission is granted
        if not role_permission.has_ownership_restriction:
            return True
        
        # If ownership restriction exists, validate ownership
        if resource_id is not None:
            return self._validate_ownership(user, permission.resource_type, resource_id)
        
        # If ownership restriction exists but no resource_id provided, deny access
        return False
    
    def _validate_ownership(self, user: User, resource_type: str, resource_id: int) -> bool:
        """
        Validate if user owns or has access to a specific resource.
        
        Args:
            user: The user to check ownership for
            resource_type: Type of resource (e.g., 'question_bank')
            resource_id: ID of the resource
            
        Returns:
            bool: True if user owns the resource, False otherwise
        """
        if resource_type == 'question_bank':
            return self._validate_question_ownership(user, resource_id)
        
        # Add other resource type validations as needed
        return False
    
    def _validate_question_ownership(self, user: User, question_id: int) -> bool:
        """
        Validate if user owns a specific question.
        For School Admin role, they can only edit/delete questions they created.
        
        Args:
            user: The user to check ownership for
            question_id: ID of the question
            
        Returns:
            bool: True if user owns the question, False otherwise
        """
        question = self.db.query(Questions).filter(Questions.id == question_id).first()
        
        if not question:
            return False
        
        # Check if the question was created by this user
        return question.created_by == user.id
    
    def get_user_permissions(self, user: User) -> List[str]:
        """
        Get all permission codes for a user.
        
        Args:
            user: The user to get permissions for
            
        Returns:
            List[str]: List of permission codes
        """
        permissions = self.db.query(Permission.permission_code).join(
            RolePermission, Permission.id == RolePermission.permission_id
        ).filter(
            RolePermission.role_id == user.role_id
        ).all()
        
        return [perm[0] for perm in permissions]
    
    def get_hierarchical_scope_filter(self, user: User, query, model_class):
        """
        Apply hierarchical scope filtering to a query based on user's organizational position.
        
        Args:
            user: The user to apply scope filtering for
            query: SQLAlchemy query object
            model_class: The model class being queried
            
        Returns:
            Filtered query object
        """
        # Super Admin has access to everything
        if user.role.role_code == 'super_admin':
            return query
        
        # Admin and Admin-User have organization-level access
        if user.role.role_code in ['admin', 'admin_user']:
            if hasattr(model_class, 'organization_id') and user.organization_id:
                return query.filter(model_class.organization_id == user.organization_id)
        
        # Block Admin has block-level access
        elif user.role.role_code == 'block_admin':
            if hasattr(model_class, 'block_id') and user.block_id:
                return query.filter(model_class.block_id == user.block_id)
        
        # Teacher has school-level access (School Admin role removed for MVP)
        elif user.role.role_code == 'teacher':
            if hasattr(model_class, 'school_id') and user.school_id:
                return query.filter(model_class.school_id == user.school_id)
        
        # If no specific scope applies, return empty result
        return query.filter(False)
    
    def can_access_organizational_level(self, user: User, target_org_id: Optional[int] = None, 
                                      target_block_id: Optional[int] = None, 
                                      target_school_id: Optional[int] = None) -> bool:
        """
        Check if user can access a specific organizational level.
        
        Args:
            user: The user to check access for
            target_org_id: Target organization ID
            target_block_id: Target block ID
            target_school_id: Target school ID
            
        Returns:
            bool: True if user can access the organizational level, False otherwise
        """
        # Super Admin can access everything
        if user.role.role_code == 'super_admin':
            return True
        
        # Admin and Admin-User can access their organization and below
        if user.role.role_code in ['admin', 'admin_user']:
            if target_org_id and user.organization_id:
                return target_org_id == user.organization_id
            return True  # Can access within their org
        
        # Block Admin can access their block and below
        if user.role.role_code == 'block_admin':
            if target_block_id and user.block_id:
                return target_block_id == user.block_id
            if target_org_id and user.organization_id:
                return target_org_id == user.organization_id
            return True  # Can access within their block
        
        # Teacher can access their school only
        if user.role.role_code == 'teacher':
            if target_school_id and user.school_id:
                return target_school_id == user.school_id
            if target_block_id and user.block_id:
                return target_block_id == user.block_id
            if target_org_id and user.organization_id:
                return target_org_id == user.organization_id
            return True  # Can access within their school
        
        return False


class PermissionError(Exception):
    """Custom exception for permission-related errors."""
    
    def __init__(self, message: str, user_id: int, permission_code: str, resource_id: Optional[int] = None):
        self.message = message
        self.user_id = user_id
        self.permission_code = permission_code
        self.resource_id = resource_id
        super().__init__(self.message)


class OwnershipError(PermissionError):
    """Custom exception for ownership-related permission errors."""
    
    def __init__(self, user_id: int, resource_type: str, resource_id: int):
        message = f"User {user_id} does not own {resource_type} with ID {resource_id}"
        super().__init__(message, user_id, f"{resource_type}.ownership", resource_id)


class ScopeViolationError(Exception):
    """Custom exception for hierarchical scope violations."""
    
    def __init__(self, user_id: int, attempted_scope: str, user_scope: str):
        self.user_id = user_id
        self.attempted_scope = attempted_scope
        self.user_scope = user_scope
        message = f"User {user_id} attempted to access {attempted_scope} outside their scope: {user_scope}"
        super().__init__(message)