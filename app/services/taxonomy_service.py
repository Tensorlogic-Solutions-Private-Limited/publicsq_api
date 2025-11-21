"""
Taxonomy service layer for business logic operations.

This module contains the core business logic for taxonomy management,
including creation, validation, code generation, and scenario handling.
"""

from typing import Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status
from enum import Enum

from app.models.master import Taxonomy, Subject, Medium, Board, State
from app.schemas.taxonomy import TaxonomyCreateRequest


class TaxonomyCreationScenario(Enum):
    """Enumeration of taxonomy creation scenarios."""
    COMPLETE_HIERARCHY = 1  # New chapter, topic, subtopic
    NEW_TOPIC = 2          # Existing chapter, new topic and subtopic
    NEW_SUBTOPIC = 3       # Existing chapter and topic, new subtopic


class TaxonomyService:
    """Service class for taxonomy operations."""
    
    @staticmethod
    def validate_creation_scenario(request: TaxonomyCreateRequest) -> TaxonomyCreationScenario:
        """
        Validate and determine the taxonomy creation scenario.
        
        Updated to be consistent with bulk upload - topic_name and subtopic_name are optional.
        
        Args:
            request: Validated taxonomy creation request
            
        Returns:
            TaxonomyCreationScenario: The determined scenario
            
        Raises:
            HTTPException: For invalid field combinations
        """
        # Helper function to check if a field has a meaningful value
        def has_value(field):
            return field is not None and field.strip() != ""
        
        # Scenario 1: Complete new hierarchy
        # Required: chapter_name
        # Optional: topic_name, subtopic_name
        # Forbidden: chapter_code, topic_code, subtopic_code
        if (has_value(request.chapter_name) and 
            not has_value(request.chapter_code) and 
            not has_value(request.topic_code) and 
            not has_value(request.subtopic_code)):
            return TaxonomyCreationScenario.COMPLETE_HIERARCHY
        
        # Scenario 2: New topic in existing chapter
        # Required: chapter_code
        # Optional: topic_name, subtopic_name
        # Forbidden: topic_code, subtopic_code, chapter_name
        if (has_value(request.chapter_code) and 
            not has_value(request.topic_code) and 
            not has_value(request.subtopic_code) and 
            not has_value(request.chapter_name)):
            return TaxonomyCreationScenario.NEW_TOPIC
        
        # Scenario 3: New subtopic in existing topic
        # Required: chapter_code, topic_code
        # Optional: subtopic_name
        # Forbidden: subtopic_code, chapter_name, topic_name
        if (has_value(request.chapter_code) and 
            has_value(request.topic_code) and
            not has_value(request.subtopic_code) and 
            not has_value(request.chapter_name) and 
            not has_value(request.topic_name)):
            return TaxonomyCreationScenario.NEW_SUBTOPIC
        
        # If none of the scenarios match, raise validation error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid field combination for taxonomy creation",
                "message": "Request must follow one of the supported scenarios",
                "scenarios": {
                    "1": "Complete hierarchy: provide chapter_name (topic_name, subtopic_name optional)",
                    "2": "New topic: provide chapter_code (topic_name, subtopic_name optional)",
                    "3": "New subtopic: provide chapter_code + topic_code (subtopic_name optional)"
                },
                "provided_fields": {
                    "chapter_code": request.chapter_code,
                    "chapter_name": request.chapter_name,
                    "topic_code": request.topic_code,
                    "topic_name": request.topic_name,
                    "subtopic_code": request.subtopic_code,
                    "subtopic_name": request.subtopic_name
                }
            }
        )
    
    @staticmethod
    async def validate_scenario_requirements(
        request: TaxonomyCreateRequest,
        scenario: TaxonomyCreationScenario,
        db: AsyncSession
    ) -> None:
        """
        Validate that the request meets all requirements for the determined scenario.
        
        Updated to be consistent with bulk upload - topic_name and subtopic_name are optional.
        
        Args:
            request: Taxonomy creation request
            scenario: Determined creation scenario
            db: Database session
            
        Raises:
            HTTPException: For validation failures
        """
        # Helper function to check if a field has a meaningful value
        def has_value(field):
            return field is not None and field.strip() != ""
        
        if scenario == TaxonomyCreationScenario.COMPLETE_HIERARCHY:
            # Only chapter_name is required, topic_name and subtopic_name are optional
            if not has_value(request.chapter_name):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="chapter_name is required for complete hierarchy creation"
                )
        
        elif scenario == TaxonomyCreationScenario.NEW_TOPIC:
            # Only chapter_code is required, topic_name and subtopic_name are optional
            if not has_value(request.chapter_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="chapter_code is required for new topic creation"
                )
        
        elif scenario == TaxonomyCreationScenario.NEW_SUBTOPIC:
            # Both chapter_code and topic_code are required, subtopic_name is optional
            if not has_value(request.chapter_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="chapter_code is required for new subtopic creation"
                )
            if not has_value(request.topic_code):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="topic_code is required for new subtopic creation"
                )
    
    @staticmethod
    async def validate_master_data_context(
        request: TaxonomyCreateRequest,
        db: AsyncSession
    ) -> Tuple[Subject, Medium, Board, State]:
        """
        Validate that all master data references exist in the given context.
        
        Args:
            request: Taxonomy creation request
            db: Database session
            
        Returns:
            Tuple of (Subject, Medium, Board, State) objects
            
        Raises:
            HTTPException: If any master data is not found
        """
        # Validate subject exists
        subject_result = await db.execute(
            select(Subject).filter(Subject.smt_subject_code == request.subject_code)
        )
        subject = subject_result.scalar_one_or_none()
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject not found with code: {request.subject_code}"
            )
        
        # Validate medium exists
        medium_result = await db.execute(
            select(Medium).filter(Medium.mmt_medium_code == request.medium_code)
        )
        medium = medium_result.scalar_one_or_none()
        if not medium:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Medium not found with code: {request.medium_code}"
            )
        
        # Validate board exists
        board_result = await db.execute(
            select(Board).filter(Board.id == request.board_id)
        )
        board = board_result.scalar_one_or_none()
        if not board:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Board not found with ID: {request.board_id}"
            )
        
        # Validate state exists
        state_result = await db.execute(
            select(State).filter(State.id == request.state_id)
        )
        state = state_result.scalar_one_or_none()
        if not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"State not found with ID: {request.state_id}"
            )
        
        # Additional validation: ensure subject belongs to the specified medium and standard
        if subject.smt_medium_id != medium.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject {request.subject_code} does not belong to medium {request.medium_code}"
            )
        
        if subject.smt_standard != request.standard:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subject {request.subject_code} does not belong to standard {request.standard}"
            )
        
        return subject, medium, board, state  
  
    @staticmethod
    async def resolve_taxonomy_hierarchy(
        request: TaxonomyCreateRequest,
        scenario: TaxonomyCreationScenario,
        subject: Subject,
        medium: Medium,
        board: Board,
        state: State,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Resolve taxonomy hierarchy based on the creation scenario.
        
        For existing codes, validates their existence and retrieves names.
        For new entries, prepares data for code generation.
        
        Args:
            request: Taxonomy creation request
            scenario: Determined creation scenario
            subject: Validated subject object
            medium: Validated medium object
            board: Validated board object
            state: Validated state object
            db: Database session
            
        Returns:
            Dict containing resolved hierarchy data
            
        Raises:
            HTTPException: If existing codes are not found
        """
        # Helper function to safely get string value (consistent with bulk upload)
        def safe_string(value):
            return value.strip() if value else ""
        
        hierarchy_data = {
            "subject": subject,
            "medium": medium,
            "board": board,
            "state": state,
            "chapter_code": None,
            "chapter_name": None,
            "topic_code": None,
            "topic_name": None,
            "subtopic_code": None,
            "subtopic_name": safe_string(request.subtopic_name),
            "needs_chapter_code": False,
            "needs_topic_code": False,
            "needs_subtopic_code": True  # Always need to generate subtopic code
        }
        
        if scenario == TaxonomyCreationScenario.COMPLETE_HIERARCHY:
            # All new - need to generate all codes
            hierarchy_data.update({
                "chapter_name": safe_string(request.chapter_name),
                "topic_name": safe_string(request.topic_name),
                "needs_chapter_code": True,
                "needs_topic_code": True
            })
        
        elif scenario == TaxonomyCreationScenario.NEW_TOPIC:
            # Existing chapter, new topic and subtopic
            chapter_data = await TaxonomyService._validate_existing_chapter(
                request.chapter_code, subject.id, medium.id, request.standard,
                board.id, state.id, db
            )
            hierarchy_data.update({
                "chapter_code": chapter_data["chapter_code"],
                "chapter_name": chapter_data["chapter_name"],
                "topic_name": safe_string(request.topic_name),
                "needs_topic_code": True
            })
        
        elif scenario == TaxonomyCreationScenario.NEW_SUBTOPIC:
            # Existing chapter and topic, new subtopic
            chapter_topic_data = await TaxonomyService._validate_existing_chapter_topic(
                request.chapter_code, request.topic_code, subject.id, medium.id,
                request.standard, board.id, state.id, db
            )
            hierarchy_data.update({
                "chapter_code": chapter_topic_data["chapter_code"],
                "chapter_name": chapter_topic_data["chapter_name"],
                "topic_code": chapter_topic_data["topic_code"],
                "topic_name": chapter_topic_data["topic_name"]
            })
        
        return hierarchy_data
    
    @staticmethod
    async def _validate_existing_chapter(
        chapter_code: str,
        subject_id: int,
        medium_id: int,
        standard: str,
        board_id: int,
        state_id: int,
        db: AsyncSession
    ) -> Dict[str, str]:
        """
        Validate that a chapter exists in the given context and return its data.
        
        Args:
            chapter_code: Code of the chapter to validate
            subject_id: ID of the subject
            medium_id: ID of the medium
            standard: Class/standard level
            board_id: ID of the board
            state_id: ID of the state
            db: Database session
            
        Returns:
            Dict containing chapter_code and chapter_name
            
        Raises:
            HTTPException: If chapter not found in context
        """
        result = await db.execute(
            select(Taxonomy).filter(
                and_(
                    Taxonomy.stm_chapter_code == chapter_code,
                    Taxonomy.stm_subject_id == subject_id,
                    Taxonomy.stm_medium_id == medium_id,
                    Taxonomy.stm_standard == standard,
                    Taxonomy.board_id == board_id,
                    Taxonomy.state_id == state_id
                )
            ).limit(1)
        )
        existing_taxonomy = result.scalar_one_or_none()
        
        if not existing_taxonomy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Chapter not found",
                    "message": f"Chapter with code '{chapter_code}' does not exist in the specified context",
                    "context": {
                        "subject_id": subject_id,
                        "medium_id": medium_id,
                        "standard": standard,
                        "board_id": board_id,
                        "state_id": state_id
                    }
                }
            )
        
        return {
            "chapter_code": existing_taxonomy.stm_chapter_code,
            "chapter_name": existing_taxonomy.stm_chapter_name
        }
    
    @staticmethod
    async def _validate_existing_chapter_topic(
        chapter_code: str,
        topic_code: str,
        subject_id: int,
        medium_id: int,
        standard: str,
        board_id: int,
        state_id: int,
        db: AsyncSession
    ) -> Dict[str, str]:
        """
        Validate that a chapter/topic combination exists in the given context.
        
        Args:
            chapter_code: Code of the chapter to validate
            topic_code: Code of the topic to validate
            subject_id: ID of the subject
            medium_id: ID of the medium
            standard: Class/standard level
            board_id: ID of the board
            state_id: ID of the state
            db: Database session
            
        Returns:
            Dict containing chapter and topic codes and names
            
        Raises:
            HTTPException: If chapter/topic combination not found in context
        """
        result = await db.execute(
            select(Taxonomy).filter(
                and_(
                    Taxonomy.stm_chapter_code == chapter_code,
                    Taxonomy.stm_topic_code == topic_code,
                    Taxonomy.stm_subject_id == subject_id,
                    Taxonomy.stm_medium_id == medium_id,
                    Taxonomy.stm_standard == standard,
                    Taxonomy.board_id == board_id,
                    Taxonomy.state_id == state_id
                )
            ).limit(1)
        )
        existing_taxonomy = result.scalar_one_or_none()
        
        if not existing_taxonomy:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Chapter/Topic combination not found",
                    "message": f"Chapter '{chapter_code}' with topic '{topic_code}' does not exist in the specified context",
                    "context": {
                        "subject_id": subject_id,
                        "medium_id": medium_id,
                        "standard": standard,
                        "board_id": board_id,
                        "state_id": state_id
                    }
                }
            )
        
        return {
            "chapter_code": existing_taxonomy.stm_chapter_code,
            "chapter_name": existing_taxonomy.stm_chapter_name,
            "topic_code": existing_taxonomy.stm_topic_code,
            "topic_name": existing_taxonomy.stm_topic_name
        }
    
    @staticmethod
    async def generate_taxonomy_codes(
        hierarchy_data: Dict[str, Any],
        db: AsyncSession
    ) -> Dict[str, str]:
        """
        Generate unique codes for taxonomy hierarchy elements.
        
        Generates codes in the format:
        - Chapter: C{3-digit-number} (e.g., C000, C001, C002)
        - Topic: T{3-digit-number} (e.g., T000, T001, T002)
        - Subtopic: S{3-digit-number} (e.g., S000, S001, S002)
        - Taxonomy: TAXC000T000S001-B7-S9-M3-STD10-S11
        
        Args:
            hierarchy_data: Resolved hierarchy data from resolve_taxonomy_hierarchy
            db: Database session
            
        Returns:
            Dict containing generated codes
        """
        generated_codes = {}
        
        # Generate chapter code if needed
        if hierarchy_data["needs_chapter_code"]:
            chapter_code = await TaxonomyService._generate_chapter_code(db)
            generated_codes["chapter_code"] = chapter_code
        else:
            generated_codes["chapter_code"] = hierarchy_data["chapter_code"]
        
        # Generate topic code if needed AND topic name is not empty
        if hierarchy_data["needs_topic_code"]:
            # Only generate topic code if topic name has meaningful content
            if hierarchy_data["topic_name"] and hierarchy_data["topic_name"].strip():
                topic_code = await TaxonomyService._generate_topic_code(db)
                generated_codes["topic_code"] = topic_code
            else:
                # Empty topic name = empty topic code (consistent with bulk upload)
                generated_codes["topic_code"] = ""
        else:
            generated_codes["topic_code"] = hierarchy_data["topic_code"] or ""
        
        # Generate subtopic code only if subtopic name is not empty
        if hierarchy_data["subtopic_name"] and hierarchy_data["subtopic_name"].strip():
            subtopic_code = await TaxonomyService._generate_subtopic_code(db)
            generated_codes["subtopic_code"] = subtopic_code
        else:
            # Empty subtopic name = empty subtopic code (consistent with bulk upload)
            generated_codes["subtopic_code"] = ""
        
        # Generate complex taxonomy code
        taxonomy_code = TaxonomyService._generate_taxonomy_code(
            generated_codes["chapter_code"],
            generated_codes["topic_code"],
            generated_codes["subtopic_code"],
            hierarchy_data["board"].id,
            hierarchy_data["state"].id,
            hierarchy_data["medium"].id,
            hierarchy_data["subject"].smt_standard,
            hierarchy_data["subject"].id
        )
        generated_codes["taxonomy_code"] = taxonomy_code
        
        return generated_codes
    
    @staticmethod
    async def _generate_chapter_code(db: AsyncSession) -> str:
        """
        Generate unique chapter code with format C{3-digit-number}.
        
        Args:
            db: Database session
            
        Returns:
            Generated chapter code (e.g., C000, C001, C002)
        """
        # Get count of distinct chapters globally
        result = await db.execute(
            select(func.count(func.distinct(Taxonomy.stm_chapter_code)))
        )
        chapter_count = result.scalar() or 0
        
        # Generate code with 3-digit zero-padding
        chapter_number = str(chapter_count).zfill(3)
        return f"C{chapter_number}"
    
    @staticmethod
    async def _generate_topic_code(db: AsyncSession) -> str:
        """
        Generate unique topic code with format T{3-digit-number}.
        
        Args:
            db: Database session
            
        Returns:
            Generated topic code (e.g., T000, T001, T002)
        """
        # Get count of distinct topics globally
        result = await db.execute(
            select(func.count(func.distinct(Taxonomy.stm_topic_code)))
        )
        topic_count = result.scalar() or 0
        
        # Generate code with 3-digit zero-padding
        topic_number = str(topic_count).zfill(3)
        return f"T{topic_number}"
    
    @staticmethod
    async def _generate_subtopic_code(db: AsyncSession) -> str:
        """
        Generate unique subtopic code with format S{3-digit-number}.
        
        Args:
            db: Database session
            
        Returns:
            Generated subtopic code (e.g., S000, S001, S002)
        """
        # Get count of distinct subtopics globally
        result = await db.execute(
            select(func.count(func.distinct(Taxonomy.stm_subtopic_code)))
        )
        subtopic_count = result.scalar() or 0
        
        # Generate code with 3-digit zero-padding
        subtopic_number = str(subtopic_count).zfill(3)
        return f"S{subtopic_number}"
    
    @staticmethod
    def _generate_taxonomy_code(
        chapter_code: str,
        topic_code: str,
        subtopic_code: str,
        board_id: int,
        state_id: int,
        medium_id: int,
        standard: str,
        subject_id: int
    ) -> str:
        """
        Generate complex taxonomy code combining all hierarchy and context elements.
        
        Format: TAXC000T000S001-B7-S9-M3-STD10-S11
        
        Args:
            chapter_code: Chapter code (e.g., C000)
            topic_code: Topic code (e.g., T000)
            subtopic_code: Subtopic code (e.g., S001)
            board_id: Board ID
            state_id: State ID
            medium_id: Medium ID
            standard: Class/standard level
            subject_id: Subject ID
            
        Returns:
            Generated taxonomy code
        """
        return (
            f"TAX{chapter_code}{topic_code}{subtopic_code}-"
            f"B{board_id}-S{state_id}-M{medium_id}-STD{standard}-S{subject_id}"
        )    

    @staticmethod
    async def check_taxonomy_duplicate_by_content(
        hierarchy_data: Dict[str, Any],
        db: AsyncSession
    ) -> Optional[Taxonomy]:
        """
        Check for existing taxonomy entry with the same content (names) and context.
        
        This checks for duplicates based on the actual content rather than generated codes,
        which is what we want to prevent - creating the same taxonomy with different codes.
        
        Args:
            hierarchy_data: Resolved hierarchy data containing names and context
            db: Database session
            
        Returns:
            Existing Taxonomy if duplicate found, None otherwise
        """
        result = await db.execute(
            select(Taxonomy)
            .options(
                joinedload(Taxonomy.subject),
                joinedload(Taxonomy.medium),
                joinedload(Taxonomy.board),
                joinedload(Taxonomy.state),
                joinedload(Taxonomy.created_by_user),
                joinedload(Taxonomy.updated_by_user)
            )
            .filter(
                and_(
                    Taxonomy.stm_chapter_name == hierarchy_data["chapter_name"],
                    Taxonomy.stm_topic_name == hierarchy_data["topic_name"],
                    Taxonomy.stm_subtopic_name == hierarchy_data["subtopic_name"],
                    Taxonomy.stm_subject_id == hierarchy_data["subject"].id,
                    Taxonomy.stm_medium_id == hierarchy_data["medium"].id,
                    Taxonomy.stm_standard == hierarchy_data["subject"].smt_standard,
                    Taxonomy.board_id == hierarchy_data["board"].id,
                    Taxonomy.state_id == hierarchy_data["state"].id
                )
            )
            .limit(1)  # Get only the first match to avoid multiple rows error
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def check_taxonomy_duplicate(
        hierarchy_data: Dict[str, Any],
        generated_codes: Dict[str, str],
        db: AsyncSession
    ) -> Optional[Taxonomy]:
        """
        Check for existing taxonomy entry with the same hierarchy and context.
        
        Uses the unique constraint: (stm_chapter_code, stm_topic_code, stm_subtopic_code,
        stm_subject_id, stm_medium_id, stm_standard, board_id, state_id)
        
        This is used to prevent database constraint violations after code generation.
        
        Args:
            hierarchy_data: Resolved hierarchy data
            generated_codes: Generated codes for the taxonomy
            db: Database session
            
        Returns:
            Existing Taxonomy if duplicate found, None otherwise
        """
        result = await db.execute(
            select(Taxonomy)
            .options(
                joinedload(Taxonomy.subject),
                joinedload(Taxonomy.medium),
                joinedload(Taxonomy.board),
                joinedload(Taxonomy.state),
                joinedload(Taxonomy.created_by_user),
                joinedload(Taxonomy.updated_by_user)
            )
            .filter(
                and_(
                    Taxonomy.stm_chapter_code == generated_codes["chapter_code"],
                    Taxonomy.stm_topic_code == generated_codes["topic_code"],
                    Taxonomy.stm_subtopic_code == generated_codes["subtopic_code"],
                    Taxonomy.stm_subject_id == hierarchy_data["subject"].id,
                    Taxonomy.stm_medium_id == hierarchy_data["medium"].id,
                    Taxonomy.stm_standard == hierarchy_data["subject"].smt_standard,
                    Taxonomy.board_id == hierarchy_data["board"].id,
                    Taxonomy.state_id == hierarchy_data["state"].id
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    def build_conflict_response(existing_taxonomy: Taxonomy) -> Dict[str, Any]:
        """
        Build conflict response with existing taxonomy details.
        
        Args:
            existing_taxonomy: Existing taxonomy entry that conflicts
            
        Returns:
            Dict containing conflict response data
        """
        return {
            "detail": "Taxonomy already exists with the same hierarchy and context",
            "existing_taxonomy": {
                "taxonomy_code": existing_taxonomy.stm_taxonomy_code,
                "subject_code": existing_taxonomy.subject.smt_subject_code if existing_taxonomy.subject else None,
                "medium_code": existing_taxonomy.medium.mmt_medium_code if existing_taxonomy.medium else None,
                "standard": existing_taxonomy.stm_standard,
                "board_id": existing_taxonomy.board_id,
                "state_id": existing_taxonomy.state_id,
                "chapter_code": existing_taxonomy.stm_chapter_code,
                "chapter_name": existing_taxonomy.stm_chapter_name,
                "topic_code": existing_taxonomy.stm_topic_code,
                "topic_name": existing_taxonomy.stm_topic_name,
                "subtopic_code": existing_taxonomy.stm_subtopic_code,
                "subtopic_name": existing_taxonomy.stm_subtopic_name,
                "created_by": existing_taxonomy.created_by_username,
                "created_at": existing_taxonomy.created_at.isoformat() if existing_taxonomy.created_at else None,
                "updated_by": existing_taxonomy.updated_by_username,
                "updated_at": existing_taxonomy.updated_at.isoformat() if existing_taxonomy.updated_at else None
            }
        }
    
    @staticmethod
    async def check_content_duplicate_and_return_existing(
        hierarchy_data: Dict[str, Any],
        db: AsyncSession
    ) -> Optional[Taxonomy]:
        """
        Check for existing taxonomy with the same content and return it if found.
        
        This allows us to return existing taxonomies instead of creating duplicates
        when the same content is requested.
        
        Args:
            hierarchy_data: Resolved hierarchy data containing names and context
            db: Database session
            
        Returns:
            Existing Taxonomy if duplicate found, None if no duplicate exists
        """
        return await TaxonomyService.check_taxonomy_duplicate_by_content(
            hierarchy_data, db
        )

    @staticmethod
    async def validate_unique_constraint(
        hierarchy_data: Dict[str, Any],
        generated_codes: Dict[str, str],
        db: AsyncSession
    ) -> None:
        """
        Validate that the taxonomy entry will not violate unique constraints.
        
        This is a final check after code generation to prevent database constraint violations.
        
        Args:
            hierarchy_data: Resolved hierarchy data
            generated_codes: Generated codes for the taxonomy
            db: Database session
            
        Raises:
            HTTPException: If duplicate taxonomy is found
        """
        existing_taxonomy = await TaxonomyService.check_taxonomy_duplicate(
            hierarchy_data, generated_codes, db
        )
        
        if existing_taxonomy:
            conflict_response = TaxonomyService.build_conflict_response(existing_taxonomy)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=conflict_response
            )
    
    @staticmethod
    async def create_taxonomy(
        request: TaxonomyCreateRequest,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Main taxonomy creation workflow orchestrating all steps.
        
        This method implements the complete taxonomy creation process:
        1. Validate creation scenario
        2. Validate master data context
        3. Resolve taxonomy hierarchy
        4. Generate unique codes
        5. Check for duplicates
        6. Create taxonomy entry
        7. Return success response
        
        Args:
            request: Validated taxonomy creation request
            db: Database session
            user_id: ID of the authenticated user for audit trail
            
        Returns:
            Dict containing created taxonomy data
            
        Raises:
            HTTPException: For validation errors, conflicts, or creation failures
        """
        try:
            # Step 1: Validate and determine creation scenario
            scenario = TaxonomyService.validate_creation_scenario(request)
            
            # Step 2: Validate scenario-specific requirements
            await TaxonomyService.validate_scenario_requirements(request, scenario, db)
            
            # Step 3: Validate master data context
            subject, medium, board, state = await TaxonomyService.validate_master_data_context(
                request, db
            )
            
            # Step 4: Resolve taxonomy hierarchy
            hierarchy_data = await TaxonomyService.resolve_taxonomy_hierarchy(
                request, scenario, subject, medium, board, state, db
            )
            
            # Step 5: Check for existing taxonomy with same content (early duplicate detection)
            existing_taxonomy = await TaxonomyService.check_content_duplicate_and_return_existing(
                hierarchy_data, db
            )
            
            if existing_taxonomy:
                # Taxonomy with same content already exists - return 409 conflict
                conflict_response = TaxonomyService.build_conflict_response(existing_taxonomy)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=conflict_response
                )
            
            # Step 6: Generate unique codes (only if no duplicate found)
            generated_codes = await TaxonomyService.generate_taxonomy_codes(
                hierarchy_data, db
            )
            
            # Step 7: Validate unique constraint (final check for code-based duplicates)
            await TaxonomyService.validate_unique_constraint(
                hierarchy_data, generated_codes, db
            )
            
            # Step 8: Create new taxonomy entry
            new_taxonomy = Taxonomy(
                stm_taxonomy_code=generated_codes["taxonomy_code"],
                stm_subject_id=subject.id,
                stm_medium_id=medium.id,
                stm_standard=request.standard,
                stm_chapter_code=generated_codes["chapter_code"],
                stm_chapter_name=hierarchy_data["chapter_name"],
                stm_topic_code=generated_codes["topic_code"],
                stm_topic_name=hierarchy_data["topic_name"],
                stm_subtopic_code=generated_codes["subtopic_code"],
                stm_subtopic_name=hierarchy_data["subtopic_name"],
                board_id=board.id,
                state_id=state.id,
                created_by=user_id,
                updated_by=user_id
            )
            
            # Step 9: Save to database with transaction management
            db.add(new_taxonomy)
            await db.commit()
            await db.refresh(new_taxonomy)
            
            # Step 10: Load relationships for response building
            result = await db.execute(
                select(Taxonomy)
                .options(
                    joinedload(Taxonomy.subject),
                    joinedload(Taxonomy.medium),
                    joinedload(Taxonomy.board),
                    joinedload(Taxonomy.state),
                    joinedload(Taxonomy.created_by_user),
                    joinedload(Taxonomy.updated_by_user)
                )
                .filter(Taxonomy.id == new_taxonomy.id)
            )
            taxonomy_with_relations = result.scalar_one()
            
            # Step 11: Build and return success response
            return taxonomy_with_relations
            
        except HTTPException:
            # Re-raise HTTP exceptions (validation errors, conflicts)
            await db.rollback()
            raise
        except Exception as e:
            # Handle unexpected errors with rollback
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Failed to create taxonomy",
                    "message": "An unexpected error occurred during taxonomy creation",
                    "details": str(e)
                }
            )

    
