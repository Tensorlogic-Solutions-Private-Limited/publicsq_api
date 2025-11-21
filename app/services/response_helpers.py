"""
Response helper classes for building API response data.

This module provides domain-specific helper classes to centralize response building logic
and eliminate manual Pydantic model construction across endpoints. Each helper handles
audit field resolution and relationship serialization for its specific domain model.
"""

from typing import Dict, Any, Optional, List, Union
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import time
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class QueryOptimizer:
    """
    Utility class for optimizing database queries for response helpers.
    
    This class provides optimized query methods that load all required relationships
    for response helpers in single queries, reducing N+1 query problems.
    """
    
    @staticmethod
    @asynccontextmanager
    async def monitor_query_performance(operation_name: str):
        """Context manager to monitor query performance."""
        start_time = time.time()
        try:
            yield
        finally:
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"Query performance - {operation_name}: {duration:.3f}s")
            
            # Log slow queries (> 1 second)
            if duration > 1.0:
                logger.warning(f"Slow query detected - {operation_name}: {duration:.3f}s")
    
    @staticmethod
    async def get_question_with_all_relationships(db: AsyncSession, question_id: int):
        """
        Get question with all relationships loaded for QuestionResponseHelper.
        
        This method uses optimized loading strategies to fetch all required relationships
        in a single query, preventing N+1 query issues.
        """
        async with QueryOptimizer.monitor_query_performance("get_question_with_all_relationships"):
            from app.models.master import Questions
            
            stmt = (
                select(Questions)
                .options(
                    # Core relationships for question data
                    joinedload(Questions.subject),
                    joinedload(Questions.format),
                    joinedload(Questions.type),
                    joinedload(Questions.taxonomy),
                    joinedload(Questions.cognitive_learning),
                    joinedload(Questions.difficulty),
                    joinedload(Questions.medium),
                    joinedload(Questions.board),
                    joinedload(Questions.state),
                    
                    # Organizational relationships
                    joinedload(Questions.organization),
                    joinedload(Questions.block),
                    joinedload(Questions.school),
                    
                    # Audit field relationships
                    joinedload(Questions.created_by_user),
                    joinedload(Questions.updated_by_user)
                )
                .where(Questions.id == question_id)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_question_by_code_with_all_relationships(db: AsyncSession, question_code: str):
        """
        Get question by code with all relationships loaded for QuestionResponseHelper.
        """
        async with QueryOptimizer.monitor_query_performance("get_question_by_code_with_all_relationships"):
            from app.models.master import Questions
            
            stmt = (
                select(Questions)
                .options(
                    # Core relationships for question data
                    joinedload(Questions.subject),
                    joinedload(Questions.format),
                    joinedload(Questions.type),
                    joinedload(Questions.taxonomy),
                    joinedload(Questions.cognitive_learning),
                    joinedload(Questions.difficulty),
                    joinedload(Questions.medium),
                    joinedload(Questions.board),
                    joinedload(Questions.state),
                    
                    # Organizational relationships
                    joinedload(Questions.organization),
                    joinedload(Questions.block),
                    joinedload(Questions.school),
                    
                    # Audit field relationships
                    joinedload(Questions.created_by_user),
                    joinedload(Questions.updated_by_user)
                )
                .where(Questions.qmt_question_code == question_code)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_questions_with_all_relationships(db: AsyncSession, question_ids: List[int]):
        """
        Get multiple questions with all relationships loaded for QuestionResponseHelper.
        
        Uses selectinload for collections to optimize bulk loading.
        """
        async with QueryOptimizer.monitor_query_performance("get_questions_with_all_relationships"):
            from app.models.master import Questions
            
            stmt = (
                select(Questions)
                .options(
                    # Core relationships for question data
                    joinedload(Questions.subject),
                    joinedload(Questions.format),
                    joinedload(Questions.type),
                    joinedload(Questions.taxonomy),
                    joinedload(Questions.cognitive_learning),
                    joinedload(Questions.difficulty),
                    joinedload(Questions.medium),
                    joinedload(Questions.board),
                    joinedload(Questions.state),
                    
                    # Organizational relationships
                    joinedload(Questions.organization),
                    joinedload(Questions.block),
                    joinedload(Questions.school),
                    
                    # Audit field relationships
                    joinedload(Questions.created_by_user),
                    joinedload(Questions.updated_by_user)
                )
                .where(Questions.id.in_(question_ids))
            )
            
            result = await db.execute(stmt)
            return result.unique().scalars().all()
    
    @staticmethod
    async def get_organization_with_all_relationships(db: AsyncSession, organization_id: int):
        """
        Get organization with all relationships loaded for OrganizationResponseHelper.
        """
        async with QueryOptimizer.monitor_query_performance("get_organization_with_all_relationships"):
            from app.models.organization import Organization
            
            stmt = (
                select(Organization)
                .options(
                    # Hierarchy relationships - use selectinload for collections
                    selectinload(Organization.blocks).joinedload("created_by_user"),
                    selectinload(Organization.blocks).joinedload("updated_by_user"),
                    selectinload(Organization.schools).joinedload("created_by_user"),
                    selectinload(Organization.schools).joinedload("updated_by_user"),
                    
                    # Audit field relationships
                    joinedload(Organization.created_by_user),
                    joinedload(Organization.updated_by_user)
                )
                .where(Organization.id == organization_id)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_organization_by_uuid_with_all_relationships(db: AsyncSession, organization_uuid):
        """
        Get organization by UUID with all relationships loaded for OrganizationResponseHelper.
        """
        async with QueryOptimizer.monitor_query_performance("get_organization_by_uuid_with_all_relationships"):
            from app.models.organization import Organization
            
            stmt = (
                select(Organization)
                .options(
                    # Hierarchy relationships - use selectinload for collections
                    selectinload(Organization.blocks).joinedload("created_by_user"),
                    selectinload(Organization.blocks).joinedload("updated_by_user"),
                    selectinload(Organization.schools).joinedload("created_by_user"),
                    selectinload(Organization.schools).joinedload("updated_by_user"),
                    
                    # Audit field relationships
                    joinedload(Organization.created_by_user),
                    joinedload(Organization.updated_by_user)
                )
                .where(Organization.uuid == organization_uuid)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_block_with_all_relationships(db: AsyncSession, block_id: int):
        """
        Get block with all relationships loaded for BlockResponseHelper.
        """
        async with QueryOptimizer.monitor_query_performance("get_block_with_all_relationships"):
            from app.models.organization import Block
            
            stmt = (
                select(Block)
                .options(
                    # Organization relationship
                    joinedload(Block.organization).joinedload("created_by_user"),
                    joinedload(Block.organization).joinedload("updated_by_user"),
                    
                    # State relationship
                    joinedload(Block.state),
                    
                    # Schools relationship - use selectinload for collection
                    selectinload(Block.schools).joinedload("created_by_user"),
                    selectinload(Block.schools).joinedload("updated_by_user"),
                    
                    # Audit field relationships
                    joinedload(Block.created_by_user),
                    joinedload(Block.updated_by_user)
                )
                .where(Block.id == block_id)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()
    
    @staticmethod
    async def get_school_with_all_relationships(db: AsyncSession, school_id: int):
        """
        Get school with all relationships loaded for SchoolResponseHelper.
        """
        async with QueryOptimizer.monitor_query_performance("get_school_with_all_relationships"):
            from app.models.organization import School
            
            stmt = (
                select(School)
                .options(
                    # Organization and block relationships
                    joinedload(School.organization).joinedload("created_by_user"),
                    joinedload(School.organization).joinedload("updated_by_user"),
                    joinedload(School.block).joinedload("created_by_user"),
                    joinedload(School.block).joinedload("updated_by_user"),
                    
                    # State relationship
                    joinedload(School.state),
                    
                    # Audit field relationships
                    joinedload(School.created_by_user),
                    joinedload(School.updated_by_user)
                )
                .where(School.id == school_id)
            )
            
            result = await db.execute(stmt)
            return result.unique().scalar_one_or_none()


class BaseResponseHelper:
    """
    Base class providing common patterns and utilities for response helpers.
    
    This class contains shared functionality for audit field resolution and
    common response building patterns that can be used across all domain-specific helpers.
    """
    
    @staticmethod
    def _resolve_audit_fields(obj: Any) -> Dict[str, Optional[Union[str, Any]]]:
        """
        Resolve audit fields (created_by/updated_by) to usernames and include timestamps.
        
        Args:
            obj: SQLAlchemy model instance with audit fields
            
        Returns:
            Dictionary containing resolved audit field data
        """
        try:
            return {
                'created_by': obj.created_by_user.username if hasattr(obj, 'created_by_user') and obj.created_by_user else None,
                'updated_by': obj.updated_by_user.username if hasattr(obj, 'updated_by_user') and obj.updated_by_user else None,
                'created_at': obj.created_at if hasattr(obj, 'created_at') else None,
                'updated_at': obj.updated_at if hasattr(obj, 'updated_at') else None
            }
        except AttributeError as e:
            logger.warning(f"Error resolving audit fields for object {type(obj).__name__}: {e}")
            return {
                'created_by': None,
                'updated_by': None,
                'created_at': getattr(obj, 'created_at', None),
                'updated_at': getattr(obj, 'updated_at', None)
            }
    
    @staticmethod
    def _safe_get_attr(obj: Any, attr: str, default: Any = None) -> Any:
        """
        Safely get attribute from object with default fallback.
        
        Args:
            obj: Object to get attribute from
            attr: Attribute name
            default: Default value if attribute doesn't exist
            
        Returns:
            Attribute value or default
        """
        return getattr(obj, attr, default)
    
    @staticmethod
    def _safe_str_uuid(uuid_obj: Any) -> Optional[str]:
        """
        Safely convert UUID object to string.
        
        Args:
            uuid_obj: UUID object or None
            
        Returns:
            String representation of UUID or None
        """
        return str(uuid_obj) if uuid_obj is not None else None
    
    @staticmethod
    def _build_minimal_object_data(obj: Any, fields: List[str]) -> Dict[str, Any]:
        """
        Build minimal object data with specified fields.
        
        Args:
            obj: SQLAlchemy model instance
            fields: List of field names to include
            
        Returns:
            Dictionary with specified fields
        """
        if obj is None:
            return None
            
        data = {}
        for field in fields:
            if field == 'uuid':
                data[field] = BaseResponseHelper._safe_str_uuid(getattr(obj, field, None))
            else:
                data[field] = BaseResponseHelper._safe_get_attr(obj, field)
        
        return data
    
    @staticmethod
    def _handle_response_error(obj: Any, error: Exception, minimal_fields: List[str] = None) -> Dict[str, Any]:
        """
        Handle errors during response building by returning minimal safe response.
        
        Args:
            obj: SQLAlchemy model instance
            error: Exception that occurred
            minimal_fields: List of minimal fields to include in fallback response
            
        Returns:
            Minimal safe response dictionary
        """
        obj_type = type(obj).__name__
        obj_id = getattr(obj, 'id', 'unknown')
        
        # Structured logging with context
        logger.error(
            "Response building error",
            extra={
                'model_type': obj_type,
                'model_id': obj_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'operation': 'build_response_data'
            }
        )
        
        # Default minimal fields if not specified
        if minimal_fields is None:
            minimal_fields = ['id', 'uuid']
        
        try:
            minimal_response = BaseResponseHelper._build_minimal_object_data(obj, minimal_fields)
            
            # Log successful fallback
            logger.info(
                "Fallback response created",
                extra={
                    'model_type': obj_type,
                    'model_id': obj_id,
                    'fallback_fields': minimal_fields
                }
            )
            
            return minimal_response
            
        except Exception as fallback_error:
            # Critical error - even minimal response failed
            logger.critical(
                "Minimal response building failed",
                extra={
                    'model_type': obj_type,
                    'model_id': obj_id,
                    'original_error': str(error),
                    'fallback_error': str(fallback_error)
                }
            )
            
            return {
                'id': getattr(obj, 'id', None),
                'uuid': None,
                'error': 'Failed to build response data',
                'error_type': 'critical_response_failure'
            }
    
    @staticmethod
    def _log_helper_usage(helper_name: str, model_type: str, model_id: Any, operation: str):
        """
        Log helper usage for monitoring and debugging.
        
        Args:
            helper_name: Name of the helper class
            model_type: Type of model being processed
            model_id: ID of the model
            operation: Operation being performed
        """
        logger.debug(
            "Helper usage",
            extra={
                'helper_name': helper_name,
                'model_type': model_type,
                'model_id': model_id,
                'operation': operation
            }
        )
    
    @staticmethod
    def _log_relationship_error(obj: Any, relationship_name: str, error: Exception):
        """
        Log relationship processing errors with context.
        
        Args:
            obj: SQLAlchemy model instance
            relationship_name: Name of the relationship that failed
            error: Exception that occurred
        """
        logger.warning(
            "Relationship processing error",
            extra={
                'model_type': type(obj).__name__,
                'model_id': getattr(obj, 'id', 'unknown'),
                'relationship': relationship_name,
                'error_type': type(error).__name__,
                'error_message': str(error)
            }
        )
    
    @staticmethod
    def _safe_process_relationship(obj: Any, relationship_name: str, processor_func, default_value=None):
        """
        Safely process a relationship with error handling and logging.
        
        Args:
            obj: SQLAlchemy model instance
            relationship_name: Name of the relationship
            processor_func: Function to process the relationship
            default_value: Default value if processing fails
            
        Returns:
            Processed relationship data or default value
        """
        try:
            relationship_obj = getattr(obj, relationship_name, None)
            if relationship_obj is None:
                return default_value
            
            return processor_func(relationship_obj)
            
        except AttributeError as e:
            BaseResponseHelper._log_relationship_error(obj, relationship_name, e)
            return default_value
        except Exception as e:
            BaseResponseHelper._log_relationship_error(obj, relationship_name, e)
            return default_value


class QuestionResponseHelper(BaseResponseHelper):
    """
    Helper for building question response data.
    
    This class handles the construction of question response dictionaries,
    including core question fields, audit field resolution, and relationship serialization.
    """
    
    @staticmethod
    def build_response_data(question) -> Dict[str, Any]:
        """
        Build complete question response data dictionary.
        
        Args:
            question: Questions SQLAlchemy model instance
            
        Returns:
            Dictionary containing complete question response data
        """
        # Log helper usage
        QuestionResponseHelper._log_helper_usage(
            'QuestionResponseHelper', 
            'Questions', 
            getattr(question, 'id', 'unknown'),
            'build_response_data'
        )
        
        try:
            # Base question fields - explicit field mapping for clarity and debuggability
            response_data = {
                'id': question.id,
                'uuid': QuestionResponseHelper._safe_str_uuid(question.uuid) if hasattr(question, 'uuid') else None,
                'qmt_question_code': QuestionResponseHelper._safe_get_attr(question, 'qmt_question_code', ''),
                'qmt_question_text': QuestionResponseHelper._safe_get_attr(question, 'qmt_question_text', ''),
                'qmt_option1': QuestionResponseHelper._safe_get_attr(question, 'qmt_option1', ''),
                'qmt_option2': QuestionResponseHelper._safe_get_attr(question, 'qmt_option2', ''),
                'qmt_option3': QuestionResponseHelper._safe_get_attr(question, 'qmt_option3', ''),
                'qmt_option4': QuestionResponseHelper._safe_get_attr(question, 'qmt_option4', ''),
                'qmt_correct_answer': QuestionResponseHelper._safe_get_attr(question, 'qmt_correct_answer', ''),
                'qmt_marks': QuestionResponseHelper._safe_get_attr(question, 'qmt_marks', 0),
                'qmt_is_active': QuestionResponseHelper._safe_get_attr(question, 'qmt_is_active', True),
                'status': QuestionResponseHelper._safe_get_attr(question, 'status', 'Approved'),
                

                
                # Foreign key IDs for reference
                'qmt_format_id': QuestionResponseHelper._safe_get_attr(question, 'qmt_format_id'),
                'qmt_type_id': QuestionResponseHelper._safe_get_attr(question, 'qmt_type_id'),
                'qmt_taxonomy_id': QuestionResponseHelper._safe_get_attr(question, 'qmt_taxonomy_id'),
                'qmt_taxonomy_code': QuestionResponseHelper._safe_get_attr(question, 'qmt_taxonomy_code', ''),
                'cognitive_learning_id': QuestionResponseHelper._safe_get_attr(question, 'cognitive_learning_id'),
                'difficulty_id': QuestionResponseHelper._safe_get_attr(question, 'difficulty_id'),
                'subject_id': QuestionResponseHelper._safe_get_attr(question, 'subject_id'),
                'medium_id': QuestionResponseHelper._safe_get_attr(question, 'medium_id'),
                'board_id': QuestionResponseHelper._safe_get_attr(question, 'board_id'),
                'state_id': QuestionResponseHelper._safe_get_attr(question, 'state_id'),
                'organization_id': QuestionResponseHelper._safe_get_attr(question, 'organization_id'),
                'block_id': QuestionResponseHelper._safe_get_attr(question, 'block_id'),
                'school_id': QuestionResponseHelper._safe_get_attr(question, 'school_id'),
            }
            
            # Add audit fields with username resolution
            try:
                audit_fields = QuestionResponseHelper._resolve_audit_fields(question)
                response_data.update(audit_fields)
            except Exception as e:
                QuestionResponseHelper._log_relationship_error(question, 'audit_fields', e)
                response_data.update({
                    'created_by': None,
                    'updated_by': None,
                    'created_at': QuestionResponseHelper._safe_get_attr(question, 'created_at'),
                    'updated_at': QuestionResponseHelper._safe_get_attr(question, 'updated_at')
                })
            
            # Add UUID fields for organizational context with safe processing
            response_data.update({
                'organization_uuid': QuestionResponseHelper._safe_process_relationship(
                    question, 'organization', 
                    lambda org: QuestionResponseHelper._safe_str_uuid(getattr(org, 'uuid', None))
                ),
                'block_uuid': QuestionResponseHelper._safe_process_relationship(
                    question, 'block',
                    lambda block: QuestionResponseHelper._safe_str_uuid(getattr(block, 'uuid', None))
                ),
                'school_uuid': QuestionResponseHelper._safe_process_relationship(
                    question, 'school',
                    lambda school: QuestionResponseHelper._safe_str_uuid(getattr(school, 'uuid', None))
                ),
            })
            
            # Add relationship serialization with safe processing
            response_data.update({
                'subject': QuestionResponseHelper._safe_process_relationship(
                    question, 'subject', QuestionResponseHelper._build_subject_data
                ),
                'format': QuestionResponseHelper._safe_process_relationship(
                    question, 'format', QuestionResponseHelper._build_format_data
                ),
                'type': QuestionResponseHelper._safe_process_relationship(
                    question, 'type', QuestionResponseHelper._build_type_data
                ),
                'taxonomy': QuestionResponseHelper._safe_process_relationship(
                    question, 'taxonomy', QuestionResponseHelper._build_taxonomy_data
                ),
                'cognitive_learning': QuestionResponseHelper._safe_process_relationship(
                    question, 'cognitive_learning', QuestionResponseHelper._build_cognitive_learning_data
                ),
                'difficulty': QuestionResponseHelper._safe_process_relationship(
                    question, 'difficulty', QuestionResponseHelper._build_difficulty_data
                ),
                'medium': QuestionResponseHelper._safe_process_relationship(
                    question, 'medium', QuestionResponseHelper._build_medium_data
                ),
                'board': QuestionResponseHelper._safe_process_relationship(
                    question, 'board', QuestionResponseHelper._build_board_data
                ),
                'state': QuestionResponseHelper._safe_process_relationship(
                    question, 'state', QuestionResponseHelper._build_state_data
                ),
                'organization': QuestionResponseHelper._safe_process_relationship(
                    question, 'organization', QuestionResponseHelper._build_organization_data
                ),
                'block': QuestionResponseHelper._safe_process_relationship(
                    question, 'block', QuestionResponseHelper._build_block_data
                ),
                'school': QuestionResponseHelper._safe_process_relationship(
                    question, 'school', QuestionResponseHelper._build_school_data
                ),
            })
            
            # Log successful response building
            logger.debug(
                "Question response built successfully",
                extra={
                    'question_id': question.id,
                    'question_code': response_data.get('qmt_question_code'),
                    'relationships_loaded': sum(1 for v in response_data.values() if v is not None and isinstance(v, dict))
                }
            )
            
            return response_data
            
        except Exception as e:
            # Handle errors gracefully by returning minimal response
            minimal_fields = ['id', 'uuid', 'qmt_question_code', 'qmt_question_text']
            return QuestionResponseHelper._handle_response_error(question, e, minimal_fields)
    
    @staticmethod
    def build_minimal_response_data(question) -> Dict[str, Any]:
        """
        Build minimal question response data for error scenarios or performance optimization.
        
        Args:
            question: Questions SQLAlchemy model instance
            
        Returns:
            Dictionary containing minimal question response data
        """
        QuestionResponseHelper._log_helper_usage(
            'QuestionResponseHelper', 
            'Questions', 
            getattr(question, 'id', 'unknown'),
            'build_minimal_response_data'
        )
        
        try:
            return {
                'id': question.id,
                'uuid': QuestionResponseHelper._safe_str_uuid(getattr(question, 'uuid', None)),
                'qmt_question_code': QuestionResponseHelper._safe_get_attr(question, 'qmt_question_code', ''),
                'qmt_question_text': QuestionResponseHelper._safe_get_attr(question, 'qmt_question_text', ''),
                'qmt_marks': QuestionResponseHelper._safe_get_attr(question, 'qmt_marks', 0),
                'status': QuestionResponseHelper._safe_get_attr(question, 'status', 'Approved'),
                'created_at': QuestionResponseHelper._safe_get_attr(question, 'created_at'),
                'updated_at': QuestionResponseHelper._safe_get_attr(question, 'updated_at'),
                'created_by': None,
                'updated_by': None
            }
        except Exception as e:
            logger.error(f"Failed to build minimal question response: {e}")
            return {
                'id': getattr(question, 'id', None),
                'uuid': None,
                'qmt_question_code': '',
                'error': 'Failed to build minimal response'
            }
    
    @staticmethod
    def _build_subject_data(subject) -> Dict[str, Any]:
        """Build subject data for question responses."""
        if subject is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(subject, 'id'),
            'smt_subject_code': QuestionResponseHelper._safe_get_attr(subject, 'smt_subject_code', ''),
            'smt_subject_name': QuestionResponseHelper._safe_get_attr(subject, 'smt_subject_name', ''),
            'smt_standard': QuestionResponseHelper._safe_get_attr(subject, 'smt_standard', ''),
        }
    
    @staticmethod
    def _build_format_data(format_obj) -> Dict[str, Any]:
        """Build format data for question responses."""
        if format_obj is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(format_obj, 'id'),
            'qfm_format_code': QuestionResponseHelper._safe_get_attr(format_obj, 'qfm_format_code', ''),
            'qfm_format_name': QuestionResponseHelper._safe_get_attr(format_obj, 'qfm_format_name', ''),
        }
    
    @staticmethod
    def _build_type_data(type_obj) -> Dict[str, Any]:
        """Build type data for question responses."""
        if type_obj is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(type_obj, 'id'),
            'qtm_type_code': QuestionResponseHelper._safe_get_attr(type_obj, 'qtm_type_code', ''),
            'qtm_type_name': QuestionResponseHelper._safe_get_attr(type_obj, 'qtm_type_name', ''),
        }
    
    @staticmethod
    def _build_taxonomy_data(taxonomy) -> Dict[str, Any]:
        """Build taxonomy data for question responses."""
        if taxonomy is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(taxonomy, 'id'),
            'stm_taxonomy_code': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_taxonomy_code', ''),
            'stm_chapter_code': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_chapter_code', ''),
            'stm_chapter_name': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_chapter_name', ''),
            'stm_topic_code': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_topic_code', ''),
            'stm_topic_name': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_topic_name', ''),
            'stm_standard': QuestionResponseHelper._safe_get_attr(taxonomy, 'stm_standard', ''),
        }
    
    @staticmethod
    def _build_cognitive_learning_data(cognitive_learning) -> Dict[str, Any]:
        """Build cognitive learning data for question responses."""
        if cognitive_learning is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(cognitive_learning, 'id'),
            'cognitive_learning_name': QuestionResponseHelper._safe_get_attr(cognitive_learning, 'clm_cognitive_learning_name', ''),
        }
    
    @staticmethod
    def _build_difficulty_data(difficulty) -> Dict[str, Any]:
        """Build difficulty data for question responses."""
        if difficulty is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(difficulty, 'id'),
            'difficulty_name': QuestionResponseHelper._safe_get_attr(difficulty, 'dm_difficulty_name', ''),
        }
    
    @staticmethod
    def _build_medium_data(medium) -> Dict[str, Any]:
        """Build medium data for question responses."""
        if medium is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(medium, 'id'),
            'mmt_medium_code': QuestionResponseHelper._safe_get_attr(medium, 'mmt_medium_code', ''),
            'mmt_medium_name': QuestionResponseHelper._safe_get_attr(medium, 'mmt_medium_name', ''),
        }
    
    @staticmethod
    def _build_board_data(board) -> Dict[str, Any]:
        """Build board data for question responses."""
        if board is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(board, 'id'),
            'board_name': QuestionResponseHelper._safe_get_attr(board, 'bm_board_name', ''),
        }
    
    @staticmethod
    def _build_state_data(state) -> Dict[str, Any]:
        """Build state data for question responses."""
        if state is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(state, 'id'),
            'state_name': QuestionResponseHelper._safe_get_attr(state, 'sm_state_name', ''),
            'iso_code': QuestionResponseHelper._safe_get_attr(state, 'sm_iso_code', ''),
        }
    
    @staticmethod
    def _build_organization_data(organization) -> Dict[str, Any]:
        """Build organization data for question responses."""
        if organization is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(organization, 'id'),
            'org_name': QuestionResponseHelper._safe_get_attr(organization, 'org_name', ''),
            'org_code': QuestionResponseHelper._safe_get_attr(organization, 'org_code', ''),
        }
    
    @staticmethod
    def _build_block_data(block) -> Dict[str, Any]:
        """Build block data for question responses."""
        if block is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(block, 'id'),
            'block_name': QuestionResponseHelper._safe_get_attr(block, 'block_name', ''),
            'block_code': QuestionResponseHelper._safe_get_attr(block, 'block_code', ''),
        }
    
    @staticmethod
    def _build_school_data(school) -> Dict[str, Any]:
        """Build school data for question responses."""
        if school is None:
            return None
        
        return {
            'id': QuestionResponseHelper._safe_get_attr(school, 'id'),
            'school_name': QuestionResponseHelper._safe_get_attr(school, 'school_name', ''),
            'udise_code': QuestionResponseHelper._safe_get_attr(school, 'udise_code', ''),
        }
    



class OrganizationResponseHelper(BaseResponseHelper):
    """
    Helper for building organization response data.
    
    This class handles the construction of organization response dictionaries,
    including core organization fields, audit field resolution, and hierarchy relationship serialization.
    """
    
    @staticmethod
    def build_response_data(organization) -> Dict[str, Any]:
        """
        Build complete organization response data dictionary.
        
        Args:
            organization: Organization SQLAlchemy model instance
            
        Returns:
            Dictionary containing complete organization response data
        """
        # Log helper usage
        OrganizationResponseHelper._log_helper_usage(
            'OrganizationResponseHelper', 
            'Organization', 
            getattr(organization, 'id', 'unknown'),
            'build_response_data'
        )
        
        try:
            # Base organization fields - explicit field mapping for clarity and debuggability
            response_data = {
                'id': organization.id,
                'uuid': OrganizationResponseHelper._safe_str_uuid(organization.uuid) if hasattr(organization, 'uuid') else None,
                'org_code': OrganizationResponseHelper._safe_get_attr(organization, 'org_code', ''),
                'org_name': OrganizationResponseHelper._safe_get_attr(organization, 'org_name', ''),
                'org_description': OrganizationResponseHelper._safe_get_attr(organization, 'org_description', ''),
                'is_active': OrganizationResponseHelper._safe_get_attr(organization, 'is_active', True),
            }
            
            # Add audit fields with username resolution
            try:
                audit_fields = OrganizationResponseHelper._resolve_audit_fields(organization)
                response_data.update(audit_fields)
            except Exception as e:
                OrganizationResponseHelper._log_relationship_error(organization, 'audit_fields', e)
                response_data.update({
                    'created_by': None,
                    'updated_by': None,
                    'created_at': OrganizationResponseHelper._safe_get_attr(organization, 'created_at'),
                    'updated_at': OrganizationResponseHelper._safe_get_attr(organization, 'updated_at')
                })
            
            # Add hierarchy relationships with safe processing
            try:
                blocks_data = []
                if hasattr(organization, 'blocks') and organization.blocks:
                    for block in organization.blocks:
                        try:
                            block_data = OrganizationResponseHelper._build_block_summary(block)
                            if block_data:
                                blocks_data.append(block_data)
                        except Exception as e:
                            OrganizationResponseHelper._log_relationship_error(organization, f'block_{getattr(block, "id", "unknown")}', e)
                            continue
                response_data['blocks'] = blocks_data
            except Exception as e:
                OrganizationResponseHelper._log_relationship_error(organization, 'blocks', e)
                response_data['blocks'] = []
            
            try:
                schools_data = []
                if hasattr(organization, 'schools') and organization.schools:
                    for school in organization.schools:
                        try:
                            school_data = OrganizationResponseHelper._build_school_summary(school)
                            if school_data:
                                schools_data.append(school_data)
                        except Exception as e:
                            OrganizationResponseHelper._log_relationship_error(organization, f'school_{getattr(school, "id", "unknown")}', e)
                            continue
                response_data['schools'] = schools_data
            except Exception as e:
                OrganizationResponseHelper._log_relationship_error(organization, 'schools', e)
                response_data['schools'] = []
            
            # Log successful response building
            logger.debug(
                "Organization response built successfully",
                extra={
                    'organization_id': organization.id,
                    'org_code': response_data.get('org_code'),
                    'blocks_count': len(response_data.get('blocks', [])),
                    'schools_count': len(response_data.get('schools', []))
                }
            )
            
            return response_data
            
        except Exception as e:
            # Handle errors gracefully by returning minimal response
            minimal_fields = ['id', 'uuid', 'org_code', 'org_name']
            return OrganizationResponseHelper._handle_response_error(organization, e, minimal_fields)
    
    @staticmethod
    def build_minimal_response_data(organization) -> Dict[str, Any]:
        """
        Build minimal organization response data for error scenarios or performance optimization.
        
        Args:
            organization: Organization SQLAlchemy model instance
            
        Returns:
            Dictionary containing minimal organization response data
        """
        OrganizationResponseHelper._log_helper_usage(
            'OrganizationResponseHelper', 
            'Organization', 
            getattr(organization, 'id', 'unknown'),
            'build_minimal_response_data'
        )
        
        try:
            return {
                'id': organization.id,
                'uuid': OrganizationResponseHelper._safe_str_uuid(getattr(organization, 'uuid', None)),
                'org_code': OrganizationResponseHelper._safe_get_attr(organization, 'org_code', ''),
                'org_name': OrganizationResponseHelper._safe_get_attr(organization, 'org_name', ''),
                'is_active': OrganizationResponseHelper._safe_get_attr(organization, 'is_active', True),
                'created_at': OrganizationResponseHelper._safe_get_attr(organization, 'created_at'),
                'updated_at': OrganizationResponseHelper._safe_get_attr(organization, 'updated_at'),
                'created_by': None,
                'updated_by': None,
                'blocks': [],
                'schools': []
            }
        except Exception as e:
            logger.error(f"Failed to build minimal organization response: {e}")
            return {
                'id': getattr(organization, 'id', None),
                'uuid': None,
                'org_code': '',
                'org_name': '',
                'error': 'Failed to build minimal response'
            }
    
    @staticmethod
    def _build_block_summary(block) -> Dict[str, Any]:
        """
        Build block summary for organization responses.
        
        Args:
            block: Block SQLAlchemy model instance
            
        Returns:
            Dictionary containing block summary data
        """
        if block is None:
            return None
        
        base_data = {
            'id': OrganizationResponseHelper._safe_get_attr(block, 'id'),
            'uuid': OrganizationResponseHelper._safe_str_uuid(getattr(block, 'uuid', None)),
            'block_code': OrganizationResponseHelper._safe_get_attr(block, 'block_code', ''),
            'block_name': OrganizationResponseHelper._safe_get_attr(block, 'block_name', ''),
            'block_description': OrganizationResponseHelper._safe_get_attr(block, 'block_description', ''),
            'is_active': OrganizationResponseHelper._safe_get_attr(block, 'is_active', True),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = OrganizationResponseHelper._resolve_audit_fields(block)
            base_data.update(audit_fields)
        except Exception as e:
            OrganizationResponseHelper._log_relationship_error(block, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': OrganizationResponseHelper._safe_get_attr(block, 'created_at'),
                'updated_at': OrganizationResponseHelper._safe_get_attr(block, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def _build_school_summary(school) -> Dict[str, Any]:
        """
        Build school summary for organization responses.
        
        Args:
            school: School SQLAlchemy model instance
            
        Returns:
            Dictionary containing school summary data
        """
        if school is None:
            return None
        
        base_data = {
            'id': OrganizationResponseHelper._safe_get_attr(school, 'id'),
            'uuid': OrganizationResponseHelper._safe_str_uuid(getattr(school, 'uuid', None)),
            'udise_code': OrganizationResponseHelper._safe_get_attr(school, 'udise_code', ''),
            'school_name': OrganizationResponseHelper._safe_get_attr(school, 'school_name', ''),
            'school_description': OrganizationResponseHelper._safe_get_attr(school, 'school_description', ''),
            'address': OrganizationResponseHelper._safe_get_attr(school, 'address', ''),
            'is_active': OrganizationResponseHelper._safe_get_attr(school, 'is_active', True),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = OrganizationResponseHelper._resolve_audit_fields(school)
            base_data.update(audit_fields)
        except Exception as e:
            OrganizationResponseHelper._log_relationship_error(school, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': OrganizationResponseHelper._safe_get_attr(school, 'created_at'),
                'updated_at': OrganizationResponseHelper._safe_get_attr(school, 'updated_at')
            })
        
        return base_data


class BlockResponseHelper(BaseResponseHelper):
    """
    Helper for building block response data.
    
    This class handles the construction of block response dictionaries,
    including core block fields, audit field resolution, and organization/school relationship serialization.
    """
    
    @staticmethod
    def build_response_data(block) -> Dict[str, Any]:
        """
        Build complete block response data dictionary.
        
        Args:
            block: Block SQLAlchemy model instance
            
        Returns:
            Dictionary containing complete block response data
        """
        # Log helper usage
        BlockResponseHelper._log_helper_usage(
            'BlockResponseHelper', 
            'Block', 
            getattr(block, 'id', 'unknown'),
            'build_response_data'
        )
        
        try:
            # Base block fields - explicit field mapping for clarity and debuggability
            response_data = {
                'id': block.id,
                'uuid': BlockResponseHelper._safe_str_uuid(block.uuid) if hasattr(block, 'uuid') else None,
                'block_code': BlockResponseHelper._safe_get_attr(block, 'block_code', ''),
                'block_name': BlockResponseHelper._safe_get_attr(block, 'block_name', ''),
                'block_description': BlockResponseHelper._safe_get_attr(block, 'block_description', ''),
                'organization_id': BlockResponseHelper._safe_get_attr(block, 'organization_id'),
                'state_id': BlockResponseHelper._safe_get_attr(block, 'state_id'),
                'is_active': BlockResponseHelper._safe_get_attr(block, 'is_active', True),
            }
            
            # Add audit fields with username resolution
            try:
                audit_fields = BlockResponseHelper._resolve_audit_fields(block)
                response_data.update(audit_fields)
            except Exception as e:
                BlockResponseHelper._log_relationship_error(block, 'audit_fields', e)
                response_data.update({
                    'created_by': None,
                    'updated_by': None,
                    'created_at': BlockResponseHelper._safe_get_attr(block, 'created_at'),
                    'updated_at': BlockResponseHelper._safe_get_attr(block, 'updated_at')
                })
            
            # Add UUID fields for organizational context with safe processing
            response_data.update({
                'organization_uuid': BlockResponseHelper._safe_process_relationship(
                    block, 'organization',
                    lambda org: BlockResponseHelper._safe_str_uuid(getattr(org, 'uuid', None))
                ),
                'state_name': BlockResponseHelper._safe_process_relationship(
                    block, 'state',
                    lambda state: BlockResponseHelper._safe_get_attr(state, 'state_name')
                ),
            })
            
            # Add comprehensive state information with safe processing
            response_data.update({
                'state': BlockResponseHelper._safe_process_relationship(
                    block, 'state', BlockResponseHelper._build_state_data
                ),
            })
            
            # Add relationship serialization with safe processing
            response_data.update({
                'organization': BlockResponseHelper._safe_process_relationship(
                    block, 'organization', BlockResponseHelper._build_organization_data
                ),
            })
            
            # Add schools relationship with safe processing
            try:
                schools_data = []
                if hasattr(block, 'schools') and block.schools:
                    for school in block.schools:
                        try:
                            school_data = BlockResponseHelper._build_school_summary(school)
                            if school_data:
                                schools_data.append(school_data)
                        except Exception as e:
                            BlockResponseHelper._log_relationship_error(block, f'school_{getattr(school, "id", "unknown")}', e)
                            continue
                response_data['schools'] = schools_data
            except Exception as e:
                BlockResponseHelper._log_relationship_error(block, 'schools', e)
                response_data['schools'] = []
            
            # Log successful response building
            logger.debug(
                "Block response built successfully",
                extra={
                    'block_id': block.id,
                    'block_code': response_data.get('block_code'),
                    'schools_count': len(response_data.get('schools', []))
                }
            )
            
            return response_data
            
        except Exception as e:
            # Handle errors gracefully by returning minimal response
            minimal_fields = ['id', 'uuid', 'block_code', 'block_name']
            return BlockResponseHelper._handle_response_error(block, e, minimal_fields)
    
    @staticmethod
    def _build_organization_data(organization) -> Dict[str, Any]:
        """
        Build organization data for block responses.
        
        Args:
            organization: Organization SQLAlchemy model instance
            
        Returns:
            Dictionary containing organization data
        """
        if organization is None:
            return None
        
        base_data = {
            'id': BlockResponseHelper._safe_get_attr(organization, 'id'),
            'uuid': BlockResponseHelper._safe_str_uuid(getattr(organization, 'uuid', None)),
            'org_code': BlockResponseHelper._safe_get_attr(organization, 'org_code', ''),
            'org_name': BlockResponseHelper._safe_get_attr(organization, 'org_name', ''),
            'org_description': BlockResponseHelper._safe_get_attr(organization, 'org_description', ''),
            'is_active': BlockResponseHelper._safe_get_attr(organization, 'is_active', True),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = BlockResponseHelper._resolve_audit_fields(organization)
            base_data.update(audit_fields)
        except Exception as e:
            BlockResponseHelper._log_relationship_error(organization, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': BlockResponseHelper._safe_get_attr(organization, 'created_at'),
                'updated_at': BlockResponseHelper._safe_get_attr(organization, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def _build_school_summary(school) -> Dict[str, Any]:
        """
        Build school summary for block responses.
        
        Args:
            school: School SQLAlchemy model instance
            
        Returns:
            Dictionary containing school summary data
        """
        if school is None:
            return None
        
        base_data = {
            'id': BlockResponseHelper._safe_get_attr(school, 'id'),
            'uuid': BlockResponseHelper._safe_str_uuid(getattr(school, 'uuid', None)),
            'udise_code': BlockResponseHelper._safe_get_attr(school, 'udise_code', ''),
            'school_name': BlockResponseHelper._safe_get_attr(school, 'school_name', ''),
            'school_description': BlockResponseHelper._safe_get_attr(school, 'school_description', ''),
            'address': BlockResponseHelper._safe_get_attr(school, 'address', ''),
            'is_active': BlockResponseHelper._safe_get_attr(school, 'is_active', True),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = BlockResponseHelper._resolve_audit_fields(school)
            base_data.update(audit_fields)
        except Exception as e:
            BlockResponseHelper._log_relationship_error(school, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': BlockResponseHelper._safe_get_attr(school, 'created_at'),
                'updated_at': BlockResponseHelper._safe_get_attr(school, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def _build_state_data(state) -> Dict[str, Any]:
        """
        Build state data for block responses.
        
        Args:
            state: State SQLAlchemy model instance
            
        Returns:
            Dictionary containing state data
        """
        if state is None:
            return None
        
        base_data = {
            'id': BlockResponseHelper._safe_get_attr(state, 'id'),
            'state_name': BlockResponseHelper._safe_get_attr(state, 'state_name', ''),
            'iso_code': BlockResponseHelper._safe_get_attr(state, 'iso_code', ''),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = BlockResponseHelper._resolve_audit_fields(state)
            base_data.update(audit_fields)
        except Exception as e:
            BlockResponseHelper._log_relationship_error(state, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': BlockResponseHelper._safe_get_attr(state, 'created_at'),
                'updated_at': BlockResponseHelper._safe_get_attr(state, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def build_minimal_response_data(block) -> Dict[str, Any]:
        """
        Build minimal block response data for error scenarios or performance optimization.
        
        Args:
            block: Block SQLAlchemy model instance
            
        Returns:
            Dictionary containing minimal block response data including state information
        """
        BlockResponseHelper._log_helper_usage(
            'BlockResponseHelper', 
            'Block', 
            getattr(block, 'id', 'unknown'),
            'build_minimal_response_data'
        )
        
        try:
            # Minimal block fields with state information
            response_data = {
                'id': BlockResponseHelper._safe_get_attr(block, 'id'),
                'uuid': BlockResponseHelper._safe_str_uuid(getattr(block, 'uuid', None)),
                'block_code': BlockResponseHelper._safe_get_attr(block, 'block_code', ''),
                'block_name': BlockResponseHelper._safe_get_attr(block, 'block_name', ''),
                'state_id': BlockResponseHelper._safe_get_attr(block, 'state_id'),
                'state_name': BlockResponseHelper._safe_process_relationship(
                    block, 'state',
                    lambda state: BlockResponseHelper._safe_get_attr(state, 'state_name')
                ),
                'is_active': BlockResponseHelper._safe_get_attr(block, 'is_active', True),
            }
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to build minimal block response: {e}")
            return {
                'id': getattr(block, 'id', None),
                'uuid': None,
                'block_code': '',
                'block_name': '',
                'state_id': None,
                'state_name': None,
                'error': 'Failed to build minimal response'
            }


class SchoolResponseHelper(BaseResponseHelper):
    """
    Helper for building school response data.
    
    This class handles the construction of school response dictionaries,
    including core school fields, audit field resolution, and block/organization relationship serialization.
    """
    
    @staticmethod
    def build_response_data(school) -> Dict[str, Any]:
        """
        Build complete school response data dictionary.
        
        Args:
            school: School SQLAlchemy model instance
            
        Returns:
            Dictionary containing complete school response data
        """
        # Log helper usage
        SchoolResponseHelper._log_helper_usage(
            'SchoolResponseHelper', 
            'School', 
            getattr(school, 'id', 'unknown'),
            'build_response_data'
        )
        
        try:
            # Base school fields - explicit field mapping for clarity and debuggability
            response_data = {
                'id': school.id,
                'uuid': SchoolResponseHelper._safe_str_uuid(school.uuid) if hasattr(school, 'uuid') else None,
                'udise_code': SchoolResponseHelper._safe_get_attr(school, 'udise_code', ''),
                'school_name': SchoolResponseHelper._safe_get_attr(school, 'school_name', ''),
                'school_description': SchoolResponseHelper._safe_get_attr(school, 'school_description', ''),
                'address': SchoolResponseHelper._safe_get_attr(school, 'address', ''),
                'local_govt_body_id': SchoolResponseHelper._safe_get_attr(school, 'local_govt_body_id'),
                'state_id': SchoolResponseHelper._safe_get_attr(school, 'state_id'),
                'block_id': SchoolResponseHelper._safe_get_attr(school, 'block_id'),
                'organization_id': SchoolResponseHelper._safe_get_attr(school, 'organization_id'),
                'is_active': SchoolResponseHelper._safe_get_attr(school, 'is_active', True),
                'logo_image_url': SchoolResponseHelper._safe_get_attr(school, 'logo_image_url'),
                'other_images_urls': SchoolResponseHelper._safe_get_attr(school, 'other_images_urls', []),
            }
            
            # Add audit fields with username resolution
            try:
                audit_fields = SchoolResponseHelper._resolve_audit_fields(school)
                response_data.update(audit_fields)
            except Exception as e:
                SchoolResponseHelper._log_relationship_error(school, 'audit_fields', e)
                response_data.update({
                    'created_by': None,
                    'updated_by': None,
                    'created_at': SchoolResponseHelper._safe_get_attr(school, 'created_at'),
                    'updated_at': SchoolResponseHelper._safe_get_attr(school, 'updated_at')
                })
            
            # Add UUID fields for organizational context with safe processing
            response_data.update({
                'block_uuid': SchoolResponseHelper._safe_process_relationship(
                    school, 'block',
                    lambda block: SchoolResponseHelper._safe_str_uuid(getattr(block, 'uuid', None))
                ),
                'organization_uuid': SchoolResponseHelper._safe_process_relationship(
                    school, 'organization',
                    lambda org: SchoolResponseHelper._safe_str_uuid(getattr(org, 'uuid', None))
                ),
            })
            
            # Add relationship serialization with safe processing
            response_data.update({
                'organization': SchoolResponseHelper._safe_process_relationship(
                    school, 'organization', SchoolResponseHelper._build_organization_data
                ),
                'block': SchoolResponseHelper._safe_process_relationship(
                    school, 'block', SchoolResponseHelper._build_block_data
                ),
                'state': SchoolResponseHelper._safe_process_relationship(
                    school, 'state', SchoolResponseHelper._build_state_data
                ),
            })
            
            # Add school boards and class levels with safe processing
            try:
                boards_data = []
                class_levels_data = []
                if hasattr(school, 'school_boards') and school.school_boards:
                    boards_data = SchoolResponseHelper._build_boards_data(school.school_boards)
                    class_levels_data = SchoolResponseHelper._build_class_levels_data(school.school_boards)
                response_data['boards'] = boards_data
                response_data['class_levels'] = class_levels_data
            except Exception as e:
                SchoolResponseHelper._log_relationship_error(school, 'school_boards', e)
                response_data['boards'] = []
                response_data['class_levels'] = []
            
            # Log successful response building
            logger.debug(
                "School response built successfully",
                extra={
                    'school_id': school.id,
                    'udise_code': response_data.get('udise_code'),
                    'boards_count': len(response_data.get('boards', [])),
                    'class_levels_count': len(response_data.get('class_levels', []))
                }
            )
            
            return response_data
            
        except Exception as e:
            # Handle errors gracefully by returning minimal response
            minimal_fields = ['id', 'uuid', 'udise_code', 'school_name']
            return SchoolResponseHelper._handle_response_error(school, e, minimal_fields)
    
    @staticmethod
    def _build_organization_data(organization) -> Dict[str, Any]:
        """
        Build organization data for school responses.
        
        Args:
            organization: Organization SQLAlchemy model instance
            
        Returns:
            Dictionary containing organization data
        """
        if organization is None:
            return None
        
        base_data = {
            'id': SchoolResponseHelper._safe_get_attr(organization, 'id'),
            'uuid': SchoolResponseHelper._safe_str_uuid(getattr(organization, 'uuid', None)),
            'org_code': SchoolResponseHelper._safe_get_attr(organization, 'org_code', ''),
            'org_name': SchoolResponseHelper._safe_get_attr(organization, 'org_name', ''),
            'org_description': SchoolResponseHelper._safe_get_attr(organization, 'org_description', ''),
            'is_active': SchoolResponseHelper._safe_get_attr(organization, 'is_active', True),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = SchoolResponseHelper._resolve_audit_fields(organization)
            base_data.update(audit_fields)
        except Exception as e:
            SchoolResponseHelper._log_relationship_error(organization, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': SchoolResponseHelper._safe_get_attr(organization, 'created_at'),
                'updated_at': SchoolResponseHelper._safe_get_attr(organization, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def _build_block_data(block) -> Dict[str, Any]:
        """
        Build block data for school responses.
        
        Args:
            block: Block SQLAlchemy model instance
            
        Returns:
            Dictionary containing block data
        """
        if block is None:
            return None
        
        base_data = {
            'id': SchoolResponseHelper._safe_get_attr(block, 'id'),
            'uuid': SchoolResponseHelper._safe_str_uuid(getattr(block, 'uuid', None)),
            'block_code': SchoolResponseHelper._safe_get_attr(block, 'block_code', ''),
            'block_name': SchoolResponseHelper._safe_get_attr(block, 'block_name', ''),
            'block_description': SchoolResponseHelper._safe_get_attr(block, 'block_description', ''),
            'state_id': SchoolResponseHelper._safe_get_attr(block, 'state_id'),
            'is_active': SchoolResponseHelper._safe_get_attr(block, 'is_active', True),
            'organization_uuid': SchoolResponseHelper._safe_process_relationship(
                block, 'organization',
                lambda org: SchoolResponseHelper._safe_str_uuid(getattr(org, 'uuid', None))
            ),
        }
        
        # Add audit fields with safe resolution
        try:
            audit_fields = SchoolResponseHelper._resolve_audit_fields(block)
            base_data.update(audit_fields)
        except Exception as e:
            SchoolResponseHelper._log_relationship_error(block, 'audit_fields', e)
            base_data.update({
                'created_by': None,
                'updated_by': None,
                'created_at': SchoolResponseHelper._safe_get_attr(block, 'created_at'),
                'updated_at': SchoolResponseHelper._safe_get_attr(block, 'updated_at')
            })
        
        return base_data
    
    @staticmethod
    def _build_state_data(state) -> Dict[str, Any]:
        """
        Build state data for school responses.
        
        Args:
            state: State SQLAlchemy model instance
            
        Returns:
            Dictionary containing state data
        """
        if state is None:
            return None
        
        return {
            'id': SchoolResponseHelper._safe_get_attr(state, 'id'),
            'sm_state_name': SchoolResponseHelper._safe_get_attr(state, 'sm_state_name', ''),
            'sm_iso_code': SchoolResponseHelper._safe_get_attr(state, 'sm_iso_code', ''),
        }
    
    @staticmethod
    def _build_boards_data(school_boards) -> List[int]:
        """
        Build boards data for school responses.
        
        Args:
            school_boards: List of SchoolBoard SQLAlchemy model instances
            
        Returns:
            List of board IDs (integers)
        """
        if not school_boards:
            return []
        
        board_ids = []
        for school_board in school_boards:
            try:
                if school_board:
                    # Only include active school_board records
                    is_active = SchoolResponseHelper._safe_get_attr(school_board, 'is_active', True)
                    if is_active:
                        # Use board_id directly from the school_board table
                        board_id = SchoolResponseHelper._safe_get_attr(school_board, 'board_id')
                        if board_id is not None:
                            board_ids.append(board_id)
            except Exception as e:
                SchoolResponseHelper._log_relationship_error(school_board, 'board_id', e)
                continue
        
        return board_ids
    
    @staticmethod
    def _build_class_levels_data(school_boards) -> List[int]:
        """
        Build class levels data for school responses.
        
        Args:
            school_boards: List of SchoolBoard SQLAlchemy model instances
            
        Returns:
            List of class levels (sorted and deduplicated)
        """
        if not school_boards:
            return []
        
        class_levels = []
        for school_board in school_boards:
            if school_board and hasattr(school_board, 'school_board_classes'):
                # Only process class levels for active school_board records
                school_board_active = SchoolResponseHelper._safe_get_attr(school_board, 'is_active', True)
                if school_board_active:
                    for school_board_class in school_board.school_board_classes:
                        if school_board_class and SchoolResponseHelper._safe_get_attr(school_board_class, 'is_active', False):
                            class_level = SchoolResponseHelper._safe_get_attr(school_board_class, 'class_level')
                            if class_level is not None:
                                class_levels.append(class_level)
        
        # Remove duplicates and sort
        return sorted(list(set(class_levels)))
    
    @staticmethod
    def build_simple_response_data(school) -> Dict[str, Any]:
        """
        Build simple school response data with only essential fields for codes endpoint.
        
        Args:
            school: School SQLAlchemy model instance
            
        Returns:
            Dictionary containing uuid, school_name, and udise_code
        """
        return {
            'uuid': SchoolResponseHelper._safe_str_uuid(school.uuid) if hasattr(school, 'uuid') else None,
            'school_name': SchoolResponseHelper._safe_get_attr(school, 'school_name', ''),
            'udise_code': SchoolResponseHelper._safe_get_attr(school, 'udise_code', ''),
            'logo_image_url': SchoolResponseHelper._safe_get_attr(school, 'logo_image_url'),
            'other_images_urls': SchoolResponseHelper._safe_get_attr(school, 'other_images_urls', [])
        }


class SubjectResponseHelper(BaseResponseHelper):
    """
    Helper for building subject response data.
    
    This class handles the construction of subject response dictionaries,
    following the existing response helper patterns for consistency.
    """
    
    @staticmethod
    def build_create_response(subject) -> Dict[str, Any]:
        """
        Build standardized response for subject creation.
        
        Args:
            subject: Subject SQLAlchemy model instance
            
        Returns:
            Dictionary containing subject creation response data
        """
        SubjectResponseHelper._log_helper_usage(
            'SubjectResponseHelper', 
            'Subject', 
            getattr(subject, 'id', 'unknown'),
            'build_create_response'
        )
        
        try:
            # Get medium code from the relationship
            medium_code = ""
            if hasattr(subject, 'medium') and subject.medium:
                medium_code = SubjectResponseHelper._safe_get_attr(subject.medium, 'mmt_medium_code', '')
            
            return {
                "subject_code": SubjectResponseHelper._safe_get_attr(subject, 'smt_subject_code', ''),
                "subject_name": SubjectResponseHelper._safe_get_attr(subject, 'smt_subject_name', ''),
                "standard": SubjectResponseHelper._safe_get_attr(subject, 'smt_standard', ''),
                "medium_code": medium_code,
                "message": "Subject created successfully"
            }
        except Exception as e:
            logger.error(f"Failed to build subject create response: {e}")
            return {
                "subject_code": "",
                "subject_name": "",
                "standard": "",
                "medium_code": "",
                "message": "Subject created but response building failed"
            }
    
    @staticmethod
    def build_conflict_response(existing_subject) -> Dict[str, Any]:
        """
        Build response for duplicate subject conflicts.
        
        Args:
            existing_subject: Subject SQLAlchemy model instance
            
        Returns:
            Dictionary containing conflict response data
        """
        SubjectResponseHelper._log_helper_usage(
            'SubjectResponseHelper', 
            'Subject', 
            getattr(existing_subject, 'id', 'unknown'),
            'build_conflict_response'
        )
        
        try:
            # Get medium code from the relationship
            medium_code = ""
            if hasattr(existing_subject, 'medium') and existing_subject.medium:
                medium_code = SubjectResponseHelper._safe_get_attr(existing_subject.medium, 'mmt_medium_code', '')
            
            return {
                "detail": "Subject already exists",
                "existing_subject": {
                    "subject_code": SubjectResponseHelper._safe_get_attr(existing_subject, 'smt_subject_code', ''),
                    "subject_name": SubjectResponseHelper._safe_get_attr(existing_subject, 'smt_subject_name', ''),
                    "standard": SubjectResponseHelper._safe_get_attr(existing_subject, 'smt_standard', ''),
                    "medium_code": medium_code
                }
            }
        except Exception as e:
            logger.error(f"Failed to build subject conflict response: {e}")
            return {
                "detail": "Subject already exists",
                "existing_subject": {
                    "subject_code": "",
                    "subject_name": "",
                    "standard": "",
                    "medium_code": ""
                }
            }