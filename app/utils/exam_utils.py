from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,func
from sqlalchemy.orm import joinedload
import random
import logging
from collections import defaultdict
import math
from typing import List, Optional

from app.models.master import Design, Medium, Subject, Question_Type, Questions, Taxonomy

logger = logging.getLogger(__name__)

async def check_existing_design(db: AsyncSession, design_name: str, exam_id: Optional[int] = None):
    """
    Check if a design with the given name already exists.
    
    Args:
        db: Database session
        design_name: Name of the design to check
        exam_id: Optional exam ID - if provided, checks uniqueness within that exam only
        
    Raises:
        HTTPException: If a design with the same name exists in the same context
    """
    query = select(Design).where(
        Design.dm_design_name == design_name,
        Design.is_active == True
    )
    
    # If exam_id is provided, check uniqueness within that exam
    if exam_id is not None:
        query = query.where(Design.exam_id == exam_id)
    
    existing_design = await db.scalar(query)
    if existing_design:
        if exam_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Design with name '{design_name}' already exists in this exam."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Design with name '{design_name}' already exists."
            )


async def resolve_foreign_keys(db: AsyncSession, payload):
    exam_type_obj = await db.scalar(select(Question_Type).where(Question_Type.qtm_type_code == payload.exam_type_code))
    if not exam_type_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Exam Type code '{payload.exam_type_code}' not found.")

    subject_obj = await db.scalar(select(Subject).where(Subject.smt_subject_code == payload.subject_code))
    if not subject_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subject code '{payload.subject_code}' not found.")

    medium_obj = await db.scalar(select(Medium).where(Medium.mmt_medium_code == payload.medium_code))
    if not medium_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Medium code '{payload.medium_code}' not found.")

    return exam_type_obj, subject_obj, medium_obj

async def select_questions( 
    db: AsyncSession,
    qns_payload,
    is_ai_selected: bool,
    subject_code: str,
    medium_code: str,
    board_id: Optional[int],
    state_id: Optional[int],
    total_questions: int,
    no_of_sets: int,
    total_questions_design: int,
    qtn_codes_to_exclude: List[str]
):
    all_question_codes = set()
    all_excluded_codes = set(qtn_codes_to_exclude)
    shortage_tracker = {}
    distribution_tracker = {}

    def build_base_query(filter_field, code_value):
        query = (
            select(Questions)
            .options(joinedload(Questions.taxonomy))
            .join(Questions.taxonomy)
            .join(Subject, Questions.subject_id == Subject.id)
            .join(Medium, Questions.medium_id == Medium.id)
            .where(
                getattr(Taxonomy, filter_field) == code_value,
                Subject.smt_subject_code == subject_code,
                Medium.mmt_medium_code == medium_code,
                Questions.qmt_is_active == True
            )
        )
        
        # Only add board_id filter when provided
        if board_id is not None:
            query = query.where(Questions.board_id == board_id)
        
        # Only add state_id filter when provided
        if state_id is not None:
            query = query.where(Questions.state_id == state_id)
            
        return query

    logger.info(f"Question selection started | AI Mode: {is_ai_selected}, Total Required (Sets x Qns): {total_questions}")

    # ---------------- AI MODE ----------------
    if is_ai_selected:
        logger.debug("AI selection mode enabled (qn_count ignored)")

        for qn_group in qns_payload:
            code_list = [c.code for c in qn_group.codes]
            filter_field = "stm_chapter_code" if qn_group.type == 'chapter' else "stm_topic_code"

            stmt = (
                select(Questions)
                .options(joinedload(Questions.taxonomy))
                .join(Questions.taxonomy)
                .join(Subject, Questions.subject_id == Subject.id)
                .join(Medium, Questions.medium_id == Medium.id)
                .where(
                    getattr(Taxonomy, filter_field).in_(code_list),
                    Subject.smt_subject_code == subject_code,
                    Medium.mmt_medium_code == medium_code,
                    Questions.qmt_is_active == True
                )
            )
            
            # Only add board_id filter when provided
            if board_id is not None:
                stmt = stmt.where(Questions.board_id == board_id)
            
            # Only add state_id filter when provided
            if state_id is not None:
                stmt = stmt.where(Questions.state_id == state_id)
            result = await db.execute(stmt)
            questions = result.scalars().all()
            all_question_codes.update(q.qmt_question_code for q in questions)

        selected_pool = [code for code in all_question_codes if code not in all_excluded_codes]

        if len(selected_pool) < total_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Not enough questions: required {total_questions}, got {len(selected_pool)}"
            )

        selected_question_codes = random.sample(selected_pool, total_questions)

        return {
            "selected_question_codes": selected_question_codes,
            "shortfall": {},
            "distribution_tracker": {}
        }

    # ---------------- MANUAL MODE ----------------
    logger.debug("Manual selection mode enabled (qn_count respected).")

    # Validate sum of qn_count = total_questions in manual mode
    qn_count_sum = sum(code.qn_count or 0 for group in qns_payload for code in group.codes)
    if qn_count_sum != total_questions_design:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sum of qn_count ({qn_count_sum}) must equal total_questions ({total_questions_design}) in Manual selection mode."
        )

    for qn_group in qns_payload:
        filter_field = "stm_chapter_code" if qn_group.type == 'chapter' else "stm_topic_code"

        for code_item in qn_group.codes:
            required_per_code = (code_item.qn_count) * no_of_sets
            base_stmt = build_base_query(filter_field, code_item.code)
            result = await db.execute(base_stmt)
            available_questions = result.scalars().all()
            available_count = len(available_questions)

            logger.info(f"[Manual] Code {code_item.code}: Required {required_per_code}, Available {available_count}")

            selected = []
            if available_count >= required_per_code:
                selected = random.sample(available_questions, required_per_code)
            else:
                selected = available_questions.copy()
                if available_questions:
                    while len(selected) < required_per_code:
                        selected.append(random.choice(available_questions))
                shortage_tracker[code_item.code] = {
                    "required": required_per_code,
                    "available": available_count,
                    "note": "Insufficient unique questions. Repeated questions used to meet requirement."
                }

            all_question_codes.update(q.qmt_question_code for q in selected)
            distribution_tracker[code_item.code] = len(selected)

    selected_question_codes = [code for code in all_question_codes if code not in all_excluded_codes]

    logger.info(f"Final selected: {len(selected_question_codes)} | Shortages: {shortage_tracker}")

    return {
        "selected_question_codes": selected_question_codes,
        "shortfall": shortage_tracker,
        "distribution_tracker": distribution_tracker
    }

async def generate_unique_design_code(prefix,db: AsyncSession) -> str:
    result = await db.execute(
        select(Design.dm_design_code)
        .where(Design.dm_design_code.like("EXM%"))
        .order_by(Design.dm_design_code.desc())
        .limit(1)
    )
    last_code = result.scalar()
    new_number = int(last_code[3:]) + 1 if last_code and last_code[3:].isdigit() else 1
    candidate_code = f"{prefix}{new_number:05d}"

    exists = await db.scalar(select(Design.id).where(Design.dm_design_code == candidate_code))
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Generated design code already exists. Try again.")

    return candidate_code