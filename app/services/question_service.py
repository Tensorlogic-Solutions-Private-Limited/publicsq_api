from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import joinedload
from collections import defaultdict
from fastapi import HTTPException, status
from typing import Optional, Dict, Any, List
import math
from app.models.master import Taxonomy, Subject, Medium, Questions, Question_Type, Question_Format
from app.models.user import User
from app.schemas.questions import (
    ChapterCountResponse, ExamQuestionsResponse, ExamQuestionResponse, ExamQuestionGroupResponse,
    ExamQuestionsV3Response, TextQuestionResponse,
    TextQuestionText, TextQuestionOption
)
from app.services.scope_service import ScopeFilterService
from app.services.code_generation_service import code_generation_service
from app.middleware.rbac import rbac_middleware





async def _build_organizational_query(
    subject_code: str,
    board_id: int,
    state_id: int,
    medium_code: str,
    standard: str,
    db,
    scope_filter: Optional[Dict[str, Any]] = None,
    question_text: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Shared query logic for organizational filtering (used by both v2 and v3)."""
    # Build base query without pagination for count
    base_stmt = (
        select(Questions)
        .join(Taxonomy, Questions.qmt_taxonomy_id == Taxonomy.id)
        .join(Question_Type, Questions.qmt_type_id == Question_Type.id)
        .join(Question_Format, Questions.qmt_format_id == Question_Format.id)
        .join(Subject, Questions.subject_id == Subject.id)
        .join(Medium, Questions.medium_id == Medium.id)
        .where(Subject.smt_subject_code == subject_code)
        .where(Questions.board_id == board_id)
        .where(Questions.state_id == state_id)
        .where(Medium.mmt_medium_code == medium_code)
        .where(Taxonomy.stm_standard == standard)
        .where(Questions.status != "deleted")
    )
    
    # Add optional text search filter
    if question_text:
        base_stmt = base_stmt.where(Questions.qmt_question_text.ilike(f"%{question_text}%"))
    
    # Apply hierarchical scope filtering
    if scope_filter:
        scope_conditions = []
        if "organization_id" in scope_filter:
            scope_conditions.append(Questions.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            scope_conditions.append(Questions.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            scope_conditions.append(Questions.school_id == scope_filter["school_id"])
        
        if scope_conditions:
            base_stmt = base_stmt.where(or_(*scope_conditions))
    
    # Get total count before pagination
    count_query = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar()
    
    # Add options for relationships, ordering, and pagination
    stmt = base_stmt.options(
        joinedload(Questions.taxonomy), 
        joinedload(Questions.type),
        joinedload(Questions.format),
        joinedload(Questions.organization),
        joinedload(Questions.block),
        joinedload(Questions.school)
    ).order_by(Questions.created_at.desc()).offset(offset).limit(limit)
    
    result = await db.execute(stmt)
    questions = result.scalars().all()
    
    return questions, total_count


async def lookup_subject_id_by_code(subject_code: str, db) -> int:
    """
    Look up subject ID by subject code.
    
    Args:
        subject_code: Subject code to look up
        db: Database session
        
    Returns:
        int: Subject ID
        
    Raises:
        HTTPException: If subject is not found
    """
    stmt = select(Subject).where(Subject.smt_subject_code == subject_code)
    result = await db.execute(stmt)
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject not found for code: {subject_code}. Please ensure the subject code is valid."
        )
    
    return subject.id


async def lookup_subject_id_by_code_and_class(subject_code: str, standard: str, db) -> int:
    """
    Look up subject ID by subject code and class/standard.
    This ensures the subject exists for the specified class.
    
    Args:
        subject_code: Subject code to look up
        standard: Class/standard to validate
        db: Database session
        
    Returns:
        int: Subject ID
        
    Raises:
        HTTPException: If subject is not found for the specified class
    """
    stmt = select(Subject).where(
        and_(
            Subject.smt_subject_code == subject_code,
            Subject.smt_standard == standard
        )
    )
    result = await db.execute(stmt)
    subject = result.scalar_one_or_none()
    
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject code '{subject_code}' not found for class '{standard}'. Please ensure the subject exists for this class or create it via bulk upload first."
        )
    
    return subject.id


async def lookup_medium_id_by_code(medium_code: str, db) -> int:
    """
    Look up medium ID by medium code.
    
    Args:
        medium_code: Medium code to look up
        db: Database session
        
    Returns:
        int: Medium ID
        
    Raises:
        HTTPException: If medium is not found
    """
    stmt = select(Medium).where(Medium.mmt_medium_code == medium_code)
    result = await db.execute(stmt)
    medium = result.scalar_one_or_none()
    
    if not medium:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Medium not found for code: {medium_code}. Please ensure the medium code is valid."
        )
    
    return medium.id


async def lookup_format_id_by_code(format_code: str, db) -> int:
    """Look up format ID by format code."""
    from app.models.master import Question_Format
    
    stmt = select(Question_Format).where(Question_Format.qfm_format_code == format_code)
    result = await db.execute(stmt)
    format_obj = result.scalar_one_or_none()
    
    if not format_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format not found for code: {format_code}. Please ensure the format code is valid."
        )
    
    return format_obj.id


async def lookup_type_id_by_code(type_code: str, db) -> int:
    """Look up type ID by type code."""
    from app.models.master import Question_Type
    
    stmt = select(Question_Type).where(Question_Type.qtm_type_code == type_code)
    result = await db.execute(stmt)
    type_obj = result.scalar_one_or_none()
    
    if not type_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Question type not found for code: {type_code}. Please ensure the type code is valid."
        )
    
    return type_obj.id


async def get_or_create_taxonomy(
    chapter_code: str,
    topic_code: Optional[str],
    subtopic_code: Optional[str],
    subject_id: int,
    medium_id: int,
    standard: str,
    board_id: int,
    state_id: int,
    db,
    user_id: int
) -> tuple[str, int]:
    """
    Get existing taxonomy or create a new one if it doesn't exist.
    
    Args:
        chapter_code: Chapter code (mandatory)
        topic_code: Topic code (optional)
        subtopic_code: Subtopic code (optional)
        subject_id: Subject ID
        medium_id: Medium ID
        standard: Class/standard (e.g., '10')
        board_id: Board ID
        state_id: State ID
        db: Database session
        user_id: User ID for audit fields
        
    Returns:
        tuple: (taxonomy_code, taxonomy_id)
        
    Raises:
        HTTPException: If chapter/topic codes are invalid (don't exist in any taxonomy)
    """
    # Import the code generation service
    from app.services.code_generation_service import code_generation_service
    
    # Generate taxonomy code with all context fields
    taxonomy_code = code_generation_service.generate_taxonomy_code(
        chapter_code=chapter_code,
        topic_code=topic_code or "",
        subtopic_code=subtopic_code or "",
        board_id=board_id,
        state_id=state_id,
        medium_id=medium_id,
        standard=standard,
        subject_id=subject_id
    )
    
    # Try to find existing taxonomy by the generated taxonomy code
    stmt = select(Taxonomy).where(Taxonomy.stm_taxonomy_code == taxonomy_code)
    result = await db.execute(stmt)
    existing_taxonomy = result.scalar_one_or_none()
    
    if existing_taxonomy:
        return taxonomy_code, existing_taxonomy.id
    
    # Taxonomy doesn't exist, create new one
    # First try to find existing names from other taxonomies with same codes
    chapter_name = f"Chapter_{chapter_code}"
    topic_name = ""
    subtopic_name = subtopic_code or ""
    
    # Look up existing chapter name
    chapter_lookup = await db.execute(
        select(Taxonomy.stm_chapter_name)
        .where(
            Taxonomy.stm_chapter_code == chapter_code,
            Taxonomy.stm_subject_id == subject_id,
            Taxonomy.stm_medium_id == medium_id,
            Taxonomy.stm_standard == standard,
            Taxonomy.board_id == board_id,
            Taxonomy.state_id == state_id
        )
        .limit(1)
    )
    existing_chapter = chapter_lookup.scalar_one_or_none()
    if existing_chapter:
        chapter_name = existing_chapter
    
    # Look up existing topic name if topic_code is provided
    if topic_code:
        topic_lookup = await db.execute(
            select(Taxonomy.stm_topic_name)
            .where(
                Taxonomy.stm_topic_code == topic_code,
                Taxonomy.stm_subject_id == subject_id,
                Taxonomy.stm_medium_id == medium_id,
                Taxonomy.stm_standard == standard,
                Taxonomy.board_id == board_id,
                Taxonomy.state_id == state_id
            )
            .limit(1)
        )
        existing_topic = topic_lookup.scalar_one_or_none()
        if existing_topic:
            topic_name = existing_topic
        else:
            topic_name = f"Topic_{topic_code}"
    
    # Look up existing subtopic name if subtopic_code is provided
    if subtopic_code:
        subtopic_lookup = await db.execute(
            select(Taxonomy.stm_subtopic_name)
            .where(
                Taxonomy.stm_subtopic_code == subtopic_code,
                Taxonomy.stm_subject_id == subject_id,
                Taxonomy.stm_medium_id == medium_id,
                Taxonomy.stm_standard == standard,
                Taxonomy.board_id == board_id,
                Taxonomy.state_id == state_id
            )
            .limit(1)
        )
        existing_subtopic = subtopic_lookup.scalar_one_or_none()
        if existing_subtopic:
            subtopic_name = existing_subtopic
    
    # Create new taxonomy entry
    new_taxonomy = Taxonomy(
        stm_taxonomy_code=taxonomy_code,
        stm_subject_id=subject_id,
        stm_medium_id=medium_id,
        stm_standard=standard,
        stm_chapter_code=chapter_code,
        stm_chapter_name=chapter_name,
        stm_topic_code=topic_code or "",
        stm_topic_name=topic_name,
        stm_subtopic_code=subtopic_code or "",
        stm_subtopic_name=subtopic_name,
        board_id=board_id,
        state_id=state_id,
        created_by=user_id,
        updated_by=user_id
    )
    
    db.add(new_taxonomy)
    await db.flush()  # Get the ID without committing
    await db.refresh(new_taxonomy)
    
    return taxonomy_code, new_taxonomy.id


async def get_chapter_topic_question_counts(
    standard: str, 
    medium_code: str, 
    subject_code: str, 
    db, 
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None,
    board_id: Optional[int] = None,
    state_id: Optional[int] = None
):
    """Get chapter and topic question counts with hierarchical scope filtering."""
    
    # Base query for chapters with scope filtering (includes empty taxonomies)
    chapter_stmt = (
        select(
            Taxonomy.stm_chapter_code.label("chapter_code"),
            func.max(Taxonomy.stm_chapter_name).label("chapter_name"),
            func.count(Questions.id).label("chapter_question_count")
        )
        .outerjoin(Questions, Questions.qmt_taxonomy_id == Taxonomy.id)
        .join(Subject, Taxonomy.stm_subject_id == Subject.id)
        .join(Medium, Taxonomy.stm_medium_id == Medium.id)
        .where(
            Taxonomy.stm_standard == standard,
            Subject.smt_subject_code == subject_code,
            Medium.mmt_medium_code == medium_code,
        )
    )
    
    # Add board_id and state_id filtering on Taxonomy table if provided
    if board_id is not None:
        chapter_stmt = chapter_stmt.where(Taxonomy.board_id == board_id)
    
    if state_id is not None:
        chapter_stmt = chapter_stmt.where(Taxonomy.state_id == state_id)
    
    # Add board_id and state_id filtering on Questions table if provided (to match exam creation logic)
    if board_id is not None:
        chapter_stmt = chapter_stmt.where(
            or_(
                Questions.board_id == board_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    if state_id is not None:
        chapter_stmt = chapter_stmt.where(
            or_(
                Questions.state_id == state_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    # Filter out questions in review state
    chapter_stmt = chapter_stmt.where(
        or_(
            Questions.status != "review",
            Questions.id.is_(None)  # Include taxonomies without questions
        )
    )
    
    chapter_stmt = chapter_stmt.group_by(Taxonomy.stm_chapter_code).order_by(Taxonomy.stm_chapter_code)
    chapter_result = await db.execute(chapter_stmt)
    chapter_rows = chapter_result.all()

    # Base query for topics with scope filtering (includes empty taxonomies, excludes empty topic codes)
    topic_stmt = (
        select(
            Taxonomy.stm_chapter_code.label("chapter_code"),
            Taxonomy.stm_topic_code.label("topic_code"),
            func.max(Taxonomy.stm_topic_name).label("topic_name"),
            func.count(Questions.id).label("topic_question_count")
        )
        .outerjoin(Questions, Questions.qmt_taxonomy_id == Taxonomy.id)
        .join(Subject, Taxonomy.stm_subject_id == Subject.id)
        .join(Medium, Taxonomy.stm_medium_id == Medium.id)
        .where(
            Taxonomy.stm_standard == standard,
            Subject.smt_subject_code == subject_code,
            Medium.mmt_medium_code == medium_code,
            Taxonomy.stm_topic_code != ""  # Only include taxonomies with topic codes
        )
    )
    
    # Add board_id and state_id filtering on Taxonomy table if provided
    if board_id is not None:
        topic_stmt = topic_stmt.where(Taxonomy.board_id == board_id)
    
    if state_id is not None:
        topic_stmt = topic_stmt.where(Taxonomy.state_id == state_id)
    
    # Add board_id and state_id filtering on Questions table if provided (to match exam creation logic)
    if board_id is not None:
        topic_stmt = topic_stmt.where(
            or_(
                Questions.board_id == board_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    if state_id is not None:
        topic_stmt = topic_stmt.where(
            or_(
                Questions.state_id == state_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    # Filter out questions in review state
    topic_stmt = topic_stmt.where(
        or_(
            Questions.status != "review",
            Questions.id.is_(None)  # Include taxonomies without questions
        )
    )
    
    topic_stmt = topic_stmt.group_by(
        Taxonomy.stm_chapter_code,
        Taxonomy.stm_topic_code
    ).order_by(
        Taxonomy.stm_chapter_code,
        Taxonomy.stm_topic_code
    )
    topic_result = await db.execute(topic_stmt)
    topic_rows = topic_result.all()

    # Base query for subtopics with scope filtering (includes empty taxonomies)
    subtopic_stmt = (
        select(
            Taxonomy.stm_chapter_code.label("chapter_code"),
            Taxonomy.stm_topic_code.label("topic_code"),
            Taxonomy.stm_subtopic_code.label("subtopic_code"),
            func.max(Taxonomy.stm_subtopic_name).label("subtopic_name"),
            func.count(Questions.id).label("subtopic_question_count")
        )
        .outerjoin(Questions, Questions.qmt_taxonomy_id == Taxonomy.id)
        .join(Subject, Taxonomy.stm_subject_id == Subject.id)
        .join(Medium, Taxonomy.stm_medium_id == Medium.id)
        .where(
            Taxonomy.stm_standard == standard,
            Subject.smt_subject_code == subject_code,
            Medium.mmt_medium_code == medium_code,
            Taxonomy.stm_subtopic_code != ""  # Only include taxonomies with subtopic codes
        )
    )
    
    # Add board_id and state_id filtering on Taxonomy table if provided
    if board_id is not None:
        subtopic_stmt = subtopic_stmt.where(Taxonomy.board_id == board_id)
    
    if state_id is not None:
        subtopic_stmt = subtopic_stmt.where(Taxonomy.state_id == state_id)
    
    # Add board_id and state_id filtering on Questions table if provided (to match exam creation logic)
    if board_id is not None:
        subtopic_stmt = subtopic_stmt.where(
            or_(
                Questions.board_id == board_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    if state_id is not None:
        subtopic_stmt = subtopic_stmt.where(
            or_(
                Questions.state_id == state_id,
                Questions.id.is_(None)  # Include taxonomies without questions
            )
        )
    
    # Filter out questions in review state
    subtopic_stmt = subtopic_stmt.where(
        or_(
            Questions.status != "review",
            Questions.id.is_(None)  # Include taxonomies without questions
        )
    )
    
    subtopic_stmt = subtopic_stmt.group_by(
        Taxonomy.stm_chapter_code,
        Taxonomy.stm_topic_code,
        Taxonomy.stm_subtopic_code
    ).order_by(
        Taxonomy.stm_chapter_code,
        Taxonomy.stm_topic_code,
        Taxonomy.stm_subtopic_code
    )
    subtopic_result = await db.execute(subtopic_stmt)
    subtopic_rows = subtopic_result.all()

    # Build subtopic mapping: (chapter_code, topic_code) -> [subtopics]
    topic_to_subtopics = defaultdict(list)
    for subtopic in subtopic_rows:
        topic_key = (subtopic.chapter_code, subtopic.topic_code)
        topic_to_subtopics[topic_key].append({
            "code": subtopic.subtopic_code,
            "name": subtopic.subtopic_name,
            "question_count": subtopic.subtopic_question_count
        })

    chapter_to_topics = defaultdict(list)
    for topic in topic_rows:
        topic_key = (topic.chapter_code, topic.topic_code)
        chapter_to_topics[topic.chapter_code].append({
            "code": topic.topic_code,
            "name": topic.topic_name,
            "question_count": topic.topic_question_count,
            "subtopics": topic_to_subtopics.get(topic_key, [])
        })

    final_chapters = []
    for chapter in chapter_rows:
        final_chapters.append({
            "code": chapter.chapter_code,
            "name": chapter.chapter_name,
            "question_count": chapter.chapter_question_count,
            "topics": chapter_to_topics.get(chapter.chapter_code, [])
        })

    return ChapterCountResponse(data=final_chapters)


async def get_questions_by_filters(
    filter_type: str, 
    codes: str, 
    db, 
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None,
    subject_id: Optional[int] = None,
    board_id: Optional[int] = None,
    state_id: Optional[int] = None,
    medium_id: Optional[int] = None,
    standard: Optional[str] = None
):
    """Get questions by filters with hierarchical scope filtering."""
    if filter_type not in ["chapter", "topic"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid type. Must be 'chapter' or 'topic'.")

    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not code_list:
        return ExamQuestionsResponse(qn_groups=[], qns=[])

    filter_column = Taxonomy.stm_chapter_code if filter_type == "chapter" else Taxonomy.stm_topic_code

    stmt = (
        select(Questions)
        .join(Taxonomy, Questions.qmt_taxonomy_id == Taxonomy.id)
        .join(Question_Type, Questions.qmt_type_id == Question_Type.id)
        .join(Question_Format, Questions.qmt_format_id == Question_Format.id)
        .where(filter_column.in_(code_list))
        .where(Questions.status != "deleted")
        .where(Questions.status != "review")
        .options(
            joinedload(Questions.taxonomy), 
            joinedload(Questions.type),
            joinedload(Questions.format),
            joinedload(Questions.organization),
            joinedload(Questions.block),
            joinedload(Questions.school)
        )
    )
    
    # Apply additional filters via taxonomy joins
    if subject_id is not None:
        stmt = stmt.where(Taxonomy.stm_subject_id == subject_id)
    
    if board_id is not None:
        stmt = stmt.where(Taxonomy.board_id == board_id)
    
    if state_id is not None:
        stmt = stmt.where(Questions.state_id == state_id)
    
    if medium_id is not None:
        stmt = stmt.where(Taxonomy.stm_medium_id == medium_id)
    
    if standard is not None:
        stmt = stmt.where(Taxonomy.stm_standard == standard)
    
    # Apply hierarchical scope filtering
    if scope_filter:
        scope_conditions = []
        if "organization_id" in scope_filter:
            scope_conditions.append(Questions.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            scope_conditions.append(Questions.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            scope_conditions.append(Questions.school_id == scope_filter["school_id"])
        
        if scope_conditions:
            stmt = stmt.where(or_(*scope_conditions))
    
    result = await db.execute(stmt)
    questions = result.scalars().all()

    qns_list = []
    type_codes_set = set()
    type_names_set = set()

    for q in questions:
        taxonomy = q.taxonomy
        grp_code = taxonomy.stm_chapter_code if filter_type == "chapter" else taxonomy.stm_topic_code
        grp_name = taxonomy.stm_chapter_name if filter_type == "chapter" else taxonomy.stm_topic_name
        type_codes_set.add(grp_code)
        type_names_set.add(grp_name)

        qns_list.append(ExamQuestionResponse(
            code=q.qmt_question_code,
            type=q.type.qtm_type_name,
            marks=q.qmt_marks,
            difficulty_level="Medium",
            grp_type=filter_type,
            grp_type_name=grp_name,
            grp_type_code=grp_code,
            text=q.qmt_question_text,
            option1=q.qmt_option1,
            option2=q.qmt_option2,
            option3=q.qmt_option3,
            option4=q.qmt_option4,
            correct_answer=q.qmt_correct_answer,
            format_code=q.format.qfm_format_code if q.format else None,
            type_code=q.type.qtm_type_code if q.type else None
        ))

    qn_groups = [ExamQuestionGroupResponse(
        type=filter_type,
        type_codes=list(type_codes_set),
        type_names=list(type_names_set),
        no_of_qns=len(qns_list)
    )]

    return ExamQuestionsResponse(
        qn_groups=qn_groups,
        qns=qns_list,
        total=len(qns_list),
        page=1,
        page_size=len(qns_list)
    )


async def get_questions_by_organizational_filters(
    subject_code: str,
    board_id: int,
    state_id: int,
    medium_code: str,
    standard: str,
    db, 
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None,
    question_text: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get questions filtered by organizational criteria with optional text search and pagination."""
    
    # Use shared query logic - now returns tuple (questions, total_count)
    questions, total_count = await _build_organizational_query(
        subject_code, board_id, state_id, medium_code, standard, db, 
        scope_filter, question_text, limit, offset
    )

    qns_list = []
    type_codes_set = set()
    type_names_set = set()

    for q in questions:
        taxonomy = q.taxonomy
        # For organizational filtering, we'll group by chapter by default
        grp_code = taxonomy.stm_chapter_code
        grp_name = taxonomy.stm_chapter_name
        type_codes_set.add(grp_code)
        type_names_set.add(grp_name)

        qns_list.append(ExamQuestionResponse(
            code=q.qmt_question_code,
            type=q.type.qtm_type_name,
            marks=q.qmt_marks,
            difficulty_level="Medium",
            grp_type="chapter",
            grp_type_name=grp_name,
            grp_type_code=grp_code,
            text=q.qmt_question_text,
            option1=q.qmt_option1,
            option2=q.qmt_option2,
            option3=q.qmt_option3,
            option4=q.qmt_option4,
            correct_answer=q.qmt_correct_answer,
            format_code=q.format.qfm_format_code if q.format else None,
            type_code=q.type.qtm_type_code if q.type else None
        ))

    qn_groups = [ExamQuestionGroupResponse(
        type="chapter",
        type_codes=list(type_codes_set),
        type_names=list(type_names_set),
        no_of_qns=len(qns_list)
    )]

    # Calculate pagination info
    page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = math.ceil(total_count / limit) if total_count > 0 and limit > 0 else 1
    
    return ExamQuestionsResponse(
        qn_groups=qn_groups,
        qns=qns_list,
        total=total_count,
        page=page,
        page_size=limit,
        total_pages=total_pages,
        grandTotal=total_count
    )


async def get_questions_by_organizational_filters_v3(
    subject_code: str,
    board_id: int,
    state_id: int,
    medium_code: str,
    standard: str,
    db, 
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None,
    question_text: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get questions filtered by organizational criteria with v3 unified response format."""
    
    # Use shared query logic (same as v2) - now returns tuple (questions, total_count)
    questions, total_count = await _build_organizational_query(
        subject_code, board_id, state_id, medium_code, standard, db, 
        scope_filter, question_text, limit, offset
    )

    qns_list = []
    type_codes_set = set()
    type_names_set = set()

    for q in questions:
        taxonomy = q.taxonomy
        # For organizational filtering, we'll group by chapter by default
        grp_code = taxonomy.stm_chapter_code
        grp_name = taxonomy.stm_chapter_name
        type_codes_set.add(grp_code)
        type_names_set.add(grp_name)
        
        # Use text question builder
        question_response = TextQuestionResponse(
            code=q.qmt_question_code,
            type=q.type.qtm_type_name,
            marks=q.qmt_marks,
            difficulty_level="Medium",
            grp_type="chapter",
            grp_type_name=grp_name,
            grp_type_code=grp_code,
            format_code=q.format.qfm_format_code if q.format else None,
            type_code=q.type.qtm_type_code if q.type else None,
            correct_answer=q.qmt_correct_answer,
            qn=TextQuestionText(text=q.qmt_question_text),
            option1=TextQuestionOption(text=q.qmt_option1),
            option2=TextQuestionOption(text=q.qmt_option2),
            option3=TextQuestionOption(text=q.qmt_option3),
            option4=TextQuestionOption(text=q.qmt_option4)
        )
        
        qns_list.append(question_response)

    qn_groups = [ExamQuestionGroupResponse(
        type="chapter",
        type_codes=list(type_codes_set),
        type_names=list(type_names_set),
        no_of_qns=len(qns_list)
    )]

    # Calculate pagination info
    page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = math.ceil(total_count / limit) if total_count > 0 and limit > 0 else 1
    
    return ExamQuestionsV3Response(
        qn_groups=qn_groups,
        qns=qns_list,
        total=total_count,
        page=page,
        page_size=limit,
        total_pages=total_pages,
        grandTotal=total_count
    )





async def upload_question(
    question_data: Dict[str, Any],
    db,
    user: User
) -> Questions:
    """Upload a new question with organizational context."""
    
    # Load user context to get organizational scope
    user_context = await rbac_middleware.load_user_context(db, user)
    
    # Generate question ID and code automatically
    question_id = await code_generation_service.get_next_question_id(db)
    question_code = code_generation_service.generate_question_code(question_id)
    
    # Look up IDs from codes
    subject_id = await lookup_subject_id_by_code_and_class(question_data["subject_code"], question_data["standard"], db)
    medium_id = await lookup_medium_id_by_code(question_data["medium_code"], db)
    format_id = await lookup_format_id_by_code(question_data["format_code"], db)
    type_id = await lookup_type_id_by_code(question_data["type_code"], db)
    
    # Get or create taxonomy entry
    taxonomy_code, taxonomy_id = await get_or_create_taxonomy(
        chapter_code=question_data["chapter_code"],
        topic_code=question_data.get("topic_code"),
        subtopic_code=question_data.get("subtopic_code"),
        subject_id=subject_id,
        medium_id=medium_id,
        standard=question_data["standard"],
        board_id=question_data["board_id"],
        state_id=question_data["state_id"],
        db=db,
        user_id=user.id
    )
    
    # Create question with organizational context
    question = Questions(
        qmt_question_code=question_code,  # Auto-generated
        qmt_question_text=question_data["question_text"],
        qmt_option1=question_data["option1"],
        qmt_option2=question_data["option2"],
        qmt_option3=question_data["option3"],
        qmt_option4=question_data["option4"],
        qmt_correct_answer=question_data["correct_answer"],
        qmt_marks=question_data.get("marks", 1),
        qmt_format_id=format_id,
        qmt_type_id=type_id,
        qmt_taxonomy_id=taxonomy_id,
        qmt_taxonomy_code=taxonomy_code,
        qmt_is_active=True,
        status=question_data.get("status", "Approved"),  # Use provided status or default to Approved
        # Master data references - lookup IDs from codes
        subject_id=subject_id,
        medium_id=medium_id,
        board_id=question_data["board_id"],
        state_id=question_data["state_id"],
        cognitive_learning_id=question_data["cognitive_learning_id"],
        difficulty_id=question_data["difficulty_id"],
        # Associate with user's organizational context
        organization_id=user_context.organizational_scope["organization_id"],
        block_id=user_context.organizational_scope["block_id"],
        school_id=user_context.organizational_scope["school_id"],
        created_by=user.id
    )
    
    db.add(question)
    await db.flush()
    await db.refresh(question)
    
    # Load the question with all relationships for proper serialization
    stmt = (
        select(Questions)
        .options(
            joinedload(Questions.taxonomy),
            joinedload(Questions.type),
            joinedload(Questions.format),
            joinedload(Questions.subject),
            joinedload(Questions.medium),
            joinedload(Questions.board),
            joinedload(Questions.state),
            joinedload(Questions.cognitive_learning),
            joinedload(Questions.difficulty),
            joinedload(Questions.organization),
            joinedload(Questions.block),
            joinedload(Questions.school)
        )
        .where(Questions.id == question.id)
    )
    result = await db.execute(stmt)
    question_with_relationships = result.unique().scalar_one()
    
    return question_with_relationships


async def get_question_by_code(
    question_code: str,
    db,
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None
) -> Questions:
    """Get question by question code with scope validation."""
    
    # First, check if the question exists at all (without scope filtering)
    base_stmt = select(Questions).where(
        Questions.qmt_question_code == question_code,
        Questions.qmt_is_active == True
    )
    
    result = await db.execute(base_stmt)
    question_exists = result.scalar_one_or_none()
    
    if not question_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found for code: {question_code}"
        )
    
    # If question exists, now apply scope filtering with eager loading
    stmt = select(Questions).where(
        Questions.qmt_question_code == question_code,
        Questions.qmt_is_active == True
    ).options(
        joinedload(Questions.taxonomy),
        joinedload(Questions.type),
        joinedload(Questions.format),
        joinedload(Questions.subject),
        joinedload(Questions.medium),
        joinedload(Questions.board),
        joinedload(Questions.state),
        joinedload(Questions.cognitive_learning),
        joinedload(Questions.difficulty),
        joinedload(Questions.organization),
        joinedload(Questions.block),
        joinedload(Questions.school),
        joinedload(Questions.created_by_user),
        joinedload(Questions.updated_by_user)
    )
    
    # Apply scope filtering if provided
    if scope_filter:
        scope_service = ScopeFilterService()
        stmt = await scope_service.filter_questions_query(db, user, stmt)
    
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found for code: {question_code} or not accessible within your scope"
        )
    
    return question


async def update_question(
    question_code: str,
    question_data: Dict[str, Any],
    db,
    user: User
) -> Questions:
    """Update an existing question with ownership validation."""
    
    # Get the existing question by code
    stmt = select(Questions).where(Questions.qmt_question_code == question_code).options(
        joinedload(Questions.subject),
        joinedload(Questions.medium),
        joinedload(Questions.board),
        joinedload(Questions.state)
    )
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question not found for code: {question_code}"
        )
    
    # Handle code-based fields specially (subject, medium, format, type, taxonomy)
    code_fields = ["subject_code", "medium_code", "format_code", "type_code", "chapter_code", "topic_code", "subtopic_code"]
    
    # Handle subject and medium code lookups
    if "subject_code" in question_data:
        subject_id = await lookup_subject_id_by_code(question_data["subject_code"], db)
        question.subject_id = subject_id
        question_data.pop("subject_code", None)
        
    if "medium_code" in question_data:
        medium_id = await lookup_medium_id_by_code(question_data["medium_code"], db)
        question.medium_id = medium_id
        question_data.pop("medium_code", None)
    
    # Handle format and type code lookups
    if "format_code" in question_data:
        format_id = await lookup_format_id_by_code(question_data["format_code"], db)
        question.qmt_format_id = format_id
        question_data.pop("format_code", None)
        
    if "type_code" in question_data:
        type_id = await lookup_type_id_by_code(question_data["type_code"], db)
        question.qmt_type_id = type_id
        question_data.pop("type_code", None)
    
    # Handle taxonomy-related fields specially
    taxonomy_fields = ["chapter_code", "topic_code", "subtopic_code", "standard"]
    if any(field in question_data for field in taxonomy_fields):
        # If any taxonomy field is provided, construct new taxonomy code and lookup ID
        chapter_code = question_data.get("chapter_code")
        topic_code = question_data.get("topic_code")
        subtopic_code = question_data.get("subtopic_code")
        
        if chapter_code:  # chapter_code is mandatory for taxonomy construction
            taxonomy_code, taxonomy_id = await get_or_create_taxonomy(
                chapter_code=chapter_code,
                topic_code=topic_code,
                subtopic_code=subtopic_code,
                subject_id=question.subject_id,
                medium_id=question.medium_id,
                standard=question_data.get("standard"),
                board_id=question_data.get("board_id", question.board_id),
                state_id=question_data.get("state_id", question.state_id),
                db=db,
                user_id=user.id
            )
            question.qmt_taxonomy_id = taxonomy_id
            question.qmt_taxonomy_code = taxonomy_code
        
        # Remove taxonomy fields from question_data to avoid setting them directly
        for field in taxonomy_fields:
            question_data.pop(field, None)
    
    # Map schema field names to database field names
    field_mapping = {
        "question_text": "qmt_question_text",
        "option1": "qmt_option1",
        "option2": "qmt_option2",
        "option3": "qmt_option3",
        "option4": "qmt_option4",
        "correct_answer": "qmt_correct_answer",
        "marks": "qmt_marks"
    }
    
    # Update other question fields directly with mapped field names
    # Filter out fields that shouldn't be set directly
    excluded_fields = {"id", "created_at", "updated_at", "created_by", "updated_by", "qmt_question_code", "standard", "board_id", "state_id"}
    
    for field, value in question_data.items():
        if field in excluded_fields:
            continue
            
        db_field = field_mapping.get(field, field)
        if hasattr(question, db_field):
            setattr(question, db_field, value)
    
    question.updated_by = user.id
    
    await db.flush()
    
    # Reload the question with all relationships to avoid lazy loading issues
    stmt = select(Questions).where(Questions.id == question.id).options(
        joinedload(Questions.taxonomy),
        joinedload(Questions.type),
        joinedload(Questions.format),
        joinedload(Questions.subject),
        joinedload(Questions.medium),
        joinedload(Questions.board),
        joinedload(Questions.state),
        joinedload(Questions.cognitive_learning),
        joinedload(Questions.difficulty),
        joinedload(Questions.organization),
        joinedload(Questions.block),
        joinedload(Questions.school)
    )
    
    result = await db.execute(stmt)
    refreshed_question = result.unique().scalar_one()
    
    return refreshed_question


async def delete_question(
    question_id: int,
    db,
    user: User
) -> bool:
    """Soft delete a question by setting status to 'deleted'."""
    
    # Get the existing question
    stmt = select(Questions).where(Questions.id == question_id)
    result = await db.execute(stmt)
    question = result.scalar_one_or_none()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found"
        )
    
    # Soft delete by setting status to 'deleted'
    question.status = "deleted"
    question.updated_by = user.id
    
    await db.flush()
    
    return True


async def get_question_by_id(
    question_id: int,
    db,
    user: User,
    scope_filter: Optional[Dict[str, Any]] = None
) -> Optional[Questions]:
    """Get a question by ID with scope filtering."""
    
    stmt = (
        select(Questions)
        .where(Questions.id == question_id)
        .options(
            joinedload(Questions.taxonomy),
            joinedload(Questions.type),
            joinedload(Questions.format),
            joinedload(Questions.subject),
            joinedload(Questions.medium),
            joinedload(Questions.board),
            joinedload(Questions.state),
            joinedload(Questions.cognitive_learning),
            joinedload(Questions.difficulty),
            joinedload(Questions.organization),
            joinedload(Questions.block),
            joinedload(Questions.school)
        )
    )
    
    # Apply hierarchical scope filtering
    if scope_filter:
        scope_conditions = []
        if "organization_id" in scope_filter:
            scope_conditions.append(Questions.organization_id == scope_filter["organization_id"])
        elif "block_id" in scope_filter:
            scope_conditions.append(Questions.block_id == scope_filter["block_id"])
        elif "school_id" in scope_filter:
            scope_conditions.append(Questions.school_id == scope_filter["school_id"])
        
        if scope_conditions:
            stmt = stmt.where(or_(*scope_conditions))
    
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


