"""
Pydantic schemas for subject management.

This module contains request and response schemas for subject creation
and management operations.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class SubjectCreateRequest(BaseModel):
    """Schema for creating a new subject."""
    
    subject_name: str = Field(
        ..., 
        min_length=1, 
        max_length=255, 
        description="Name of the subject (e.g., 'Mathematics', 'Science')"
    )
    standard: str = Field(
        ..., 
        min_length=1, 
        max_length=10, 
        description="Class/standard level (e.g., '1', '10', '12')"
    )
    medium_code: str = Field(
        ..., 
        min_length=1, 
        max_length=10, 
        description="Code of the medium from medium_master_table (e.g., '2000')"
    )

    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "subject_name": "Advanced Mathematics",
                "standard": "12",
                "medium_code": "2000"
            }
        }
    )


class SubjectCreateResponse(BaseModel):
    """Schema for successful subject creation response."""
    
    subject_code: str = Field(
        ..., 
        description="Auto-generated unique subject code (e.g., '3001')"
    )
    subject_name: str = Field(
        ..., 
        description="Name of the created subject"
    )
    standard: str = Field(
        ..., 
        description="Class/standard level"
    )
    medium_code: str = Field(
        ..., 
        description="Medium code"
    )
    message: str = Field(
        ..., 
        description="Success message"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "subject_code": "3001",
                "subject_name": "Advanced Mathematics",
                "standard": "12",
                "medium_code": "2000",
                "message": "Subject created successfully"
            }
        }
    )


class SubjectConflictResponse(BaseModel):
    """Schema for subject conflict error response."""
    
    detail: str = Field(
        ..., 
        description="Error message indicating the conflict"
    )
    existing_subject: Dict[str, Any] = Field(
        ..., 
        description="Details of the existing subject that conflicts"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "detail": "Subject already exists",
                "existing_subject": {
                    "subject_code": "3005",
                    "subject_name": "Advanced Mathematics",
                    "standard": "12",
                    "medium_code": "2000"
                }
            }
        }
    )