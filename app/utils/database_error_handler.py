"""
Database error handling utilities for consistent constraint error processing.
"""
import re
from typing import Optional, Dict, Any
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status

from app.exceptions.state_exceptions import DatabaseConstraintError


class DatabaseErrorHandler:
    """Utility class for handling database constraint errors."""
    
    @staticmethod
    def handle_integrity_error(
        error: IntegrityError,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle SQLAlchemy IntegrityError and raise appropriate custom exceptions.
        
        Args:
            error: The IntegrityError instance
            table_name: Name of the table where error occurred
            operation: Operation being performed (create, update, delete)
            context: Additional context information
            
        Raises:
            DatabaseConstraintError: For constraint violations
            HTTPException: For other database errors
        """
        error_msg = str(error.orig) if hasattr(error, 'orig') else str(error)
        error_msg_lower = error_msg.lower()
        
        # Extract constraint details from error message
        constraint_info = DatabaseErrorHandler._parse_constraint_error(error_msg)
        
        # Handle foreign key constraint violations
        if 'foreign key constraint' in error_msg_lower or constraint_info.get('type') == 'foreign_key':
            DatabaseErrorHandler._handle_foreign_key_error(
                error_msg, constraint_info, table_name, operation, context
            )
        
        # Handle unique constraint violations
        elif 'unique constraint' in error_msg_lower or constraint_info.get('type') == 'unique':
            DatabaseErrorHandler._handle_unique_constraint_error(
                error_msg, constraint_info, table_name, operation, context
            )
        
        # Handle not null constraint violations
        elif 'not null constraint' in error_msg_lower or constraint_info.get('type') == 'not_null':
            DatabaseErrorHandler._handle_not_null_error(
                error_msg, constraint_info, table_name, operation, context
            )
        
        # Handle check constraint violations
        elif 'check constraint' in error_msg_lower or constraint_info.get('type') == 'check':
            DatabaseErrorHandler._handle_check_constraint_error(
                error_msg, constraint_info, table_name, operation, context
            )
        
        # Generic integrity error
        else:
            raise DatabaseConstraintError(
                constraint_type="unknown",
                table_name=table_name,
                operation=operation,
                additional_context=f"Database integrity error: {error_msg}"
            )
    
    @staticmethod
    def _parse_constraint_error(error_msg: str) -> Dict[str, Any]:
        """
        Parse constraint error message to extract constraint details.
        
        Args:
            error_msg: Error message from database
            
        Returns:
            Dict containing parsed constraint information
        """
        constraint_info = {}
        
        # Common PostgreSQL constraint patterns
        patterns = {
            'foreign_key': [
                r'violates foreign key constraint "([^"]+)"',
                r'foreign key constraint "([^"]+)" fails',
                r'FOREIGN KEY constraint failed'
            ],
            'unique': [
                r'violates unique constraint "([^"]+)"',
                r'UNIQUE constraint failed: ([^,\s]+)',
                r'duplicate key value violates unique constraint "([^"]+)"'
            ],
            'not_null': [
                r'violates not-null constraint',
                r'NOT NULL constraint failed: ([^,\s]+)',
                r'null value in column "([^"]+)" violates not-null constraint'
            ],
            'check': [
                r'violates check constraint "([^"]+)"',
                r'CHECK constraint failed: ([^,\s]+)'
            ]
        }
        
        for constraint_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, error_msg, re.IGNORECASE)
                if match:
                    constraint_info['type'] = constraint_type
                    constraint_info['name'] = match.group(1) if match.groups() else None
                    break
            if constraint_info.get('type'):
                break
        
        # Extract table name if present
        table_match = re.search(r'on table "([^"]+)"', error_msg, re.IGNORECASE)
        if table_match:
            constraint_info['table'] = table_match.group(1)
        
        # Extract column name if present
        column_match = re.search(r'column "([^"]+)"', error_msg, re.IGNORECASE)
        if column_match:
            constraint_info['column'] = column_match.group(1)
        
        return constraint_info
    
    @staticmethod
    def _handle_foreign_key_error(
        error_msg: str,
        constraint_info: Dict[str, Any],
        table_name: Optional[str],
        operation: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> None:
        """Handle foreign key constraint violations."""
        constraint_name = constraint_info.get('name', '')
        table = constraint_info.get('table') or table_name
        
        # Specific handling for state-related foreign keys
        if 'state_id' in constraint_name or 'state_id' in error_msg:
            if 'blocks' in (table or ''):
                additional_context = "The specified state does not exist or has been deleted."
            else:
                additional_context = "Invalid state reference."
        
        # Specific handling for organization-related foreign keys
        elif 'organization_id' in constraint_name or 'organization_id' in error_msg:
            additional_context = "The specified organization does not exist or has been deleted."
        
        # Specific handling for block-related foreign keys
        elif 'block_id' in constraint_name or 'block_id' in error_msg:
            additional_context = "The specified block does not exist or has been deleted."
        
        # Generic foreign key error
        else:
            additional_context = "Invalid reference. The specified resource does not exist or has been deleted."
        
        raise DatabaseConstraintError(
            constraint_type="foreign_key",
            table_name=table,
            constraint_name=constraint_name,
            operation=operation,
            additional_context=additional_context
        )
    
    @staticmethod
    def _handle_unique_constraint_error(
        error_msg: str,
        constraint_info: Dict[str, Any],
        table_name: Optional[str],
        operation: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> None:
        """Handle unique constraint violations."""
        constraint_name = constraint_info.get('name', '')
        table = constraint_info.get('table') or table_name
        
        # Specific handling for common unique constraints
        if 'block_code' in constraint_name or 'block_code' in error_msg:
            additional_context = "A block with this code already exists."
        elif 'org_code' in constraint_name or 'org_code' in error_msg:
            additional_context = "An organization with this code already exists."
        elif 'udise_code' in constraint_name or 'udise_code' in error_msg:
            additional_context = "A school with this UDISE code already exists."
        elif 'uuid' in constraint_name or 'uuid' in error_msg:
            additional_context = "Duplicate UUID detected. Please try again."
        else:
            additional_context = "Duplicate value. This record already exists."
        
        raise DatabaseConstraintError(
            constraint_type="unique",
            table_name=table,
            constraint_name=constraint_name,
            operation=operation,
            additional_context=additional_context
        )
    
    @staticmethod
    def _handle_not_null_error(
        error_msg: str,
        constraint_info: Dict[str, Any],
        table_name: Optional[str],
        operation: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> None:
        """Handle not null constraint violations."""
        column = constraint_info.get('column', '')
        table = constraint_info.get('table') or table_name
        
        # Specific handling for common not null constraints
        if 'state_id' in column or 'state_id' in error_msg:
            additional_context = "State ID is required and cannot be null."
        elif 'organization_id' in column or 'organization_id' in error_msg:
            additional_context = "Organization ID is required and cannot be null."
        elif 'block_id' in column or 'block_id' in error_msg:
            additional_context = "Block ID is required and cannot be null."
        else:
            field_name = column.replace('_', ' ').title() if column else "Required field"
            additional_context = f"{field_name} is required and cannot be null."
        
        raise DatabaseConstraintError(
            constraint_type="not_null",
            table_name=table,
            constraint_name=column,
            operation=operation,
            additional_context=additional_context
        )
    
    @staticmethod
    def _handle_check_constraint_error(
        error_msg: str,
        constraint_info: Dict[str, Any],
        table_name: Optional[str],
        operation: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> None:
        """Handle check constraint violations."""
        constraint_name = constraint_info.get('name', '')
        table = constraint_info.get('table') or table_name
        
        additional_context = "Data validation failed. Please check your input values."
        
        raise DatabaseConstraintError(
            constraint_type="check",
            table_name=table,
            constraint_name=constraint_name,
            operation=operation,
            additional_context=additional_context
        )
    
    @staticmethod
    def handle_sqlalchemy_error(
        error: SQLAlchemyError,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Handle general SQLAlchemy errors.
        
        Args:
            error: The SQLAlchemyError instance
            table_name: Name of the table where error occurred
            operation: Operation being performed
            context: Additional context information
            
        Raises:
            DatabaseConstraintError: For constraint violations
            HTTPException: For other database errors
        """
        if isinstance(error, IntegrityError):
            DatabaseErrorHandler.handle_integrity_error(error, table_name, operation, context)
        else:
            # Generic SQLAlchemy error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error occurred during {operation or 'operation'}. Please try again."
            )
    
    @staticmethod
    def wrap_database_operation(
        operation_func,
        table_name: Optional[str] = None,
        operation: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Decorator to wrap database operations with error handling.
        
        Args:
            operation_func: The database operation function
            table_name: Name of the table being operated on
            operation: Type of operation (create, update, delete)
            context: Additional context information
            
        Returns:
            Wrapped function with error handling
        """
        async def wrapper(*args, **kwargs):
            try:
                return await operation_func(*args, **kwargs)
            except IntegrityError as e:
                DatabaseErrorHandler.handle_integrity_error(e, table_name, operation, context)
            except SQLAlchemyError as e:
                DatabaseErrorHandler.handle_sqlalchemy_error(e, table_name, operation, context)
        
        return wrapper