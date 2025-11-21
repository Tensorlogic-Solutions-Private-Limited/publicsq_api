import pandas as pd
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import Role, User
from app.models.master import Question_Type, Medium, Subject, Criteria, Question_Format, Taxonomy, Questions
from app.middleware.rbac import rbac_middleware
from app.database import Base, engine
from fastapi import HTTPException, status
from io import BytesIO
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

async def load_excel(file_path: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found at {file_path}")

    try:
        df = pd.read_excel(file_path)
        if df.empty:
            raise HTTPException(status_code=400, detail="Excel file is empty")
        return df
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading Excel: {str(e)}")

async def insert_if_missing(db: AsyncSession, model, defaults):
    result = await db.execute(select(model))
    existing = result.scalars().first()
    if not existing:
        db.add_all(defaults)

async def upload_excel_to_db(db: AsyncSession, file_path: str, user: User):
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Insert master data if missing
    await insert_if_missing(db, Role, [
        Role(role_name="admin", role_code="100"),
        Role(role_name="educator", role_code="101")
    ])
    await insert_if_missing(db, Question_Type, [Question_Type(qtm_type_code="1000", qtm_type_name="MCQ")])
    await insert_if_missing(db, Medium, [Medium(mmt_medium_code="2000", mmt_medium_name="English")])
    await insert_if_missing(db, Subject, [
        Subject(smt_subject_code="3000", smt_subject_name="Social Science", smt_standard="10", smt_medium_id=1)
    ])
    await insert_if_missing(db, Criteria, [
        Criteria(scm_criteria_code="4000", scm_criteria_name="Chapter"),
        Criteria(scm_criteria_code="4001", scm_criteria_name="Topic")
    ])
    await insert_if_missing(db, Question_Format, [Question_Format(qfm_format_code="5000", qfm_format_name="Text")])
    await db.commit()

    # Load Excel Data
    df = await load_excel(file_path)

    taxonomy_mappings = {}

    # Insert taxonomy data
    for _, row in df.iterrows():
        result = await db.execute(
            select(Taxonomy).where(Taxonomy.stm_topic_name == row['topic_name'])
        )
        existing = result.scalars().first()
        key = (str(row['chapter_code']), str(row['topic_code']))

        if existing:
            taxonomy_mappings[key] = (existing.id, existing.stm_taxonomy_code)
            continue

        # Validate required fields
        if 'board_id' not in row or row['board_id'] is None:
            raise ValueError("board_id is required but not provided in row data")
        if 'state_id' not in row or row['state_id'] is None:
            raise ValueError("state_id is required but not provided in row data")
        
        # Generate taxonomy code with all context fields
        from app.services.code_generation_service import code_generation_service
        taxonomy_code = code_generation_service.generate_taxonomy_code(
            chapter_code=str(row['chapter_code']),
            topic_code=str(row['topic_code']),
            subtopic_code="",  # No subtopic in this service
            board_id=row['board_id'],  # Required field
            state_id=row['state_id'],  # Required field
            medium_id=row['medium_id'],
            standard=str(row['standard']),
            subject_id=row['subject_id']
        )
        
        taxonomy = Taxonomy(
            stm_taxonomy_code=taxonomy_code,
            stm_subject_id=row['subject_id'],
            stm_medium_id=row['medium_id'],
            stm_chapter_code=str(row['chapter_code']),
            stm_chapter_name=row['chapter_name'],
            stm_topic_code=str(row['topic_code']),
            stm_topic_name=row['topic_name'],
            stm_standard=str(row['standard']),
            board_id=row['board_id'],  # Required field
            state_id=row['state_id']   # Required field
        )
        db.add(taxonomy)
        await db.flush()
        await db.refresh(taxonomy)
        taxonomy_mappings[key] = (taxonomy.id, taxonomy.stm_taxonomy_code)

    await db.commit()

    # Load user context for organizational assignment
    user_context = await rbac_middleware.load_user_context(db, user)
    
    # Insert questions
    for _, row in df.iterrows():
        taxonomy_id, taxonomy_code = taxonomy_mappings.get(
            (str(row['chapter_code']), str(row['topic_code'])), (None, None)
        )
        if taxonomy_id is None:
            continue

        result = await db.execute(
            select(Questions).where(Questions.qmt_question_code == f"Q{row['q_id']}")
        )
        existing_question = result.scalars().first()
        if not existing_question:
            question = Questions(
                qmt_question_code=f"Q{row['q_id']}",
                qmt_question_text=str(row['q_text']),
                qmt_option1=str(row['qat_option1']),
                qmt_option2=str(row['qat_option2']),
                qmt_option3=str(row['qat_option3']),
                qmt_option4=str(row['qat_option4']),
                qmt_correct_answer=str(row['qat_correct_answer']),
                qmt_marks=1,
                qmt_format_id=1,
                qmt_type_id=1,
                qmt_taxonomy_id=taxonomy_id,
                qmt_taxonomy_code=taxonomy_code,
                qmt_is_active=True,
                status="Approved",  # Set default status to Approved
                # Associate with user's organizational context
                organization_id=user_context.organizational_scope["organization_id"],
                block_id=user_context.organizational_scope["block_id"],
                school_id=user_context.organizational_scope["school_id"],
                created_by=user.id
            )
            db.add(question)

    await db.commit()
    return {"message": "Excel data uploaded successfully"}

def generate_excel_template():
    wb = Workbook()

    # Sheet 1: Template
    ws_template = wb.active
    ws_template.title = "Questions"
    
    # New template headers
    headers = [
        "Question_text", "answer_option_A", "answer_option_B", 
        "answer_option_C", "answer_option_D", "correct_answer",
        "chapter_name", "topic_name", "subtopic_name",
        "Medium", "Board", "State", "Class", "Subject",
        "cognitive_learning", "difficulty"
    ]
    ws_template.append(headers)
    
    # One simple sample row
    sample_row = [
        "What is the capital of India?",
        "Delhi", "Mumbai", "Chennai", "Kolkata",
        "A",
        "Geography", "Cities", "Capital Cities",
        "English", "CBSE", "Delhi", "10", "Social Science",
        "Understanding", "Easy"
    ]
    ws_template.append(sample_row)

    # Sheet 2: Simple Instructions
    ws_instructions = wb.create_sheet(title="Instructions")
    instructions = [
        "Fill in the columns with your question data.",
        "Use A, B, C, or D for correct_answer.",
        "All other fields are text entries."
    ]

    for instruction in instructions:
        ws_instructions.append([instruction])

    # Return Excel file
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Enhanced_Question_Upload_Template.xlsx"}
    )