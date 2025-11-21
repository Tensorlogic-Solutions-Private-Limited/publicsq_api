"""
Custom exception classes for RBAC system.
"""
from typing import Optional, Dict, Any


class RBACException(Exception):
    """Base exception class for RBAC-related errors."""
    
    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class PermissionDeniedError(RBACException):
    """Exception raised when user lacks required permissions."""
    
    def __init__(
        self, 
        user_id: int, 
        permission: str, 
        resource_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None
    ):
        self.user_id = user_id
        self.permission = permission
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.action = action
        
        details = {
            "user_id": user_id,
            "permission": permission,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "action": action
        }
        
        message = f"User {user_id} lacks permission '{permission}'"
        if resource_type and action:
            message += f" to {action} {resource_type}"
        if resource_id:
            message += f" (resource ID: {resource_id})"
        
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            details=details
        )


class ScopeViolationError(RBACException):
    """Exception raised when user attempts to access outside their scope."""
    
    def __init__(
        self, 
        user_id: int, 
        attempted_scope: str,
        user_scope: Optional[Dict[str, Any]] = None,
        violation_type: str = "hierarchical"
    ):
        self.user_id = user_id
        self.attempted_scope = attempted_scope
        self.user_scope = user_scope or {}
        self.violation_type = violation_type
        
        details = {
            "user_id": user_id,
            "attempted_scope": attempted_scope,
            "user_scope": user_scope,
            "violation_type": violation_type
        }
        
        message = f"User {user_id} attempted to access outside their {violation_type} scope: {attempted_scope}"
        
        super().__init__(
            message=message,
            error_code="SCOPE_VIOLATION",
            details=details
        )


class OwnershipViolationError(RBACException):
    """Exception raised when user attempts to access resource they don't own."""
    
    def __init__(
        self, 
        user_id: int, 
        resource_id: int,
        resource_type: str,
        resource_owner_id: int,
        action: str
    ):
        self.user_id = user_id
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.resource_owner_id = resource_owner_id
        self.action = action
        
        details = {
            "user_id": user_id,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "resource_owner_id": resource_owner_id,
            "action": action
        }
        
        message = f"User {user_id} cannot {action} {resource_type} {resource_id} owned by user {resource_owner_id}"
        
        super().__init__(
            message=message,
            error_code="OWNERSHIP_VIOLATION",
            details=details
        )


class RoleNotFoundError(RBACException):
    """Exception raised when user role is not found or invalid."""
    
    def __init__(self, user_id: int, role_id: Optional[int] = None):
        self.user_id = user_id
        self.role_id = role_id
        
        details = {
            "user_id": user_id,
            "role_id": role_id
        }
        
        message = f"User {user_id} has invalid or missing role"
        if role_id:
            message += f" (role ID: {role_id})"
        
        super().__init__(
            message=message,
            error_code="ROLE_NOT_FOUND",
            details=details
        )


class OrganizationalContextError(RBACException):
    """Exception raised when user lacks proper organizational context."""
    
    def __init__(
        self, 
        user_id: int, 
        required_context: str,
        user_context: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.required_context = required_context
        self.user_context = user_context or {}
        
        details = {
            "user_id": user_id,
            "required_context": required_context,
            "user_context": user_context
        }
        
        message = f"User {user_id} lacks required organizational context: {required_context}"
        
        super().__init__(
            message=message,
            error_code="ORGANIZATIONAL_CONTEXT_ERROR",
            details=details
        )


class ResourceNotFoundError(RBACException):
    """Exception raised when requested resource is not found in user's scope."""
    
    def __init__(
        self, 
        user_id: int, 
        resource_type: str,
        resource_id: int,
        scope_filter: Optional[Dict[str, Any]] = None
    ):
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.scope_filter = scope_filter or {}
        
        details = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "scope_filter": scope_filter
        }
        
        message = f"{resource_type} {resource_id} not found in user {user_id}'s accessible scope"
        
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            details=details
        )