from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

# from app.models.master import Design, Subject, Medium, Question_Type
# from app.models.user import Role, User
# from app.schemas.pydantic_models import DesignPaperListResponseItem
# from app.models.master import Design, Subject, Medium, Question_Type, QuestionPaperDetails
from app.models.user import Role, User
from app.models import user
from app.utils.auth import get_current_user
from app.database import get_db

from app.services.qn_paper_view_service import get_question_paper_details,get_admin_question_paper

router = APIRouter()

@router.get(
    "/v1/qn_papers/{paper_code}",
    tags=["View/Print QPs"]
)
async def get_question_paper_by_id(
    paper_code: str,
    format: str = Query("json", enum=["json", "pdf"]),
    db: AsyncSession = Depends(get_db),
    current_user: user.User = Depends(get_current_user)
):
    """
        Retrieve a specific question paper by its code in either JSON or PDF format.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if secured)

        ### Path Parameters:
        - **paper_code** (str, required): Unique code of the question paper to retrieve.

        ### Query Parameters:
        - **format** (str, optional): Output format of the question paper.
            - Default: `json`
            - Allowed values:
                - `"json"`: Returns question paper details in structured JSON.
                - `"pdf"`: Returns the question paper in downloadable PDF format.

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json | application/pdf):
        - **200 OK**:
            - If `format=json`: Returns exam paper details including questions and options.
            - If `format=pdf`: Returns the question paper in PDF format.

        #### Example Response (JSON):
        ```json
        {
        "exam_name": "Final Science Exam 1",
        "exam_code": "EXM00010",
        "set": "Set 1",
        "version": "V1",
        "no_of_qns": 5,
        "subject": "Social Science",
        "medium": "English",
        "questions": [
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
        ```

        #### Example Response (PDF):
        - Returns a binary PDF file (with appropriate headers for download).

        ### Error Responses:
        - **400 Bad Request**:
            ```json
            { "detail": "Invalid format. Use ?format=json or ?format=pdf" }
            ```
        - **404 Not Found**:
            ```json
            { "detail": "Question paper with code QP99S01V01 not found." }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to view this question paper." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while retrieving the question paper." }
            ```

        ### Notes:
        - Admin users can view answers (`is_correct`) in the response JSON, while non-admins receive options without correct answer flags.
        - Use `format=pdf` for downloading/printing the question paper in PDF format.
        - This endpoint is useful for both online viewing (JSON) and offline printing (PDF).
    """

    result = await get_question_paper_details(paper_code, current_user, db)

    if format == "json":
        return JSONResponse(content=result["json"].dict(exclude_none=True))
    elif format == "pdf":
        return result["pdf"]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format. Use ?format=json or ?format=pdf")

@router.get(
    "/v1/admin/qn_papers/{paper_code}",
    tags=["Admin View/Print QPs"]
)
async def admin_get_question_paper_by_id(
    paper_code: str,
    format: str = Query("json", enum=["json", "pdf"]),
    questions_only: bool = Query(False, description="If true, hides answers even for admin"),
    db: AsyncSession = Depends(get_db),
    current_user: user.User = Depends(get_current_user)
):
    """
        Retrieve a specific question paper (Admin View) by its code in either JSON or PDF format.

        ### Request Headers:
        - `Content-Type`: application/json  
        - *(Optional)* `Authorization`: Bearer token (Admin access required)

        ### Path Parameters:
        - **paper_code** (str, required): Unique code of the question paper to retrieve.

        ### Query Parameters:
        - **format** (str, optional): Output format of the question paper.
            - Default: `json`
            - Allowed values:
                - `"json"`: Returns question paper details in structured JSON.
                - `"pdf"`: Returns the question paper in downloadable PDF format.
        - **questions_only** (bool, optional):  
            - Default: `false`  
            - If `true`, hides correct answers even for admins (useful for preview/distribution without answers).

        ### Request Body:
        - None (GET request does not require a body)

        ### Response (application/json | application/pdf):
        - **200 OK**:
            - If `format=json`: Returns detailed question paper data, including answers (unless `questions_only=true`).
            - If `format=pdf`: Returns a PDF version of the question paper.

        #### Example Response (JSON):
        ```json
        {
        "exam_name": "Final Science Exam 1",
        "exam_code": "EXM00010",
        "set": "Set 1",
        "version": "V1",
        "no_of_qns": 5,
        "subject": "Social Science",
        "medium": "English",
        "questions": [
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
        ```

        #### Example Response (PDF):
        - Returns a downloadable PDF of the question paper.

        ### Error Responses:
        - **400 Bad Request**:
            ```json
            { "detail": "Invalid format. Use ?format=json or ?format=pdf" }
            ```
        - **403 Forbidden**:
            ```json
            { "detail": "You are not authorized to view this question paper." }
            ```
        - **404 Not Found**:
            ```json
            { "detail": "Question paper with code QP99S01V01 not found." }
            ```
        - **500 Internal Server Error**:
            ```json
            { "detail": "Unexpected error occurred while retrieving the question paper." }
            ```

        ### Notes:
        - This endpoint is strictly for **Admin users** to view or print question papers.
        - Use `questions_only=true` to generate papers without answers, even in Admin mode.
        - Supports both **online viewing (JSON)** and **printable PDF download**.
        - Admin mode overrides normal user access restrictions, but still respects question paper ownership rules.
    """
    result = await get_admin_question_paper(
        paper_id=paper_code,
        current_user=current_user,
        db=db,
        questions_only=questions_only
    )

    if format == "json":
        return JSONResponse(content=result["json"].dict(exclude_none=True))
    elif format == "pdf":
        return result["pdf"]
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format. Use ?format=json or ?format=pdf")