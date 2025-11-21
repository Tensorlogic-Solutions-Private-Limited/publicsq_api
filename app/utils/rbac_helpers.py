"""
Helper utilities for RBAC operations.
"""
from typing import Optional, Dict, Any, Type, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Query

from app.models.user import User
from app.middleware.rbac import rbac_middleware
from app.exceptions.rbac_exceptions import ResourceNotFoundError
from app.utils.rbac_logger import rbac_logger


async def get_resource_with_scope_check(
    db: AsyncSession,
    user: User,
    model_class: Type,
    resource_id: int,
    resource_type: str,
    additional_filters: Optional[Dict[str, Any]] = None
):
    """
    Get a resource with automatic scope checking.
    
    Args:
        db: Database session
        user: Current user
        model_class: SQLAlchemy model class
        resource_id: ID of the resource to fetch
        resource_type: Type of resource for logging
        additional_filters: Additional filters to apply
    
    Returns:
        The resource object if found and accessible
    
    Raises:
        ResourceNotFoundError: If resource not found in user's scope
    """
    
    # Get user's scope filter
    scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
    
    # Build query
    query = select(model_class).filter(model_class.id == resource_id)
    
    # Apply scope filters
    for field, value in scope_filter.items():
        if hasattr(model_class, field):
            query = query.filter(getattr(model_class, field) == value)
    
    # Apply additional filters
    if additional_filters:
        for field, value in additional_filters.items():
            if hasattr(model_class, field):
                query = query.filter(getattr(model_class, field) == value)
    
    # Execute query
    result = await db.execute(query)
    resource = result.scalar_one_or_none()
    
    if not resource:
        rbac_logger.log_security_event(
            event_type="resource_not_found",
            user_id=user.id,
            severity="medium",
            description=f"User attempted to access non-existent or out-of-scope resource",
            additional_data={
                "resource_type": resource_type,
                "resource_id": resource_id,
                "scope_filter": scope_filter,
                "additional_filters": additional_filters or {}
            }
        )
        
        raise ResourceNotFoundError(
            user_id=user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            scope_filter=scope_filter
        )
    
    return resource


async def apply_scope_to_query(
    db: AsyncSession,
    user: User,
    query: Union[Query, select],
    model_class: Type
) -> Union[Query, select]:
    """
    Apply user's hierarchical scope to a query.
    
    Args:
        db: Database session
        user: Current user
        query: SQLAlchemy query or select statement
        model_class: Model class being queried
    
    Returns:
        Modified query with scope filters applied
    """
    
    # Get user's scope filter
    scope_filter = await rbac_middleware.get_hierarchical_scope_filter(db, user)
    
    # Apply scope filters to query
    for field, value in scope_filter.items():
        if hasattr(model_class, field):
            query = query.filter(getattr(model_class, field) == value)
    
    rbac_logger.log_scope_validation(
        user_id=user.id,
        valid=True,
        user_scope=scope_filter,
        reason=f"Applied scope filter to {model_class.__name__} query"
    )
    
    return query


def log_resource_access(
    user_id: int,
    resource_type: str,
    resource_id: int,
    action: str,
    success: bool = True,
    additional_data: Optional[Dict[str, Any]] = None
):
    """
    Log resource access for audit trail.
    
    Args:
        user_id: ID of the user accessing the resource
        resource_type: Type of resource being accessed
        resource_id: ID of the resource
        action: Action being performed
        success: Whether the access was successful
        additional_data: Additional data to log
    """
    
    rbac_logger.log_audit_trail(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        success=success
    )
    
    if additional_data:
        rbac_logger.log_security_event(
            event_type="resource_access",
            user_id=user_id,
            severity="low",
            description=f"User {action} {resource_type} {resource_id}",
            additional_data=additional_data
        )


def validate_organizational_context(user: User, required_context: str) -> bool:
    """
    Validate that user has required organizational context.
    
    Args:
        user: User object
        required_context: Required context ("organization", "block", "school")
    
    Returns:
        bool: True if user has required context
    
    Raises:
        OrganizationalContextError: If user lacks required context
    """
    from app.exceptions.rbac_exceptions import OrganizationalContextError
    
    context_mapping = {
        "organization": user.organization_id,
        "block": user.block_id,
        "school": user.school_id
    }
    
    if required_context not in context_mapping:
        raise ValueError(f"Invalid required context: {required_context}")
    
    if not context_mapping[required_context]:
        rbac_logger.log_security_event(
            event_type="missing_organizational_context",
            user_id=user.id,
            severity="medium",
            description=f"User lacks required {required_context} context",
            additional_data={
                "required_context": required_context,
                "user_organization_id": user.organization_id,
                "user_block_id": user.block_id,
                "user_school_id": user.school_id
            }
        )
        
        raise OrganizationalContextError(
            user_id=user.id,
            required_context=required_context,
            user_context={
                "organization_id": user.organization_id,
                "block_id": user.block_id,
                "school_id": user.school_id
            }
        )
    
    return True


class RBACHelper:
    """Helper class for common RBAC operations."""
    
    @staticmethod
    async def check_resource_ownership(
        db: AsyncSession,
        user: User,
        model_class: Type,
        resource_id: int,
        owner_field: str = "created_by"
    ) -> bool:
        """
        Check if user owns a specific resource.
        
        Args:
            db: Database session
            user: Current user
            model_class: SQLAlchemy model class
            resource_id: ID of the resource
            owner_field: Field name that contains the owner ID
        
        Returns:
            bool: True if user owns the resource
        """
        
        query = select(model_class).filter(model_class.id == resource_id)
        result = await db.execute(query)
        resource = result.scalar_one_or_none()
        
        if not resource:
            return False
        
        owner_id = getattr(resource, owner_field, None)
        is_owner = owner_id == user.id
        
        rbac_logger.log_ownership_check(
            user_id=user.id,
            resource_id=resource_id,
            resource_type=model_class.__name__,
            resource_owner_id=owner_id or 0,
            action="ownership_check",
            allowed=is_owner,
            reason="Ownership verification"
        )
        
        return is_owner
    
    @staticmethod
    def log_permission_attempt(
        user_id: int,
        permission: str,
        resource_type: str,
        action: str,
        granted: bool,
        reason: str
    ):
        """Log a permission attempt for audit purposes."""
        
        rbac_logger.log_permission_check(
            user_id=user_id,
            permission=permission,
            granted=granted,
            resource_type=resource_type,
            action=action,
            reason=reason
        )
    
    @staticmethod
    def log_security_violation(
        user_id: int,
        violation_type: str,
        description: str,
        severity: str = "medium",
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """Log a security violation."""
        
        rbac_logger.log_security_event(
            event_type=violation_type,
            user_id=user_id,
            severity=severity,
            description=description,
            additional_data=additional_data or {}
        )