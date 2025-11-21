from datetime import date
from typing import Optional, List, Tuple

import sqlalchemy as sa
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.master import Design, Subject, Medium, Question_Type, Questions, Taxonomy, QuestionPaperDetails, State, Board
from app.models.user import Role, User
from app.schemas.qn_papers import SingleDesignResponse, SingleDesignResponseItem, DesignPaperListResponseItem, DesignPaperListResponsePaginated
from app.utils.get_user_role import get_user_role

async def get_all_exam_designs(
    db: AsyncSession,
    current_user: User,
    status: str,
    exam_name: Optional[str] = None,
    subject: Optional[str] = None,
    medium: Optional[str] = None,
    standard: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    page: int = 1,
    limit: int = 20,
    scope_filter: Optional[dict] = None,
    state_id: Optional[int] = None
) -> Tuple[List[dict], int]:
    """Fetches paginated exam designs with filters for admins and regular users."""

    # Validate status
    if status not in ["draft", "closed"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'draft' or 'closed'.")

    # Role validation
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    is_admin = role_obj.role_code in ["super_admin", "admin", "admin_user"]

    # Base query (designs only)
    query = (
        select(Design)
        .where(Design.dm_status == status, Design.is_active == True)
        .options(
            joinedload(Design.subject),
            joinedload(Design.medium),
            joinedload(Design.type),
            joinedload(Design.created_by_user),
            joinedload(Design.updated_by_user)
        )
    )

    # Apply role-based scope filtering
    if scope_filter:
        for key, value in scope_filter.items():
            if hasattr(Design, key):
                query = query.where(getattr(Design, key) == value)

    # Dynamic filters
    filters = []
    if exam_name:
        filters.append(Design.dm_design_name.ilike(f"%{exam_name}%"))
    if subject:
        filters.append(Design.subject.has(Subject.smt_subject_name == subject))
    if medium:
        filters.append(Design.medium.has(Medium.mmt_medium_name == medium))
    if standard:
        filters.append(Design.dm_standard == standard)
    if start_date and end_date:
        filters.append(func.date(Design.created_at).between(start_date, end_date))
    elif start_date:
        filters.append(func.date(Design.created_at) >= start_date)
    elif end_date:
        filters.append(func.date(Design.created_at) <= end_date)

    # State filtering is now handled through scope_filter in the endpoint

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(Design.created_at.desc())

    # Count query for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_count = (await db.execute(count_query)).scalar()

    # Paginated fetch
    query = query.limit(limit).offset((page - 1) * limit)
    result = await db.execute(query)
    designs = result.scalars().all()

    # Construct response dicts manually (no Pydantic)
    response_designs = []
    for d in designs:
        # Always query codes directly from foreign keys for reliability
        subject_code = None
        medium_code = None
        board_id = None
        
        try:
            if d.dm_subject_id:
                subject_result = await db.execute(
                    select(Subject.smt_subject_code).where(Subject.id == d.dm_subject_id)
                )
                subject_code = subject_result.scalar_one_or_none()
                print(f"Debug: Design {d.dm_design_code}, subject_id={d.dm_subject_id}, subject_code={subject_code}")
            
            if d.dm_medium_id:
                medium_result = await db.execute(
                    select(Medium.mmt_medium_code).where(Medium.id == d.dm_medium_id)
                )
                medium_code = medium_result.scalar_one_or_none()
                print(f"Debug: Design {d.dm_design_code}, medium_id={d.dm_medium_id}, medium_code={medium_code}")
        except Exception as e:
            print(f"Error querying codes for design {d.dm_design_code}: {e}")
        
        # Derive board_id, state_id, board_name, and state_name from first question of first paper (like detail endpoint)
        state_id = None
        state_name = None
        board_name = None
        try:
            # get first paper id for this design
            paper_stmt = select(QuestionPaperDetails.qpd_paper_id).where(QuestionPaperDetails.qpd_design_id == d.id)
            first_paper_id = (await db.execute(paper_stmt.limit(1))).scalar_one_or_none()
            if first_paper_id:
                # get q_codes for paper
                qcodes_stmt = select(QuestionPaperDetails.qpd_q_codes).where(QuestionPaperDetails.qpd_paper_id == first_paper_id)
                qcodes = (await db.execute(qcodes_stmt)).scalar_one_or_none()
                if qcodes and len(qcodes) > 0:
                    first_qcode = qcodes[0]
                    q_board_stmt = select(Questions.board_id).where(Questions.qmt_question_code == first_qcode)
                    board_id = (await db.execute(q_board_stmt)).scalar_one_or_none()
                    # Derive state_id from the same first question
                    q_state_stmt = select(Questions.state_id).where(Questions.qmt_question_code == first_qcode)
                    state_id = (await db.execute(q_state_stmt)).scalar_one_or_none()
                    
                    # Get board name if board_id is available
                    if board_id:
                        board_name_stmt = select(Board.board_name).where(Board.id == board_id)
                        board_name = (await db.execute(board_name_stmt)).scalar_one_or_none()
                    
                    # Get state name if state_id is available
                    if state_id:
                        state_name_stmt = select(State.state_name).where(State.id == state_id)
                        state_name = (await db.execute(state_name_stmt)).scalar_one_or_none()
        except Exception as e:
            print(f"Error deriving board_id, state_id, board_name, and state_name for design {d.dm_design_code}: {e}")
        
        response_designs.append({
            "exam_name": d.dm_design_name,
            "exam_code": d.dm_design_code,
            "exam_type": d.type.qtm_type_name if d.type else None,
            "exam_mode": d.dm_exam_mode or None,
            "standard": d.dm_standard or None,
            "division": d.division or None,
            "subject": d.subject.smt_subject_name if d.subject else None,
            "medium": d.medium.mmt_medium_name if d.medium else None,
            "status": d.dm_status,
            "number_of_sets": d.dm_no_of_sets,
            "number_of_versions": d.dm_no_of_versions,
            "total_questions": d.dm_total_questions,
            "board_id": board_id,  # Derived from first question of first paper
            "board_name": board_name,  # Derived from first question of first paper
            "state_id": state_id,  # Derived from first question of first paper
            "state_name": state_name,  # Derived from first question of first paper
            "subject_code": subject_code,
            "medium_code": medium_code,
            "created_at": d.created_at.isoformat() if d.created_at else None,  
            "created_by": d.created_by_user.username if d.created_by_user else None,
        })

    return response_designs, total_count

async def get_design_by_exam_code(
    db: AsyncSession,
    exam_code: str,
    current_user: User
) -> dict:
    # Get user role
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")

    # Get design
    stmt = select(Design).where(Design.dm_design_code == exam_code, Design.is_active == True)
    
    # Apply hierarchical scope filtering
    if role_obj.role_code == "teacher":
        # Teachers can only see their own designs within their school
        stmt = stmt.where(
            Design.created_by == current_user.id,
            Design.school_id == current_user.school_id
        )
    elif role_obj.role_code == "block_admin":
        # Block admins can see designs within their block
        stmt = stmt.where(Design.block_id == current_user.block_id)
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can see designs within their organization
        stmt = stmt.where(Design.organization_id == current_user.organization_id)
    # Super admins can see all designs (no additional filtering)

    result = await db.execute(stmt)
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found or access denied")

    # Lookup values
    subject_name = (await db.execute(
        select(Subject.smt_subject_name).where(Subject.id == design.dm_subject_id)
    )).scalar_one_or_none() or "Unknown"

    medium_name = (await db.execute(
        select(Medium.mmt_medium_name).where(Medium.id == design.dm_medium_id)
    )).scalar_one_or_none() or "Unknown"

    exam_type_name = (await db.execute(
        select(Question_Type.qtm_type_name).where(Question_Type.id == design.dm_exam_type_id)
    )).scalar_one_or_none() or "Unknown"

    # Paper codes
    paper_codes = (await db.execute(
        select(QuestionPaperDetails.qpd_paper_id)
        .where(QuestionPaperDetails.qpd_design_id == design.id)
    )).scalars().all()

    # Questions to exclude
    qtn_codes_to_exclude = []
    codes_list = design.dm_questions_to_exclude or []

    if codes_list:
        result = await db.execute(
            select(
                Questions.qmt_question_code,
                Questions.qmt_question_text,
                Taxonomy.stm_chapter_code,
                Taxonomy.stm_chapter_name,
                Taxonomy.stm_topic_code,
                Taxonomy.stm_topic_name
            )
            .join(Taxonomy, Questions.qmt_taxonomy_id == Taxonomy.id)
            .where(Questions.qmt_question_code.in_(codes_list))
        )

        for code, txt, ch_code, ch_name, t_code, t_name in result.all():
            qtn_codes_to_exclude.append({
                "code": code,
                "txt": txt,
                "chapter_details": {"code": ch_code, "name": ch_name},
                "topic_details": {"code": t_code, "name": t_name}
            })

    # Resolve chapter/topic groups using the reusable helper
    raw_chapters_topics = design.dm_chapter_topics or []
    resolved_chapters_topics = await resolve_chapter_topics_with_names(db, raw_chapters_topics)

    # Fetch board_id, state_id, medium_code, and subject_code from a question in the exam
    board_id = None
    board_name = None
    state_id = None
    state_name = None
    medium_code = None
    subject_code = None
    
    if paper_codes:
        # Get the first paper code
        first_paper_code = paper_codes[0]
        
        # Get question codes from the paper
        paper_result = await db.execute(
            select(QuestionPaperDetails.qpd_q_codes)
            .where(QuestionPaperDetails.qpd_paper_id == first_paper_code)
        )
        paper_data = paper_result.scalar_one_or_none()
        
        if paper_data and len(paper_data) > 0:
            # Get the first question code from the JSON array
            first_question_code = paper_data[0]
            
            # Get question details
            question_result = await db.execute(
                select(Questions.qmt_question_code, Questions.board_id, Questions.state_id, Questions.medium_id, Questions.subject_id)
                .where(Questions.qmt_question_code == first_question_code)
            )
            
            question_data = question_result.first()
            if question_data:
                board_id = question_data.board_id
                state_id = question_data.state_id
                
                # Get board_name from board_master
                if board_id:
                    board_result = await db.execute(
                        select(Board.board_name)
                        .where(Board.id == board_id)
                    )
                    board_name = board_result.scalar_one_or_none()
                
                # Get state_name from state_master
                if state_id:
                    state_result = await db.execute(
                        select(State.state_name)
                        .where(State.id == state_id)
                    )
                    state_name = state_result.scalar_one_or_none()
                
                # Get medium_code from medium_master
                if question_data.medium_id:
                    medium_result = await db.execute(
                        select(Medium.mmt_medium_code)
                        .where(Medium.id == question_data.medium_id)
                    )
                    medium_code = medium_result.scalar_one_or_none()
                
                # Get subject_code from subject_master
                if question_data.subject_id:
                    subject_result = await db.execute(
                        select(Subject.smt_subject_code)
                        .where(Subject.id == question_data.subject_id)
                    )
                    subject_code = subject_result.scalar_one_or_none()
    
    # Fallback: If medium_code and subject_code are still None, get them from design's foreign keys
    if medium_code is None and design.dm_medium_id:
        medium_result = await db.execute(
            select(Medium.mmt_medium_code)
            .where(Medium.id == design.dm_medium_id)
        )
        medium_code = medium_result.scalar_one_or_none()
    
    if subject_code is None and design.dm_subject_id:
        subject_result = await db.execute(
            select(Subject.smt_subject_code)
            .where(Subject.id == design.dm_subject_id)
        )
        subject_code = subject_result.scalar_one_or_none()

    # Final response
    response_model = SingleDesignResponse(
        design=SingleDesignResponseItem(
            exam_name=design.dm_design_name,
            exam_code=design.dm_design_code,
            exam_type=exam_type_name,
            exam_mode=design.dm_exam_mode,
            standard=design.dm_standard,
            division=design.division,
            subject=subject_name,
            medium=medium_name,
            status=design.dm_status,
            number_of_sets=design.dm_no_of_sets,
            number_of_versions=design.dm_no_of_versions,
            total_questions=design.dm_total_questions,
            board_id=board_id,
            board_name=board_name,
            state_id=state_id,
            state_name=state_name,
            medium_code=medium_code,
            subject_code=subject_code,
            created_at=design.created_at.isoformat() if design.created_at else None,
            qtn_codes_to_exclude=qtn_codes_to_exclude,
            chapters_topics=resolved_chapters_topics,
            papers=paper_codes
        )
    )

    return response_model.model_dump(exclude_none=False)


async def resolve_chapter_topics_with_names(db: AsyncSession, raw_chapters_topics: list) -> list:
    """
    Resolve chapter/topic codes with their names and chapter details for topics.
    This matches the format used in GET /v1/exams/{exam_code} endpoint.
    Extracted from get_design_by_exam_code to be reusable across services.
    """
    resolved_chapters_topics = []

    for group in raw_chapters_topics:
        group_type = group.get("type")
        codes = group.get("codes", [])
        code_values = [item["code"] for item in codes]
        resolved_codes = []

        if group_type == "chapter":
            result = await db.execute(
                select(Taxonomy.stm_chapter_code, Taxonomy.stm_chapter_name)
                .where(Taxonomy.stm_chapter_code.in_(code_values))
                .distinct()
            )
            name_map = {code: name for code, name in result.all()}

            for item in codes:
                resolved_codes.append({
                    "code": item["code"],
                    "qn_count": item.get("qn_count"),
                    "name": name_map.get(item["code"], "Unknown")
                    # No chapter_details included for chapters
                })

        elif group_type == "topic":
            result = await db.execute(
                select(
                    Taxonomy.stm_topic_code,
                    Taxonomy.stm_topic_name,
                    Taxonomy.stm_chapter_code,
                    Taxonomy.stm_chapter_name
                )
                .where(Taxonomy.stm_topic_code.in_(code_values))
                .distinct()
            )
            topic_map = {
                code: {
                    "name": name,
                    "chapter_details": {
                        "code": ch_code,
                        "name": ch_name
                    }
                }
                for code, name, ch_code, ch_name in result.all()
            }

            for item in codes:
                topic_data = topic_map.get(item["code"], {})
                resolved_code = {
                    "code": item["code"],
                    "qn_count": item.get("qn_count"),
                    "name": topic_data.get("name", "Unknown"),
                }

                if "chapter_details" in topic_data:
                    resolved_code["chapter_details"] = topic_data["chapter_details"]

                resolved_codes.append(resolved_code)

        resolved_chapters_topics.append({
            "type": group_type,
            "codes": resolved_codes
        })

    return resolved_chapters_topics


# async def get_design_by_exam_code(
#     db: AsyncSession,
#     exam_code: str,
#     current_user: User
# ) -> SingleDesignResponse:

#     # Get user role
#     role_obj = await get_user_role(db, current_user.role_id)
#     if not role_obj:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")

#     is_admin = role_obj.role_code == "100"

#     # Get design
#     design_stmt = select(Design).where(Design.dm_design_code == exam_code)
#     if not is_admin:
#         design_stmt = design_stmt.where(Design.created_by == current_user.id)

#     design_result = await db.execute(design_stmt)
#     design = design_result.scalar_one_or_none()
#     if not design:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Design not found")

#     # Subject
#     subject_name = (await db.execute(
#         select(Subject.smt_subject_name).where(Subject.id == design.dm_subject_id)
#     )).scalar_one_or_none() or "Unknown"

#     # Medium
#     medium_name = (await db.execute(
#         select(Medium.mmt_medium_name).where(Medium.id == design.dm_medium_id)
#     )).scalar_one_or_none() or "Unknown"

#     # Exam type
#     exam_type_name = (await db.execute(
#         select(Question_Type.qtm_type_name).where(Question_Type.id == design.dm_exam_type_id)
#     )).scalar_one_or_none() or "Unknown"

#     # Paper codes
#     paper_codes = (await db.execute(
#         select(QuestionPaperDetails.qpd_paper_id).where(QuestionPaperDetails.qpd_design_id == design.id)
#     )).scalars().all()

#     # Questions to exclude
#     qtn_codes_to_exclude = []
#     codes_list = design.dm_questions_to_exclude or []

#     if codes_list:
#         q_texts_result = await db.execute(
#             select(
#                 Questions.qmt_question_code,
#                 Questions.qmt_question_text,
#                 Taxonomy.stm_chapter_code,
#                 Taxonomy.stm_chapter_name,
#                 Taxonomy.stm_topic_code,
#                 Taxonomy.stm_topic_name
#             )
#             .join(Taxonomy, Questions.qmt_taxonomy_id == Taxonomy.id)
#             .where(Questions.qmt_question_code.in_(codes_list))
#         )
#         question_info = q_texts_result.all()

#         question_info_map = {
#             code: {
#                 "txt": txt,
#                 "chapter_details": {
#                     "code": ch_code,
#                     "name": ch_name
#                 },
#                 "topic_details": {
#                     "code": t_code,
#                     "name": t_name
#                 }
#             }
#             for code, txt, ch_code, ch_name, t_code, t_name in question_info
#         }

#         for code in codes_list:
#             info = question_info_map.get(code)
#             if info:
#                 qtn_codes_to_exclude.append({
#                     "code": code,
#                     "txt": info["txt"],
#                     "chapter_details": info["chapter_details"],
#                     "topic_details": info["topic_details"]
#                 })

#     # Resolve chapters_topics with names
#     raw_chapters_topics = design.dm_chapter_topics or []
#     resolved_chapters_topics = []

#     for group in raw_chapters_topics:
#         group_type = group.get("type")
#         codes = group.get("codes", [])
#         code_values = [item["code"] for item in codes]
#         resolved_codes = []

#         if group_type == "chapter":
#             result = await db.execute(
#                 select(Taxonomy.stm_chapter_code, Taxonomy.stm_chapter_name)
#                 .where(Taxonomy.stm_chapter_code.in_(code_values))
#                 .distinct()
#             )
#             name_map = {code: name for code, name in result.all()}

#         elif group_type == "topic":
#             result = await db.execute(
#                 select(Taxonomy.stm_topic_code, Taxonomy.stm_topic_name)
#                 .where(Taxonomy.stm_topic_code.in_(code_values))
#                 .distinct()
#             )
#             name_map = {code: name for code, name in result.all()}

#         else:
#             name_map = {}

#         for item in codes:
#             resolved_codes.append({
#                 "code": item["code"],
#                 "qn_count": item.get("qn_count", 0),
#                 "name": name_map.get(item["code"], "Unknown")
#             })

#         resolved_chapters_topics.append({
#             "type": group_type,
#             "codes": resolved_codes
#         })

#     # Final response
#     return SingleDesignResponse(
#         design=SingleDesignResponseItem(
#             exam_name=design.dm_design_name,
#             exam_code=design.dm_design_code,
#             exam_type=exam_type_name,
#             exam_mode=design.dm_exam_mode,
#             standard=design.dm_standard,
#             subject=subject_name,
#             medium=medium_name,
#             status=design.dm_status,
#             number_of_sets=design.dm_no_of_sets,
#             number_of_versions=design.dm_no_of_versions,
#             total_questions=design.dm_total_questions,
#             qtn_codes_to_exclude=qtn_codes_to_exclude,
#             chapters_topics=resolved_chapters_topics,
#             papers=paper_codes
#         )
#     )
async def delete_design_by_exam_code(
    db: AsyncSession,
    current_user: User,
    exam_code: str
) -> str:
    # Get user role
    role_obj = await get_user_role(db, current_user.role_id)

    if not role_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")

    # Fetch design with hierarchical permission check
    stmt = select(Design).where(Design.dm_design_code == exam_code, Design.is_active == True)

    # Apply hierarchical scope filtering for deletion
    if role_obj.role_code == "teacher":
        # Teachers can delete only exams they created
        stmt = stmt.where(Design.created_by == current_user.id)
    elif role_obj.role_code == "block_admin":
        # Block admins can delete designs within their block
        stmt = stmt.where(Design.block_id == current_user.block_id)
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can delete designs within their organization
        stmt = stmt.where(Design.organization_id == current_user.organization_id)
    # super_admin -> no extra filter

    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam code not found or you do not have permission to delete it"
        )

    # Check if exam is finalized - cannot delete finalized exams
    if design.dm_status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a finalized exam. Only draft exams can be deleted."
        )
    
    # Check if design belongs to an exam and validate exam status
    if design.exam_id:
        from app.models.master import ExamMaster
        exam_stmt = select(ExamMaster).where(ExamMaster.id == design.exam_id)
        exam_result = await db.execute(exam_stmt)
        exam = exam_result.scalar_one_or_none()
        
        if exam and exam.status in ["started", "completed"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete design from exam with status '{exam.status}'. Only designs from draft or saved exams can be deleted."
            )

    try:
        # Remove associated question papers (DB delete)
        await db.execute(
            delete(QuestionPaperDetails).where(QuestionPaperDetails.qpd_design_id == design.id)
        )

        # Hard delete the design record
        await db.execute(
            delete(Design).where(Design.id == design.id)
        )

        await db.commit()
        return f"Exam with code '{exam_code}' deleted successfully."
    except Exception as exc:
        await db.rollback()
        # optional: log.exception here
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete exam design")


async def delete_question_paper_by_code(
    db: AsyncSession,
    current_user: User,
    paper_code: str
) -> str:
    role_obj = await get_user_role(db, current_user.role_id)

    if not role_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")

    is_admin = role_obj.role_code in ["super_admin", "admin", "admin_user"]

    # Fetch the question paper
    stmt = select(QuestionPaperDetails).where(QuestionPaperDetails.qpd_paper_id == paper_code)
    if not is_admin:
        stmt = stmt.where(QuestionPaperDetails.created_by == current_user.id)

    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()

    if not paper:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question paper not found or you do not have permission to delete it"
        )

    try:
        # Hard delete the paper row
        await db.delete(paper)
        await db.commit()
        return f"Question paper with code '{paper_code}' deleted successfully."
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete question paper")
