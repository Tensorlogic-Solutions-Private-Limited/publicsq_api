"""
Master data lookup service for handling master table lookups and creation.
Provides text normalization and automatic creation of missing master data entries.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from fastapi import HTTPException, status

from app.models.master import Board, State, Medium, Subject, CognitiveLearning, Difficulty
from app.models.user import User


class MasterDataLookupService:
    """Service for looking up and creating master data entries with text normalization."""
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text by trimming whitespace and converting to lowercase for comparison."""
        if not text:
            return ""
        return text.strip().lower()
    
    @staticmethod
    async def get_or_create_board(
        board_name: str, 
        db: AsyncSession, 
        user_id: int
    ) -> Board:
        """
        Get existing board or create new one if not found.
        Performs case-insensitive lookup with text normalization.
        """
        if not board_name or not board_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Board name cannot be empty"
            )
        
        normalized_name = MasterDataLookupService._normalize_text(board_name)
        
        # Look for existing board (case-insensitive)
        result = await db.execute(
            select(Board).where(
                Board.board_name.ilike(f"%{normalized_name}%")
            )
        )
        existing_board = result.scalars().first()
        
        if existing_board:
            return existing_board
        
        # Create new board with original case preserved
        new_board = Board(
            board_name=board_name.strip(),
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_board)
        await db.flush()
        await db.refresh(new_board)
        
        return new_board
    
    @staticmethod
    async def get_or_create_state(
        state_name: str, 
        db: AsyncSession, 
        user_id: int
    ) -> State:
        """
        Get existing state or create new one if not found.
        Performs case-insensitive lookup with text normalization.
        """
        if not state_name or not state_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="State name cannot be empty"
            )
        
        normalized_name = MasterDataLookupService._normalize_text(state_name)
        
        # Look for existing state (case-insensitive)
        result = await db.execute(
            select(State).where(
                State.state_name.ilike(f"%{normalized_name}%")
            )
        )
        existing_state = result.scalars().first()
        
        if existing_state:
            return existing_state
        
        # Create new state with original case preserved
        new_state = State(
            state_name=state_name.strip(),
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_state)
        await db.flush()
        await db.refresh(new_state)
        
        return new_state
    
    @staticmethod
    async def get_or_create_medium(
        medium_name: str, 
        db: AsyncSession, 
        user_id: int
    ) -> Medium:
        """
        Get existing medium or create new one if not found.
        Performs case-insensitive lookup with text normalization.
        """
        if not medium_name or not medium_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Medium name cannot be empty"
            )
        
        normalized_name = MasterDataLookupService._normalize_text(medium_name)
        
        # Look for existing medium (case-insensitive)
        result = await db.execute(
            select(Medium).where(
                Medium.mmt_medium_name.ilike(f"%{normalized_name}%")
            )
        )
        existing_medium = result.scalars().first()
        
        if existing_medium:
            return existing_medium
        
        # Generate medium code (simple sequential approach)
        # Get the highest existing code and increment
        max_code_result = await db.execute(
            select(Medium.mmt_medium_code).order_by(Medium.mmt_medium_code.desc()).limit(1)
        )
        max_code = max_code_result.scalar()
        
        if max_code:
            # Extract numeric part and increment
            try:
                next_code_num = int(max_code) + 1
                new_code = str(next_code_num)
            except ValueError:
                # Fallback if code format is unexpected
                new_code = "3000"  # Start from 3000 as per existing pattern
        else:
            new_code = "2000"  # Default starting code
        
        # Create new medium with original case preserved
        new_medium = Medium(
            mmt_medium_code=new_code,
            mmt_medium_name=medium_name.strip(),
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_medium)
        await db.flush()
        await db.refresh(new_medium)
        
        return new_medium
    
    @staticmethod
    async def lookup_subject(
        subject_name: str, 
        db: AsyncSession
    ) -> Optional[Subject]:
        """
        Lookup subject by name with text normalization.
        Returns None if not found (does not create new subjects).
        """
        if not subject_name or not subject_name.strip():
            return None
        
        normalized_name = MasterDataLookupService._normalize_text(subject_name)
        
        # Look for existing subject (case-insensitive)
        result = await db.execute(
            select(Subject).where(
                Subject.smt_subject_name.ilike(f"%{normalized_name}%")
            )
        )
        
        return result.scalars().first()
    
    @staticmethod
    async def get_or_create_subject(
        subject_name: str,
        standard: str,
        medium_id: int,
        db: AsyncSession,
        user_id: int
    ) -> Subject:
        """
        Get existing subject or create a new one if not found.
        Looks for subject by BOTH name AND class/standard to ensure proper associations.
        
        Args:
            subject_name: Name of the subject
            standard: Class/standard (e.g., "10", "12")
            medium_id: ID of the medium
            db: Database session
            user_id: User ID for audit trail
            
        Returns:
            Subject: Existing or newly created subject for the specific class
        """
        if not subject_name or not subject_name.strip():
            raise ValueError("Subject name cannot be empty")
        
        subject_name_clean = subject_name.strip()
        
        # First try to find existing subject by BOTH name AND class
        result = await db.execute(
            select(Subject).where(
                and_(
                    Subject.smt_subject_name.ilike(f"%{subject_name_clean}%"),
                    Subject.smt_standard == standard,
                    Subject.smt_medium_id == medium_id
                )
            )
        )
        existing_subject = result.scalar_one_or_none()
        
        if existing_subject:
            return existing_subject
        
        # Subject doesn't exist for this class, create new one
        # Generate unique subject code
        count_result = await db.execute(select(Subject))
        existing_subjects = count_result.scalars().all()
        next_code_number = len(existing_subjects) + 3001  # Start from 3001
        
        # Create new subject for this specific class
        new_subject = Subject(
            smt_subject_code=str(next_code_number),
            smt_subject_name=subject_name_clean,
            smt_standard=standard,
            smt_medium_id=medium_id,
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_subject)
        await db.flush()  # Get the ID without committing
        await db.refresh(new_subject)
        
        return new_subject
    
    @staticmethod
    async def lookup_cognitive_learning(
        cognitive_learning_name: str, 
        db: AsyncSession
    ) -> Optional[CognitiveLearning]:
        """
        Lookup cognitive learning by name with text normalization.
        Returns None if not found (does not create new entries).
        """
        if not cognitive_learning_name or not cognitive_learning_name.strip():
            return None
        
        normalized_name = MasterDataLookupService._normalize_text(cognitive_learning_name)
        
        # Look for existing cognitive learning (case-insensitive)
        result = await db.execute(
            select(CognitiveLearning).where(
                CognitiveLearning.cognitive_learning_name.ilike(f"%{normalized_name}%")
            )
        )
        
        return result.scalars().first()
    
    @staticmethod
    async def get_or_create_cognitive_learning(
        cognitive_learning_name: str, 
        db: AsyncSession, 
        user_id: int
    ) -> CognitiveLearning:
        """
        Get existing cognitive learning or create new one if not found.
        Performs case-insensitive lookup with text normalization.
        """
        if not cognitive_learning_name or not cognitive_learning_name.strip():
            raise ValueError("Cognitive learning name cannot be empty")
        
        # First try to find existing cognitive learning
        existing_cognitive_learning = await MasterDataLookupService.lookup_cognitive_learning(
            cognitive_learning_name, db
        )
        if existing_cognitive_learning:
            return existing_cognitive_learning
        
        # Create new cognitive learning with original case preserved
        new_cognitive_learning = CognitiveLearning(
            cognitive_learning_name=cognitive_learning_name.strip(),
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_cognitive_learning)
        await db.flush()
        await db.refresh(new_cognitive_learning)
        
        return new_cognitive_learning
    
    
    @staticmethod
    async def lookup_difficulty(
        difficulty_name: str, 
        db: AsyncSession
    ) -> Optional[Difficulty]:
        """
        Lookup difficulty by name with text normalization.
        Returns None if not found (does not create new entries).
        """
        if not difficulty_name or not difficulty_name.strip():
            return None
        
        normalized_name = MasterDataLookupService._normalize_text(difficulty_name)
        
        # Look for existing difficulty (case-insensitive)
        result = await db.execute(
            select(Difficulty).where(
                Difficulty.difficulty_name.ilike(f"%{normalized_name}%")
            )
        )
        
        return result.scalars().first()
    
    @staticmethod
    async def get_or_create_difficulty(
        difficulty_name: str, 
        db: AsyncSession, 
        user_id: int
    ) -> Difficulty:
        """
        Get existing difficulty or create new one if not found.
        Performs case-insensitive lookup with text normalization.
        """
        if not difficulty_name or not difficulty_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Difficulty name cannot be empty"
            )
        
        # First try to find existing difficulty
        existing_difficulty = await MasterDataLookupService.lookup_difficulty(
            difficulty_name, db
        )
        if existing_difficulty:
            return existing_difficulty
        
        # Create new difficulty with original case preserved
        new_difficulty = Difficulty(
            difficulty_name=difficulty_name.strip(),
            created_by=user_id,
            updated_by=user_id
        )
        
        db.add(new_difficulty)
        await db.flush()
        await db.refresh(new_difficulty)
        
        return new_difficulty
    
    @staticmethod
    async def validate_required_lookups(
        subject_name: str,
        cognitive_learning_name: str,
        difficulty_name: str,
        db: AsyncSession
    ) -> dict:
        """
        Validate that all required lookup values exist in the database.
        Returns a dictionary with lookup results and any errors.
        """
        errors = []
        results = {}
        
        # Lookup subject
        subject = await MasterDataLookupService.lookup_subject(subject_name, db)
        if not subject:
            errors.append(f"Subject '{subject_name}' not found in master data")
        results['subject'] = subject
        
        # Lookup cognitive learning
        cognitive_learning = await MasterDataLookupService.lookup_cognitive_learning(
            cognitive_learning_name, db
        )
        if not cognitive_learning:
            errors.append(f"Cognitive learning '{cognitive_learning_name}' not found in master data")
        results['cognitive_learning'] = cognitive_learning
        
        # Lookup difficulty
        difficulty = await MasterDataLookupService.lookup_difficulty(difficulty_name, db)
        if not difficulty:
            errors.append(f"Difficulty '{difficulty_name}' not found in master data")
        results['difficulty'] = difficulty
        
        results['errors'] = errors
        results['is_valid'] = len(errors) == 0
        
        return results
    
    @staticmethod
    async def process_row_master_data(
        row_data: dict,
        db: AsyncSession,
        user_id: int
    ) -> dict:
        """
        Process all master data lookups for a single Excel row.
        Returns a dictionary with all resolved master data or errors.
        
        This method implements requirement 1.2 (auto-creation) and 8.1 (error handling).
        """
        results = {
            'board': None,
            'state': None,
            'medium': None,
            'subject': None,
            'cognitive_learning': None,
            'difficulty': None,
            'errors': [],
            'is_valid': True
        }
        
        try:
            # Process Board (auto-create if missing)
            if row_data.get('Board'):
                results['board'] = await MasterDataLookupService.get_or_create_board(
                    row_data['Board'], db, user_id
                )
            else:
                results['errors'].append("Board field is required but empty")
            
            # Process State (auto-create if missing)
            if row_data.get('State'):
                results['state'] = await MasterDataLookupService.get_or_create_state(
                    row_data['State'], db, user_id
                )
            else:
                results['errors'].append("State field is required but empty")
            
            # Process Medium (auto-create if missing)
            if row_data.get('Medium'):
                results['medium'] = await MasterDataLookupService.get_or_create_medium(
                    row_data['Medium'], db, user_id
                )
            else:
                results['errors'].append("Medium field is required but empty")
            
            # Process Subject (auto-create if missing)
            if row_data.get('Subject'):
                # We need medium and standard for subject creation
                if results.get('medium') and row_data.get('Class'):
                    results['subject'] = await MasterDataLookupService.get_or_create_subject(
                        row_data['Subject'], 
                        row_data['Class'], 
                        results['medium'].id, 
                        db, 
                        user_id
                    )
                else:
                    results['errors'].append("Medium and Class are required for subject creation")
            else:
                results['errors'].append("Subject field is required but empty")
            
            # Process Cognitive Learning (lookup only - do not create)
            if row_data.get('cognitive_learning'):
                results['cognitive_learning'] = await MasterDataLookupService.lookup_cognitive_learning(
                    row_data['cognitive_learning'], db
                )
                if not results['cognitive_learning']:
                    results['errors'].append(f"Cognitive learning '{row_data['cognitive_learning']}' not found in master data")
            else:
                results['errors'].append("Cognitive learning field is required but empty")
            
            # Process Difficulty (lookup only - do not create)
            if row_data.get('difficulty'):
                results['difficulty'] = await MasterDataLookupService.lookup_difficulty(
                    row_data['difficulty'], db
                )
                if not results['difficulty']:
                    results['errors'].append(f"Difficulty '{row_data['difficulty']}' not found in master data")
            else:
                results['errors'].append("Difficulty field is required but empty")
                
        except Exception as e:
            results['errors'].append(f"Error processing master data: {str(e)}")
        
        results['is_valid'] = len(results['errors']) == 0
        return results


# Create a singleton instance for use across the application
master_data_lookup_service = MasterDataLookupService()