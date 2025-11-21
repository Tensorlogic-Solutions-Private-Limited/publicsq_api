"""
State Resolution Service for user-based state resolution and validation.

This service handles automatic state resolution for different user types and validates
state access permissions based on user roles and organizational hierarchy.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from app.models.user import User
from app.models.organization import Block
from app.models.master import State
from app.exceptions.state_exceptions import (
    InvalidStateError,
    MissingStateParameterError,
    BlockStateAssociationError,
    StateAccessDeniedError,
    StateResolutionError
)


class StateResolutionService:
    """Service for resolving and validating state access for users."""
    
    @staticmethod
    async def resolve_state_for_user(db: AsyncSession, user: User, explicit_state_id: Optional[int] = None) -> Optional[int]:
        """
        Resolve state_id based on user's role and block association.
        
        Args:
            db: Database session
            user: User object with loaded relationships
            explicit_state_id: Optional explicit state_id provided by user
            
        Returns:
            int: Resolved state_id
            
        Raises:
            HTTPException: If state resolution fails or validation errors occur
        """
        try:
            # Ensure user has role loaded
            if not user.role:
                raise StateResolutionError(
                    user_id=user.id,
                    resolution_type="role_not_found"
                )
            
            role_code = user.role.role_code
            
            # For super_admin, admin, and admin_user roles: state_id is optional
            if role_code in ["super_admin", "admin", "admin_user"]:
                if explicit_state_id is not None:
                    # Validate the provided state_id exists if one is provided
                    await StateResolutionService._validate_state_exists(db, explicit_state_id)
                    return explicit_state_id
                else:
                    # No state_id provided - no state filtering
                    return None
            
            # For block_admin and teacher roles: use their block's state_id
            elif role_code in ["block_admin", "teacher"]:
                if explicit_state_id is not None:
                    # If explicit state_id is provided, validate it matches user's block state
                    user_state_id = await StateResolutionService._get_user_block_state_id(db, user)
                    if user_state_id != explicit_state_id:
                        # Get state names for better error message
                        requested_state = await db.execute(
                            select(State).filter(State.id == explicit_state_id)
                        )
                        requested_state = requested_state.scalar_one_or_none()
                        
                        user_state = await db.execute(
                            select(State).filter(State.id == user_state_id)
                        )
                        user_state = user_state.scalar_one_or_none()
                        
                        raise StateAccessDeniedError(
                            user_id=user.id,
                            requested_state_id=explicit_state_id,
                            user_state_id=user_state_id,
                            requested_state_name=requested_state.state_name if requested_state else None,
                            user_state_name=user_state.state_name if user_state else None
                        )
                    return explicit_state_id
                else:
                    # Use user's block state_id
                    return await StateResolutionService._get_user_block_state_id(db, user)
            
            else:
                raise StateResolutionError(
                    user_id=user.id,
                    user_role=role_code,
                    resolution_type="unsupported_role"
                )
        
        except (InvalidStateError, MissingStateParameterError, BlockStateAssociationError, 
                StateAccessDeniedError, StateResolutionError):
            # Re-raise state exceptions as-is
            raise
        except SQLAlchemyError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred during state resolution. Please try again."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during state resolution. Please contact administrator."
            )
    
    @staticmethod
    async def _get_user_block_state_id(db: AsyncSession, user: User) -> int:
        """
        Get state_id from user's associated block.
        
        Args:
            db: Database session
            user: User object
            
        Returns:
            int: State ID from user's block
            
        Raises:
            HTTPException: If user has no block association or block has no state
        """
        try:
            # Check if user has block association
            if not user.block_id:
                raise BlockStateAssociationError(
                    error_type="no_block_association",
                    user_id=user.id
                )
            
            # Load block with state relationship if not already loaded
            if not user.block or not hasattr(user.block, 'state_id'):
                result = await db.execute(
                    select(Block)
                    .options(joinedload(Block.state))
                    .filter(Block.id == user.block_id)
                )
                block = result.unique().scalar_one_or_none()
                
                if not block:
                    raise BlockStateAssociationError(
                        error_type="block_not_found",
                        block_id=user.block_id,
                        user_id=user.id
                    )
            else:
                block = user.block
            
            # Check if block has state association
            if not block.state_id:
                raise BlockStateAssociationError(
                    error_type="no_state_association",
                    block_id=block.id,
                    block_name=block.block_name,
                    user_id=user.id
                )
            
            return block.state_id
        
        except BlockStateAssociationError:
            # Re-raise block state association exceptions as-is
            raise
        except SQLAlchemyError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while retrieving block state information. Please try again."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while retrieving block state information. Please contact administrator."
            )
    
    @staticmethod
    async def validate_state_access(db: AsyncSession, user: User, state_id: int) -> bool:
        """
        Validate if user can access the specified state based on their role and scope.
        
        Args:
            db: Database session
            user: User object with loaded relationships
            state_id: State ID to validate access for
            
        Returns:
            bool: True if user can access the state
            
        Raises:
            HTTPException: If access validation fails
        """
        try:
            # Ensure user has role loaded
            if not user.role:
                raise StateResolutionError(
                    user_id=user.id,
                    resolution_type="role_not_found"
                )
            
            role_code = user.role.role_code
            
            # Validate state exists first
            await StateResolutionService._validate_state_exists(db, state_id)
            
            # Super admin can access any state
            if role_code == "super_admin":
                return True
            
            # Admin and admin_user can access any state within their scope
            # (For now, we allow them to access any state since organizational scope 
            # filtering will be handled at the question level)
            if role_code in ["admin", "admin_user"]:
                return True
            
            # Block admin and teacher can only access their block's state
            if role_code in ["block_admin", "teacher"]:
                user_state_id = await StateResolutionService._get_user_block_state_id(db, user)
                if state_id != user_state_id:
                    # Get state names for better error message
                    state_result = await db.execute(
                        select(State).filter(State.id == state_id)
                    )
                    requested_state = state_result.scalar_one_or_none()
                    
                    user_state_result = await db.execute(
                        select(State).filter(State.id == user_state_id)
                    )
                    user_state = user_state_result.scalar_one_or_none()
                    
                    raise StateAccessDeniedError(
                        user_id=user.id,
                        requested_state_id=state_id,
                        user_state_id=user_state_id,
                        requested_state_name=requested_state.state_name if requested_state else None,
                        user_state_name=user_state.state_name if user_state else None
                    )
                return True
            
            # Unknown role
            raise StateResolutionError(
                user_id=user.id,
                user_role=role_code,
                resolution_type="unsupported_role"
            )
        
        except (InvalidStateError, BlockStateAssociationError, StateAccessDeniedError, StateResolutionError):
            # Re-raise state exceptions as-is
            raise
        except SQLAlchemyError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred during state access validation. Please try again."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred during state access validation. Please contact administrator."
            )
    
    @staticmethod
    async def _validate_state_exists(db: AsyncSession, state_id: int) -> None:
        """
        Validate that a state_id exists in the state_master table.
        
        Args:
            db: Database session
            state_id: State ID to validate
            
        Raises:
            HTTPException: If state_id is invalid
        """
        try:
            result = await db.execute(
                select(State).filter(State.id == state_id)
            )
            state = result.scalar_one_or_none()
            
            if not state:
                raise InvalidStateError(state_id=state_id)
        
        except InvalidStateError:
            # Re-raise state exceptions as-is
            raise
        except SQLAlchemyError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error occurred while validating state. Please try again."
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred while validating state. Please contact administrator."
            )