"""
Custom exception classes for state-related errors.
"""
from typing import Optional, Dict, Any
from app.exceptions.rbac_exceptions import RBACException


class StateException(RBACException):
    """Base exception class for state-related errors."""
    
    def __init__(self, message: str, error_code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, error_code, details)


class InvalidStateError(StateException):
    """Exception raised when an invalid state_id is provided."""
    
    def __init__(self, state_id: int, additional_context: Optional[str] = None):
        self.state_id = state_id
        self.additional_context = additional_context
        
        details = {
            "state_id": state_id,
            "additional_context": additional_context
        }
        
        message = f"Invalid state_id: {state_id}. State does not exist in the system."
        if additional_context:
            message += f" {additional_context}"
        
        super().__init__(
            message=message,
            error_code="INVALID_STATE_ID",
            details=details
        )


class MissingStateParameterError(StateException):
    """Exception raised when state_id parameter is required but not provided."""
    
    def __init__(self, user_role: str, user_id: Optional[int] = None):
        self.user_role = user_role
        self.user_id = user_id
        
        details = {
            "user_role": user_role,
            "user_id": user_id
        }
        
        message = f"state_id parameter is required for your user role ({user_role})"
        
        super().__init__(
            message=message,
            error_code="MISSING_STATE_PARAMETER",
            details=details
        )


class BlockStateAssociationError(StateException):
    """Exception raised when there are issues with block-state associations."""
    
    def __init__(
        self, 
        error_type: str,
        block_id: Optional[int] = None,
        block_name: Optional[str] = None,
        user_id: Optional[int] = None,
        additional_context: Optional[str] = None
    ):
        self.error_type = error_type
        self.block_id = block_id
        self.block_name = block_name
        self.user_id = user_id
        self.additional_context = additional_context
        
        details = {
            "error_type": error_type,
            "block_id": block_id,
            "block_name": block_name,
            "user_id": user_id,
            "additional_context": additional_context
        }
        
        if error_type == "no_block_association":
            message = "No block associated with your account. Please contact administrator to assign you to a block."
        elif error_type == "block_not_found":
            message = f"Block with ID {block_id} not found for your account. Please contact administrator."
        elif error_type == "no_state_association":
            block_ref = f"'{block_name}'" if block_name else f"ID {block_id}"
            message = f"No state associated with your block {block_ref}. Please contact administrator to assign a state to your block."
        else:
            message = f"Block-state association error: {error_type}"
        
        if additional_context:
            message += f" {additional_context}"
        
        super().__init__(
            message=message,
            error_code="BLOCK_STATE_ASSOCIATION_ERROR",
            details=details
        )


class StateAccessDeniedError(StateException):
    """Exception raised when user tries to access a state they don't have permission for."""
    
    def __init__(
        self,
        user_id: int,
        requested_state_id: int,
        user_state_id: Optional[int] = None,
        requested_state_name: Optional[str] = None,
        user_state_name: Optional[str] = None
    ):
        self.user_id = user_id
        self.requested_state_id = requested_state_id
        self.user_state_id = user_state_id
        self.requested_state_name = requested_state_name
        self.user_state_name = user_state_name
        
        details = {
            "user_id": user_id,
            "requested_state_id": requested_state_id,
            "user_state_id": user_state_id,
            "requested_state_name": requested_state_name,
            "user_state_name": user_state_name
        }
        
        requested_state_ref = requested_state_name or f"ID {requested_state_id}"
        user_state_ref = user_state_name or f"ID {user_state_id}" if user_state_id else "unknown"
        
        message = f"Access denied. You can only access questions from your block's state ({user_state_ref}). Requested state: {requested_state_ref}"
        
        super().__init__(
            message=message,
            error_code="STATE_ACCESS_DENIED",
            details=details
        )


class DatabaseConstraintError(StateException):
    """Exception raised when database constraints are violated."""
    
    def __init__(
        self,
        constraint_type: str,
        table_name: Optional[str] = None,
        constraint_name: Optional[str] = None,
        operation: Optional[str] = None,
        additional_context: Optional[str] = None
    ):
        self.constraint_type = constraint_type
        self.table_name = table_name
        self.constraint_name = constraint_name
        self.operation = operation
        self.additional_context = additional_context
        
        details = {
            "constraint_type": constraint_type,
            "table_name": table_name,
            "constraint_name": constraint_name,
            "operation": operation,
            "additional_context": additional_context
        }
        
        if constraint_type == "foreign_key":
            if table_name == "blocks" and "state_id" in (constraint_name or ""):
                message = "Invalid state reference. The specified state does not exist or has been deleted."
            else:
                message = "Invalid reference. The specified resource does not exist or has been deleted."
        elif constraint_type == "not_null":
            if table_name == "blocks" and "state_id" in (constraint_name or ""):
                message = "State ID is required and cannot be null."
            else:
                message = "Required field cannot be null."
        elif constraint_type == "unique":
            message = "Duplicate value. This record already exists."
        elif constraint_type == "check":
            message = "Data validation failed. Please check your input values."
        else:
            message = f"Database constraint violation: {constraint_type}"
        
        if additional_context:
            message += f" {additional_context}"
        
        super().__init__(
            message=message,
            error_code="DATABASE_CONSTRAINT_ERROR",
            details=details
        )


class StateResolutionError(StateException):
    """Exception raised when state resolution fails."""
    
    def __init__(
        self,
        user_id: int,
        user_role: Optional[str] = None,
        resolution_type: Optional[str] = None,
        additional_context: Optional[str] = None
    ):
        self.user_id = user_id
        self.user_role = user_role
        self.resolution_type = resolution_type
        self.additional_context = additional_context
        
        details = {
            "user_id": user_id,
            "user_role": user_role,
            "resolution_type": resolution_type,
            "additional_context": additional_context
        }
        
        if resolution_type == "unsupported_role":
            message = f"Unsupported user role: {user_role}. Please contact administrator."
        elif resolution_type == "role_not_found":
            message = "User role not found. Please contact administrator."
        else:
            message = "State resolution failed. Please contact administrator."
        
        if additional_context:
            message += f" {additional_context}"
        
        super().__init__(
            message=message,
            error_code="STATE_RESOLUTION_ERROR",
            details=details
        )