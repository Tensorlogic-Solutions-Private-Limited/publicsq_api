from sqlalchemy import select
from fastapi import HTTPException
from reportlab.pdfgen import canvas
from io import BytesIO
from fastapi.responses import StreamingResponse

from app.models.master import Subject, Medium, Question_Type, Questions
from app.utils.build_options import build_options
from app.schemas.qn_paper_views import QuestionResponseEach, OptionResponseEach

async def get_questions(db, question_codes, include_answers):
    result = await db.execute(
        select(Questions)
        .where(Questions.qmt_question_code.in_(question_codes))
    )
    questions = result.scalars().all()
    questions_map = {q.qmt_question_code: q for q in questions}

    qns_list = []
    for code in question_codes:
        q = questions_map.get(code)
        if not q:
            continue

        opts = build_options(q, include_answers=include_answers)
        if not include_answers:
            for o in opts:
                o.pop("is_correct", None)

        options_objs = [OptionResponseEach(**opt) for opt in opts]
        
        # Build question response
        question_data = {
            "id": q.qmt_question_code,
            "text": q.qmt_question_text,
            "options": options_objs
        }
        
        qns_list.append(QuestionResponseEach(**question_data))

    return qns_list