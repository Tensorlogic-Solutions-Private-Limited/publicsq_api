from fastapi import APIRouter, Depends
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
from app.decorators.permissions import require_permission, scope_filter
from app.services.state_resolution_service import StateResolutionService

router = APIRouter()

@router.get(
    "/v1/designs",
    response_model=DesignPaperListResponsePaginated,
    tags=["Design History"]
)
@require_permission("quiz.view")
async def list_all_designs(
    exam_name: Optional[str] = Query(None, description="Filter designs by name"),
    subject: Optional[str] = Query(None, description="Filter designs by subject name"),
    medium: Optional[str] = Query(None, description="Filter designs by medium name"),
    standard: Optional[str] = Query(None, description="Filter designs by standard/class"),
    start_date: Optional[date] = Query(None, description="Filter designs from this start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Filter designs up to this end date (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of designs per page (default: 20)"),
    state_id: Optional[int] = Query(None, description="State ID for filtering designs (optional for org admins)"),
    status: str = Query(..., description="status for query('draft'/'closed')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all designs with optional filters, date range, and pagination.
    
    This endpoint functions exactly like GET /v1/exams but with clearer naming.
    """
    # Apply role-based filtering
    user_role = current_user.role.role_code if current_user.role else None
    
    # Build scope filter based on user role
    scope_filter = {}
    
    if user_role == "super_admin":
        scope_filter = {}
    elif user_role in ["admin", "admin_user"]:
        if current_user.organization_id:
            scope_filter["organization_id"] = current_user.organization_id
        if state_id:
            scope_filter["state_id"] = state_id
    elif user_role == "block_admin":
        if current_user.block_id:
            scope_filter["block_id"] = current_user.block_id
        elif current_user.organization_id:
            scope_filter["organization_id"] = current_user.organization_id
    elif user_role == "teacher":
        scope_filter["created_by"] = current_user.id
    else:
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
        state_id=None
    )
    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "exams": designs
    }

@router.put("/v1/designs/{design_code}", tags=["Designs"])
@require_permission("quiz.edit_properties")
async def put_exam_design(
    design_code: str,
    payload: DesignUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
        Create a new Design and generate question papers with multiple sets and versions.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if secured)
        ### Description:
        - `status = 1`: Save as **draft** (updates design data only)
        - `status = 2`: **Finalize** the design and generate question papers

        ### Path Parameters:
        - **design_code** (str): Unique code of the design to update (e.g., "EXM00010")

        ### Query Parameters:
        - None

        ### Request Body:
        - **status** (int):  
            - `1`: Draft mode  
            - `2`: Finalize and generate question papers
        - **is_ai_selected** (bool):  
            - `true`: Auto-select questions (ignore `qn_count`)  
            - `false`: Manual selection based on `qn_count`
        - **exam_name** (str): Unique name of the design
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
        "message": "Design finalized and question papers generated successfully",
        "data": {
            "exam_name": "Updated Science Design",
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
                "exam_name": "My Design 100",
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
        - **201 Created**: Returns design details and generated question papers.

        #### Top-level fields:
        - **exam_name** (str): Name of the design.
        - **exam_code** (str): Auto-generated unique design code (e.g., `"EXM00010"`).
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
        "exam_name": "Final Science Design 1",
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
            - Design with the same name already exists.
            - Unable to generate unique design code.
        - **500 Internal Server Error**:
            - For unexpected server/database errors.

        ### Notes:
        - This endpoint supports both AI-driven and manual question allocation.
        - Globally excluded question codes (`qtn_codes_to_exclude`) are filtered out before selection.
        - Only admin users see correct answers in the question options.
        - Validates that sum of `qn_count` equals `total_questions` in manual mode.
        """
    # Check if design is finalized - prevent updates to finalized designs
    existing_exam = await get_design_by_exam_code(db, design_code, current_user)
    if existing_exam.get('status') == 'closed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a finalized design. Finalized designs are immutable."
        )
    
    return await update_design_service(db, design_code, payload, current_user, payload.state_id)

@router.get(
    "/v1/designs/{design_code}",
    response_model=SingleDesignResponse,
    tags=["Design History"]
)
@require_permission("quiz.view")
async def get_exam_by_code(
    design_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
        Retrieve a single design and its associated question papers using the design code.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (required for secured access)

        ### Path Parameters:
        - **design_code** (str, required): Unique design code (e.g., `EXM00010`).

        ### Query Parameters:
        - None

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json):
        - **200 OK**: Returns the design details and its associated question papers.

        #### Example Response:
        ```json
        {
            "design": {
                "exam_name": "My Design 111 (final)",
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
            { "detail": "Design with code EXM99999 not found." }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to view this design." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while fetching design details." }
            ```

        ### Notes:
        - Returns detailed information of a single design including:
            - Metadata (design name, subject, medium, mode, sets, versions).
            - Status of the design (e.g., `active`, `closed`).
            - Associated question papers listed by their codes.
        - **Admins**: Can access any design.
        - **Non-admin users**: Can only access their own designs.
        """
    return await get_design_by_exam_code(db=db, exam_code=design_code, current_user=current_user)

@router.delete(
    "/v1/designs/{design_code}",
    status_code=status.HTTP_200_OK,
    tags=["Delete Designs"]
)
@require_permission("quiz.edit_properties")
async def delete_exam_by_code(
    design_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
        Delete a design by its code.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (required for secured access)

        ### Path Parameters:
        - **design_code** (str, required): Unique design code (e.g., `EXM00010`).

        ### Query Parameters:
        - None

        ### Request Body:
        - None (DELETE request does not require a body)

        ### Response (application/json):
        - **200 OK**: Design deleted successfully.
        
        #### Example Response:
        ```json
        {
        "message": "Design EXM00010 deleted successfully."
        }
        ```

        ### Error Responses:
        - **400 Bad Request**:
            ```json
            { "detail": "Cannot delete a finalized design. Only draft designs can be deleted." }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to delete this design." }
            ```
        - **404 Not Found**:
            ```json
            { "detail": "Design with code EXM00010 not found." }
            ```
        - **409 Conflict**:
            ```json
            { "detail": "Cannot delete a design with active or ongoing papers." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while deleting design." }
            ```

        ### Notes:
        - Only **Admins** or the **creator of the design** can delete it.
        - **Only draft designs can be deleted** - finalized designs cannot be deleted.
        - Deleting a design will also remove all associated question papers.
        - Useful for removing outdated or test designs from the system.
    """
    message = await delete_design_by_exam_code(db, current_user, design_code)
    return {"message": message}


@router.delete("/v1/designs/{design_code}/qn_papers/{paper_code}/questions/{question_code}", tags=["Design Questions"])
@require_permission("quiz.edit_questions")
async def remove_question_from_paper(
    design_code: str,
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
    - **design_code** (str, required): Design code (e.g., "EXM00106")
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
        { "detail": "Paper does not belong to the specified design" }
        ```
    - **403 Forbidden**: 
        ```json
        { "detail": "Insufficient permissions" }
        ```
    - **404 Not Found**: 
        ```json
        { "detail": "Design with code EXM00106 not found" }
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
        exam_code=design_code,
        paper_code=paper_code,
        question_code=question_code,
        db=db,
        current_user=current_user
    )
    
    return result
