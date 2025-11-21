from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.services.metadata_service import (
    get_all_mediums, get_all_subjects, get_all_formats, get_all_question_types, get_all_boards, get_all_states
)
from app.services.subject_service import SubjectService
from app.utils.auth import get_current_user
# from app.schemas.pydantic_models import MediumResponse, SubjectResponse, FormatResponse, QuestionTypeListResponse
# from app.schemas.pydantic_models import MediumBase, MediumResponse, SubjectBase, SubjectListResponse, FormatBase, FormatResponse, QuestionTypeBase, QuestionTypeListResponse
from app.schemas.metadata import MediumResponse, SubjectListResponse, FormatResponse, QuestionTypeListResponse, BoardResponse, StateResponse
from app.schemas.subjects import SubjectCreateRequest, SubjectCreateResponse, SubjectConflictResponse
from app.models.user import User

from app.database import get_db

router = APIRouter()

@router.get("/v1/mediums", tags=["Dropdowns"], response_model=MediumResponse)
async def get_mediums(db: AsyncSession = Depends(get_db),current_user=Depends(get_current_user)):
    """
        Retrieve all available mediums.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if access is restricted)

        ### Path Parameters:
        - None

        ### Query Parameters:
        - None

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json):
        - **200 OK**: Returns a list of mediums.

        #### Each item includes:
        - **medium_code** (str): Unique code representing the medium.
        - **medium_name** (str): Name of the medium (e.g., "English", "Hindi").

        ### Example Response:
        ```json
        [
            {
                "medium_code": "2000",
                "medium_name": "English"
            },
            {
                "medium_code": "2001",
                "medium_name": "Tamil"
            }
        ]
        ```

        ### Error Responses:
        - **500 Internal Server Error**: If a database or server error occurs.

        ### Notes:
        - Useful for categorizing or filtering educational content based on medium (e.g., language of instruction).
        - You can later enhance this model to include attributes like `active_status`, `display_order`, or descriptions.
    """
    return await get_all_mediums(db)

@router.get("/v1/subjects", tags=["Dropdowns"], response_model=SubjectListResponse)
async def get_subjects(
    standard: Optional[str] = Query(None, description="Filter by standard/class (e.g., '10', '12')"),
    medium_code: Optional[str] = Query(None, description="Filter by medium code (e.g., '2000')"),
    db: AsyncSession = Depends(get_db), 
    current_user=Depends(get_current_user)
):
    """
        Retrieve all available subjects.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if secured)

        ### Path Parameters:
        - None

        ### Query Parameters:
        - **standard** (str, optional): Filter by standard/class (e.g., '10', '12')
        - **medium_code** (str, optional): Filter by medium code (e.g., '2000')

        ### Request Body:
        - None (This is a GET request)

        ### Response (application/json):
        - **200 OK**: A list of subjects.

        #### Each item includes:
        - **subject_code** (str): Code of the subject.
        - **subject_name** (str): Name of the subject.
        - **standard** (str): Class (standard) of the subject.
        - **medium_code** (str): Unique Code to the medium.

        ### Example Response:
        ```json
        {
            "data": [
                {
                    "subject_code": "1001",
                    "subject_name": "Science",
                    "standard": "10",
                    "medium_code": '2000'
                }
            ]
        }
        ```

        ### Error Responses:
        - **500 Internal Server Error**: If something goes wrong with the database.

        ### Notes:
        - Useful for dropdowns and filtering in design/question forms.
        - Supports filtering by standard and medium_code for more targeted results.
        - Example usage: `/v1/subjects?standard=10&medium_code=2000`
    """
    return await get_all_subjects(db, standard=standard, medium_code=medium_code)

@router.post("/v1/subjects", tags=["Subjects"], response_model=SubjectCreateResponse, status_code=201, responses={409: {"model": SubjectConflictResponse}})
async def create_subject(
    subject_data: SubjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new subject with auto-generated subject code.

    ### Request Headers:
    - `Content-Type`: application/json
    - `Authorization`: Bearer token (required)

    ### Path Parameters:
    - None

    ### Query Parameters:
    - None

    ### Request Body (application/json):
    - **subject_name** (str): Name of the subject (e.g., "Mathematics", "Science")
    - **standard** (str): Class/standard level (e.g., "1", "10", "12")
    - **medium_code** (str): Code of the medium from medium_master_table

    ### Example Request:
    ```json
    {
        "subject_name": "Advanced Mathematics",
        "standard": "12",
        "medium_code": "2000"
    }
    ```

    ### Response (application/json):
    - **201 Created**: Subject created successfully

    #### Success Response includes:
    - **subject_code** (str): Auto-generated unique subject code (e.g., "3001")
    - **subject_name** (str): Name of the created subject
    - **standard** (str): Class/standard level
    - **medium_id** (int): Medium ID
    - **message** (str): Success message

    ### Example Success Response:
    ```json
    {
        "subject_code": "3001",
        "subject_name": "Advanced Mathematics",
        "standard": "12",
        "medium_id": 1,
        "message": "Subject created successfully"
    }
    ```

    ### Error Responses:
    - **400 Bad Request**: Validation errors or invalid medium_id
    - **400 Bad Request**: Validation errors or invalid medium_code
    - **401 Unauthorized**: Missing or invalid authentication token
    - **409 Conflict**: Subject already exists (duplicate name + standard + medium combination)
    - **500 Internal Server Error**: Database or server error

    #### Conflict Response (409):
    ```json
    {
        "detail": "Subject already exists",
        "existing_subject": {
            "subject_code": "3005",
            "subject_name": "Advanced Mathematics",
            "standard": "12",
            "medium_id": 1
        }
    }
    ```

    ### Notes:
    - Subject codes are auto-generated using the formula: total_subjects_count + 3001
    - Subject name matching is case-insensitive for duplicate detection
    - Authentication is required via JWT token
    - The combination of subject_name + standard + medium_code must be unique
    - Created subjects are immediately available for use in question creation and other features
    """
    return await SubjectService.create_subject(subject_data, db, current_user.id)

@router.get("/v1/formats", tags=["Dropdowns"], response_model=FormatResponse)
async def get_formats(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
        Retrieve all available question formats.

        Returns a list of question formats used to categorize question structure or presentation.

        ### Headers:
        - `Content-Type`: `application/json`
        - *(Optional)* `Authorization`: `Bearer <token>` — Required if access is restricted.

        ### Response:
        - **200 OK**: List of question formats.

        #### Each item includes:
        - `qfm_format_code` (str): Unique format code (e.g., "5000").
        - `qfm_format_name` (str): Descriptive name (e.g., "Text").

        #### Example:
        ```json
        {
        "data": [
            {
            "format_code": "5000",
            "format_name": "Text"
            }
        ]
        }
        ```

        ### Errors:
        - **500 Internal Server Error**: Server/database error.

        ### Notes:
        Useful for filtering or categorizing questions. Can be extended with metadata like `active_status`, `description`, or `display_order`.
    """
    return await get_all_formats(db)

@router.get("/v1/question_types", tags=["Dropdowns"], response_model=QuestionTypeListResponse)
async def get_question_types(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
        Retrieve all available question types.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if the endpoint is secured)

        ### Path Parameters:
        - None

        ### Query Parameters:
        - None

        ### Request Body:
        - None (This is a GET request)

        ### Response (application/json):
        - **200 OK**: A list of question types.

        #### Each item includes:
        - **id** (int): Unique identifier for the question type.
        - **qtm_type_code** (str): Unique code for the question type (e.g., "1000").
        - **qtm_type_name** (str): Descriptive name of the question type (e.g., "MCQ").

        ### Example Response:
        ```json
        {
        "data": [
                {
                    "id": 1,
                    "type_code": "1000",
                    "type_name": "MCQ"
                }
            ]
        }
        ```

        ### Error Responses:
        - **500 Internal Server Error**: If something goes wrong with the database connection or query.

        ### Notes:
        - This endpoint is helpful for populating question type dropdowns in forms or filtering question sets.
        - You can later extend the response model to include metadata like display order, status, or usage count.
    """
    
    return await get_all_question_types(db)

@router.get("/v1/boards", tags=["Dropdowns"], response_model=BoardResponse)
async def get_boards(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
        Retrieve all available boards.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if the endpoint is secured)

        ### Path Parameters:
        - None

        ### Query Parameters:
        - None

        ### Request Body:
        - None (This is a GET request)

        ### Response (application/json):
        - **200 OK**: A list of boards.

        #### Each item includes:
        - **board_id** (int): Unique identifier for the board.
        - **board_name** (str): Name of the board (e.g., "CBSE", "ICSE").

        ### Example Response:
        ```json
        {
        "data": [
                {
                    "board_id": 6,
                    "board_name": "CBSE"
                }
            ]
        }
        ```

        ### Error Responses:
        - **500 Internal Server Error**: If something goes wrong with the database connection or query.

        ### Notes:
        - This endpoint is helpful for populating board dropdowns in forms or filtering content by board.
        - Useful for educational content categorization and filtering.
    """
    
    return await get_all_boards(db)

@router.get("/v1/states", tags=["Dropdowns"], response_model=StateResponse)
async def get_states(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """
        Retrieve all available states.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if the endpoint is secured)

        ### Path Parameters:
        - None

        ### Query Parameters:
        - None

        ### Request Body:
        - None (This is a GET request)

        ### Response (application/json):
        - **200 OK**: A list of states.

        #### Each item includes:
        - **id** (int): Unique identifier for the state.
        - **state_name** (str): Name of the state (e.g., "Karnataka", "Tamil Nadu").
        - **iso_code** (str, optional): ISO code for the state (e.g., "IN-KA", "IN-TN").

        ### Example Response:
        ```json
        {
        "data": [
                {
                    "id": 6,
                    "state_name": "Karnataka",
                    "iso_code": "IN-KA"
                },
                {
                    "id": 8,
                    "state_name": "TN",
                    "iso_code": "IN-TN"
                }
            ]
        }
        ```

        ### Error Responses:
        - **500 Internal Server Error**: If something goes wrong with the database connection or query.

        ### Notes:
        - This endpoint is helpful for populating state dropdowns in forms or filtering content by state.
        - Useful for educational content categorization and filtering.
        - The iso_code field may be null for states that don't have ISO codes assigned yet.
    """
    
    return await get_all_states(db)