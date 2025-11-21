from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from sqlalchemy import select
from typing import Optional, List
from datetime import date, datetime
from fastapi import Query
from app.database import get_db
from app.utils.auth import get_current_user
# from app.schemas.exams import SingleDesignResponse
from app.schemas.qn_papers import DesignPaperListResponsePaginated, SingleDesignResponse
from app.services.qn_paper_service import get_all_exam_designs, get_design_by_exam_code, delete_design_by_exam_code
from app.models.user import User
from app.services.design_service import create_exam_design_and_generate_qps,update_design_service
from app.schemas.exams import DesignBase,DesignUpdate,DesignStatusUpdate
from app.schemas.questions import QuestionCreateRequest
from app.decorators.permissions import require_permission, scope_filter
from app.services.state_resolution_service import StateResolutionService

router = APIRouter()

@router.post("/v1/exams",  
             tags=["Create Exams"],
             status_code=status.HTTP_201_CREATED )
@require_permission("quiz.create")
async def create_question_papers(
    payload: DesignBase,
    state_id: Optional[int] = Query(None, description="State ID for question filtering (required for admin roles)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new Exam Design and optionally generates question papers.

    This endpoint supports two modes of operation based on the `status` field:

    - `1` → Draft Mode → Only saves design details, no question generation
    - `2` → Finalized Mode → Saves and generates question papers

    ---

    Design Status Mapping:

    - `1` → "draft"
    - `2` → "closed"

    ---

    Request Body Fields:

    - status (int): Required. 1 for draft, 2 for finalized
    - is_ai_selected (bool): Required. If true, questions are auto-selected (qn_count in `codes` is ignored)
    - exam_name (str): Required. Unique name of the exam
    - exam_type_code (str): Required. E.g., "1000"
    - subject_code (str): Required. E.g., "3000"
    - medium_code (str): Required. E.g., "2000"
    - exam_mode (str): Required. Must be "online" or "offline"
    - total_time (int): Required. Total duration in minutes
    - total_questions (int): Required. Number of questions per version
    - no_of_versions (int): Required. Versions per set
    - no_of_sets (int): Required. Unique sets to generate
    - standard (str): Optional. E.g., "10"
    - qtn_codes_to_exclude (list[str]): Optional. List of question codes to exclude globally
    - chapters_topics (list): Required when status = 2

    ---

    chapters_topics Format:

    Each item includes:
    - type (str): Either "chapter" or "topic"
    - codes (list):
        - code (str): Code for chapter or topic
        - qn_count (int): Required in manual mode (is_ai_selected = false)

    ---
    
    Example Request (Draft):

    ```json

    {
    "status": 1,
    "is_ai_selected": false,
    "exam_name": "My Exam 100 (final)",
    "exam_type_code": "1000",
    "subject_code": "3000",
    "medium_code": "2000",
    "exam_mode": "online",
    "total_time": 90,
    "total_questions": 12,
    "no_of_versions": 1,
    "no_of_sets": 2,
    "standard": "10",
    "qtn_codes_to_exclude": ["Q1328055"],
    "chapters_topics": [
        {
        "type": "chapter",
        "codes": [
            { "code": "1000", "qn_count": 5 },
            { "code": "1001", "qn_count": 5 }
        ]
        },
        {
        "type": "topic",
        "codes": [
            { "code": "10117", "qn_count": 1 },
            { "code": "10111", "qn_count": 1 }
        ]
        }
    ]
    }
    ```
    ---

    Example Response (status = 1 → "draft"):
    ```json

    {
    "status": 1,
    "message": "Draft saved successfully",
    "data": {
        "exam_name": "My Exam 100 (final)",
        "exam_code": "EXM00001",
        "status": "draft",
        "number_of_sets": 2,
        "number_of_versions": 1,
        "no_of_qns": 12,
        "subject": "Social Science",
        "medium": "English",
        "exam_type": "MCQ",
        "board_id": 6,
        "state_id": 7,
        "chapters_topics": [...],
        "questions_to_exclude": ["Q1328055"],
        "shortfall_info": null,
        "question_papers": null
    }
    }
    ```
    ---

    Status Codes:

    - 201 Created: Exam saved successfully
    - 400 Bad Request: Missing or invalid input (e.g., qn_count mismatch)
    - 404 Not Found: Subject, Medium, Exam Type, or User Role not found
    - 409 Conflict: Exam design with the same name already exists
    - 500 Internal Server Error: Unexpected DB or server error

    ---

    Notes:

    - In finalized mode (`status = 2`), question selection and set/version generation is performed.
    - In AI mode, qn_count inside `chapters_topics.codes` is ignored.
    - Only admins (role_code = "100") receive correct answers in the response.
    """
    try:
        # For super_admin, admin, and admin_user roles: bypass StateResolutionService and use provided state_id directly
        user_role = current_user.role.role_code if current_user.role else None
        
        # Use state_id from query parameter, or fall back to state_id from payload
        effective_state_id = state_id if state_id is not None else payload.state_id
        
        if user_role in ["super_admin", "admin", "admin_user"]:
            # Admin roles can use any state_id they provide, no validation needed
            resolved_state_id = effective_state_id
        else:
            # For other roles (block_admin, teacher), use StateResolutionService for validation
            resolved_state_id = await StateResolutionService.resolve_state_for_user(
                db=db, 
                user=current_user, 
                explicit_state_id=effective_state_id
            )
        
        return await create_exam_design_and_generate_qps(payload, current_user, db, resolved_state_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.put("/v1/exams/{exam_code}", tags=["Exams"])
@require_permission("quiz.edit_properties")
async def put_exam_design(
    exam_code: str,
    payload: DesignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
        Create a new Exam Design and generate question papers with multiple sets and versions.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if secured)
        ### Description:
        - `status = 1`: Save as **draft** (updates design data only)
        - `status = 2`: **Finalize** the design and generate question papers

        ### Path Parameters:
        - **exam_code** (str): Unique code of the exam to update (e.g., "EXM00010")

        ### Query Parameters:
        - None

        ### Request Body:
        - **status** (int):  
            - `1`: Draft mode  
            - `2`: Finalize and generate question papers
        - **is_ai_selected** (bool):  
            - `true`: Auto-select questions (ignore `qn_count`)  
            - `false`: Manual selection based on `qn_count`
        - **exam_name** (str): Unique name of the exam
        - **exam_type_code** (str): Exam type code (e.g., "1000")
        - **subject_code** (str): Subject code (e.g., "3000")
        - **medium_code** (str): Medium code (e.g., "2000")
        - **exam_mode** (str): "online" or "offline"
        - **total_time** (int): Duration in minutes
        - **total_questions** (int): Number of questions per paper
        - **no_of_versions** (int): Versions per set
        - **no_of_sets** (int): Number of sets
        - **standard** (str, optional): Grade/class (e.g., "10")
        - **qtn_codes_to_exclude** (list[str], optional): Question codes to exclude
        - **chapters_topics** (list, required for `status = 2`):  
        List of chapter/topic groupings

        #### Each `chapters_topics` item:
        - **type** (str): `"chapter"` or `"topic"`.
        - **codes** (list[object]): List of selection objects:
            - **code** (str): Chapter or topic code.
            - **qn_count** (int): Number of questions to select (required in manual mode, omit/null in AI mode).

        ### Example Request (Finalize):
        ```json
                {
        "status": 2,
        "message": "Exam finalized and question papers generated successfully",
        "data": {
            "exam_name": "Updated Science Exam",
            "exam_code": "EXM00010",
            "status": "closed",
            "number_of_sets": 2,
            "number_of_versions": 1,
            "no_of_qns": 10,
            "subject": "Social Science",
            "medium": "English",
            "exam_type": "MCQ",
            "shortfall_info": {},
            "question_papers": [
            {
                "id": "QP01S01V01",
                "qns": [
                {
                    "id": "Q12345",
                    "text": "What is ...?",
                    "options": [
                    { "id": "A", "text": "Option 1", "is_correct": false },
                    { "id": "B", "text": "Option 2", "is_correct": true }
                    ]
                }
                ]
            }
            ]
        }
        }
        ```

        ### Example Request (Draft):
        ```json
        {
            "status": 1,
            "message": "Draft saved successfully",
            "data": {
                "exam_name": "My Exam 100",
                "exam_code": "EXM00001",
                "status": "draft",
                "number_of_sets": 2,
                "number_of_versions": 1,
                "no_of_qns": 12,
                "subject": "Social Science",
                "medium": "English",
                "exam_type": "MCQ",
                "chapters_topics": [...],
                "questions_to_exclude": [...],
                "shortfall_info": null,
                "question_papers": null
            }
            }
        ```
        ### Status Values::
        - 1: draft.
        - 2: closed.

        ### Response (application/json):
        - **201 Created**: Returns exam design details and generated question papers.

        #### Top-level fields:
        - **exam_name** (str): Name of the exam.
        - **exam_code** (str): Auto-generated unique exam code (e.g., `"EXM00010"`).
        - **number_of_sets** (int): Number of sets generated.
        - **number_of_versions** (int): Versions per set.
        - **no_of_qns** (int): Number of questions per paper.
        - **subject** (str): Subject name.
        - **medium** (str): Medium name.
        - **exam_type** (str): Exam type name.
        - **shortfall_info** (object): Tracks shortage details if any.
        - **question_papers** (list):
            - **id** (str): Paper ID (e.g., `"QP01S01V01"`).
            - **qns** (list):
                - **id** (str): Question code.
                - **text** (str): Question text.
                - **options** (list): Question options (answers visible if user is admin).

        ### Example Response:
        ```json
        {
        "exam_name": "Final Science Exam 1",
        "exam_code": "EXM00010",
        "number_of_sets": 2,
        "number_of_versions": 3,
        "no_of_qns": 5,
        "subject": "Social Science",
        "medium": "English",
        "exam_type": "MCQ",
        "shortfall_info": {},
        "question_papers": [
            {
            "id": "QP41S01V01",
            "qns": [
                {
                "id": "Q1327552",
                "text": "What is British climate?",
                "options": [
                    { "id": "A", "text": "Extremely hot and humid", "is_correct": false },
                    { "id": "B", "text": "Mild and wet", "is_correct": true },
                    { "id": "C", "text": "Extremely cold and dry", "is_correct": false },
                    { "id": "D", "text": "Hot and dry", "is_correct": false }
                ]
                }
            ]
            }
        ]
        }
        ```

        ### Error Responses:
        - **400 Bad Request**:
            - Invalid `type` in `chapters_topics` (must be `"chapter"` or `"topic"`).
            - Insufficient questions available for sets/versions.
        - **404 Not Found**:
            - User role not found.
            - Exam type, subject, or medium not found.
        - **409 Conflict**:
            - Exam design with the same name already exists.
            - Unable to generate unique design code.
        - **500 Internal Server Error**:
            - For unexpected server/database errors.

        ### Notes:
        - This endpoint supports both AI-driven and manual question allocation.
        - Globally excluded question codes (`qtn_codes_to_exclude`) are filtered out before selection.
        - Only admin users see correct answers in the question options.
        - Validates that sum of `qn_count` equals `total_questions` in manual mode.
        """
    # Check if exam is finalized - prevent updates to finalized exams
    existing_exam = await get_design_by_exam_code(db, exam_code, current_user)
    if existing_exam.get('status') == 'closed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a finalized exam. Finalized exams are immutable."
        )
    
    return await update_design_service(db, exam_code, payload, current_user, payload.state_id)

@router.patch("/v1/exams/{exam_code}", tags=["Exams"])
@require_permission("quiz.edit_properties")
async def patch_exam_status(
    exam_code: str,
    payload: DesignStatusUpdate,
    state_id: Optional[int] = Query(None, description="State ID for question filtering (required for admin roles when finalizing)"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update only the status of an existing exam design.

    ### Path Parameters:
    - **exam_code** (str): Unique code of the exam to update (e.g., "EXM00010")

    ### Request Body:
    - **status** (int): 
        - `1`: Draft mode
        - `2`: Finalized mode (generates question papers)

    ### Validation Rules:
    - Exam must exist
    - Cannot transition from finalized (2) back to draft (1)
    - User must have permission to edit the exam

    ### Example Request:
    ```json
    {
        "status": 2
    }
    ```

    ### Example Response:
    ```json
    {
        "status": 1,
        "message": "Exam status updated successfully"
    }
    ```
    """
    try:
        # Get the existing exam to validate it exists and check current status
        existing_exam = await get_design_by_exam_code(db, exam_code, current_user)
        if not existing_exam:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Exam with code {exam_code} not found"
            )
        
        # Check if trying to go from finalized back to draft (not allowed)
        current_status = existing_exam.get('status')
        if current_status == 2 and payload.status == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change exam status from finalized back to draft"
            )
        
        # If status is already the same, return success
        if current_status == payload.status:
            return {
                "status": 1,
                "message": f"Exam status is already {payload.status}"
            }
        
        # For status update only, we need to handle it differently
        # If going from draft (1) to finalized (2), we need to trigger the full finalization process
        if current_status == 1 and payload.status == 2:
            # Resolve state_id for finalization process
            resolved_state_id = await StateResolutionService.resolve_state_for_user(
                db=db, 
                user=current_user, 
                explicit_state_id=state_id
            )
            
            # Get the existing exam data and create a complete payload for finalization
            from app.models.master import Design
            from sqlalchemy import select
            
            # Get the design record from database
            stmt = select(Design).where(Design.dm_design_code == exam_code)
            result = await db.execute(stmt)
            design = result.scalar_one_or_none()
            
            if not design:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Exam design not found for code {exam_code}"
                )
            
            # Create a complete DesignUpdate payload with existing data + new status
            update_payload = DesignUpdate(
                exam_name=design.dm_design_name,
                exam_type_code="1000",  # Default exam type
                subject_code="3000",    # Default subject
                medium_code="2000",     # Default medium
                exam_mode=design.dm_exam_mode,
                total_time=design.dm_total_time,
                total_questions=design.dm_total_questions,
                no_of_versions=design.dm_no_of_versions,
                no_of_sets=design.dm_no_of_sets,
                standard=design.dm_standard,
                status=payload.status,
                chapters_topics=design.dm_chapter_topics or [],
                qtn_codes_to_exclude=design.dm_questions_to_exclude or []
            )
            
            # Use the existing update service for finalization with state filtering
            result = await update_design_service(db, exam_code, update_payload, current_user, resolved_state_id)
        else:
            # For other status changes (like draft to draft), just update the status directly
            from app.models.master import Design
            from sqlalchemy import select, update
            
            stmt = update(Design).where(Design.dm_design_code == exam_code).values(
                dm_status="draft" if payload.status == 1 else "closed",
                updated_at=datetime.utcnow(),
                updated_by=current_user.id
            )
            await db.execute(stmt)
            await db.commit()
        
        return {
            "status": 1,
            "message": "Exam status updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating exam status: {str(e)}"
        )

@router.get(
    "/v1/exams",
    response_model=DesignPaperListResponsePaginated,
    tags=["Exam History"]
)
@require_permission("quiz.view")
async def list_all_question_papers(
    exam_name: Optional[str] = Query(None, description="Filter exams by exam name"),
    subject: Optional[str] = Query(None, description="Filter exams by subject name"),
    medium: Optional[str] = Query(None, description="Filter exams by medium name"),
    standard: Optional[str] = Query(None, description="Filter exams by standard/class"),
    start_date: Optional[date] = Query(None, description="Filter exams from this start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter exams up to this end date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of exams per page (default: 20)"),
    state_id: Optional[int] = Query(None, description="State ID for filtering exams (optional for org admins)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status: str = Query(..., description="status for query('draft'/'closed')")
):
    """
    Retrieve all exam designs with optional filters, date range, and pagination.

    ### Request Headers
    - `Content-Type`: `application/json`
    - `Authorization`: `Bearer <token>` (optional; required for secured access)

    ### Query Parameters
    - `exam_name` (string, optional): Filter by exam name (partial match allowed)
    - `subject` (string, optional): Filter by subject name (exact match)
    - `medium` (string, optional): Filter by medium name (exact match)
    - `standard` (string, optional): Filter by standard/class (exact match)
    - `start_date` (string, optional, format: YYYY-MM-DD): Include exams on or after this date
    - `end_date` (string, optional, format: YYYY-MM-DD): Include exams on or before this date
    - `page` (integer, optional, default: 1): Page number for pagination
    - `status` (string, required): Filter exams by status. Allowed values: `'draft'`, `'closed'`
    - `limit` (integer, optional, default: 20): Number of exams per page (max: 100)

    ### Response - 200 OK
    Returns a paginated list of exam designs.

    #### Response Structure
    - `total` (integer): Total number of exams
    - `page` (integer): Current page number
    - `limit` (integer): Number of records per page
    - `exams` (array): List of exam details

    #### Example Response (application/json)
        {
        "total": 45,
        "page": 1,
        "limit": 20,
        "exams": [
            {
            "exam_name": "Midterm Test 41",
            "exam_code": "EXM00041",
            "exam_type": "MCQ",
            "exam_mode": "online",
            "standard": "10",
            "subject": "Social Science",
            "medium": "English",
            "status": "closed",
            "number_of_sets": 2,
            "number_of_versions": 1,
            "total_questions": 5,
            "board_id": null,
            "state_id": 7,
            "created_at": "2025-07-23",
            "created_by": "teacher",
            "created_by_id": 2
            }
        ]
        }

    ### Error Responses
    403 Forbidden:
        {
        "detail": "You are not authorized to view exam history."
        }

    500 Internal Server Error:
        {
        "detail": "Unexpected error occurred while fetching exam history."
        }

    ### Notes
    - Admins can view all exam designs.
    - Regular users can view only their own exams.
    - Supports filtering by exam name, subject, medium, standard, and date range.
    - Pagination improves performance when loading large data sets.
    - Use `/v1/exams/{exam_code}` to get full exam details including question papers.
    """
    
    # Apply role-based filtering instead of state resolution
    user_role = current_user.role.role_code if current_user.role else None
    
    # Build scope filter based on user role
    scope_filter = {}
    
    if user_role == "super_admin":
        # Super admins see everything - no filtering
        scope_filter = {}
    elif user_role in ["admin", "admin_user"]:
        # Org admins see exams from their organization
        if current_user.organization_id:
            scope_filter["organization_id"] = current_user.organization_id
        # Optional state filtering for org admins
        if state_id:
            scope_filter["state_id"] = state_id
    elif user_role == "block_admin":
        # Block admins see exams from their block and organization
        if current_user.block_id:
            scope_filter["block_id"] = current_user.block_id
        elif current_user.organization_id:
            # Fallback to organization if no block assigned
            scope_filter["organization_id"] = current_user.organization_id
    elif user_role == "teacher":
        # Teachers see only their own created exams
        scope_filter["created_by"] = current_user.id
    else:
        # Default: no access for unknown roles
        scope_filter["id"] = -1
    
    designs, total_count = await get_all_exam_designs(
        db=db,
        current_user=current_user,
        exam_name=exam_name,
        subject=subject,
        medium=medium,
        standard=standard,
        start_date=start_date,
        end_date=end_date,
        page=page,
        limit=limit,
        status=status,
        scope_filter=scope_filter,
        state_id=None  # Remove state_id parameter since we handle it in scope_filter
    )
    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "exams": designs
    }

@router.get(
    "/v1/exams/{exam_code}",
    response_model=SingleDesignResponse,
    tags=["Exam History"]
)
@require_permission("quiz.view")
async def get_exam_by_code(
    exam_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
        Retrieve a single exam design and its associated question papers using the exam code.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (required for secured access)

        ### Path Parameters:
        - **exam_code** (str, required): Unique exam code (e.g., `EXM00010`).

        ### Query Parameters:
        - None

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json):
        - **200 OK**: Returns the exam design details and its associated question papers.

        #### Example Response:
        ```json
        {
            "design": {
                "exam_name": "My Exam 111 (final)",
                "exam_code": "EXM00005",
                "exam_type": "MCQ",
                "exam_mode": "online",
                "standard": "10",
                "subject": "Social Science",
                "medium": "English",
                "status": "closed",
                "number_of_sets": 2,
                "number_of_versions": 1,
                "total_questions": 12,
                "board_id": null,
                "state_id": 7,
                "qtn_codes_to_exclude": [
                {
                    "code": "Q1328055",
                    "txt": "Who among the following directly rules the state in the name of the president when National Emergency is declared by the president during times of war?",
                    "chapter_details": {
                    "code": "1014",
                    "name": "State Government"
                    },
                    "topic_details": {
                    "code": "10117",
                    "name": "powers and functions of the Governor"
                    }
                },
                {
                    "code": "Q1328055",
                    "txt": "Who among the following directly rules the state in the name of the president when National Emergency is declared by the president during times of war?",
                    "chapter_details": {
                    "code": "1014",
                    "name": "State Government"
                    },
                    "topic_details": {
                    "code": "10117",
                    "name": "powers and functions of the Governor"
                    }
                }
                ],
                "chapters_topics": [
                {
                    "type": "chapter",
                    "codes": [
                    {
                        "code": "1014",
                        "qn_count": null,
                        "name": "State Government"
                    },
                    {
                        "code": "1001",
                        "qn_count": null,
                        "name": "India's Foreign Policy"
                    }
                    ]
                },
                {
                    "type": "topic",
                    "codes": [
                    {
                        "code": "10117",
                        "qn_count": null,
                        "name": "powers and functions of the Governor"
                    },
                    {
                        "code": "10111",
                        "qn_count": null,
                        "name": "Chief Minister"
                    }
                    ]
                }
                ],
                "papers": [
                "QP12S01V01",
                "QP12S02V01"
                ]
            }
            }
        ```

        ### Error Responses:
        - **404 Not Found**:
            ```json
            { "detail": "Exam design with code EXM99999 not found." }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to view this exam design." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while fetching exam details." }
            ```

        ### Notes:
        - Returns detailed information of a single exam design including:
            - Metadata (exam name, subject, medium, mode, sets, versions).
            - Status of the exam (e.g., `active`, `closed`).
            - Associated question papers listed by their codes.
        - **Admins**: Can access any exam.
        - **Non-admin users**: Can only access their own exams.
        """
    return await get_design_by_exam_code(db=db, exam_code=exam_code, current_user=current_user)

@router.delete(
    "/v1/exams/{exam_code}",
    status_code=status.HTTP_200_OK,
    tags=["Delete Exams"]
)
@require_permission("quiz.edit_properties")
async def delete_exam_by_code(
    exam_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
        Delete an exam design by its code.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (required for secured access)

        ### Path Parameters:
        - **exam_code** (str, required): Unique exam code of the design to delete (e.g., `EXM00010`).

        ### Query Parameters:
        - None

        ### Request Body:
        - None (DELETE request does not require a body)

        ### Response (application/json):
        - **200 OK**: Exam design deleted successfully.
        
        #### Example Response:
        ```json
        {
        "message": "Exam design EXM00010 deleted successfully."
        }
        ```

        ### Error Responses:
        - **400 Bad Request**:
            ```json
            { "detail": "Cannot delete a finalized exam. Only draft exams can be deleted." }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to delete this exam design." }
            ```
        - **404 Not Found**:
            ```json
            { "detail": "Exam design with code EXM00010 not found." }
            ```
        - **409 Conflict**:
            ```json
            { "detail": "Cannot delete an exam design with active or ongoing papers." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while deleting exam design." }
            ```

        ### Notes:
        - Only **Admins** or the **creator of the exam** can delete it.
        - **Only draft exams can be deleted** - finalized exams cannot be deleted.
        - Deleting an exam will also remove all associated question papers.
        - Useful for removing outdated or test exam designs from the system.
    """
    message = await delete_design_by_exam_code(db, current_user, exam_code)
    return {"message": message}


@router.delete("/v1/exams/{exam_code}/qn_papers/{paper_code}/questions/{question_code}", tags=["Exam Questions"])
@require_permission("quiz.edit_questions")
async def remove_question_from_paper(
    exam_code: str,
    paper_code: str,
    question_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a question from a specific question paper.
    
    This endpoint removes a question from the specified question paper's question list.
    If the question has status "review", it will be marked as "deleted" in the database.
    If the question has any other status, only the removal from the paper will occur.
    
    ### Request Headers:
    - `Authorization`: Bearer token (required)
    
    ### Path Parameters:
    - **exam_code** (str, required): Exam code (e.g., "EXM00106")
    - **paper_code** (str, required): Question paper code (e.g., "QP99S01V01")
    - **question_code** (str, required): Question code to remove (e.g., "Q42")
    
    ### Request Body:
    - None (DELETE request does not require a body)
    
    ### Response (application/json):
    - **200 OK**: Question removed successfully from the paper
    
    #### Example Response:
    ```json
    {
        "message": "Question Q42 removed successfully from paper QP99S01V01"
    }
    ```
    
    ### Error Responses:
    - **400 Bad Request**: 
        ```json
        { "detail": "Paper does not belong to the specified exam" }
        ```
    - **403 Forbidden**: 
        ```json
        { "detail": "Insufficient permissions" }
        ```
    - **404 Not Found**: 
        ```json
        { "detail": "Exam with code EXM00106 not found" }
        ```
        ```json
        { "detail": "Question paper with code QP99S01V01 not found" }
        ```
        ```json
        { "detail": "Question with code Q42 not found" }
        ```
    - **422 Unprocessable Entity**: 
        ```json
        { "detail": "Question is not part of the specified paper" }
        ```
    
    ### Notes:
    - The question is removed from the paper's question list and total counts are updated
    - If the question has status "review", it will be marked as "deleted" in the database
    - If the question has any other status, only the removal from the paper will occur
    - Only users with question_bank.upload permission can remove questions
    - The operation is reversible - the question can be added back to the paper later
    """
    from app.services.design_service import remove_question_from_exam_paper
    
    result = await remove_question_from_exam_paper(
        exam_code=exam_code,
        paper_code=paper_code,
        question_code=question_code,
        db=db,
        current_user=current_user
    )
    
    return result
