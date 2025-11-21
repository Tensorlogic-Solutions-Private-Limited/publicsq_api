"""
Pydantic schemas for taxonomy management.

This module contains request and response schemas for taxonomy creation
and management operations, supporting three creation scenarios:
1. Complete new hierarchy (chapter, topic, subtopic)
2. New topic in existing chapter
3. New subtopic in existing topic
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from enum import Enum


class TaxonomyCreateRequest(BaseModel):
    """
    Schema for creating taxonomy entries with flexible scenario support.
    
    Supports three creation scenarios:
    1. Complete hierarchy: Provide names for chapter, topic, subtopic (no codes)
    2. New topic: Provide chapter_code, topic_name, subtopic_name
    3. New subtopic: Provide chapter_code, topic_code, subtopic_name
    """
    
    # Context fields (required for all scenarios)
    subject_code: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Code of the subject from subject_master_table (e.g., '3001')"
    )
    medium_code: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Code of the medium from medium_master_table (e.g., '2000')"
    )
    standard: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Class/standard level (e.g., '1', '10', '12')"
    )
    board_id: int = Field(
        ...,
        gt=0,
        description="ID of the board from board_master table"
    )
    state_id: int = Field(
        ...,
        gt=0,
        description="ID of the state from state_master table"
    )
    
    # Chapter level fields
    chapter_code: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10,
        description="Existing chapter code (format: C000) - used in scenarios 2 & 3"
    )
    chapter_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=255,
        description="Chapter name - required for scenario 1 (complete new hierarchy)"
    )
    
    # Topic level fields
    topic_code: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10,
        description="Existing topic code (format: T000) - used in scenario 3"
    )
    topic_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Topic name - required for scenarios 1 & 2, can be empty string or null"
    )
    
    # Subtopic level fields
    subtopic_code: Optional[str] = Field(
        None,
        min_length=1,
        max_length=10,
        description="Subtopic code (format: S000) - not used in creation scenarios"
    )
    subtopic_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Subtopic name - can be empty string or null for consistency with bulk upload"
    )

    @field_validator('chapter_code', 'topic_code', 'subtopic_code')
    @classmethod
    def validate_code_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate that codes follow the expected format if provided."""
        if v is None:
            return v
        
        if len(v) < 4:
            raise ValueError("Code must be at least 4 characters long")
        
        # Check format: C000, T000, S000
        prefix = v[0].upper()
        if prefix not in ['C', 'T', 'S']:
            raise ValueError("Code must start with C (chapter), T (topic), or S (subtopic)")
        
        if not v[1:].isdigit():
            raise ValueError("Code must have numeric suffix after prefix")
        
        return v.upper()

    @model_validator(mode='after')
    def validate_creation_scenario(self):
        """
        Validate that the request follows one of the supported scenarios.
        
        Note: topic_name and subtopic_name are optional for consistency with bulk upload.
        Empty strings or None values are converted to empty strings.
        
        Scenario 1 (Complete new hierarchy):
        - Required: chapter_name
        - Optional: topic_name, subtopic_name
        - Forbidden: chapter_code, topic_code, subtopic_code
        
        Scenario 2 (New topic in existing chapter):
        - Required: chapter_code
        - Optional: topic_name, subtopic_name
        - Forbidden: topic_code, subtopic_code, chapter_name
        
        Scenario 3 (New subtopic in existing topic):
        - Required: chapter_code, topic_code
        - Optional: subtopic_name
        - Forbidden: subtopic_code, chapter_name, topic_name
        
        Scenario 4 (Bulk upload style - minimal requirements):
        - Required: At least chapter_name OR chapter_code
        - Optional: All other fields
        """
        
        # Normalize None values to empty strings (consistent with bulk upload)
        if self.topic_name is None:
            self.topic_name = ""
        if self.subtopic_name is None:
            self.subtopic_name = ""
        if self.chapter_name is None:
            self.chapter_name = ""
        
        # Check for scenario 1: Complete new hierarchy
        if (self.chapter_name and self.chapter_name.strip() and 
            not self.chapter_code and not self.topic_code and not self.subtopic_code):
            return self
        
        # Check for scenario 2: New topic in existing chapter
        if (self.chapter_code and self.chapter_code.strip() and 
            not self.topic_code and not self.subtopic_code and 
            (not self.chapter_name or not self.chapter_name.strip())):
            return self
        
        # Check for scenario 3: New subtopic in existing topic
        if (self.chapter_code and self.chapter_code.strip() and 
            self.topic_code and self.topic_code.strip() and
            not self.subtopic_code and 
            (not self.chapter_name or not self.chapter_name.strip()) and
            (not self.topic_name or not self.topic_name.strip())):
            return self
        
        # Check for scenario 4: Bulk upload style (minimal validation)
        if (self.chapter_name and self.chapter_name.strip()) or (self.chapter_code and self.chapter_code.strip()):
            return self
        
        # If none of the scenarios match, raise validation error
        raise ValueError(
            "Invalid field combination. Must provide at least:\n"
            "1. Complete hierarchy: chapter_name (topic_name and subtopic_name optional)\n"
            "2. New topic: chapter_code (topic_name and subtopic_name optional)\n"
            "3. New subtopic: chapter_code + topic_code (subtopic_name optional)\n"
            "4. Minimal: chapter_name OR chapter_code (all other fields optional)"
        )

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "description": "Scenario 1: Complete new hierarchy",
                    "value": {
                        "subject_code": "3001",
                        "medium_code": "2000",
                        "standard": "10",
                        "board_id": 7,
                        "state_id": 9,
                        "chapter_name": "Algebra",
                        "topic_name": "Linear Equations",
                        "subtopic_name": "Solving Linear Equations"
                    }
                },
                {
                    "description": "Scenario 2: New topic in existing chapter",
                    "value": {
                        "subject_code": "3001",
                        "medium_code": "2000",
                        "standard": "10",
                        "board_id": 7,
                        "state_id": 9,
                        "chapter_code": "C001",
                        "topic_name": "Quadratic Equations",
                        "subtopic_name": "Solving Quadratic Equations"
                    }
                },
                {
                    "description": "Scenario 3: New subtopic in existing topic",
                    "value": {
                        "subject_code": "3001",
                        "medium_code": "2000",
                        "standard": "10",
                        "board_id": 7,
                        "state_id": 9,
                        "chapter_code": "C001",
                        "topic_code": "T001",
                        "subtopic_name": "Advanced Problem Solving"
                    }
                }
            ]
        }
    )


class TaxonomyCreateResponse(BaseModel):
    """Schema for successful taxonomy creation response."""
    
    taxonomy_code: str = Field(
        ...,
        description="Auto-generated unique taxonomy code (format: TAXC000T000S001-B7-S9-M3-STD10-S11)"
    )
    subject_code: str = Field(
        ...,
        description="Subject code from the request"
    )
    medium_code: str = Field(
        ...,
        description="Medium code from the request"
    )
    standard: str = Field(
        ...,
        description="Standard from the request"
    )
    board_id: int = Field(
        ...,
        description="Board ID from the request"
    )
    state_id: int = Field(
        ...,
        description="State ID from the request"
    )
    chapter_code: str = Field(
        ...,
        description="Chapter code (format: C000) - either provided or auto-generated"
    )
    chapter_name: str = Field(
        ...,
        description="Chapter name"
    )
    topic_code: str = Field(
        ...,
        description="Topic code (format: T000) - either provided or auto-generated"
    )
    topic_name: str = Field(
        ...,
        description="Topic name"
    )
    subtopic_code: str = Field(
        ...,
        description="Subtopic code (format: S000) - auto-generated"
    )
    subtopic_name: str = Field(
        ...,
        description="Subtopic name from the request"
    )
    message: str = Field(
        ...,
        description="Success message"
    )
    created_by: Optional[str] = Field(
        None,
        description="Username of the user who created the taxonomy"
    )
    created_at: Optional[str] = Field(
        None,
        description="Timestamp when the taxonomy was created"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "taxonomy_code": "TAXC001T001S001-B7-S9-M3-STD10-S11",
                "subject_code": "3001",
                "medium_code": "2000",
                "standard": "10",
                "board_id": 7,
                "state_id": 9,
                "chapter_code": "C001",
                "chapter_name": "Algebra",
                "topic_code": "T001",
                "topic_name": "Linear Equations",
                "subtopic_code": "S001",
                "subtopic_name": "Solving Linear Equations",
                "message": "Taxonomy created successfully",
                "created_by": "john.doe",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )


class TaxonomyConflictResponse(BaseModel):
    """Schema for taxonomy conflict error response."""
    
    detail: str = Field(
        ...,
        description="Error message indicating the conflict"
    )
    existing_taxonomy: Dict[str, Any] = Field(
        ...,
        description="Details of the existing taxonomy that conflicts"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "detail": "Taxonomy already exists with the same hierarchy and context",
                "existing_taxonomy": {
                    "taxonomy_code": "TAXC001T001S001-B7-S9-M3-STD10-S11",
                    "subject_code": "3001",
                    "medium_code": "2000",
                    "standard": "10",
                    "board_id": 7,
                    "state_id": 9,
                    "chapter_code": "C001",
                    "chapter_name": "Algebra",
                    "topic_code": "T001",
                    "topic_name": "Linear Equations",
                    "subtopic_code": "S001",
                    "subtopic_name": "Solving Linear Equations"
                }
            }
        }
    )


