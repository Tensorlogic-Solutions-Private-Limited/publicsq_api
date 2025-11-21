"""
Permission decorators for API endpoints.
"""
from functools import wraps
from typing import Optional, Callable, Any
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User
from app.middleware.rbac import rbac_middleware
from app.exceptions.rbac_exceptions import (
    PermissionDeniedError,
    ScopeViolationError,
    OwnershipViolationError,
    ResourceNotFoundError
)
from app.utils.rbac_logger import rbac_logger


def require_permission(
    permission_code: str,
    resource_id_param: Optional[str] = None,
    resource_owner_param: Optional[str] = None
):
    """
    Decorator to require specific permission for an endpoint.
    
    Args:
        permission_code: The permission code required
        resource_id_param: Parameter name containing resource ID (for ownership checks)
        resource_owner_param: Parameter name containing resource owner ID
    
    Usage:
        @require_permission("question_bank.upload")
        async def upload_question(user: User = Depends(get_current_user)):
            pass
        
        @require_permission("question_bank.edit", resource_owner_param="question_owner_id")
        async def edit_question(question_id: int, question_owner_id: int, user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from kwargs
            user = None
            db = None
            
            # Find user and db in args and kwargs (injected by FastAPI)
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, User):
                    user = value
                elif hasattr(value, 'execute'):  # AsyncSession has execute method
                    db = value
            
            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies (user or db)"
                )
            
            # Extract resource parameters if specified
            resource_id = kwargs.get(resource_id_param) if resource_id_param else None
            resource_owner_id = kwargs.get(resource_owner_param) if resource_owner_param else None
            
            # Extract user_uuid for self-access checks (for user.view permission)
            target_user_uuid = kwargs.get('user_uuid') if permission_code == "user.view" else None
            
            try:
                # Extract resource type and action from permission code for better logging
                parts = permission_code.split('.')
                resource_type = parts[0] if len(parts) > 0 else None
                action = parts[1] if len(parts) > 1 else None
                
                # Check permission
                await rbac_middleware.check_permission(
                    db=db,
                    user=user,
                    permission_code=permission_code,
                    resource_id=resource_id,
                    resource_owner_id=resource_owner_id,
                    resource_type=resource_type,
                    action=action,
                    target_user_uuid=target_user_uuid
                )
                
                # Call the original function
                return await func(*args, **kwargs)
                
            except (PermissionDeniedError, ScopeViolationError, OwnershipViolationError) as e:
                # Let the error handling middleware handle these
                raise e
            except HTTPException as e:
                # Let HTTPExceptions (like 404, 400, etc.) pass through unchanged
                raise e
            except Exception as e:
                # Log unexpected errors in permission checking
                rbac_logger.log_security_event(
                    event_type="permission_check_error",
                    user_id=user.id,
                    severity="high",
                    description=f"Unexpected error during permission check: {str(e)}",
                    additional_data={
                        "permission_code": permission_code,
                        "function_name": func.__name__,
                        "exception_type": type(e).__name__
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An error occurred while checking permissions"
                )
        
        return wrapper
    return decorator


def scope_filter(filter_type: str = "hierarchical"):
    """
    Decorator to apply scope filtering to endpoint responses.
    
    Args:
        filter_type: Type of filtering to apply ("hierarchical", "ownership")
    
    Usage:
        @scope_filter("hierarchical")
        async def list_users(user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from kwargs
            user = None
            db = None
            
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, User):
                    user = value
                elif hasattr(value, 'execute'):
                    db = value
            
            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies (user or db)"
                )
            
            try:
                if filter_type == "hierarchical":
                    # Add scope filter to kwargs for the function to use
                    scope_filter_conditions = await rbac_middleware.get_hierarchical_scope_filter(db, user)
                    kwargs['scope_filter'] = scope_filter_conditions
                    
                    # Log scope filter application
                    rbac_logger.log_scope_validation(
                        user_id=user.id,
                        valid=True,
                        user_scope=scope_filter_conditions,
                        reason=f"Applied {filter_type} scope filter to {func.__name__}"
                    )
                
                # Call the original function
                return await func(*args, **kwargs)
                
            except ScopeViolationError as e:
                # Let the error handling middleware handle this
                raise e
            except HTTPException as e:
                # Let HTTPExceptions (like 404, 400, etc.) pass through unchanged
                raise e
            except Exception as e:
                # Log unexpected errors in scope filtering but don't mask the original error
                rbac_logger.log_security_event(
                    event_type="scope_filter_error",
                    user_id=user.id,
                    severity="medium",
                    description=f"Unexpected error during scope filtering: {str(e)}",
                    additional_data={
                        "filter_type": filter_type,
                        "function_name": func.__name__,
                        "exception_type": type(e).__name__
                    }
                )
                raise e
        
        return wrapper
    return decorator


def validate_scope(
    organization_param: Optional[str] = None,
    block_param: Optional[str] = None,
    school_param: Optional[str] = None
):
    """
    Decorator to validate hierarchical scope access.
    
    Args:
        organization_param: Parameter name containing organization ID
        block_param: Parameter name containing block ID
        school_param: Parameter name containing school ID
    
    Usage:
        @validate_scope(organization_param="org_id", school_param="school_id")
        async def create_user(org_id: int, school_id: int, user: User = Depends(get_current_user)):
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from kwargs
            user = None
            db = None
            
            for value in list(args) + list(kwargs.values()):
                if isinstance(value, User):
                    user = value
                elif hasattr(value, 'execute'):
                    db = value
            
            if not user or not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Missing required dependencies (user or db)"
                )
            
            # Extract scope parameters
            target_org_id = kwargs.get(organization_param) if organization_param else None
            target_block_id = kwargs.get(block_param) if block_param else None
            target_school_id = kwargs.get(school_param) if school_param else None
            
            # Handle nested parameters in Pydantic models
            if target_org_id is None and organization_param:
                # Try to extract from Pydantic model parameters (check both args and kwargs)
                for value in list(args) + list(kwargs.values()):
                    if hasattr(value, organization_param):
                        org_value = getattr(value, organization_param)
                        if org_value is not None:
                            # Check if it's already an integer ID or a UUID
                            if isinstance(org_value, int):
                                target_org_id = org_value
                            else:
                                # Convert UUID to integer ID
                                from sqlalchemy import select
                                from app.models.organization import Organization
                                result = await db.execute(select(Organization.id).where(Organization.uuid == org_value))
                                target_org_id = result.scalar_one_or_none()
                        break
                    # Also try common Pydantic model names
                    if hasattr(value, organization_param):
                        org_uuid = getattr(value, organization_param)
                        if org_uuid is not None:
                            # Convert UUID to integer ID
                            from sqlalchemy import select
                            from app.models.organization import Organization
                            result = await db.execute(select(Organization.id).where(Organization.uuid == org_uuid))
                            target_org_id = result.scalar_one_or_none()
                        break
            
            if target_block_id is None and block_param:
                # Try to extract from Pydantic model parameters (check both args and kwargs)
                for value in list(args) + list(kwargs.values()):
                    if hasattr(value, block_param):
                        block_value = getattr(value, block_param)
                        if block_value is not None:
                            # Check if it's already an integer ID or a UUID
                            if isinstance(block_value, int):
                                target_block_id = block_value
                            else:
                                # Convert UUID to integer ID
                                from sqlalchemy import select
                                from app.models.organization import Block
                                result = await db.execute(select(Block.id).where(Block.uuid == block_value))
                                target_block_id = result.scalar_one_or_none()
                        break
            
            if target_school_id is None and school_param:
                # Try to extract from Pydantic model parameters (check both args and kwargs)
                for value in list(args) + list(kwargs.values()):
                    if hasattr(value, school_param):
                        school_value = getattr(value, school_param)
                        if school_value is not None:
                            # Check if it's already an integer ID or a UUID
                            if isinstance(school_value, int):
                                target_school_id = school_value
                            else:
                                # Convert UUID to integer ID
                                from sqlalchemy import select
                                from app.models.organization import School
                                result = await db.execute(select(School.id).where(School.uuid == school_value))
                                target_school_id = result.scalar_one_or_none()
                        break
            
            try:
                # Validate scope BEFORE calling the function
                await rbac_middleware.validate_hierarchical_scope(
                    db=db,
                    user=user,
                    target_organization_id=target_org_id,
                    target_block_id=target_block_id,
                    target_school_id=target_school_id
                )
                
                # Log successful scope validation
                rbac_logger.log_scope_validation(
                    user_id=user.id,
                    valid=True,
                    attempted_scope={
                        "organization_id": target_org_id,
                        "block_id": target_block_id,
                        "school_id": target_school_id
                    },
                    reason=f"Scope validation passed for {func.__name__}"
                )
                
            except ScopeViolationError as e:
                # Let the error handling middleware handle this
                raise e
            except Exception as e:
                # Log unexpected errors in scope validation
                rbac_logger.log_security_event(
                    event_type="scope_validation_error",
                    user_id=user.id,
                    severity="high",
                    description=f"Unexpected error during scope validation: {str(e)}",
                    additional_data={
                        "target_org_id": target_org_id,
                        "target_block_id": target_block_id,
                        "target_school_id": target_school_id,
                        "function_name": func.__name__,
                        "exception_type": type(e).__name__
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An error occurred while validating scope"
                )
            
            # Call the original function AFTER scope validation
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator# Test reload
