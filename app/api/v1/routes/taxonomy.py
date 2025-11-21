"""
Taxonomy API routes for creating and managing subject taxonomy entries.

This module provides RESTful endpoints for taxonomy management operations,
supporting three creation scenarios and listing with filtering capabilities.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
from pydantic import ValidationError

from app.services.taxonomy_service import TaxonomyService
from app.services.taxonomy_response_helper import TaxonomyResponseHelper
from app.utils.auth import get_current_user
from app.schemas.taxonomy import (
    TaxonomyCreateRequest,
    TaxonomyCreateResponse,
    TaxonomyConflictResponse
)
from app.database import get_db
from app.models.user import User
from app.decorators.permissions import require_permission

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/v1/taxonomy",
    tags=["Taxonomy"],
    response_model=TaxonomyCreateResponse,
    status_code=201,
    responses={409: {"model": TaxonomyConflictResponse}}
)
@require_permission("question_bank.upload")
async def create_taxonomy(
    request: Request,
    taxonomy_data: TaxonomyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new taxonomy entry with auto-generated codes.

    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)

    ### Path Parameters:
    - None

    ### Query Parameters:
    - None

    ### Request Body (application/json):
    Supports three creation scenarios:

    #### Scenario 1: Complete New Hierarchy
    Create entirely new chapter, topic, and subtopic:
    ```json
    {
        "subject_code": "3001",
        "medium_code": "2000",
        "standard": "10",
        "board_id": 7,
        "state_id": 9,
        "chapter_name": "Algebra",
        "topic_name": "Linear Equations",
        "subtopic_name": "Solving Linear Equations"
    }
    ```

    #### Scenario 2: New Topic in Existing Chapter
    Add new topic and subtopic to existing chapter:
    ```json
    {
        "subject_code": "3001",
        "medium_code": "2000",
        "standard": "10",
        "board_id": 7,
        "state_id": 9,
        "chapter_code": "C001",
        "topic_name": "Quadratic Equations",
        "subtopic_name": "Solving Quadratic Equations"
    }
    ```

    #### Scenario 3: New Subtopic in Existing Topic
    Add new subtopic to existing chapter/topic combination:
    ```json
    {
        "subject_code": "3001",
        "medium_code": "2000",
        "standard": "10",
        "board_id": 7,
        "state_id": 9,
        "chapter_code": "C001",
        "topic_code": "T001",
        "subtopic_name": "Advanced Problem Solving"
    }
    ```

    ### Response (application/json):
    - **201 Created**: Taxonomy created successfully

    #### Success Response includes:
    - **taxonomy_code** (str): Auto-generated unique taxonomy code (format: TAXC000T000S001-B7-S9-M3-STD10-S11)
    - **subject_code** (str): Subject code from the request
    - **medium_code** (str): Medium code from the request
    - **standard** (str): Standard from the request
    - **board_id** (int): Board ID from the request
    - **state_id** (int): State ID from the request
    - **chapter_code** (str): Chapter code (format: C000) - either provided or auto-generated
    - **chapter_name** (str): Chapter name
    - **topic_code** (str): Topic code (format: T000) - either provided or auto-generated
    - **topic_name** (str): Topic name
    - **subtopic_code** (str): Subtopic code (format: S000) - auto-generated
    - **subtopic_name** (str): Subtopic name from the request
    - **message** (str): Success message
    - **created_by** (str, optional): Username of the user who created the taxonomy
    - **created_at** (str, optional): Timestamp when the taxonomy was created

    ### Example Success Response:
    ```json
    {
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
    ```

    ### Error Responses:
    - **400 Bad Request**: Validation errors or invalid scenario combinations
    - **401 Unauthorized**: Missing or invalid authentication token
    - **404 Not Found**: Referenced codes (chapter_code, topic_code) not found in scenarios 2 & 3
    - **409 Conflict**: Taxonomy already exists (duplicate hierarchy and context)
    - **500 Internal Server Error**: Database or server error

    #### Conflict Response (409):
    ```json
    {
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
    ```

    ### Notes:
    - Taxonomy codes are auto-generated using sequential numbering with zero-padding
    - Chapter codes: C000, C001, C002, etc.
    - Topic codes: T000, T001, T002, etc.
    - Subtopic codes: S000, S001, S002, etc.
    - Complex taxonomy codes combine all elements: TAXC000T000S001-B7-S9-M3-STD10-S11
    - Authentication is required via JWT token
    - The combination of hierarchy codes and context must be unique
    - Created taxonomies are immediately available for use in question creation
    - All master data references (subject, medium, board, state) are validated
    """
    # Log request
    logger.info(
        f"Taxonomy creation request from user {current_user.username}",
        extra={
            "user_id": current_user.id,
            "username": current_user.username,
            "request_data": taxonomy_data.dict(),
            "client_ip": request.client.host if request.client else None
        }
    )
    
    try:
        # No additional validation needed - schema and service layer handle optional fields
        
        result = await TaxonomyService.create_taxonomy(taxonomy_data, db, current_user.id)
        
        # Check if result is a conflict response
        if isinstance(result, dict) and "existing_taxonomy" in result:
            logger.info(
                f"Taxonomy creation conflict for user {current_user.username}",
                extra={
                    "user_id": current_user.id,
                    "conflict_data": result
                }
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=result
            )
        
        # Build success response
        response_data = TaxonomyResponseHelper.build_create_response(result)
        
        # Log successful creation
        logger.info(
            f"Taxonomy created successfully by user {current_user.username}",
            extra={
                "user_id": current_user.id,
                "taxonomy_code": response_data.get("taxonomy_code"),
                "taxonomy_id": getattr(result, 'id', None)
            }
        )
        
        return TaxonomyCreateResponse(**response_data)
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(
            f"Validation error in taxonomy creation for user {current_user.username}: {str(e)}",
            extra={
                "user_id": current_user.id,
                "validation_errors": e.errors()
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in taxonomy creation for user {current_user.username}: {str(e)}",
            extra={
                "user_id": current_user.id,
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating taxonomy"
        )


