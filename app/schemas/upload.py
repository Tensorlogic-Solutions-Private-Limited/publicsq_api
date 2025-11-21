"""
Pydantic schemas for upload-related operations.

This module contains schemas for error handling and upload results
used in the enhanced bulk upload system.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class JobStatusSchema(str, Enum):
    """Job status values for upload jobs."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationErrorTypeSchema(str, Enum):
    """Types of validation errors that can occur during upload."""
    MISSING_REQUIRED_FIELD = "missing_required_field"
    INVALID_DATA_TYPE = "invalid_data_type"
    LOOKUP_FAILED = "lookup_failed"
    PROCESSING_ERROR = "processing_error"


class RowErrorSchema(BaseModel):
    """Schema for representing an error that occurred while processing a specific row."""
    row_number: int = Field(..., description="Row number where the error occurred (1-based)")
    error_type: ValidationErrorTypeSchema = Field(..., description="Type of validation error")
    error_message: str = Field(..., description="Human-readable error message")
    row_data: Dict[str, Any] = Field(default_factory=dict, description="Row data that caused the error")

    class Config:
        json_schema_extra = {
            "example": {
                "row_number": 5,
                "error_type": "missing_required_field",
                "error_message": "Missing required fields: Subject, Medium",
                "row_data": {
                    "Question_text": "What is the capital of India?",
                    "answer_option_A": "Delhi",
                    "Subject": "",
                    "Medium": ""
                }
            }
        }


class ValidationResultSchema(BaseModel):
    """Schema for Excel structure validation result."""
    is_valid: bool = Field(..., description="Whether the Excel structure is valid")
    missing_columns: List[str] = Field(default_factory=list, description="List of missing required columns")
    error_message: Optional[str] = Field(None, description="Error message if validation failed")

    class Config:
        json_schema_extra = {
            "example": {
                "is_valid": False,
                "missing_columns": ["Board", "State", "cognitive_learning"],
                "error_message": "Missing required columns: Board, State, cognitive_learning"
            }
        }


class UploadResultSchema(BaseModel):
    """Schema for the complete upload process result."""
    success_count: int = Field(..., description="Number of successfully processed questions", ge=0)
    error_count: int = Field(..., description="Number of rows that had errors", ge=0)
    errors: List[RowErrorSchema] = Field(default_factory=list, description="List of errors encountered during processing")
    message: str = Field(..., description="Summary message of the upload result")

    class Config:
        json_schema_extra = {
            "example": {
                "success_count": 45,
                "error_count": 5,
                "errors": [
                    {
                        "row_number": 3,
                        "error_type": "missing_required_field",
                        "error_message": "Missing required fields: Subject",
                        "row_data": {"Question_text": "Sample question", "Subject": ""}
                    },
                    {
                        "row_number": 7,
                        "error_type": "lookup_failed",
                        "error_message": "Subject 'Physics' not found in database",
                        "row_data": {"Subject": "Physics"}
                    }
                ],
                "message": "Uploaded 45 questions successfully, 5 rows had errors"
            }
        }


class UploadProgressSchema(BaseModel):
    """Schema for upload progress tracking."""
    total_rows: Optional[int] = Field(None, description="Total number of rows to process")
    processed_rows: int = Field(0, description="Number of rows processed so far", ge=0)
    success_count: int = Field(0, description="Number of successfully processed rows", ge=0)
    error_count: int = Field(0, description="Number of rows with errors", ge=0)
    current_row: Optional[int] = Field(None, description="Currently processing row number")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_rows": 100,
                "processed_rows": 75,
                "success_count": 70,
                "error_count": 5,
                "current_row": 76
            }
        }


class BulkUploadRequestSchema(BaseModel):
    """Schema for bulk upload request parameters."""
    skip_validation: bool = Field(False, description="Whether to skip Excel structure validation")
    continue_on_error: bool = Field(True, description="Whether to continue processing when errors occur")
    max_errors: Optional[int] = Field(None, description="Maximum number of errors before stopping processing", gt=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "skip_validation": False,
                "continue_on_error": True,
                "max_errors": 10
            }
        }


class ErrorSummarySchema(BaseModel):
    """Schema for error summary by type."""
    error_type: ValidationErrorTypeSchema = Field(..., description="Type of validation error")
    count: int = Field(..., description="Number of occurrences of this error type", ge=0)
    sample_message: str = Field(..., description="Sample error message for this type")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_type": "missing_required_field",
                "count": 3,
                "sample_message": "Missing required fields: Subject, Medium"
            }
        }


class DetailedUploadResultSchema(UploadResultSchema):
    """Extended upload result schema with additional details."""
    error_summary: List[ErrorSummarySchema] = Field(default_factory=list, description="Summary of errors by type")
    processing_time_seconds: Optional[float] = Field(None, description="Total processing time in seconds")
    file_info: Optional[Dict[str, Any]] = Field(None, description="Information about the uploaded file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success_count": 45,
                "error_count": 5,
                "errors": [],
                "message": "Uploaded 45 questions successfully, 5 rows had errors",
                "error_summary": [
                    {
                        "error_type": "missing_required_field",
                        "count": 3,
                        "sample_message": "Missing required fields: Subject"
                    },
                    {
                        "error_type": "lookup_failed",
                        "count": 2,
                        "sample_message": "Subject 'Physics' not found in database"
                    }
                ],
                "processing_time_seconds": 12.5,
                "file_info": {
                    "filename": "questions.xlsx",
                    "size_bytes": 15420,
                    "total_rows": 50
                }
            }
        }


class JobStatusResponseSchema(BaseModel):
    """Schema for job status tracking response."""
    job_id: str = Field(..., description="Unique job identifier")
    filename: str = Field(..., description="Name of the uploaded file")
    status: JobStatusSchema = Field(..., description="Current job status")
    uploadedby: str = Field(..., description="Username of the user who uploaded the file")
    total_rows: Optional[int] = Field(None, description="Total number of rows to process")
    processed_rows: int = Field(0, description="Number of rows processed so far", ge=0)
    success_count: int = Field(0, description="Number of successfully processed rows", ge=0)
    error_count: int = Field(0, description="Number of rows with errors", ge=0)
    error_details: Optional[Dict[str, Any]] = Field(None, description="Detailed error information")
    result_message: Optional[str] = Field(None, description="Final result or error message")
    result_loc: Optional[str] = Field(None, description="S3 URL of the result file with processing status")
    started_at: Optional[datetime] = Field(None, description="When job processing started")
    completed_at: Optional[datetime] = Field(None, description="When job processing completed")
    created_at: datetime = Field(..., description="When job was created")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "summary": "Job in Progress",
                    "description": "Example of a job currently being processed",
                    "value": {
                        "job_id": "123e4567-e89b-12d3-a456-426614174000",
                        "filename": "questions_batch_1.xlsx",
                        "status": "processing",
                        "uploadedby": "john_doe",
                        "total_rows": 100,
                        "processed_rows": 75,
                        "success_count": 70,
                        "error_count": 5,
                        "error_details": None,
                        "result_message": None,
                        "started_at": "2024-01-15T10:30:00Z",
                        "completed_at": None,
                        "created_at": "2024-01-15T10:29:45Z"
                    }
                },
                {
                    "summary": "Completed Successfully",
                    "description": "Example of a successfully completed job with no errors",
                    "value": {
                        "job_id": "456e7890-e89b-12d3-a456-426614174001",
                        "filename": "questions_perfect.xlsx",
                        "status": "completed",
                        "uploadedby": "jane_smith",
                        "total_rows": 50,
                        "processed_rows": 50,
                        "success_count": 50,
                        "error_count": 0,
                        "error_details": None,
                        "result_message": "Upload completed successfully: 50 questions created",
                        "started_at": "2024-01-15T11:00:00Z",
                        "completed_at": "2024-01-15T11:01:30Z",
                        "created_at": "2024-01-15T10:59:45Z"
                    }
                },
                {
                    "summary": "Completed with Errors",
                    "description": "Example of a completed job with some row errors",
                    "value": {
                        "job_id": "789e1234-e89b-12d3-a456-426614174002",
                        "filename": "questions_mixed.xlsx",
                        "status": "completed",
                        "uploadedby": "mike_wilson",
                        "total_rows": 100,
                        "processed_rows": 100,
                        "success_count": 85,
                        "error_count": 15,
                        "error_details": {
                            "errors": [
                                {
                                    "row_number": 3,
                                    "error_type": "missing_required_field",
                                    "error_message": "Missing required fields: Subject, Medium",
                                    "row_data": {
                                        "Question_text": "What is photosynthesis?",
                                        "Subject": "",
                                        "Medium": ""
                                    }
                                },
                                {
                                    "row_number": 15,
                                    "error_type": "lookup_failed",
                                    "error_message": "Subject 'Advanced Physics' not found in database",
                                    "row_data": {
                                        "Subject": "Advanced Physics"
                                    }
                                }
                            ],
                            "error_summary": [
                                {
                                    "error_type": "missing_required_field",
                                    "count": 10,
                                    "sample_message": "Missing required fields: Subject, Medium"
                                },
                                {
                                    "error_type": "lookup_failed",
                                    "count": 5,
                                    "sample_message": "Subject not found in database"
                                }
                            ]
                        },
                        "result_message": "Upload completed: 85 questions created successfully, 15 rows had errors",
                        "started_at": "2024-01-15T12:00:00Z",
                        "completed_at": "2024-01-15T12:03:45Z",
                        "created_at": "2024-01-15T11:59:30Z"
                    }
                },
                {
                    "summary": "Failed Job",
                    "description": "Example of a job that failed due to system error",
                    "value": {
                        "job_id": "abc1234-e89b-12d3-a456-426614174003",
                        "filename": "corrupted_file.xlsx",
                        "status": "failed",
                        "uploadedby": "sarah_jones",
                        "total_rows": None,
                        "processed_rows": 0,
                        "success_count": 0,
                        "error_count": 0,
                        "error_details": None,
                        "result_message": "File processing failed: Invalid Excel format or corrupted file",
                        "started_at": "2024-01-15T13:00:00Z",
                        "completed_at": "2024-01-15T13:00:15Z",
                        "created_at": "2024-01-15T12:59:45Z"
                    }
                }
            ]
        }


class JobListResponseSchema(BaseModel):
    """Schema for list of all upload jobs."""
    jobs: List[JobStatusResponseSchema] = Field(..., description="List of all upload jobs")
    total_count: int = Field(..., description="Total number of jobs", ge=0)
    grandTotal: int = Field(..., description="Total number of all jobs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "jobs": [
                    {
                        "job_id": "2b7dca2d-aa1e-417b-92cc-1ef36d25855c",
                        "filename": "QuestionBulkUploadtemplate_v3.xlsx",
                        "status": "completed",
                        "uploadedby": "admin_user",
                        "total_rows": 1,
                        "processed_rows": 1,
                        "success_count": 1,
                        "error_count": 0,
                        "error_details": None,
                        "result_message": "Successfully processed all 1 questions",
                        "started_at": "2025-09-10T06:09:05.961725Z",
                        "completed_at": "2025-09-10T06:09:06.686458Z",
                        "created_at": "2025-09-10T06:09:05.750222Z"
                    },
                    {
                        "job_id": "f64090bb-e269-47b8-b603-6e61137e94c3",
                        "filename": "QuestionBulkUploadtemplate_v3.xlsx",
                        "status": "completed",
                        "uploadedby": "test_user",
                        "total_rows": 1,
                        "processed_rows": 1,
                        "success_count": 0,
                        "error_count": 1,
                        "error_details": {
                            "error_summary": {
                                "lookup_failed": {
                                    "count": 1,
                                    "sample_message": "Master data lookup failed: 'cognitive_learning'",
                                    "sample_row": 2
                                }
                            }
                        },
                        "result_message": "Processed 1 rows: 0 successful, 1 errors",
                        "started_at": "2025-09-10T05:52:49.269740Z",
                        "completed_at": "2025-09-10T05:52:50.239953Z",
                        "created_at": "2025-09-10T05:52:48.770550Z"
                    }
                ],
                "total_count": 2
            }
        }