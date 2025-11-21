"""
Exception classes for the application.
"""
from .rbac_exceptions import (
    RBACException,
    PermissionDeniedError,
    ScopeViolationError,
    OwnershipViolationError,
    RoleNotFoundError,
    OrganizationalContextError,
    ResourceNotFoundError
)

__all__ = [
    "RBACException",
    "PermissionDeniedError",
    "ScopeViolationError",
    "OwnershipViolationError",
    "RoleNotFoundError",
    "OrganizationalContextError",
    "ResourceNotFoundError"
]