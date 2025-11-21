from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, List
from app.services.question_service import (
    get_chapter_topic_question_counts, 
    get_questions_by_filters,
    get_questions_by_organizational_filters,
    get_questions_by_organizational_filters_v3,
    upload_question,
    update_question,
    delete_question,
    get_question_by_code
)

from app.services.response_helpers import QuestionResponseHelper
from app.services.state_resolution_service import StateResolutionService
from app.utils.auth import get_current_user
from app.schemas.questions import (
    ChapterTopicQuestionCountResponse, 
    ExamQuestionsResponse,
    ExamQuestionsV3Response,
    QuestionUpdateRequest,
    QuestionResponse
)
from app.database import get_db
from app.models.user import User
from app.decorators.permissions import require_permission, scope_filter
from app.middleware.rbac import rbac_middleware

router = APIRouter()

async def get_scope_filter(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Optional[Dict[str, Any]]:
    """Dependency to get scope filter for the current user."""
    return await rbac_middleware.get_question_scope_filter(db, current_user)

@router.get("/v1/chapters_topics", tags=["Questions"], response_model=ChapterTopicQuestionCountResponse)
@require_permission("question_bank.view")
async def get_chapter_topic_question_counts_route(
    standard: str = Query(..., description="Class/standard (e.g., '10')"),
    medium_code: str = Query(..., description="Medium Code"),
    subject_code: str = Query(..., description="Subject Code"),
    board_id: Optional[int] = Query(None, description="Board ID filter", gt=0),
    state_id: Optional[int] = Query(None, description="State ID filter (auto-resolved from user context if not provided)", gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
    Retrieve chapters, topics, and their question counts for a given standard, medium, and subject.

    ### Request Headers:
    - `Content-Type`: application/json  
    - *(Optional)* `Authorization`: Bearer token (if access is restricted)

    ### Query Parameters:
    - **standard** (str, required): Standard/class (e.g., `"10"`).
    - **medium_code** (str, required): Medium code (e.g., `"2000"` for English).
    - **subject_code** (str, required): Subject code (e.g., `"3000"` for Social Science).
    - **board_id** (int, optional): Board ID filter to match exam creation logic.
    - **state_id** (int, optional): State ID filter to match exam creation logic.

    ### Path Parameters:
    - None

    ### Request Body:
    - None (GET request does not require a body)

    ### Response (application/json):
    - **200 OK**: Returns a list of chapters, their topics, and associated question counts.

    #### Example Response:
    ```json
    {
      "data": [
        {
          "code": "1000",
          "name": "Climate and Natural Vegetation of India",
          "question_count": 50,
          "topics": [
            {
              "code": "10000",
              "name": "Distribution of rainfall",
              "question_count": 2,
              "subtopics": []
            },
            {
              "code": "10001",
              "name": "Introduction",
              "question_count": 28,
              "subtopics": []
            },
            {
              "code": "10002",
              "name": "Monsoon",
              "question_count": 7,
              "subtopics": []
            },
            {
              "code": "10004",
              "name": "The factors affecting the climate",
              "question_count": 10,
              "subtopics": []
            },
            {
              "code": "10005",
              "name": "Wildlife",
              "question_count": 3,
              "subtopics": []
            }
          ]
        },
        {
          "code": "1001",
          "name": "India's Foreign Policy",
          "question_count": 16,
          "topics": [
            {
              "code": "10006",
              "name": "Basic Determinants of a Foreign Policy",
              "question_count": 1,
              "subtopics": []
            },
            {
              "code": "10008",
              "name": "Main objectives of our Foreign Policy",
              "question_count": 2,
              "subtopics": []
            },
            {
              "code": "10009",
              "name": "Non-aligned movement",
              "question_count": 5,
              "subtopics": []
            }
          ]
        }
      ]
    }
    ```

    ### Error Responses:
    - **400 Bad Request**:
        ```json
        { "detail": "Missing required query parameters: standard, medium_code, or subject_code." }
        ```
    - **404 Not Found**:
        ```json
        { "detail": "No chapters or topics found for the given parameters." }
        ```
    - **500 Internal Server Error**:
        ```json
        { "detail": "Unexpected error occurred while retrieving chapter/topic data." }
        ```

    ### Notes:
    - Provides hierarchical data: **Chapters → Topics → Subtopics** with question counts.
    - Helps exam designers select chapters/topics with enough questions for exam design.
    - Can be used in question paper design workflows to show available content.
    - State ID is auto-resolved from user context if not provided (for non-admin roles)
    """
    # Resolve state_id from user context if not provided
    user_role = current_user.role.role_code if current_user.role else None
    
    if state_id is None:
        # Auto-resolve state_id based on user role
        if user_role in ["super_admin", "admin", "admin_user"]:
            # Admin roles can see all states if not specified
            resolved_state_id = None
        else:
            # For block_admin and teacher, resolve from user context
            resolved_state_id = await StateResolutionService.resolve_state_for_user(
                db=db,
                user=current_user,
                explicit_state_id=None
            )
    else:
        # Use provided state_id
        resolved_state_id = state_id
    
    return await get_chapter_topic_question_counts(standard, medium_code, subject_code, db, current_user, scope_filter, board_id, resolved_state_id)

@router.get("/v1/questions", tags=["Questions"], response_model=ExamQuestionsResponse)
@require_permission("question_bank.view")
async def get_questions(
    type: str = Query(..., description="chapter or topic"),
    codes: str = Query(..., description="Comma-separated list of codes"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
        Retrieve questions filtered by chapter or topic codes.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (if access is restricted)

        ### Query Parameters:
        - **type** (str, required): Must be either `"chapter"` or `"topic"`.
            - Indicates whether to fetch questions based on chapter or topic codes.
        - **codes** (str, required): Comma-separated list of codes.
            - Example: `"C100,C101"` for chapters or `"T100,T101"` for topics.

        ### Path Parameters:
        - None

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json):
        - **200 OK**: Returns question groups and detailed question data.

        #### Example Response:
        ```json
        {
        "qn_groups": [
            {
            "type": "chapter",
            "type_codes": ["1000"],
            "type_names": ["Climate and Natural Vegetation of India"],
            "no_of_qns": 50
            }
        ],
        "qns": [
            {
            "code": "Q1258163",
            "type": "MCQ",
            "marks": 1,
            "difficulty_level": "Medium",
            "grp_type": "chapter",
            "grp_type_name": "Climate and Natural Vegetation of India",
            "grp_type_code": "1000",
            "text": "Which is in the Eastern border of Tamil Nadu?"
            }
        ]
        }
        ```

        ### Error Responses:
        - **400 Bad Request**:
            ```json
            { "detail": "Invalid type. Must be 'chapter' or 'topic'." }
            ```
        - **404 Not Found**:
            ```json
            { "detail": "No questions found for the provided codes." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while fetching questions." }
            ```

        ### Notes:
        - Use this endpoint to fetch questions tied to specific **chapters** or **topics**.
        - The response includes both:
            - **`qn_groups`**: Summary of selected chapter/topic groups with question counts.
            - **`qns`**: Detailed list of individual questions.
        - Useful for exam paper design and manual question selection workflows.
    """
    return await get_questions_by_filters(type, codes, db, current_user, scope_filter)


@router.get("/v2/questions", tags=["Questions"], response_model=ExamQuestionsResponse)
@require_permission("question_bank.view")
async def get_questions_filtered(
    subject_code: str = Query(..., description="Filter by subject code (e.g., '3005')"),
    board_id: int = Query(..., description="Filter by board ID (required)", gt=0),
    state_id: int = Query(..., description="Filter by state ID (required)", gt=0),
    medium_code: str = Query(..., description="Filter by medium code (e.g., '2000')"),
    standard: str = Query(..., description="Filter by standard/class (e.g., '10', '12')"),
    question_text: Optional[str] = Query(None, description="Search in question text (optional)"),
    limit: int = Query(50, description="Maximum number of results", gt=0),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
    Retrieve questions filtered by organizational criteria with optional text search and pagination.

    ### Request Headers:
    - `Content-Type`: application/json  
    - *(Optional)* `Authorization`: Bearer token (if access is restricted)

    ### Query Parameters:
    - **subject_code** (str, required): Filter questions by subject code (e.g., "3005").
    - **board_id** (int, required): Filter questions by board ID (must be positive integer).
    - **state_id** (int, required): Filter questions by state ID (must be positive integer).
    - **medium_code** (str, required): Filter questions by medium code (e.g., "2000").
    - **standard** (str, required): Filter questions by standard/class (e.g., "10", "12").
    - **question_text** (str, optional): Search in question text (case-insensitive partial match).
    - **limit** (int, optional): Maximum number of results (default: 50, must be positive).
    - **offset** (int, optional): Number of results to skip for pagination (default: 0, must be >= 0).

    ### Path Parameters:
    - None

    ### Request Body:
    - None (GET request does not require a body)

    ### Response (application/json):
    - **200 OK**: Returns question groups and detailed question data.

    #### Example Response:
    ```json
    {
    "qn_groups": [
        {
        "type": "chapter",
        "type_codes": ["1000", "1001"],
        "type_names": ["Climate and Natural Vegetation of India", "Agriculture in India"],
        "no_of_qns": 25
        }
    ],
    "qns": [
        {
        "code": "Q31",
        "type": "MCQ",
        "marks": 1,
        "difficulty_level": "Medium",
        "grp_type": "chapter",
        "grp_type_name": "Indian Constitution",
        "grp_type_code": "C001",
        "text": "Who was the first President of India?",
        "option1": "Dr. Rajendra Prasad",
        "option2": "Jawaharlal Nehru",
        "option3": "S. Radhakrishnan",
        "option4": "Mahatma Gandhi",
        "correct_answer": "a"
        }
    ]
    }
    ```

    ### Error Responses:
    - **400 Bad Request**:
        ```json
        { "detail": "subject_id must be a positive integer" }
        ```
    - **404 Not Found**:
        ```json
        { "detail": "No questions found for the provided criteria." }
        ```
    - **500 Internal Server Error**:
        ```json
        { "detail": "Unexpected error occurred while fetching questions." }
        ```

    ### Notes:
    - Use this endpoint to fetch questions filtered by organizational criteria with optional text search.
    - The five organizational parameters (subject_code, board_id, state_id, medium_code, standard) are mandatory.
    - Uses business codes instead of database IDs for better stability and portability.
    - Text search is optional and performs case-insensitive partial matching.
    - Results are paginated using limit and offset parameters.
    - Questions are grouped by chapter by default.
    - The response includes both:
        - **`qn_groups`**: Summary of chapter groups with question counts.
        - **`qns`**: Detailed list of individual questions with all options and correct answer.
    - Combines organizational filtering with text search functionality.
    """
    return await get_questions_by_organizational_filters(
        subject_code, board_id, state_id, medium_code, standard, db, current_user, scope_filter, question_text, limit, offset
    )


@router.get("/v3/questions", tags=["Questions"], response_model=ExamQuestionsV3Response)
@require_permission("question_bank.view")
async def get_questions_filtered_v3(
    subject_code: str = Query(..., description="Filter by subject code (e.g., '3005')"),
    board_id: int = Query(..., description="Filter by board ID (required)", gt=0),
    state_id: int = Query(..., description="Filter by state ID (required)", gt=0),
    medium_code: str = Query(..., description="Filter by medium code (e.g., '2000')"),
    standard: str = Query(..., description="Filter by standard/class (e.g., '10', '12')"),
    question_text: Optional[str] = Query(None, description="Search in question text (optional)"),
    limit: int = Query(50, description="Maximum number of results", gt=0),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
    Retrieve questions filtered by organizational criteria with v3 unified response format.

    ### Request Headers:
    - `Content-Type`: application/json  
    - *(Optional)* `Authorization`: Bearer token (if access is restricted)

    ### Query Parameters:
    - **subject_code** (str, required): Filter questions by subject code (e.g., "3005").
    - **board_id** (int, required): Filter questions by board ID (must be positive integer).
    - **state_id** (int, required): Filter questions by state ID (must be positive integer).
    - **medium_code** (str, required): Filter questions by medium code (e.g., "2000").
    - **standard** (str, required): Filter questions by standard/class (e.g., "10", "12").
    - **question_text** (str, optional): Search in question text (case-insensitive partial match).
    - **limit** (int, optional): Maximum number of results (default: 50, must be positive).
    - **offset** (int, optional): Number of results to skip for pagination (default: 0, must be >= 0).

    ### Path Parameters:
    - None

    ### Request Body:
    - None (GET request does not require a body)

    ### Response (application/json):
    - **200 OK**: Returns question groups and detailed question data with unified structure.

    #### Example Response for Text Questions:
    ```json
    {
    "qn_groups": [
        {
        "type": "chapter",
        "type_codes": ["1000", "1001"],
        "type_names": ["Algebra", "Geometry"],
        "no_of_qns": 25
        }
    ],
    "qns": [
        {
        "code": "Q31",
        "type": "MCQ",
        "marks": 1,
        "difficulty_level": "Medium",
        "grp_type": "chapter",
        "grp_type_name": "Algebra",
        "grp_type_code": "C001",
        "format_code": "5000",
        "type_code": "1000",
        "correct_answer": "A",
        "qn": {
            "text": "What is the value of x in 2x + 5 = 15?"
        },
        "option1": {
            "text": "x = 5"
        },
        "option2": {
            "text": "x = 10"
        },
        "option3": {
            "text": "x = 7.5"
        },
        "option4": {
            "text": "x = 2.5"
        }
        }
    ]
    }
    ```

    #### Example Response for Image Questions:
    ```json
    {
    "qns": [
        {
        "code": "Q67890",
        "format_code": "6000",
        "qn": {
            "text": "What is the area of the triangle shown?",
            "media": ["https://s3.amazonaws.com/bucket/triangle-diagram.jpg"]
        },
        "option1": {
            "text": "25 square units",
            "media": ["https://s3.amazonaws.com/bucket/option1-calc.jpg"]
        },
        "option2": {
            "text": "30 square units", 
            "media": []
        }
        }
    ]
    }
    ```

    ### Error Responses:
    - **400 Bad Request**:
        ```json
        { "detail": "subject_id must be a positive integer" }
        ```
    - **404 Not Found**:
        ```json
        { "detail": "No questions found for the provided criteria." }
        ```
    - **500 Internal Server Error**:
        ```json
        { "detail": "Unexpected error occurred while fetching questions." }
        ```
    """
    return await get_questions_by_organizational_filters_v3(
        subject_code, board_id, state_id, medium_code, standard, db, current_user, scope_filter, question_text, limit, offset
    )


@router.get("/v1/questions/{question_code}", tags=["Questions"], response_model=QuestionResponse)
@require_permission("question_bank.view")
@scope_filter("hierarchical")
async def get_question(
    question_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = None
):
    """
    Get a specific question by question code.
    
    The question must be within the user's organizational scope to be accessible.
    
    ### Path Parameters:
    - **question_code** (str, required): Question code (e.g., "Q123")
    
    ### Response:
    - **200 OK**: Question details
    - **404 Not Found**: Question not found or not accessible
    - **403 Forbidden**: Insufficient permissions
    """
    question = await get_question_by_code(question_code, db, current_user, scope_filter)
    
    # Use QuestionResponseHelper to build response data
    response_data = QuestionResponseHelper.build_response_data(question)
    
    return QuestionResponse(**response_data)


@router.put("/v1/questions/{question_code}", tags=["Questions"], response_model=QuestionResponse)
@require_permission("question_bank.edit", resource_owner_param="question_owner_id")
@scope_filter("hierarchical")
async def update_question_endpoint(
    question_code: str,
    question_data: QuestionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
    Update an existing question.
    
    For School Admin role, only questions created by the user can be edited (ownership restriction).
    Other admin roles can edit questions within their organizational scope.
    
    ### Path Parameters:
    - **question_code** (str, required): Question code (e.g., "Q123")
    
    ### Request Body (application/json):
    - **question_text** (str, optional): The question text
    - **option1** (str, optional): First answer option
    - **option2** (str, optional): Second answer option
    - **option3** (str, optional): Third answer option
    - **option4** (str, optional): Fourth answer option
    - **correct_answer** (str, optional): Correct answer option
    - **marks** (int, optional): Question marks
    - **format_code** (str, optional): Question format code (e.g., "5000")
    - **type_code** (str, optional): Question type code (e.g., "1000")
    - **chapter_code** (str, optional): Chapter code
    - **topic_code** (str, optional): Topic code
    - **subtopic_code** (str, optional): Subtopic code
    - **subject_code** (str, optional): Subject code
    - **medium_code** (str, optional): Medium code
    - **board_id** (int, optional): Board ID
    - **state_id** (int, optional): State ID
    - **cognitive_learning_id** (int, optional): Cognitive learning ID
    - **difficulty_id** (int, optional): Difficulty ID
    
    ### Response:
    - **200 OK**: Updated question details
    - **404 Not Found**: Question not found or not accessible
    - **403 Forbidden**: Insufficient permissions or ownership restriction
    """
    # First check if question exists and is accessible
    existing_question = await get_question_by_code(question_code, db, current_user, scope_filter)
    
    # Add question owner ID for ownership validation
    question_owner_id = existing_question.created_by
    
    # Update the question
    updated_question = await update_question(
        question_code, 
        question_data.dict(exclude_unset=True), 
        db, 
        current_user
    )
    await db.commit()
    
    # Use QuestionResponseHelper to build response data
    response_data = QuestionResponseHelper.build_response_data(updated_question)
    
    return QuestionResponse(**response_data)


@router.delete("/v1/questions/{question_code}", tags=["Questions"])
@require_permission("question_bank.delete", resource_owner_param="question_owner_id")
@scope_filter("hierarchical")
async def delete_question_endpoint(
    question_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope_filter: Optional[Dict[str, Any]] = Depends(get_scope_filter)
):
    """
    Delete a question.
    
    For School Admin role, only questions created by the user can be deleted (ownership restriction).
    Other admin roles can delete questions within their organizational scope.
    Teachers cannot delete questions from the question bank.
    
    ### Path Parameters:
    - **question_code** (str, required): Question code (e.g., "Q123")
    
    ### Response:
    - **204 No Content**: Question deleted successfully
    - **404 Not Found**: Question not found or not accessible
    - **403 Forbidden**: Insufficient permissions or ownership restriction
    """
    # Restrict teachers from deleting questions from question bank
    if current_user.role and current_user.role.role_code == "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teachers cannot delete questions from the question bank"
        )
    
    # First check if question exists and is accessible
    existing_question = await get_question_by_code(question_code, db, current_user, scope_filter)
    
    if not existing_question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found or not accessible"
        )
    
    # Add question owner ID for ownership validation
    question_owner_id = existing_question.created_by
    
    # Delete the question
    await delete_question(existing_question.id, db, current_user)
    await db.commit()
    
    return {"message": "Question deleted successfully"}
