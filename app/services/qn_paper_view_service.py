from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.master import Design, QuestionPaperDetails, Subject, Medium, Question_Type
from app.schemas.qn_paper_views import QuestionPaperResponseEach

from app.utils.get_questions import get_questions
from app.utils.get_user_role import get_user_role
from app.utils.get_name import get_name
from app.utils.generate_pdf import generate_pdf

async def get_question_paper_details(paper_id, current_user, db):
    role = await get_user_role(db, current_user.role_id)
    include_answers = role.role_code in ["super_admin", "admin", "admin_user", "teacher"]

    stmt = select(QuestionPaperDetails).where(
        QuestionPaperDetails.qpd_paper_id == paper_id,
        *( [] if include_answers else [QuestionPaperDetails.created_by == current_user.id] )
    )
    paper = (await db.execute(stmt)).scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question Paper not found.")

    design = (await db.execute(select(Design).where(Design.id == paper.qpd_design_id))).scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design not found.")

    subject_name = await get_name(db, Subject, Subject.id, design.dm_subject_id, "smt_subject_name")
    medium_name = await get_name(db, Medium, Medium.id, design.dm_medium_id, "mmt_medium_name")
    exam_type_name = await get_name(db, Question_Type, Question_Type.id, design.dm_exam_type_id, "qtm_type_name")

    qns_list = await get_questions(db, paper.qpd_q_codes or [], include_answers)

    json_response = QuestionPaperResponseEach(
        id=paper.qpd_paper_id,
        exam_name=design.dm_design_name,
        exam_code=design.dm_design_code,
        design_id=design.id,
        number_of_sets=design.dm_no_of_sets,
        number_of_versions=design.dm_no_of_versions,
        no_of_qns=design.dm_total_questions,
        total_time=design.dm_total_time,
        subject=subject_name,
        medium=medium_name,
        exam_type=exam_type_name,
        standard=design.dm_standard,
        qns=qns_list
    )

    pdf_response = generate_pdf(paper.qpd_paper_id, design, subject_name, medium_name, exam_type_name, qns_list, design.dm_total_questions, design.dm_total_time, include_answers)
    return {"json": json_response, "pdf": pdf_response}


async def get_admin_question_paper(paper_id, current_user, db, questions_only=False):
    role = await get_user_role(db, current_user.role_id)
    # Check for admin-level roles: super_admin, admin, admin_user
    if role.role_code not in ["super_admin", "admin", "admin_user"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can access this endpoint.")

    paper = (await db.execute(select(QuestionPaperDetails).where(QuestionPaperDetails.qpd_paper_id == paper_id))).scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question Paper not found.")

    design = (await db.execute(select(Design).where(Design.id == paper.qpd_design_id))).scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design not found.")

    subject_name = await get_name(db, Subject, Subject.id, design.dm_subject_id, "smt_subject_name")
    medium_name = await get_name(db, Medium, Medium.id, design.dm_medium_id, "mmt_medium_name")
    exam_type_name = await get_name(db, Question_Type, Question_Type.id, design.dm_exam_type_id, "qtm_type_name")

    include_answers = not questions_only
    qns_list = await get_questions(db, paper.qpd_q_codes or [], include_answers)

    json_response = QuestionPaperResponseEach(
        id=paper.qpd_paper_id,
        exam_name=design.dm_design_name,
        exam_code=design.dm_design_code,
        design_id=design.id,
        number_of_sets=design.dm_no_of_sets,
        number_of_versions=design.dm_no_of_versions,
        no_of_qns=design.dm_total_questions,
        total_time=design.dm_total_time,
        subject=subject_name,
        medium=medium_name,
        exam_type=exam_type_name,
        standard=design.dm_standard,
        qns=qns_list
    )

    pdf_response = generate_pdf(paper.qpd_paper_id, design, subject_name, medium_name, exam_type_name, qns_list, design.dm_total_questions, design.dm_total_time, include_answers)
    return {"json": json_response, "pdf": pdf_response}
