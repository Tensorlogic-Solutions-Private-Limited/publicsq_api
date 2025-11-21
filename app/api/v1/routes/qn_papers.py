from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, Query
from sqlalchemy import select

from app.database import get_db
from app.utils.auth import get_current_user
from app.models.user import User, Role
from app.models.master import Design
# from app.schemas.exams import DesignBase,DesignUpdate

from app.services.qn_paper_service import delete_question_paper_by_code
from app.services.design_service import create_exam_design_and_generate_qps,update_design_service

router = APIRouter()

@router.delete(
    "/v1/qn_papers/{paper_code}",
    status_code=status.HTTP_200_OK,
    tags=["Delete QPs"]
)
async def delete_question_paper_endpoint(
    paper_code: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
        Delete a question paper by its code.

        ### Request Headers:
        - `Content-Type`: application/json
        - *(Optional)* `Authorization`: Bearer token (if secured)

        ### Path Parameters:
        - **paper_code** (str, required): Unique code of the question paper to delete.

        ### Query Parameters:
        - None

        ### Request Body:
        - None (DELETE request does not require a body)

        ### Response (application/json):
        - **200 OK**: Successfully deleted the question paper.
            ```json
            {
                "message": "Question paper QP41S01V01 deleted successfully."
            }
            ```

        ### Error Responses:
        - **403 Forbidden**: If the user is not an Admin or not the creator of the question paper.
            ```json
            {
                "detail": "You are not authorized to delete this question paper."
            }
            ```
        - **404 Not Found**: If the question paper with the given code does not exist.
            ```json
            {
                "detail": "Question paper with code QP99S01V01 not found."
            }
            ```
        - **500 Internal Server Error**: If an unexpected database or server error occurs.

        ### Notes:
        - Only Admin users or the creator of the question paper can delete it.
        - Once deleted, the action is irreversible.
        - Useful for managing question paper cleanup or correcting mistakes.
    """
    message = await delete_question_paper_by_code(db, current_user, paper_code)
    return {"message": message}