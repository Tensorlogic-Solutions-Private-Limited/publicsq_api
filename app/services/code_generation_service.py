from sqlalchemy import select, func, and_, or_, update, Integer, text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any
from app.models.master import QuestionSequence, Taxonomy
from app.models.user import User
import logging

logger = logging.getLogger(__name__)


class CodeGenerationService:
    """Service for generating unique codes for questions, chapters, topics, and subtopics."""
    
    def __init__(self):
        # In-memory caches for generated codes during upload session
        self._chapter_codes_cache: Dict[str, str] = {}
        self._topic_codes_cache: Dict[str, str] = {}
        self._subtopic_codes_cache: Dict[str, str] = {}
        
        # Track codes assigned in current session (not yet committed)
        self._session_chapter_codes: Dict[str, str] = {}
        self._session_topic_codes: Dict[str, str] = {}
        self._session_subtopic_codes: Dict[str, str] = {}
        
        # Track the next available code numbers
        self._next_chapter_number: Optional[int] = None
        self._next_topic_number: Optional[int] = None
        self._next_subtopic_number: Optional[int] = None
        
    async def get_next_question_id(self, db: AsyncSession) -> int:
        """
        Get the next sequential question ID from the QuestionSequence table.
        Uses atomic database operations to prevent race conditions.
        Also ensures the sequence is in sync with the actual highest question ID.
        
        Args:
            db: Database session
            
        Returns:
            int: Next question ID
        """
        try:
            from sqlalchemy import text, select, func
            from app.models.master import Questions
            
            # First, get the actual highest question ID from the questions table
            max_id_stmt = select(func.max(Questions.id))
            result = await db.execute(max_id_stmt)
            max_existing_id = result.scalar() or 0
            
            # Use atomic UPDATE with row-level locking to prevent race conditions
            # This ensures only one process can increment the sequence at a time
            # We also ensure the sequence is at least as high as the max existing ID
            update_stmt = text("""
                UPDATE question_sequence 
                SET last_question_id = GREATEST(last_question_id + 1, :max_id + 1)
                WHERE id = (SELECT id FROM question_sequence ORDER BY id LIMIT 1 FOR UPDATE)
                RETURNING last_question_id
            """)
            
            result = await db.execute(update_stmt, {"max_id": max_existing_id})
            new_question_id = result.scalar()
            
            if new_question_id is None:
                # No existing record, create one with the max existing ID + 1
                insert_stmt = text("""
                    INSERT INTO question_sequence (last_question_id) 
                    VALUES (:max_id + 1) 
                    ON CONFLICT (id) DO UPDATE SET last_question_id = GREATEST(question_sequence.last_question_id + 1, :max_id + 1)
                    RETURNING last_question_id
                """)
                
                result = await db.execute(insert_stmt, {"max_id": max_existing_id})
                new_question_id = result.scalar()
                
                if new_question_id is None:
                    # Fallback: create record manually if needed
                    sequence_record = QuestionSequence(last_question_id=max_existing_id + 1)
                    db.add(sequence_record)
                    await db.flush()
                    new_question_id = max_existing_id + 1
            
            await db.commit()
            
            logger.info(f"Generated new question ID: {new_question_id} (max existing: {max_existing_id})")
            return new_question_id
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error generating question ID: {str(e)}")
            raise
    
    async def get_or_create_chapter_code(
        self, 
        chapter_name: str, 
        db: AsyncSession
    ) -> str:
        """
        Get existing chapter code or create a new one with format C{3-digit-number}.
        
        Args:
            chapter_name: Name of the chapter
            db: Database session
            
        Returns:
            str: Chapter code in format C000, C001, etc.
        """
        try:
            # Normalize chapter name for lookup
            normalized_name = chapter_name.strip().lower()
            
            # Check cache first
            if normalized_name in self._chapter_codes_cache:
                return self._chapter_codes_cache[normalized_name]
            
            # Check session cache (codes assigned in current session)
            if normalized_name in self._session_chapter_codes:
                code = self._session_chapter_codes[normalized_name]
                self._chapter_codes_cache[normalized_name] = code
                return code
            
            # Check if chapter code already exists in database
            stmt = select(Taxonomy.stm_chapter_code).where(
                func.lower(func.trim(Taxonomy.stm_chapter_name)) == normalized_name
            ).distinct()
            result = await db.execute(stmt)
            existing_code = result.scalar_one_or_none()
            
            if existing_code:
                self._chapter_codes_cache[normalized_name] = existing_code
                return existing_code
            
            # Initialize next chapter number if not set
            if self._next_chapter_number is None:
                stmt = select(func.max(
                    func.cast(
                        func.substring(Taxonomy.stm_chapter_code, 2), 
                        Integer
                    )
                )).where(
                    and_(
                        Taxonomy.stm_chapter_code.like('C%'),
                        func.length(Taxonomy.stm_chapter_code) >= 2,
                        text("substring(stm_chapter_code, 2) ~ '^[0-9]+$'")
                    )
                )
                result = await db.execute(stmt)
                max_number = result.scalar_one_or_none()
                if max_number is None:
                    max_number = -1
                self._next_chapter_number = max_number + 1
            
            # Generate new chapter code using session-aware counter
            new_code = f"C{self._next_chapter_number:03d}"
            self._next_chapter_number += 1
            
            # Store in both caches
            self._chapter_codes_cache[normalized_name] = new_code
            self._session_chapter_codes[normalized_name] = new_code
            
            logger.info(f"Generated new chapter code: {new_code} for chapter: {chapter_name}")
            return new_code
            
        except Exception as e:
            logger.error(f"Error generating chapter code for '{chapter_name}': {str(e)}")
            raise
    
    async def get_or_create_topic_code(
        self, 
        topic_name: str, 
        chapter_code: str, 
        db: AsyncSession
    ) -> str:
        """
        Get existing topic code or create a new one with format T{3-digit-number}.
        
        Args:
            topic_name: Name of the topic
            chapter_code: Associated chapter code
            db: Database session
            
        Returns:
            str: Topic code in format T000, T001, etc.
        """
        try:
            # Normalize topic name for lookup
            normalized_name = topic_name.strip().lower()
            cache_key = f"{chapter_code}:{normalized_name}"
            
            # Check cache first
            if cache_key in self._topic_codes_cache:
                return self._topic_codes_cache[cache_key]
            
            # Check session cache (codes assigned in current session)
            if cache_key in self._session_topic_codes:
                code = self._session_topic_codes[cache_key]
                self._topic_codes_cache[cache_key] = code
                return code
            
            # Check if topic code already exists in database for this chapter
            stmt = select(Taxonomy.stm_topic_code).where(
                and_(
                    Taxonomy.stm_chapter_code == chapter_code,
                    func.lower(func.trim(Taxonomy.stm_topic_name)) == normalized_name
                )
            ).distinct()
            result = await db.execute(stmt)
            existing_code = result.scalar_one_or_none()
            
            if existing_code:
                self._topic_codes_cache[cache_key] = existing_code
                return existing_code
            
            # Initialize next topic number if not set
            if self._next_topic_number is None:
                stmt = select(func.max(
                    func.cast(
                        func.substring(Taxonomy.stm_topic_code, 2), 
                        Integer
                    )
                )).where(
                    and_(
                        Taxonomy.stm_topic_code.like('T%'),
                        func.length(Taxonomy.stm_topic_code) >= 2,
                        text("substring(stm_topic_code, 2) ~ '^[0-9]+$'")
                    )
                )
                result = await db.execute(stmt)
                max_number = result.scalar_one_or_none()
                if max_number is None:
                    max_number = -1
                self._next_topic_number = max_number + 1
            
            # Generate new topic code using session-aware counter
            new_code = f"T{self._next_topic_number:03d}"
            self._next_topic_number += 1
            
            # Store in both caches
            self._topic_codes_cache[cache_key] = new_code
            self._session_topic_codes[cache_key] = new_code
            
            logger.info(f"Generated new topic code: {new_code} for topic: {topic_name} in chapter: {chapter_code}")
            return new_code
            
        except Exception as e:
            logger.error(f"Error generating topic code for '{topic_name}' in chapter '{chapter_code}': {str(e)}")
            raise
    
    async def get_or_create_subtopic_code(
        self, 
        subtopic_name: str, 
        topic_code: str, 
        db: AsyncSession
    ) -> str:
        """
        Get existing subtopic code or create a new one with format S{3-digit-number}.
        
        Args:
            subtopic_name: Name of the subtopic
            topic_code: Associated topic code
            db: Database session
            
        Returns:
            str: Subtopic code in format S000, S001, etc.
        """
        try:
            # Normalize subtopic name for lookup
            normalized_name = subtopic_name.strip().lower()
            cache_key = f"{topic_code}:{normalized_name}"
            
            # Check cache first
            if cache_key in self._subtopic_codes_cache:
                return self._subtopic_codes_cache[cache_key]
            
            # Check session cache (codes assigned in current session)
            if cache_key in self._session_subtopic_codes:
                code = self._session_subtopic_codes[cache_key]
                self._subtopic_codes_cache[cache_key] = code
                return code
            
            # Check if subtopic code already exists in database for this topic
            stmt = select(Taxonomy.stm_subtopic_code).where(
                and_(
                    Taxonomy.stm_topic_code == topic_code,
                    func.lower(func.trim(Taxonomy.stm_subtopic_name)) == normalized_name
                )
            ).distinct()
            result = await db.execute(stmt)
            existing_code = result.scalar_one_or_none()
            
            if existing_code:
                self._subtopic_codes_cache[cache_key] = existing_code
                return existing_code
            
            # Initialize next subtopic number if not set
            if self._next_subtopic_number is None:
                stmt = select(func.max(
                    func.cast(
                        func.substring(Taxonomy.stm_subtopic_code, 2), 
                        Integer
                    )
                )).where(
                    and_(
                        Taxonomy.stm_subtopic_code.like('S%'),
                        func.length(Taxonomy.stm_subtopic_code) >= 2,
                        text("substring(stm_subtopic_code, 2) ~ '^[0-9]+$'")
                    )
                )
                result = await db.execute(stmt)
                max_number = result.scalar_one_or_none()
                if max_number is None:
                    max_number = -1
                self._next_subtopic_number = max_number + 1
            
            # Generate new subtopic code using session-aware counter
            new_code = f"S{self._next_subtopic_number:03d}"
            self._next_subtopic_number += 1
            
            # Store in both caches
            self._subtopic_codes_cache[cache_key] = new_code
            self._session_subtopic_codes[cache_key] = new_code
            
            logger.info(f"Generated new subtopic code: {new_code} for subtopic: {subtopic_name} in topic: {topic_code}")
            return new_code
            
        except Exception as e:
            logger.error(f"Error generating subtopic code for '{subtopic_name}' in topic '{topic_code}': {str(e)}")
            raise
    
    def generate_taxonomy_code(
        self, 
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
        Generate taxonomy code by concatenating chapter, topic, subtopic codes and context fields.
        
        Args:
            chapter_code: Chapter code (e.g., C000)
            topic_code: Topic code (e.g., T000)
            subtopic_code: Subtopic code (e.g., S000)
            board_id: Board ID
            state_id: State ID
            medium_id: Medium ID
            standard: Standard/class (e.g., '10')
            subject_id: Subject ID
            
        Returns:
            str: Taxonomy code in format TAX{chapter_code}{topic_code}{subtopic_code}-B{board_id}-S{state_id}-M{medium_id}-STD{standard}-S{subject_id}
        """
        try:
            # Build base taxonomy code
            base_code = f"TAX{chapter_code}"
            if topic_code:
                base_code += topic_code
            if subtopic_code:
                base_code += subtopic_code
            
            # Add context fields to make taxonomy code unique per context
            taxonomy_code = f"{base_code}-B{board_id}-S{state_id}-M{medium_id}-STD{standard}-S{subject_id}"
            logger.info(f"Generated taxonomy code: {taxonomy_code}")
            return taxonomy_code
            
        except Exception as e:
            logger.error(f"Error generating taxonomy code: {str(e)}")
            raise
    
    def generate_question_code(self, question_id: int) -> str:
        """
        Generate question code using format Q{sequential_number}.
        
        Args:
            question_id: Sequential question ID
            
        Returns:
            str: Question code in format Q1, Q2, etc.
        """
        try:
            question_code = f"Q{question_id}"
            logger.info(f"Generated question code: {question_code}")
            return question_code
            
        except Exception as e:
            logger.error(f"Error generating question code for ID {question_id}: {str(e)}")
            raise
    
    def clear_caches(self):
        """
        Clear all in-memory caches. Should be called after upload session completion.
        """
        self._chapter_codes_cache.clear()
        self._topic_codes_cache.clear()
        self._subtopic_codes_cache.clear()
        
        # Clear session caches
        self._session_chapter_codes.clear()
        self._session_topic_codes.clear()
        self._session_subtopic_codes.clear()
        
        # Reset counters
        self._next_chapter_number = None
        self._next_topic_number = None
        self._next_subtopic_number = None
        
        logger.info("Cleared all code generation caches")
    
    async def ensure_global_uniqueness(
        self, 
        codes_to_check: Dict[str, str], 
        db: AsyncSession
    ) -> bool:
        """
        Verify that all generated codes are globally unique.
        
        Args:
            codes_to_check: Dictionary of code types and their values
            db: Database session
            
        Returns:
            bool: True if all codes are unique, False otherwise
        """
        try:
            for code_type, code_value in codes_to_check.items():
                if code_type == "chapter":
                    stmt = select(func.count(Taxonomy.id)).where(
                        Taxonomy.stm_chapter_code == code_value
                    )
                elif code_type == "topic":
                    stmt = select(func.count(Taxonomy.id)).where(
                        Taxonomy.stm_topic_code == code_value
                    )
                elif code_type == "subtopic":
                    stmt = select(func.count(Taxonomy.id)).where(
                        Taxonomy.stm_subtopic_code == code_value
                    )
                elif code_type == "taxonomy":
                    stmt = select(func.count(Taxonomy.id)).where(
                        Taxonomy.stm_taxonomy_code == code_value
                    )
                else:
                    continue
                
                result = await db.execute(stmt)
                count = result.scalar_one()
                
                if count > 0:
                    logger.warning(f"Code {code_value} of type {code_type} is not unique")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking code uniqueness: {str(e)}")
            return False


# Create a singleton instance for use across the application
code_generation_service = CodeGenerationService()