"""
Error handling middleware for consistent RBAC error responses.
"""
import logging
from typing import Dict, Any, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import traceback
import json

from app.exceptions.rbac_exceptions import (
    RBACException,
    PermissionDeniedError,
    ScopeViolationError,
    OwnershipViolationError,
    RoleNotFoundError,
    OrganizationalContextError,
    ResourceNotFoundError
)
from app.exceptions.state_exceptions import (
    StateException,
    InvalidStateError,
    MissingStateParameterError,
    BlockStateAssociationError,
    StateAccessDeniedError,
    DatabaseConstraintError,
    StateResolutionError
)
from app.utils.rbac_logger import rbac_logger


class RBACErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware to handle RBAC-related errors consistently."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = logging.getLogger("rbac.error_handler")
    
    async def dispatch(self, request: Request, call_next):
        """Process request and handle RBAC errors."""
        try:
            response = await call_next(request)
            return response
        
        except StateException as e:
            return await self._handle_state_exception(request, e)
        
        except RBACException as e:
            return await self._handle_rbac_exception(request, e)
        
        except HTTPException as e:
            # Let FastAPI handle its own HTTP exceptions
            raise e
        
        except Exception as e:
            # Handle unexpected errors
            return await self._handle_unexpected_error(request, e)
    
    async def _handle_rbac_exception(self, request: Request, exception: RBACException) -> JSONResponse:
        """Handle RBAC-specific exceptions."""
        
        # Extract user information from request if available
        user_id = getattr(request.state, 'user_id', None)
        
        # Log the error
        self._log_rbac_error(request, exception, user_id)
        
        # Determine HTTP status code and response based on exception type
        if isinstance(exception, PermissionDeniedError):
            return self._create_permission_denied_response(exception)
        
        elif isinstance(exception, ScopeViolationError):
            return self._create_scope_violation_response(exception)
        
        elif isinstance(exception, OwnershipViolationError):
            return self._create_ownership_violation_response(exception)
        
        elif isinstance(exception, ResourceNotFoundError):
            return self._create_resource_not_found_response(exception)
        
        elif isinstance(exception, RoleNotFoundError):
            return self._create_role_not_found_response(exception)
        
        elif isinstance(exception, OrganizationalContextError):
            return self._create_organizational_context_response(exception)
        
        else:
            # Generic RBAC error
            return self._create_generic_rbac_response(exception)
    
    async def _handle_state_exception(self, request: Request, exception: StateException) -> JSONResponse:
        """Handle state-specific exceptions."""
        
        # Extract user information from request if available
        user_id = getattr(request.state, 'user_id', None)
        
        # Log the error
        self._log_state_error(request, exception, user_id)
        
        # Determine HTTP status code and response based on exception type
        if isinstance(exception, InvalidStateError):
            return self._create_invalid_state_response(exception)
        
        elif isinstance(exception, MissingStateParameterError):
            return self._create_missing_state_parameter_response(exception)
        
        elif isinstance(exception, BlockStateAssociationError):
            return self._create_block_state_association_response(exception)
        
        elif isinstance(exception, StateAccessDeniedError):
            return self._create_state_access_denied_response(exception)
        
        elif isinstance(exception, DatabaseConstraintError):
            return self._create_database_constraint_response(exception)
        
        elif isinstance(exception, StateResolutionError):
            return self._create_state_resolution_response(exception)
        
        else:
            # Generic state error
            return self._create_generic_state_response(exception)
    
    def _create_permission_denied_response(self, exception: PermissionDeniedError) -> JSONResponse:
        """Create response for permission denied errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Permission Denied",
                "error_code": exception.error_code,
                "message": "You do not have permission to perform this action",
                "details": {
                    "permission_required": exception.permission,
                    "resource_type": exception.resource_type,
                    "action": exception.action
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_scope_violation_response(self, exception: ScopeViolationError) -> JSONResponse:
        """Create response for scope violation errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Access Denied",
                "error_code": exception.error_code,
                "message": "You do not have access to this resource within your organizational scope",
                "details": {
                    "violation_type": exception.violation_type,
                    "attempted_scope": exception.attempted_scope
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_ownership_violation_response(self, exception: OwnershipViolationError) -> JSONResponse:
        """Create response for ownership violation errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Ownership Violation",
                "error_code": exception.error_code,
                "message": "You can only perform this action on resources you own",
                "details": {
                    "resource_type": exception.resource_type,
                    "resource_id": exception.resource_id,
                    "action": exception.action
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_resource_not_found_response(self, exception: ResourceNotFoundError) -> JSONResponse:
        """Create response for resource not found errors."""
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "Resource Not Found",
                "error_code": exception.error_code,
                "message": "The requested resource was not found or is not accessible",
                "details": {
                    "resource_type": exception.resource_type,
                    "resource_id": exception.resource_id
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_role_not_found_response(self, exception: RoleNotFoundError) -> JSONResponse:
        """Create response for role not found errors."""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Invalid Role",
                "error_code": exception.error_code,
                "message": "Your user role is invalid or not found",
                "details": {
                    "user_id": exception.user_id,
                    "role_id": exception.role_id
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_organizational_context_response(self, exception: OrganizationalContextError) -> JSONResponse:
        """Create response for organizational context errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid Organizational Context",
                "error_code": exception.error_code,
                "message": "Your user account lacks required organizational context",
                "details": {
                    "required_context": exception.required_context
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_generic_rbac_response(self, exception: RBACException) -> JSONResponse:
        """Create response for generic RBAC errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "Access Control Error",
                "error_code": exception.error_code,
                "message": exception.message,
                "timestamp": self._get_timestamp()
            }
        )
    
    async def _handle_unexpected_error(self, request: Request, exception: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        
        # Log the unexpected error
        self.logger.error(
            f"Unexpected error in RBAC middleware: {str(exception)}\n"
            f"Request: {request.method} {request.url}\n"
            f"Traceback: {traceback.format_exc()}"
        )
        
        # Log security event for unexpected errors
        rbac_logger.log_security_event(
            event_type="unexpected_error",
            severity="high",
            description=f"Unexpected error in RBAC middleware: {str(exception)}",
            additional_data={
                "request_method": request.method,
                "request_url": str(request.url),
                "exception_type": type(exception).__name__
            }
        )
        
        # Return generic error response (don't expose internal details)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred while processing your request",
                "timestamp": self._get_timestamp()
            }
        )
    
    def _log_rbac_error(self, request: Request, exception: RBACException, user_id: Optional[int]):
        """Log RBAC error with context."""
        
        error_context = {
            "exception_type": type(exception).__name__,
            "error_code": exception.error_code,
            "message": exception.message,
            "details": exception.details,
            "request_method": request.method,
            "request_url": str(request.url),
            "user_id": user_id
        }
        
        self.logger.warning(f"RBAC error: {json.dumps(error_context)}")
        
        # Log specific error types with RBAC logger
        if isinstance(exception, PermissionDeniedError):
            rbac_logger.log_permission_check(
                user_id=exception.user_id,
                permission=exception.permission,
                granted=False,
                resource_id=exception.resource_id,
                resource_type=exception.resource_type,
                action=exception.action,
                reason="Permission denied by middleware"
            )
        
        elif isinstance(exception, ScopeViolationError):
            rbac_logger.log_scope_validation(
                user_id=exception.user_id,
                valid=False,
                user_scope=exception.user_scope,
                attempted_scope={"scope": exception.attempted_scope},
                violation_type=exception.violation_type,
                reason="Scope violation detected by middleware"
            )
        
        elif isinstance(exception, OwnershipViolationError):
            rbac_logger.log_ownership_check(
                user_id=exception.user_id,
                resource_id=exception.resource_id,
                resource_type=exception.resource_type,
                resource_owner_id=exception.resource_owner_id,
                action=exception.action,
                allowed=False,
                reason="Ownership violation detected by middleware"
            )
    
    def _create_invalid_state_response(self, exception: InvalidStateError) -> JSONResponse:
        """Create response for invalid state errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Invalid State",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "state_id": exception.state_id,
                    "additional_context": exception.additional_context
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_missing_state_parameter_response(self, exception: MissingStateParameterError) -> JSONResponse:
        """Create response for missing state parameter errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Missing Required Parameter",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "required_parameter": "state_id",
                    "user_role": exception.user_role
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_block_state_association_response(self, exception: BlockStateAssociationError) -> JSONResponse:
        """Create response for block-state association errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Block State Association Error",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "error_type": exception.error_type,
                    "block_id": exception.block_id,
                    "block_name": exception.block_name
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_state_access_denied_response(self, exception: StateAccessDeniedError) -> JSONResponse:
        """Create response for state access denied errors."""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "State Access Denied",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "requested_state_id": exception.requested_state_id,
                    "requested_state_name": exception.requested_state_name,
                    "user_state_id": exception.user_state_id,
                    "user_state_name": exception.user_state_name
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_database_constraint_response(self, exception: DatabaseConstraintError) -> JSONResponse:
        """Create response for database constraint errors."""
        status_code = status.HTTP_409_CONFLICT if exception.constraint_type == "unique" else status.HTTP_400_BAD_REQUEST
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": "Database Constraint Violation",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "constraint_type": exception.constraint_type,
                    "table_name": exception.table_name,
                    "operation": exception.operation
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_state_resolution_response(self, exception: StateResolutionError) -> JSONResponse:
        """Create response for state resolution errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "State Resolution Error",
                "error_code": exception.error_code,
                "message": exception.message,
                "details": {
                    "user_role": exception.user_role,
                    "resolution_type": exception.resolution_type
                },
                "timestamp": self._get_timestamp()
            }
        )
    
    def _create_generic_state_response(self, exception: StateException) -> JSONResponse:
        """Create response for generic state errors."""
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "State Error",
                "error_code": exception.error_code,
                "message": exception.message,
                "timestamp": self._get_timestamp()
            }
        )
    
    def _log_state_error(self, request: Request, exception: StateException, user_id: Optional[int]):
        """Log state error with context."""
        
        error_context = {
            "exception_type": type(exception).__name__,
            "error_code": exception.error_code,
            "message": exception.message,
            "details": exception.details,
            "request_method": request.method,
            "request_url": str(request.url),
            "user_id": user_id
        }
        
        self.logger.warning(f"State error: {json.dumps(error_context)}")
        
        # Log specific error types with RBAC logger for security tracking
        if isinstance(exception, StateAccessDeniedError):
            rbac_logger.log_authorization_failure(
                user_id=exception.user_id,
                endpoint=str(request.url.path),
                method=request.method,
                reason=f"State access denied: requested {exception.requested_state_id}, allowed {exception.user_state_id}"
            )
        
        elif isinstance(exception, InvalidStateError):
            rbac_logger.log_security_event(
                event_type="invalid_state_access",
                severity="medium",
                description=f"User attempted to access invalid state: {exception.state_id}",
                additional_data={
                    "state_id": exception.state_id,
                    "user_id": user_id,
                    "request_url": str(request.url)
                }
            )

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


class GlobalExceptionHandler:
    """Global exception handler for RBAC errors in FastAPI."""
    
    @staticmethod
    def setup_exception_handlers(app):
        """Setup global exception handlers for the FastAPI app."""
        
        @app.exception_handler(PermissionDeniedError)
        async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
            rbac_logger.log_authorization_failure(
                user_id=exc.user_id,
                endpoint=str(request.url.path),
                method=request.method,
                reason=f"Permission denied: {exc.permission}"
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Permission Denied",
                    "error_code": exc.error_code,
                    "message": "You do not have permission to perform this action",
                    "details": {
                        "permission_required": exc.permission,
                        "resource_type": exc.resource_type,
                        "action": exc.action
                    }
                }
            )
        
        @app.exception_handler(ScopeViolationError)
        async def scope_violation_handler(request: Request, exc: ScopeViolationError):
            rbac_logger.log_authorization_failure(
                user_id=exc.user_id,
                endpoint=str(request.url.path),
                method=request.method,
                reason=f"Scope violation: {exc.attempted_scope}"
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "Access Denied",
                    "error_code": exc.error_code,
                    "message": "You do not have access to this resource within your organizational scope",
                    "details": {
                        "violation_type": exc.violation_type,
                        "attempted_scope": exc.attempted_scope
                    }
                }
            )
        
        @app.exception_handler(ResourceNotFoundError)
        async def resource_not_found_handler(request: Request, exc: ResourceNotFoundError):
            rbac_logger.log_authorization_failure(
                user_id=exc.user_id,
                endpoint=str(request.url.path),
                method=request.method,
                reason=f"Resource not found: {exc.resource_type} {exc.resource_id}"
            )
            
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "error": "Resource Not Found",
                    "error_code": exc.error_code,
                    "message": "The requested resource was not found or is not accessible",
                    "details": {
                        "resource_type": exc.resource_type,
                        "resource_id": exc.resource_id
                    }
                }
            )
        
        @app.exception_handler(RoleNotFoundError)
        async def role_not_found_handler(request: Request, exc: RoleNotFoundError):
            rbac_logger.log_authentication_failure(
                reason=f"Invalid role for user {exc.user_id}",
                additional_data={"role_id": exc.role_id}
            )
            
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Invalid Role",
                    "error_code": exc.error_code,
                    "message": "Your user role is invalid or not found"
                }
            )
        
        # State exception handlers
        @app.exception_handler(InvalidStateError)
        async def invalid_state_handler(request: Request, exc: InvalidStateError):
            rbac_logger.log_security_event(
                event_type="invalid_state_access",
                severity="medium",
                description=f"Invalid state access attempt: {exc.state_id}",
                additional_data={"state_id": exc.state_id, "request_url": str(request.url)}
            )
            
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Invalid State",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "state_id": exc.state_id
                    }
                }
            )
        
        @app.exception_handler(MissingStateParameterError)
        async def missing_state_parameter_handler(request: Request, exc: MissingStateParameterError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Missing Required Parameter",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "required_parameter": "state_id",
                        "user_role": exc.user_role
                    }
                }
            )
        
        @app.exception_handler(BlockStateAssociationError)
        async def block_state_association_handler(request: Request, exc: BlockStateAssociationError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Block State Association Error",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "error_type": exc.error_type,
                        "block_id": exc.block_id,
                        "block_name": exc.block_name
                    }
                }
            )
        
        @app.exception_handler(StateAccessDeniedError)
        async def state_access_denied_handler(request: Request, exc: StateAccessDeniedError):
            rbac_logger.log_authorization_failure(
                user_id=exc.user_id,
                endpoint=str(request.url.path),
                method=request.method,
                reason=f"State access denied: requested {exc.requested_state_id}, allowed {exc.user_state_id}"
            )
            
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": "State Access Denied",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "requested_state_id": exc.requested_state_id,
                        "requested_state_name": exc.requested_state_name,
                        "user_state_id": exc.user_state_id,
                        "user_state_name": exc.user_state_name
                    }
                }
            )
        
        @app.exception_handler(DatabaseConstraintError)
        async def database_constraint_handler(request: Request, exc: DatabaseConstraintError):
            status_code = status.HTTP_409_CONFLICT if exc.constraint_type == "unique" else status.HTTP_400_BAD_REQUEST
            
            return JSONResponse(
                status_code=status_code,
                content={
                    "error": "Database Constraint Violation",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "constraint_type": exc.constraint_type,
                        "table_name": exc.table_name,
                        "operation": exc.operation
                    }
                }
            )
        
        @app.exception_handler(StateResolutionError)
        async def state_resolution_handler(request: Request, exc: StateResolutionError):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "State Resolution Error",
                    "error_code": exc.error_code,
                    "message": exc.message,
                    "details": {
                        "user_role": exc.user_role,
                        "resolution_type": exc.resolution_type
                    }
                }
            )