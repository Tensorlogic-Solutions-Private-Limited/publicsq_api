import random
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.status_codes import DESIGN_STATUS, DESIGN_STATUS_REVERSE
from app.models.master import (
    Design,
    Questions,
    Question_Type,
    Subject,
    Medium,
    Taxonomy,
    QuestionPaperDetails,
    State
)
from app.models.user import Role
from app.schemas.exams import DesignBase, QuestionSelection, DesignCreate, DesignUpdate
from app.services.qn_paper_service import resolve_chapter_topics_with_names
from app.services.state_resolution_service import StateResolutionService
from app.utils.build_options import build_options
from app.utils.exam_utils import (
    check_existing_design,
    resolve_foreign_keys,
    select_questions,
    generate_unique_design_code
)
from app.utils.get_user_role import get_user_role



async def create_design_record(db: AsyncSession, payload, current_user, design_code, exam_type_obj, subject_obj, medium_obj, all_question_codes):
    new_design = Design(
        dm_design_name=payload.exam_name,
        dm_design_code=design_code,
        dm_exam_type_id=exam_type_obj.id,
        dm_exam_mode=payload.exam_mode,
        dm_total_time=payload.total_time,
        dm_total_questions=payload.total_questions,
        dm_no_of_versions=payload.no_of_versions,
        dm_no_of_sets=payload.no_of_sets,
        dm_subject_id=subject_obj.id,
        dm_medium_id=medium_obj.id,
        dm_standard=payload.standard,
        division=payload.division,
        dm_status='closed',
        dm_total_question_codes=list(all_question_codes),
        created_by=current_user.id,
        # Associate with user's organizational context
        organization_id=current_user.organization_id,
        block_id=current_user.block_id,
        school_id=current_user.school_id
    )
    try:
        db.add(new_design)
        await db.commit()
        await db.refresh(new_design)
        return new_design
    except Exception as e:
        await db.rollback()
        from app.utils.database_error_handler import DatabaseErrorHandler
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        from fastapi import HTTPException, status
        
        if isinstance(e, (IntegrityError, SQLAlchemyError)):
            DatabaseErrorHandler.handle_sqlalchemy_error(
                e, 
                table_name="designs", 
                operation="create",
                context={"design_code": design_code, "exam_name": payload.exam_name}
            )
        
        # Re-raise other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create exam design"
        )


async def create_question_paper_details(db: AsyncSession, design, selected_codes, payload, current_user):
    chunks = [
        selected_codes[i * payload.total_questions : (i + 1) * payload.total_questions]
        for i in range(payload.no_of_sets)
    ]
    for set_index, question_set in enumerate(chunks, start=1):
        for version in range(1, payload.no_of_versions + 1):
            shuffled = question_set.copy()
            random.shuffle(shuffled)
            paper_id = f"QP{design.id:02d}S{set_index:02d}V{version:02d}"
            db.add(QuestionPaperDetails(
                qpd_paper_id=paper_id,
                qpd_q_codes=shuffled,
                qpd_total_time=payload.total_time,
                qpd_total_questions=payload.total_questions,
                qpd_design_name=payload.exam_name,
                qpd_design_id=design.id,
                created_by=current_user.id
            ))
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        from app.utils.database_error_handler import DatabaseErrorHandler
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        from fastapi import HTTPException, status
        
        if isinstance(e, (IntegrityError, SQLAlchemyError)):
            DatabaseErrorHandler.handle_sqlalchemy_error(
                e, 
                table_name="question_papers", 
                operation="create",
                context={"design_id": design.id}
            )
        
        # Re-raise other exceptions
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create question papers"
        )


async def build_response(db: AsyncSession, design, include_answers):
    papers = (await db.execute(
        select(QuestionPaperDetails).where(QuestionPaperDetails.qpd_design_id == design.id)
    )).scalars().all()

    all_codes = set(code for paper in papers for code in paper.qpd_q_codes)
    
    # Fetch questions
    result = await db.execute(
        select(Questions)
        .where(Questions.qmt_question_code.in_(all_codes))
    )
    questions_map = {q.qmt_question_code: q for q in result.scalars().all()}

    response = []
    for paper in papers:
        qns = []
        for code in paper.qpd_q_codes:
            q = questions_map.get(code)
            if q:
                qn_obj = {
                    "id": q.qmt_question_code,
                    "text": q.qmt_question_text,
                    "options": build_options(q, include_answers)
                }
                    
                qns.append(qn_obj)
        response.append({"id": paper.qpd_paper_id, "qns": qns})

    return response

async def create_exam_design_and_generate_qps(payload: DesignBase, current_user, db: AsyncSession, state_id: Optional[int] = None, exam_id: Optional[int] = None):
    try:
        # Resolve user role for permissions
        role = await get_user_role(db, current_user.role_id)
        # Allow teachers to view correct answers as well
        include_answers = role.role_code in ["super_admin", "admin", "admin_user", "teacher"]

        # state_id is already resolved in the endpoint, no need to resolve again

        # Get state name for response
        state_name = None
        if state_id:
            state_result = await db.execute(select(State.state_name).where(State.id == state_id))
            state_name = state_result.scalar_one_or_none()

        # Resolve foreign key references (exam type, subject, medium)
        exam_type_obj, subject_obj, medium_obj = await resolve_foreign_keys(db, payload)

        # Check for duplicate design name (within exam if exam_id provided)
        await check_existing_design(db, payload.exam_name, exam_id=exam_id)

        # Generate unique design code
        design_code = await generate_unique_design_code('EXM', db)

        # === 1. DRAFT SAVE (status=1) ===
        if payload.status == 1:
            # Generate question papers for draft mode (same as finalized)
            if not payload.chapters_topics or not isinstance(payload.chapters_topics, list):
                raise HTTPException(status_code=400, detail="chapters_topics are required for draft exams.")
            if payload.qtn_codes_to_exclude is None:
                payload.qtn_codes_to_exclude = []

            # Select questions using the same logic as finalized mode
            selected_codes_result = await select_questions(
                db=db,
                qns_payload=payload.chapters_topics,
                is_ai_selected=payload.is_ai_selected,
                subject_code=payload.subject_code,
                medium_code=payload.medium_code,
                board_id=payload.board_id,
                state_id=state_id,
                total_questions=payload.no_of_sets * payload.total_questions,  # (Sets x Questions)
                no_of_sets=payload.no_of_sets,
                total_questions_design=payload.total_questions,
                qtn_codes_to_exclude=payload.qtn_codes_to_exclude
            )

            selected_codes = selected_codes_result["selected_question_codes"]

            # Ensure at least total_questions are available to create a valid paper
            if not selected_codes or len(selected_codes) < payload.total_questions:
                raise HTTPException(
                    status_code=400,
                    detail=f"At least {payload.total_questions} questions are required to generate a question paper, "
                        f"but only {len(selected_codes) if selected_codes else 0} were available after filtering."
                )

            # Create draft design record with selected question codes
            design = await create_design_record(
                db=db,
                payload=payload,
                current_user=current_user,
                design_code=design_code,
                exam_type_obj=exam_type_obj,
                subject_obj=subject_obj,
                medium_obj=medium_obj,
                all_question_codes=selected_codes
            )

            # Save metadata for draft
            design.dm_status = "draft"
            design.dm_chapter_topics = [c.model_dump() for c in payload.chapters_topics]
            design.dm_questions_to_exclude = payload.qtn_codes_to_exclude

            await db.commit()
            await db.refresh(design)

            # Generate versions & sets for draft
            await create_question_paper_details(db, design, selected_codes, payload, current_user)

            # Build question papers response for draft (same as finalized)
            question_papers = await build_response(db, design, include_answers)

            # Resolve chapter_topics with names to match GET endpoint format
            resolved_chapter_topics = await resolve_chapter_topics_with_names(db, design.dm_chapter_topics)

            # Get board_name
            board_name = None
            if payload.board_id:
                from app.models.master import Board
                board_result = await db.execute(select(Board.board_name).where(Board.id == payload.board_id))
                board_name = board_result.scalar_one_or_none()

            # Unified Response for draft (all fields, now including question_papers)
            return {
                "status": 1,
                "message": "Draft saved successfully",
                "data": {
                    "exam_name": design.dm_design_name,
                    "exam_code": design.dm_design_code,
                    "status": design.dm_status,
                    "number_of_sets": design.dm_no_of_sets or None,
                    "number_of_versions": design.dm_no_of_versions or None,
                    "no_of_qns": design.dm_total_questions or None,
                    "subject": subject_obj.smt_subject_name,
                    "medium": medium_obj.mmt_medium_name,
                    "exam_type": exam_type_obj.qtm_type_name,
                    "board_id": payload.board_id,
                    "board_name": board_name,
                    "state_id": state_id,
                    "state_name": state_name,
                    "subject_code": payload.subject_code,
                    "medium_code": payload.medium_code,
                    "division": design.division,
                    "standard": design.dm_standard,
                    "chapters_topics": resolved_chapter_topics,
                    "questions_to_exclude": design.dm_questions_to_exclude,
                    "shortfall_info": selected_codes_result["shortfall"],
                    "question_papers": question_papers
                }
            }

        # === 2. FINALIZE (status=2) ===
        if payload.status == 2:
            # Mandatory validation for finalized exams
            if not payload.chapters_topics or not isinstance(payload.chapters_topics, list):
                raise HTTPException(status_code=400, detail="chapters_topics are required for finalized exams.")
            if payload.qtn_codes_to_exclude is None:
                payload.qtn_codes_to_exclude = []

            # Directly pass chapters_topics as qns_payload
            selected_codes_result = await select_questions(
                db=db,
                qns_payload=payload.chapters_topics,
                is_ai_selected=payload.is_ai_selected,
                subject_code=payload.subject_code,
                medium_code=payload.medium_code,
                board_id=payload.board_id,
                state_id=state_id,
                total_questions=payload.no_of_sets * payload.total_questions,  # (Sets x Questions)
                no_of_sets=payload.no_of_sets,
                total_questions_design=payload.total_questions,
                qtn_codes_to_exclude=payload.qtn_codes_to_exclude
            )

            selected_codes = selected_codes_result["selected_question_codes"]

            # Ensure at least total_questions are available to create a valid paper
            if not selected_codes or len(selected_codes) < payload.total_questions:
                raise HTTPException(
                    status_code=400,
                    detail=f"At least {payload.total_questions} questions are required to generate a question paper, "
                        f"but only {len(selected_codes) if selected_codes else 0} were available after filtering."
                )


            # Create finalized design record
            design = await create_design_record(
                db=db,
                payload=payload,
                current_user=current_user,
                design_code=design_code,
                exam_type_obj=exam_type_obj,
                subject_obj=subject_obj,
                medium_obj=medium_obj,
                all_question_codes=selected_codes
            )

            # Save metadata
            design.dm_status = "closed"
            design.dm_chapter_topics = [c.model_dump() for c in payload.chapters_topics]
            design.dm_questions_to_exclude = payload.qtn_codes_to_exclude

            await db.commit()
            await db.refresh(design)

            # Generate versions & sets
            await create_question_paper_details(db, design, selected_codes, payload, current_user)

            # Build final response
            question_papers = await build_response(db, design, include_answers)

            # Resolve chapter_topics with names to match GET endpoint format
            resolved_chapter_topics = await resolve_chapter_topics_with_names(db, design.dm_chapter_topics)

            # Get board_name
            board_name = None
            if payload.board_id:
                from app.models.master import Board
                board_result = await db.execute(select(Board.board_name).where(Board.id == payload.board_id))
                board_name = board_result.scalar_one_or_none()

            return {
                "status": 2,
                "message": "Exam finalized and question papers generated successfully",
                "data": {
                    "exam_name": design.dm_design_name,
                    "exam_code": design.dm_design_code,
                    "status": design.dm_status,
                    "number_of_sets": design.dm_no_of_sets,
                    "number_of_versions": design.dm_no_of_versions,
                    "no_of_qns": design.dm_total_questions,
                    "subject": subject_obj.smt_subject_name,
                    "medium": medium_obj.mmt_medium_name,
                    "exam_type": exam_type_obj.qtm_type_name,
                    "board_id": payload.board_id,
                    "board_name": board_name,
                    "state_id": state_id,
                    "state_name": state_name,
                    "subject_code": payload.subject_code,
                    "medium_code": payload.medium_code,
                    "division": design.division,
                    "standard": design.dm_standard,
                    "chapters_topics": resolved_chapter_topics,
                    "shortfall_info": selected_codes_result["shortfall"],
                    "question_papers": question_papers
                }
            }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating exam: {str(e)}")

async def update_design_service(
    db: AsyncSession,
    exam_code: str,
    payload: DesignUpdate,
    current_user,
    state_id: Optional[int] = None
):
    # Fetch existing design
    result = await db.execute(select(Design).where(Design.dm_design_code == exam_code))
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Exam design not found")

    # Resolve state_id using StateResolutionService if not provided
    if state_id is None:
        state_id = await StateResolutionService.resolve_state_for_user(db, current_user)

    # Get state name for response
    state_name = None
    if state_id:
        state_result = await db.execute(select(State.state_name).where(State.id == state_id))
        state_name = state_result.scalar_one_or_none()

    # Role validation and hierarchical permission check
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    
    # Check hierarchical permissions for editing
    if role_obj.role_code == "teacher":
        # Teachers can only edit their own designs within their school
        if design.created_by != current_user.id or design.school_id != current_user.school_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this design")
    elif role_obj.role_code == "block_admin":
        # Block admins can edit designs within their block
        if design.block_id != current_user.block_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this design")
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can edit designs within their organization
        if design.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this design")
    # Super admins can edit all designs (no additional checks)

    # === Duplicate exam name check (only if changed) ===
    if payload.exam_name and payload.exam_name != design.dm_design_name:
        with db.no_autoflush:  # Use synchronous context manager
            await check_existing_design(db, payload.exam_name)

    # Resolve foreign keys (exam type, subject, medium)
    exam_type_obj, subject_obj, medium_obj = await resolve_foreign_keys(db, payload)

    # Update core design fields (map API → DB)
    design.dm_design_name = payload.exam_name or design.dm_design_name
    design.dm_exam_type_id = exam_type_obj.id
    design.dm_subject_id = subject_obj.id
    design.dm_medium_id = medium_obj.id
    design.dm_exam_mode = payload.exam_mode or design.dm_exam_mode
    design.dm_total_time = payload.total_time or design.dm_total_time
    design.dm_total_questions = payload.total_questions or design.dm_total_questions
    design.dm_no_of_versions = payload.no_of_versions or design.dm_no_of_versions
    design.dm_no_of_sets = payload.no_of_sets or design.dm_no_of_sets
    design.dm_standard = payload.standard or design.dm_standard
    design.division = payload.division or design.division
    design.updated_by = current_user.id
    design.updated_at = datetime.utcnow()

    # === Draft Update (status=1) ===
    if payload.status == 1:
        design.dm_status = "draft"
        design.dm_chapter_topics = (
            [c.model_dump() for c in payload.chapters_topics] if payload.chapters_topics else None
        )
        design.dm_questions_to_exclude = payload.qtn_codes_to_exclude or None

        await db.commit()
        await db.refresh(design)

        # Resolve chapter_topics with names to match GET endpoint format
        resolved_chapter_topics = await resolve_chapter_topics_with_names(db, design.dm_chapter_topics or [])

        # Get board_name
        board_name = None
        if payload.board_id:
            from app.models.master import Board
            board_result = await db.execute(select(Board.board_name).where(Board.id == payload.board_id))
            board_name = board_result.scalar_one_or_none()

        return {
            "status": 1,
            "message": "Draft updated successfully",
            "data": {
                "exam_name": design.dm_design_name,
                "exam_code": design.dm_design_code,
                "status": design.dm_status,
                "number_of_sets": design.dm_no_of_sets,
                "number_of_versions": design.dm_no_of_versions,
                "no_of_qns": design.dm_total_questions,
                "subject": subject_obj.smt_subject_name,
                "medium": medium_obj.mmt_medium_name,
                "exam_type": exam_type_obj.qtm_type_name,
                "board_id": payload.board_id,
                "board_name": board_name,
                "state_id": state_id,
                "state_name": state_name,
                "subject_code": subject_obj.smt_subject_code,
                "medium_code": medium_obj.mmt_medium_code,
                "division": design.division,
                "standard": design.dm_standard,
                "chapters_topics": resolved_chapter_topics,
                "questions_to_exclude": design.dm_questions_to_exclude,
            }
        }

    # === Finalize Update (status=2) ===
    if payload.status == 2:
        if not payload.chapters_topics or not isinstance(payload.chapters_topics, list):
            raise HTTPException(status_code=400, detail="chapters_topics required for finalized exams")
        if payload.qtn_codes_to_exclude is None:
            payload.qtn_codes_to_exclude = []

        # Select questions
        selected_codes_result = await select_questions(
            db=db,
            qns_payload=payload.chapters_topics,
            is_ai_selected=payload.is_ai_selected,
            subject_code=payload.subject_code,
            medium_code=payload.medium_code,
            board_id=payload.board_id,
            state_id=state_id,  # Use state_id for question filtering (from PATCH finalization)
            total_questions=payload.no_of_sets * payload.total_questions,
            no_of_sets=payload.no_of_sets,
            total_questions_design=payload.total_questions,
            qtn_codes_to_exclude=payload.qtn_codes_to_exclude
        )
        selected_codes = selected_codes_result["selected_question_codes"]

        if not selected_codes or len(selected_codes) < payload.total_questions:
            raise HTTPException(
                status_code=400,
                detail=f"At least {payload.total_questions} questions are required to generate a question paper, "
                    f"but only {len(selected_codes) if selected_codes else 0} were available after filtering."
    )

        # Update finalized design
        design.dm_status = "closed"
        design.dm_chapter_topics = [c.model_dump() for c in payload.chapters_topics]
        design.dm_questions_to_exclude = payload.qtn_codes_to_exclude
        design.dm_total_question_codes = selected_codes

        await db.commit()
        await db.refresh(design)

        # Generate question papers
        await create_question_paper_details(db, design, selected_codes, payload, current_user)

        include_answers = role_obj.role_code in ["super_admin", "admin", "admin_user"]
        question_papers = await build_response(db, design, include_answers)

        # Resolve chapter_topics with names to match GET endpoint format
        resolved_chapter_topics = await resolve_chapter_topics_with_names(db, design.dm_chapter_topics or [])

        # Get board_name
        board_name = None
        if payload.board_id:
            from app.models.master import Board
            board_result = await db.execute(select(Board.board_name).where(Board.id == payload.board_id))
            board_name = board_result.scalar_one_or_none()

        return {
            "status": 2,
            "message": "Exam finalized and question papers generated successfully",
            "data": {
                "exam_name": design.dm_design_name,
                "exam_code": design.dm_design_code,
                "status": design.dm_status,
                "number_of_sets": design.dm_no_of_sets,
                "number_of_versions": design.dm_no_of_versions,
                "no_of_qns": design.dm_total_questions,
                "subject": subject_obj.smt_subject_name,
                "medium": medium_obj.mmt_medium_name,
                "exam_type": exam_type_obj.qtm_type_name,
                "board_id": payload.board_id,
                "board_name": board_name,
                "state_id": state_id,
                "state_name": state_name,
                "subject_code": payload.subject_code,
                "medium_code": payload.medium_code,
                "division": design.division,
                "standard": design.dm_standard,
                "chapters_topics": resolved_chapter_topics,
                "shortfall_info": selected_codes_result["shortfall"],
                "question_papers": question_papers,
            }
        }

async def remove_question_from_exam_paper(
    exam_code: str,
    paper_code: str,
    question_code: str,
    db: AsyncSession,
    current_user
):
    """Remove a question from a specific exam paper."""
    from app.models.master import Design, QuestionPaperDetails, Questions
    from fastapi import HTTPException, status
    from sqlalchemy.orm.attributes import flag_modified
    
    # 1. Validate that the paper belongs to the exam
    # Get the exam by exam_code
    exam_stmt = select(Design).where(Design.dm_design_code == exam_code, Design.is_active == True)
    exam_result = await db.execute(exam_stmt)
    exam = exam_result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with code '{exam_code}' not found"
        )
    
    # Get the paper by paper_code
    paper_stmt = select(QuestionPaperDetails).where(QuestionPaperDetails.qpd_paper_id == paper_code)
    paper_result = await db.execute(paper_stmt)
    paper = paper_result.scalar_one_or_none()
    
    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question paper with code '{paper_code}' not found"
        )
    
    # Validate that the paper belongs to the exam
    if paper.qpd_design_id != exam.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This paper is not associated with the given exam"
        )
    
    # 2. Check if question exists in the paper's question list
    if not paper.qpd_q_codes or question_code not in paper.qpd_q_codes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_code}' not found in paper '{paper_code}'"
        )
    
    # 3. Remove question from paper's qpd_q_codes list
    paper.qpd_q_codes.remove(question_code)
    paper.qpd_total_questions = len(paper.qpd_q_codes)
    
    # Mark the JSON field as changed for SQLAlchemy
    flag_modified(paper, 'qpd_q_codes')
    
    # 4. Remove question from exam's dm_total_question_codes list
    if exam.dm_total_question_codes and question_code in exam.dm_total_question_codes:
        exam.dm_total_question_codes.remove(question_code)
        exam.dm_total_questions = len(exam.dm_total_question_codes)
        
        # Mark the JSON field as changed for SQLAlchemy
        flag_modified(exam, 'dm_total_question_codes')
    
    # 5. Check question status and handle accordingly
    question_stmt = select(Questions).where(Questions.qmt_question_code == question_code)
    question_result = await db.execute(question_stmt)
    question = question_result.scalar_one_or_none()
    
    question_deleted = False
    if question and question.status == "review":
        # Delete associated S3 images before hard deleting the question
        await _delete_question_images(question)
        
        # Hard delete the question from the database since it's in review state
        await db.delete(question)
        question_deleted = True
    # For questions not in review state, do nothing to the question itself
    
    await db.commit()
    
    return {
        "message": f"Question '{question_code}' removed successfully from paper '{paper_code}'",
        "question_code": question_code,
        "paper_code": paper_code,
        "exam_code": exam_code,
        "total_questions_in_paper": paper.qpd_total_questions,
        "total_questions_in_exam": exam.dm_total_questions,
        "question_deleted": question_deleted
    }

async def _delete_question_images(question):
    """
    Delete all S3 images associated with a question.
    
    Args:
        question: Question object with image media fields
    """
    from app.services.s3_service import s3_service
    import logging
    import re
    
    logger = logging.getLogger(__name__)
    
    # List of image media fields to check
    image_fields = [
        'qmt_question_text_media',
        'qmt_option1_media', 
        'qmt_option2_media',
        'qmt_option3_media',
        'qmt_option4_media'
    ]
    
    deleted_files = []
    failed_deletions = []
    
    for field_name in image_fields:
        field_value = getattr(question, field_name, None)
        
        if field_value and isinstance(field_value, list):
            for s3_url in field_value:
                if s3_url and isinstance(s3_url, str):
                    try:
                        # Extract S3 key from URL
                        # URL format: https://bucket.s3.region.amazonaws.com/path/to/file.jpg
                        # We need to extract: path/to/file.jpg
                        s3_key = _extract_s3_key_from_url(s3_url)
                        
                        if s3_key:
                            # Delete the file from S3
                            success = s3_service.delete_file(s3_key)
                            if success:
                                deleted_files.append(s3_key)
                                logger.info(f"Successfully deleted S3 file: {s3_key}")
                            else:
                                failed_deletions.append(s3_key)
                                logger.warning(f"Failed to delete S3 file: {s3_key}")
                        else:
                            logger.warning(f"Could not extract S3 key from URL: {s3_url}")
                            
                    except Exception as e:
                        logger.error(f"Error deleting S3 file {s3_url}: {str(e)}")
                        failed_deletions.append(s3_url)
    
    # Log summary
    if deleted_files:
        logger.info(f"Deleted {len(deleted_files)} S3 files for question {question.qmt_question_code}")
    if failed_deletions:
        logger.warning(f"Failed to delete {len(failed_deletions)} S3 files for question {question.qmt_question_code}")


def _extract_s3_key_from_url(s3_url: str) -> str:
    """
    Extract S3 key from S3 URL.
    
    Args:
        s3_url: Full S3 URL (e.g., https://bucket.s3.region.amazonaws.com/path/to/file.jpg)
        
    Returns:
        str: S3 key (e.g., path/to/file.jpg) or None if extraction fails
    """
    import re
    
    # Pattern to match S3 URLs and extract the key part
    # Matches: https://bucket.s3.region.amazonaws.com/key/path
    pattern = r'https://[^/]+\.s3\.[^/]+\.amazonaws\.com/(.+)'
    
    match = re.match(pattern, s3_url)
    if match:
        return match.group(1)
    
    # Alternative pattern for different S3 URL formats
    # Matches: https://s3.region.amazonaws.com/bucket/key/path
    alt_pattern = r'https://s3\.[^/]+\.amazonaws\.com/[^/]+/(.+)'
    
    alt_match = re.match(alt_pattern, s3_url)
    if alt_match:
        return alt_match.group(1)
    
    return None