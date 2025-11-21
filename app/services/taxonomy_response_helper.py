"""
Taxonomy response helper for building API response data.

This module provides the TaxonomyResponseHelper class to centralize response building logic
for taxonomy-related endpoints, following the established response helper patterns.
"""

from typing import Dict, Any, Optional
import logging
from app.services.response_helpers import BaseResponseHelper

logger = logging.getLogger(__name__)


class TaxonomyResponseHelper(BaseResponseHelper):
    """
    Helper for building taxonomy response data.
    
    This class handles the construction of taxonomy response dictionaries,
    including core taxonomy fields, audit field resolution, and relationship serialization.
    """
    
    @staticmethod
    def build_create_response(taxonomy, message: str = "Taxonomy created successfully") -> Dict[str, Any]:
        """
        Build standardized response for taxonomy creation.
        
        Args:
            taxonomy: Taxonomy SQLAlchemy model instance
            message: Success message to include in response
            
        Returns:
            Dictionary containing taxonomy creation response data
        """
        TaxonomyResponseHelper._log_helper_usage(
            'TaxonomyResponseHelper', 
            'Taxonomy', 
            getattr(taxonomy, 'id', 'unknown'),
            'build_create_response'
        )
        
        try:
            # Get subject and medium codes from relationships
            subject_code = ""
            medium_code = ""
            
            if hasattr(taxonomy, 'subject') and taxonomy.subject:
                subject_code = TaxonomyResponseHelper._safe_get_attr(taxonomy.subject, 'smt_subject_code', '')
            
            if hasattr(taxonomy, 'medium') and taxonomy.medium:
                medium_code = TaxonomyResponseHelper._safe_get_attr(taxonomy.medium, 'mmt_medium_code', '')
            
            # Build response with all taxonomy fields
            response_data = {
                "taxonomy_code": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_taxonomy_code', ''),
                "subject_code": subject_code,
                "medium_code": medium_code,
                "standard": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_standard', ''),
                "board_id": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'board_id'),
                "state_id": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'state_id'),
                "chapter_code": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_chapter_code', ''),
                "chapter_name": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_chapter_name', ''),
                "topic_code": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_topic_code', ''),
                "topic_name": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_topic_name', ''),
                "subtopic_code": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_subtopic_code', ''),
                "subtopic_name": TaxonomyResponseHelper._safe_get_attr(taxonomy, 'stm_subtopic_name', ''),
                "message": message
            }
            
            # Add audit fields with username resolution
            try:
                audit_fields = TaxonomyResponseHelper._resolve_audit_fields(taxonomy)
                response_data.update({
                    'created_by': audit_fields.get('created_by'),
                    'created_at': audit_fields.get('created_at').isoformat() if audit_fields.get('created_at') else None
                })
            except Exception as e:
                TaxonomyResponseHelper._log_relationship_error(taxonomy, 'audit_fields', e)
                response_data.update({
                    'created_by': None,
                    'created_at': None
                })
            
            logger.debug(
                "Taxonomy create response built successfully",
                extra={
                    'taxonomy_id': taxonomy.id,
                    'taxonomy_code': response_data.get('taxonomy_code')
                }
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Failed to build taxonomy create response: {e}")
            return {
                "taxonomy_code": "",
                "subject_code": "",
                "medium_code": "",
                "standard": "",
                "board_id": None,
                "state_id": None,
                "chapter_code": "",
                "chapter_name": "",
                "topic_code": "",
                "topic_name": "",
                "subtopic_code": "",
                "subtopic_name": "",
                "message": "Taxonomy created but response building failed",
                "created_by": None,
                "created_at": None
            }
    
    @staticmethod
    def build_conflict_response(existing_taxonomy) -> Dict[str, Any]:
        """
        Build response for duplicate taxonomy conflicts.
        
        Args:
            existing_taxonomy: Taxonomy SQLAlchemy model instance
            
        Returns:
            Dictionary containing conflict response data
        """
        TaxonomyResponseHelper._log_helper_usage(
            'TaxonomyResponseHelper', 
            'Taxonomy', 
            getattr(existing_taxonomy, 'id', 'unknown'),
            'build_conflict_response'
        )
        
        try:
            # Get subject and medium codes from relationships
            subject_code = ""
            medium_code = ""
            
            if hasattr(existing_taxonomy, 'subject') and existing_taxonomy.subject:
                subject_code = TaxonomyResponseHelper._safe_get_attr(existing_taxonomy.subject, 'smt_subject_code', '')
            
            if hasattr(existing_taxonomy, 'medium') and existing_taxonomy.medium:
                medium_code = TaxonomyResponseHelper._safe_get_attr(existing_taxonomy.medium, 'mmt_medium_code', '')
            
            existing_data = {
                "taxonomy_code": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_taxonomy_code', ''),
                "subject_code": subject_code,
                "medium_code": medium_code,
                "standard": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_standard', ''),
                "board_id": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'board_id'),
                "state_id": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'state_id'),
                "chapter_code": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_chapter_code', ''),
                "chapter_name": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_chapter_name', ''),
                "topic_code": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_topic_code', ''),
                "topic_name": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_topic_name', ''),
                "subtopic_code": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_subtopic_code', ''),
                "subtopic_name": TaxonomyResponseHelper._safe_get_attr(existing_taxonomy, 'stm_subtopic_name', '')
            }
            
            return {
                "detail": "Taxonomy already exists with the same hierarchy and context",
                "existing_taxonomy": existing_data
            }
            
        except Exception as e:
            logger.error(f"Failed to build taxonomy conflict response: {e}")
            return {
                "detail": "Taxonomy already exists with the same hierarchy and context",
                "existing_taxonomy": {
                    "taxonomy_code": "",
                    "subject_code": "",
                    "medium_code": "",
                    "standard": "",
                    "board_id": None,
                    "state_id": None,
                    "chapter_code": "",
                    "chapter_name": "",
                    "topic_code": "",
                    "topic_name": "",
                    "subtopic_code": "",
                    "subtopic_name": ""
                }
            }
    
