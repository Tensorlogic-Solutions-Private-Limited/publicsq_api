"""
Subject service layer for business logic operations.

This module contains the core business logic for subject management,
including creation, validation, and code generation.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status

from app.models.master import Subject, Medium
from app.schemas.subjects import SubjectCreateRequest
from app.services.response_helpers import SubjectResponseHelper


class SubjectService:
    """Service class for subject operations."""
    
    @staticmethod
    async def create_subject(
        subject_data: SubjectCreateRequest,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Create a new subject with validation and code generation.
        
        Args:
            subject_data: Validated request data
            db: Database session
            user_id: ID of the authenticated user
            
        Returns:
            Dict containing created subject data
            
        Raises:
            HTTPException: For validation errors or conflicts
        """
        # Validate medium exists and get medium_id
        medium = await SubjectService.validate_medium_exists(subject_data.medium_code, db)
        
        # Check for duplicate subject
        existing_subject = await SubjectService.check_subject_duplicate(
            subject_data.subject_name,
            subject_data.standard,
            medium.id,
            db
        )
        
        if existing_subject:
            # Load the medium relationship for conflict response
            result = await db.execute(
                select(Subject)
                .options(joinedload(Subject.medium))
                .filter(Subject.id == existing_subject.id)
            )
            existing_subject_with_medium = result.scalar_one()
            
            # Return conflict response with existing subject details
            conflict_response = SubjectResponseHelper.build_conflict_response(existing_subject_with_medium)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=conflict_response
            )
        
        # Generate unique subject code
        subject_code = await SubjectService.generate_subject_code(db)
        
        # Create new subject
        new_subject = Subject(
            smt_subject_code=subject_code,
            smt_subject_name=subject_data.subject_name,
            smt_standard=subject_data.standard,
            smt_medium_id=medium.id,
            created_by=user_id,
            updated_by=user_id
        )
        
        try:
            db.add(new_subject)
            await db.commit()
            await db.refresh(new_subject)
            
            # Load the medium relationship for response building
            result = await db.execute(
                select(Subject)
                .options(joinedload(Subject.medium))
                .filter(Subject.id == new_subject.id)
            )
            subject_with_medium = result.scalar_one()
            
            return SubjectResponseHelper.build_create_response(subject_with_medium)
            
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create subject"
            )
    
    @staticmethod
    async def validate_medium_exists(medium_code: str, db: AsyncSession) -> Medium:
        """
        Validate that the medium exists and return the medium object.
        
        Args:
            medium_code: Code of the medium to validate
            db: Database session
            
        Returns:
            Medium object if found
            
        Raises:
            HTTPException: If medium not found
        """
        result = await db.execute(
            select(Medium).filter(Medium.mmt_medium_code == medium_code)
        )
        medium = result.scalar_one_or_none()
        
        if not medium:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medium not found with code: {medium_code}"
            )
        
        return medium
    
    @staticmethod
    async def check_subject_duplicate(
        subject_name: str,
        standard: str,
        medium_id: int,
        db: AsyncSession
    ) -> Optional[Subject]:
        """
        Check for existing subject with same name, standard, and medium.
        
        Args:
            subject_name: Name of the subject (case-insensitive matching)
            standard: Class/standard level
            medium_id: ID of the medium
            db: Database session
            
        Returns:
            Existing Subject if found, None otherwise
        """
        result = await db.execute(
            select(Subject).filter(
                func.lower(Subject.smt_subject_name) == func.lower(subject_name),
                Subject.smt_standard == standard,
                Subject.smt_medium_id == medium_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def generate_subject_code(db: AsyncSession) -> str:
        """
        Generate unique subject code using count + 3001 formula.
        
        Args:
            db: Database session
            
        Returns:
            Generated subject code as string
        """
        # Get total count of existing subjects
        result = await db.execute(
            select(func.count(Subject.id))
        )
        total_count = result.scalar()
        
        # Generate code using formula: count + 3001
        subject_code = str(total_count + 3001)
        
        return subject_code