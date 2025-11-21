import pandas as pd
import os
import logging
import uuid
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from dataclasses import dataclass
from enum import Enum

from app.models.user import User
from app.models.master import (
    Questions, Taxonomy, Board, State, Medium, Subject, 
    CognitiveLearning, Difficulty, Question_Format, Question_Type
)
from app.services.code_generation_service import code_generation_service
from app.services.master_data_lookup_service import master_data_lookup_service
from app.services.s3_service import s3_service
from app.middleware.rbac import rbac_middleware

logger = logging.getLogger(__name__)


class ValidationErrorType(Enum):
    """Types of validation errors that can occur during upload."""
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_DATA_TYPE = "invalid_data_type"
    LOOKUP_FAILED = "lookup_failed"
    PROCESSING_ERROR = "processing_error"


@dataclass
class RowError:
    """Represents an error that occurred while processing a specific row."""
    row_number: int
    error_type: ValidationErrorType
    error_message: str
    row_data: Dict[str, Any]


@dataclass
class ValidationResult:
    """Result of Excel structure validation."""
    is_valid: bool
    missing_columns: List[str]
    error_message: Optional[str] = None


@dataclass
class UploadResult:
    """Result of the complete upload process."""
    success_count: int
    error_count: int
    errors: List[RowError]
    message: str


class EnhancedUploadService:
    """
    Service for processing Excel uploads with new template structure.
    
    Features:
    - New Excel template structure with Board, State, Subtopic fields
    - Automatic code generation for questions, chapters, topics, subtopics
    - Row-by-row processing with error handling and row skipping
    - Data validation and normalization pipeline
    """
    
    # Excel column mapping configuration for new template structure
    EXCEL_COLUMN_MAPPING = {
        "Question_text": "qmt_question_text",
        "answer_option_a": "qmt_option1",
        "answer_option_b": "qmt_option2", 
        "answer_option_c": "qmt_option3",
        "answer_option_d": "qmt_option4",
        "correct_answer": "qmt_correct_answer",
        "chapter_name": "stm_chapter_name",
        "topic_name": "stm_topic_name",
        "subtopic_name": "stm_subtopic_name",
        "Medium": "medium_lookup",
        "Board": "board_lookup",
        "State": "state_lookup",
        "Class": "stm_standard",
        "Subject": "subject_lookup",
        "cognitive learning": "cognitive_learning_lookup",
        "difficulty": "difficulty_lookup"
    }
    
    # Required columns in the new Excel template
    REQUIRED_COLUMNS = [
        "Question_text", "answer_option_a", "answer_option_b", 
        "answer_option_c", "answer_option_d", "correct_answer",
        "chapter_name", "topic_name", "subtopic_name",
        "Medium", "Board", "State", "Class", "Subject",
        "cognitive learning", "difficulty"
    ]
    
    def __init__(self):
        self.code_service = code_generation_service
        self.lookup_service = master_data_lookup_service
        # Cache for master data to avoid repeated database queries
        self._board_cache = {}
        self._state_cache = {}
        self._medium_cache = {}
        self._subject_cache = {}
        self._cognitive_learning_cache = {}
        self._difficulty_cache = {}
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by replacing special characters with HTML equivalents.
        
        Args:
            text: Raw text from Excel that may contain special characters
            
        Returns:
            Cleaned text with HTML formatting
        """
        if not text or not isinstance(text, str):
            return text
        
        # Replace _x000D_ (carriage return) with HTML line break
        cleaned_text = text.replace('_x000D_', '<br>')
        
        # Also handle common variations
        cleaned_text = cleaned_text.replace('\r\n', '<br>')
        cleaned_text = cleaned_text.replace('\n', '<br>')
        cleaned_text = cleaned_text.replace('\r', '<br>')
        
        return cleaned_text
    
    async def get_cached_board(self, board_name: str, db: AsyncSession, user_id: int):
        """Get or create board with caching."""
        if board_name not in self._board_cache:
            self._board_cache[board_name] = await self.lookup_service.get_or_create_board(
                board_name, db, user_id
            )
        return self._board_cache[board_name]
    
    async def get_cached_state(self, state_name: str, db: AsyncSession, user_id: int):
        """Get or create state with caching."""
        if state_name not in self._state_cache:
            self._state_cache[state_name] = await self.lookup_service.get_or_create_state(
                state_name, db, user_id
            )
        return self._state_cache[state_name]
    
    async def get_cached_medium(self, medium_name: str, db: AsyncSession, user_id: int):
        """Get or create medium with caching."""
        if medium_name not in self._medium_cache:
            self._medium_cache[medium_name] = await self.lookup_service.get_or_create_medium(
                medium_name, db, user_id
            )
        return self._medium_cache[medium_name]
    
    async def get_cached_subject(self, subject_name: str, class_name: str, medium_id: int, db: AsyncSession, user_id: int):
        """Get or create subject with caching."""
        cache_key = f"{subject_name}_{class_name}_{medium_id}"
        if cache_key not in self._subject_cache:
            self._subject_cache[cache_key] = await self.lookup_service.get_or_create_subject(
                subject_name, class_name, medium_id, db, user_id
            )
        return self._subject_cache[cache_key]
    
    async def get_cached_cognitive_learning(self, cognitive_name: str, db: AsyncSession, user_id: int):
        """Get or create cognitive learning with caching."""
        if cognitive_name not in self._cognitive_learning_cache:
            self._cognitive_learning_cache[cognitive_name] = await self.lookup_service.get_or_create_cognitive_learning(
                cognitive_name, db, user_id
            )
        return self._cognitive_learning_cache[cognitive_name]
    
    async def get_cached_difficulty(self, difficulty_name: str, db: AsyncSession, user_id: int):
        """Get or create difficulty with caching."""
        if difficulty_name not in self._difficulty_cache:
            self._difficulty_cache[difficulty_name] = await self.lookup_service.get_or_create_difficulty(
                difficulty_name, db, user_id
            )
        return self._difficulty_cache[difficulty_name]
    
    async def load_excel(self, file_path: str) -> pd.DataFrame:
        """
        Load Excel file and return DataFrame.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            pd.DataFrame: Loaded Excel data
            
        Raises:
            HTTPException: If file not found or loading fails
        """
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"File not found at {file_path}")

        try:
            df = pd.read_excel(file_path)
            if df.empty:
                raise HTTPException(status_code=400, detail="Excel file is empty")
            
            logger.info(f"Successfully loaded Excel file with {len(df)} rows")
            return df
            
        except Exception as e:
            logger.error(f"Error loading Excel file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error loading Excel: {str(e)}")
    
    async def validate_excel_structure(self, df: pd.DataFrame) -> ValidationResult:
        """
        Validate that the Excel file has the required column structure.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            ValidationResult: Validation result with details
        
        """
        try:
            # Check for required columns
            missing_columns = []
            df_columns = [col.strip() for col in df.columns]
            
            for required_col in self.REQUIRED_COLUMNS:
                if required_col not in df_columns:
                    missing_columns.append(required_col)
            
            if missing_columns:
                error_msg = f"Missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                return ValidationResult(
                    is_valid=False,
                    missing_columns=missing_columns,
                    error_message=error_msg
                )
            
            logger.info("Excel structure validation passed")
            return ValidationResult(is_valid=True, missing_columns=[])
            
        except Exception as e:
            logger.error(f"Error validating Excel structure: {str(e)}")
            return ValidationResult(
                is_valid=False,
                missing_columns=[],
                error_message=f"Validation error: {str(e)}"
            )
    
    def normalize_text_data(self, value: Any) -> str:
        """
        Normalize text data by removing leading/trailing spaces and handling None values.
        
        Args:
            value: Value to normalize
            
        Returns:
            str: Normalized string value
        """
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()
    
    def validate_required_fields(self, row_data: Dict[str, Any], row_number: int) -> Optional[RowError]:
        """
        Validate that all required fields have values.
        
        Args:
            row_data: Normalized row data
            row_number: Row number for error reporting
            
        Returns:
            Optional[RowError]: Error if validation fails, None if valid
            
        
        """
        try:
            required_fields = [
                "Question_text", "answer_option_a", "answer_option_b", 
                "answer_option_c", "answer_option_d", "correct_answer",
                "chapter_name", "topic_name", "subtopic_name",
                "Medium", "Board", "State", "Class", "Subject",
                "cognitive learning", "difficulty"
            ]
            
            missing_fields = []
            for field in required_fields:
                if not row_data.get(field) or row_data[field] == "":
                    missing_fields.append(field)
            
            if missing_fields:
                error_msg = self._generate_user_friendly_error_message(
                    "missing_required_field", missing_fields
                )
                return RowError(
                    row_number=row_number,
                    error_type=ValidationErrorType.MISSING_REQUIRED_FIELD,
                    error_message=error_msg,
                    row_data=row_data
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating required fields for row {row_number}: {str(e)}")
            return RowError(
                row_number=row_number,
                error_type=ValidationErrorType.PROCESSING_ERROR,
                error_message=f"Validation error: {str(e)}",
                row_data=row_data
            )
    
    def validate_data_types(self, row_data: Dict[str, Any], row_number: int) -> Optional[RowError]:
        """
        Validate data types and formats for specific fields.
        
        Args:
            row_data: Normalized row data
            row_number: Row number for error reporting
            
        Returns:
            Optional[RowError]: Error if validation fails, None if valid
            
        8.3
        """
        try:
            validation_errors = []
            
            # Validate correct_answer is A, B, C, or D
            correct_answer = row_data.get("correct_answer", "").upper()
            if correct_answer not in ["A", "B", "C", "D"]:
                validation_errors.append("correct_answer must be A, B, C, or D")
            
            # Validate Class is numeric
            class_value = row_data.get("Class", "")
            if class_value and not str(class_value).isdigit():
                validation_errors.append("Class must be a number")
            
            # Validate question text length
            question_text = row_data.get("Question_text", "")
            if len(question_text) > 1000:  # Reasonable limit
                validation_errors.append("Question text is too long (maximum 1000 characters)")
            
            # Validate option lengths
            for option in ["answer_option_a", "answer_option_b", "answer_option_c", "answer_option_d"]:
                option_text = row_data.get(option, "")
                if len(option_text) > 200:  # Reasonable limit for options
                    validation_errors.append(f"{option} is too long (maximum 200 characters)")
            
            if validation_errors:
                error_msg = self._generate_user_friendly_error_message(
                    "invalid_data_type", validation_errors
                )
                return RowError(
                    row_number=row_number,
                    error_type=ValidationErrorType.INVALID_DATA_TYPE,
                    error_message=error_msg,
                    row_data=row_data
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error validating data types for row {row_number}: {str(e)}")
            return RowError(
                row_number=row_number,
                error_type=ValidationErrorType.PROCESSING_ERROR,
                error_message=f"Data type validation error: {str(e)}",
                row_data=row_data
            )
    
    def _generate_user_friendly_error_message(self, error_type: str, details: List[str]) -> str:
        """
        Generate user-friendly error messages for common validation failures.
        
        Args:
            error_type: Type of error
            details: List of specific error details
            
        Returns:
            str: User-friendly error message
            
        
        """
        if error_type == "missing_required_field":
            if len(details) == 1:
                return f"Required field '{details[0]}' is missing or empty. Please provide a value."
            else:
                return f"Required fields are missing or empty: {', '.join(details)}. Please provide values for all required fields."
        
        elif error_type == "invalid_data_type":
            return f"Data validation failed: {'; '.join(details)}. Please check your data format."
        
        elif error_type == "lookup_failed":
            return f"Data lookup failed: {'; '.join(details)}. Please verify that the referenced data exists in the system."
        
        elif error_type == "processing_error":
            return f"Processing error occurred: {'; '.join(details)}. Please check your data and try again."
        
        else:
            return f"Validation error: {'; '.join(details)}"
    
    def generate_error_summary(self, errors: List[RowError]) -> Dict[str, Any]:
        """
        Generate a summary of errors by type for better reporting.
        
        Args:
            errors: List of row errors
            
        Returns:
            Dict[str, Any]: Error summary with counts and sample messages
        """
        error_summary = {}
        
        for error in errors:
            error_type = error.error_type.value
            if error_type not in error_summary:
                error_summary[error_type] = {
                    "count": 0,
                    "sample_message": error.error_message,
                    "sample_row": error.row_number
                }
            error_summary[error_type]["count"] += 1
        
        return error_summary
    
    async def generate_result_excel_file(
        self,
        original_df: pd.DataFrame,
        successful_rows: List[int],
        errors: List[RowError],
        job_id: str
    ) -> str:
        """
        Generate result Excel file with original data plus is_successful and reason columns.
        
        Args:
            original_df: Original DataFrame from uploaded Excel
            successful_rows: List of row numbers that were processed successfully
            errors: List of errors that occurred during processing
            job_id: Job ID for unique file naming
            
        Returns:
            str: Path to the generated result Excel file
        """
        try:
            # Create a copy of the original DataFrame
            result_df = original_df.copy()
            
            # Add the new columns with default values
            result_df['is_successful'] = False
            result_df['reason'] = ''
            
            # Mark successful rows (convert to 0-based indexing)
            successful_indices = [row - 2 for row in successful_rows if row >= 2]  # row numbers are 1-based + header
            for idx in successful_indices:
                if 0 <= idx < len(result_df):
                    result_df.loc[idx, 'is_successful'] = True
            
            # Add error reasons for failed rows
            error_dict = {}
            for error in errors:
                error_idx = error.row_number - 2  # Convert to 0-based indexing
                if 0 <= error_idx < len(result_df):
                    error_dict[error_idx] = error.error_message
            
            for idx, reason in error_dict.items():
                result_df.loc[idx, 'reason'] = reason
            
            # Generate unique filename for result file
            result_filename = f"result_{job_id}_{uuid.uuid4().hex[:8]}.xlsx"
            
            # Create results directory if it doesn't exist
            results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "upload_results")
            os.makedirs(results_dir, exist_ok=True)
            
            result_file_path = os.path.join(results_dir, result_filename)
            
            # Save to Excel file
            with pd.ExcelWriter(result_file_path, engine='openpyxl') as writer:
                result_df.to_excel(writer, sheet_name='Results', index=False)
            
            logger.info(f"Generated result Excel file: {result_file_path}")
            return result_file_path
            
        except Exception as e:
            logger.error(f"Error generating result Excel file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to generate result file: {str(e)}")
    
    def validate_excel_data_integrity(self, df: pd.DataFrame) -> List[str]:
        """
        Perform additional data integrity checks on the Excel data.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            List[str]: List of integrity warnings
        """
        warnings = []
        
        try:
            # Check for duplicate questions
            if 'Question_text' in df.columns:
                duplicate_questions = df[df.duplicated(subset=['Question_text'], keep=False)]
                if not duplicate_questions.empty:
                    warnings.append(f"Found {len(duplicate_questions)} duplicate questions based on question text")
            
            # Check for inconsistent chapter-topic relationships
            if all(col in df.columns for col in ['chapter_name', 'topic_name']):
                chapter_topic_combos = df.groupby('chapter_name')['topic_name'].nunique()
                inconsistent_chapters = chapter_topic_combos[chapter_topic_combos > 10]  # Arbitrary threshold
                if not inconsistent_chapters.empty:
                    warnings.append(f"Some chapters have many topics which might indicate data inconsistency")
            
            # Check for missing answer options
            option_columns = ['answer_option_a', 'answer_option_b', 'answer_option_c', 'answer_option_d']
            if all(col in df.columns for col in option_columns):
                for idx, row in df.iterrows():
                    empty_options = sum(1 for col in option_columns if pd.isna(row[col]) or str(row[col]).strip() == "")
                    if empty_options > 0:
                        warnings.append(f"Row {idx + 2} has {empty_options} empty answer options")
                        break  # Only report first occurrence to avoid spam
            
        except Exception as e:
            logger.warning(f"Error during data integrity validation: {str(e)}")
            warnings.append("Could not complete all data integrity checks")
        
        return warnings
    
    async def process_excel_row(
        self, 
        row: pd.Series, 
        row_number: int,
        db: AsyncSession, 
        user: User
    ) -> Tuple[Optional[Questions], Optional[RowError]]:
        """
        Process a single Excel row and create a question if valid.
        
        Args:
            row: Pandas Series representing the row
            row_number: Row number for error reporting
            db: Database session
            user: User performing the upload
            
        Returns:
            Tuple[Optional[Questions], Optional[RowError]]: Created question or error
            
        8.1-8.4
        """
        try:
            # Normalize row data
            row_data = {}
            for col in row.index:
                row_data[col.strip()] = self.normalize_text_data(row[col])
            
            # Validate required fields
            validation_error = self.validate_required_fields(row_data, row_number)
            if validation_error:
                return None, validation_error
            
            # Validate data types and formats
            data_type_error = self.validate_data_types(row_data, row_number)
            if data_type_error:
                return None, data_type_error
            
            # Lookup/create master data entries
            board = None
            state = None
            medium = None
            subject = None
            cognitive_learning = None
            difficulty = None
            
            try:
                # Board lookup/creation (cached)
                board = await self.get_cached_board(
                    row_data["Board"], db, user.id
                )
                
                # State lookup/creation (cached)
                state = await self.get_cached_state(
                    row_data["State"], db, user.id
                )
                
                # Medium lookup/creation (cached)
                medium = await self.get_cached_medium(
                    row_data["Medium"], db, user.id
                )
                
                # Subject lookup/create (cached)
                subject = await self.get_cached_subject(
                    row_data["Subject"], 
                    row_data["Class"], 
                    medium.id, 
                    db, 
                    user.id
                )
                
                # Cognitive Learning lookup/creation (cached)
                cognitive_learning = await self.get_cached_cognitive_learning(
                    row_data["cognitive learning"], db, user.id
                )
                
                # Difficulty lookup/creation (cached)
                difficulty = await self.get_cached_difficulty(
                    row_data["difficulty"], db, user.id
                )
                
            except Exception as e:
                logger.error(f"Error looking up master data for row {row_number}: {str(e)}")
                return None, RowError(
                    row_number=row_number,
                    error_type=ValidationErrorType.LOOKUP_FAILED,
                    error_message=f"Master data lookup failed: {str(e)}",
                    row_data=row_data
                )
            
            # Verify all required variables are set
            if not all([board, state, medium, subject, cognitive_learning, difficulty]):
                logger.error(f"Missing required master data for row {row_number}")
                return None, RowError(
                    row_number=row_number,
                    error_type=ValidationErrorType.LOOKUP_FAILED,
                    error_message="Required master data lookup failed",
                    row_data=row_data
                )
            
            # Generate codes
            try:
                chapter_code = await self.code_service.get_or_create_chapter_code(
                    row_data["chapter_name"], db
                )
                topic_code = await self.code_service.get_or_create_topic_code(
                    row_data["topic_name"], chapter_code, db
                )
                subtopic_code = await self.code_service.get_or_create_subtopic_code(
                    row_data["subtopic_name"], topic_code, db
                )
                taxonomy_code = self.code_service.generate_taxonomy_code(
                    chapter_code, topic_code, subtopic_code,
                    board.id, state.id, medium.id, row_data["Class"], subject.id
                )
                
            except Exception as e:
                logger.error(f"Error generating codes for row {row_number}: {str(e)}")
                return None, RowError(
                    row_number=row_number,
                    error_type=ValidationErrorType.PROCESSING_ERROR,
                    error_message=f"Code generation failed: {str(e)}",
                    row_data=row_data
                )
            
            # Create or get taxonomy entry
            taxonomy = await self.create_taxonomy_entry(
                row_data, chapter_code, topic_code, subtopic_code, taxonomy_code,
                subject, medium, board, state, db, user
            )
            
            # Create question entry
            question = await self.create_question_entry(
                row_data, taxonomy, cognitive_learning, difficulty, board, state, db, user
            )
            
            logger.info(f"Successfully processed row {row_number}, created question {question.qmt_question_code}")
            return question, None
            
        except Exception as e:
            logger.error(f"Unexpected error processing row {row_number}: {str(e)}")
            return None, RowError(
                row_number=row_number,
                error_type=ValidationErrorType.PROCESSING_ERROR,
                error_message=f"Unexpected error: {str(e)}",
                row_data=row_data if 'row_data' in locals() else {}
            )
    
    async def create_taxonomy_entry(
        self,
        row_data: Dict[str, Any],
        chapter_code: str,
        topic_code: str,
        subtopic_code: str,
        taxonomy_code: str,
        subject: Subject,
        medium: Medium,
        board: Board,
        state: State,
        db: AsyncSession,
        user: User
    ) -> Taxonomy:
        """
        Create or retrieve taxonomy entry for the question.
        
        Args:
            row_data: Normalized row data
            chapter_code: Generated chapter code
            topic_code: Generated topic code
            subtopic_code: Generated subtopic code
            taxonomy_code: Generated taxonomy code
            subject: Subject entity
            medium: Medium entity
            board: Board entity
            state: State entity
            db: Database session
            user: User performing the upload
            
        Returns:
            Taxonomy: Created or existing taxonomy entry
        """
        try:
            # Check if taxonomy already exists
            stmt = select(Taxonomy).where(Taxonomy.stm_taxonomy_code == taxonomy_code)
            result = await db.execute(stmt)
            existing_taxonomy = result.scalar_one_or_none()
            
            if existing_taxonomy:
                return existing_taxonomy
            
            # Create new taxonomy entry
            taxonomy = Taxonomy(
                stm_taxonomy_code=taxonomy_code,
                stm_subject_id=subject.id,
                stm_medium_id=medium.id,
                stm_standard=row_data["Class"],
                stm_chapter_code=chapter_code,
                stm_chapter_name=row_data["chapter_name"],
                stm_topic_code=topic_code,
                stm_topic_name=row_data["topic_name"],
                stm_subtopic_code=subtopic_code,
                stm_subtopic_name=row_data["subtopic_name"],
                board_id=board.id,
                state_id=state.id,
                created_by=user.id,
                updated_by=user.id
            )
            
            db.add(taxonomy)
            await db.flush()
            await db.refresh(taxonomy)
            
            logger.info(f"Created new taxonomy entry: {taxonomy_code}")
            return taxonomy
            
        except Exception as e:
            logger.error(f"Error creating taxonomy entry: {str(e)}")
            raise
    
    async def create_question_entry(
        self,
        row_data: Dict[str, Any],
        taxonomy: Taxonomy,
        cognitive_learning: CognitiveLearning,
        difficulty: Difficulty,
        board: Board,
        state: State,
        db: AsyncSession,
        user: User
    ) -> Questions:
        """
        Create question entry with all relationships.
        
        Args:
            row_data: Normalized row data
            taxonomy: Taxonomy entity
            cognitive_learning: CognitiveLearning entity
            difficulty: Difficulty entity
            board: Board entity
            state: State entity
            db: Database session
            user: User performing the upload
            
        Returns:
            Questions: Created question entry
        """
        try:
            # Generate question ID and code
            question_id = await self.code_service.get_next_question_id(db)
            question_code = self.code_service.generate_question_code(question_id)
            
            # Load user context for organizational assignment
            user_context = await rbac_middleware.load_user_context(db, user)
            
            # Create question entry
            question = Questions(
                qmt_question_code=question_code,
                qmt_question_text=self._clean_text(row_data["Question_text"]),
                qmt_option1=self._clean_text(row_data["answer_option_a"]),
                qmt_option2=self._clean_text(row_data["answer_option_b"]),
                qmt_option3=self._clean_text(row_data["answer_option_c"]),
                qmt_option4=self._clean_text(row_data["answer_option_d"]),
                qmt_correct_answer=row_data["correct_answer"],
                qmt_marks=1,  # Default value
                qmt_format_id=1,  # Default format_id
                qmt_type_id=1,  # Default type_id
                qmt_taxonomy_id=taxonomy.id,
                qmt_taxonomy_code=taxonomy.stm_taxonomy_code,
                qmt_is_active=True,
                status="Approved",  # Set default status to Approved
                cognitive_learning_id=cognitive_learning.id,
                difficulty_id=difficulty.id,
                # Direct master data references
                subject_id=taxonomy.stm_subject_id,
                medium_id=taxonomy.stm_medium_id,
                board_id=board.id,
                state_id=state.id,
                # Associate with user's organizational context
                organization_id=user_context.organizational_scope["organization_id"],
                block_id=user_context.organizational_scope["block_id"],
                school_id=user_context.organizational_scope["school_id"],
                created_by=user.id,
                updated_by=user.id
            )
            
            db.add(question)
            await db.flush()
            await db.refresh(question)
            
            logger.info(f"Created new question: {question_code}")
            return question
            
        except Exception as e:
            logger.error(f"Error creating question entry: {str(e)}")
            raise
    
    async def process_excel_upload(
        self, 
        file_path: str, 
        db: AsyncSession, 
        user: User
    ) -> UploadResult:
        """
        Process complete Excel upload with row-by-row processing and error handling.
        
        Args:
            file_path: Path to the Excel file
            db: Database session
            user: User performing the upload
            
        Returns:
            UploadResult: Complete upload result with success/error counts
        """
        try:
            # Load Excel file
            df = await self.load_excel(file_path)
            
            # Validate Excel structure
            validation_result = await self.validate_excel_structure(df)
            if not validation_result.is_valid:
                return UploadResult(
                    success_count=0,
                    error_count=0,
                    errors=[],
                    message=validation_result.error_message
                )
            
            # Perform data integrity checks
            integrity_warnings = self.validate_excel_data_integrity(df)
            if integrity_warnings:
                logger.warning(f"Data integrity warnings: {'; '.join(integrity_warnings)}")
            
            # Initialize counters and error tracking
            success_count = 0
            error_count = 0
            errors: List[RowError] = []
            
            # Process each row
            for index, row in df.iterrows():
                row_number = index + 2  # Excel row number (1-based + header)
                
                try:
                    question, error = await self.process_excel_row(
                        row, row_number, db, user
                    )
                    
                    if question:
                        success_count += 1
                        # Commit successful question creation
                        await db.commit()
                    else:
                        error_count += 1
                        if error:
                            errors.append(error)
                        # Rollback failed transaction
                        await db.rollback()
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"Unexpected error processing row {row_number}: {str(e)}")
                    errors.append(RowError(
                        row_number=row_number,
                        error_type=ValidationErrorType.PROCESSING_ERROR,
                        error_message=f"Unexpected error: {str(e)}",
                        row_data={}
                    ))
                    await db.rollback()
            
            # Clear code generation caches
            self.code_service.clear_caches()
            
            # Generate result message
            total_rows = success_count + error_count
            if error_count == 0:
                message = f"Successfully processed all {success_count} questions"
            else:
                message = f"Processed {total_rows} rows: {success_count} successful, {error_count} errors"
            
            return UploadResult(
                success_count=success_count,
                error_count=error_count,
                errors=errors,
                message=message
            )
            
        except Exception as e:
            logger.error(f"Error processing Excel upload: {str(e)}")
            return UploadResult(
                success_count=0,
                error_count=0,
                errors=[],
                message=f"Upload failed: {str(e)}"
            )
    
    async def process_excel_upload_async(
        self, 
        file_path: str, 
        job_id: str,
        db: AsyncSession, 
        user: User
    ) -> None:
        """
        Process Excel upload asynchronously with job status tracking.
        
        Args:
            file_path: Path to the Excel file
            job_id: Job ID for status tracking
            db: Database session
            user: User performing the upload
        """
        from app.services.job_service import JobService
        
        try:
            # Update job status to processing
            from app.models.master import JobStatusEnum
            await JobService.update_job_status(job_id, JobStatusEnum.PROCESSING, db)
            
            # Load Excel file to get total row count
            df = await self.load_excel(file_path)
            total_rows = len(df)
            
            # Update job with total rows
            await JobService.update_job_progress(
                job_id, 0, 0, 0, total_rows, db
            )
            
            # Validate Excel structure
            validation_result = await self.validate_excel_structure(df)
            if not validation_result.is_valid:
                await JobService.fail_job(
                    job_id, 
                    validation_result.error_message, 
                    db
                )
                return
            
            # Initialize counters and error tracking
            success_count = 0
            error_count = 0
            errors: List[RowError] = []
            processed_count = 0
            successful_rows: List[int] = []  # Track successful row numbers
            
            # Process each row with progress updates
            for index, row in df.iterrows():
                row_number = index + 2  # Excel row number (1-based + header)
                
                try:
                    question, error = await self.process_excel_row(
                        row, row_number, db, user
                    )
                    
                    if question:
                        success_count += 1
                        successful_rows.append(row_number)  # Track successful row
                    else:
                        error_count += 1
                        if error:
                            errors.append(error)
                    
                    processed_count += 1
                    
                    # Commit in batches of 50 rows for better performance
                    if processed_count % 50 == 0:
                        await db.commit()
                    
                    # Update progress every 10 rows or on last row
                    if processed_count % 10 == 0 or processed_count == total_rows:
                        await JobService.update_job_progress(
                            job_id, processed_count, success_count, error_count, db=db
                        )
                        
                except Exception as e:
                    error_count += 1
                    processed_count += 1
                    logger.error(f"Unexpected error processing row {row_number}: {str(e)}")
                    errors.append(RowError(
                        row_number=row_number,
                        error_type=ValidationErrorType.PROCESSING_ERROR,
                        error_message=f"Unexpected error: {str(e)}",
                        row_data={}
                    ))
            
            # Final commit for any remaining changes
            await db.commit()
            
            # Clear code generation caches
            self.code_service.clear_caches()
            
            # Generate result Excel file with is_successful and reason columns
            result_file_path = None
            s3_url = None
            try:
                result_file_path = await self.generate_result_excel_file(
                    df, successful_rows, errors, job_id
                )
                logger.info(f"Generated result file: {result_file_path}")
                
                # Upload result file to S3
                if result_file_path:
                    filename = os.path.basename(result_file_path)
                    s3_key = s3_service.generate_s3_key(job_id, filename)
                    s3_url = await run_in_threadpool(
                        s3_service.upload_file, 
                        result_file_path, 
                        s3_key
                    )
                    logger.info(f"Uploaded result file to S3: {s3_url}")
                    
                    # Clean up local result file after successful S3 upload
                    try:
                        os.remove(result_file_path)
                        logger.info(f"Cleaned up local result file: {result_file_path}")
                    except Exception as cleanup_e:
                        logger.warning(f"Failed to clean up local result file: {cleanup_e}")
                        
            except Exception as e:
                logger.error(f"Failed to generate or upload result file: {str(e)}")
                # Continue with job completion even if result file generation/upload fails
            
            # Prepare error details for job completion
            error_details = None
            if errors:
                error_details = {
                    "error_summary": self.generate_error_summary(errors),
                    "errors": [
                        {
                            "row_number": error.row_number,
                            "error_type": error.error_type.value,
                            "error_message": error.error_message,
                            "row_data": error.row_data
                        }
                        for error in errors[:100]  # Limit to first 100 errors to avoid large payloads
                    ]
                }
            
            # Generate result message
            if error_count == 0:
                result_message = f"Successfully processed all {success_count} questions"
            else:
                result_message = f"Processed {total_rows} rows: {success_count} successful, {error_count} errors"
            
            # Complete the job with S3 location
            await JobService.complete_job(
                job_id, 
                result_message, 
                error_details, 
                db,
                result_loc=s3_url
            )
            
        except Exception as e:
            logger.error(f"Error in async Excel processing for job {job_id}: {str(e)}")
            await JobService.fail_job(
                job_id, 
                f"Processing failed: {str(e)}", 
                db
            )
        finally:
            # Clean up the uploaded file
            await JobService.cleanup_job_file(job_id, file_path, db)


# Create a singleton instance for use across the application
enhanced_upload_service = EnhancedUploadService()