from sqlalchemy import select
from app.models.master import Medium, Subject, Question_Format as Format, Question_Type, Board, State
# from app.schemas.pydantic_models import MediumBase, MediumResponse, SubjectBase, SubjectListResponse, FormatBase, FormatResponse, QuestionTypeBase, QuestionTypeListResponse
from app.schemas.metadata import MediumBase, MediumResponse, SubjectBase, SubjectListResponse, FormatBase, FormatResponse, QuestionTypeBase, QuestionTypeListResponse, BoardBase, BoardResponse, StateBase, StateResponse

from sqlalchemy.orm import selectinload

# === Get All Mediums ===
async def get_all_mediums(db):
    result = await db.execute(select(Medium))
    mediums = result.scalars().all()
    data = [
        MediumBase(
            medium_code=m.mmt_medium_code,
            medium_name=m.mmt_medium_name
        ) for m in mediums
    ]
    return MediumResponse(data=data)


# === Get All Subjects ===
async def get_all_subjects(db, standard=None, medium_code=None):
    query = select(Subject).options(selectinload(Subject.medium))
    
    # Apply filters
    if standard:
        query = query.where(Subject.smt_standard == standard)
    
    if medium_code:
        query = query.where(Subject.smt_medium_id == select(Medium.id).where(Medium.mmt_medium_code == medium_code))
    
    result = await db.execute(query)
    subjects = result.scalars().all()

    data = [
        SubjectBase(
            subject_code=s.smt_subject_code,
            subject_name=s.smt_subject_name,
            medium_code=s.medium.mmt_medium_code if s.medium else None,
            standard=s.smt_standard
        ) for s in subjects
    ]
    return SubjectListResponse(data=data)


# === Get All Formats ===
async def get_all_formats(db):
    result = await db.execute(select(Format))
    formats = result.scalars().all()
    data = [
        FormatBase(
            qfm_format_code=f.qfm_format_code,
            qfm_format_name=f.qfm_format_name
        ) for f in formats
    ]
    return FormatResponse(data=data)


# === Get All Question Types ===
async def get_all_question_types(db):
    result = await db.execute(select(Question_Type))
    types = result.scalars().all()
    data = [
        QuestionTypeBase(
            type_code=t.qtm_type_code,
            type_name=t.qtm_type_name
        ) for t in types
    ]
    return QuestionTypeListResponse(data=data)


# === Get All Boards ===
async def get_all_boards(db):
    result = await db.execute(select(Board))
    boards = result.scalars().all()
    data = [
        BoardBase(
            board_id=b.id,
            board_name=b.board_name
        ) for b in boards
    ]
    return BoardResponse(data=data)


# === Get All States ===
async def get_all_states(db):
    result = await db.execute(select(State))
    states = result.scalars().all()
    data = [
        StateBase(
            id=s.id,
            state_name=s.state_name,
            iso_code=s.iso_code
        ) for s in states
    ]
    return StateResponse(data=data)

