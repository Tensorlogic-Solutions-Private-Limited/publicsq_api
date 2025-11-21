"""
Exam service for managing exam containers that group multiple designs.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.master import Design
from app.utils.get_user_role import get_user_role


async def generate_unique_exam_code(db: AsyncSession) -> str:
    """
    Generate a unique exam code in format EXAMXXXXX.
    
    Args:
        db: Database session
        
    Returns:
        str: Unique exam code (e.g., EXAM00001)
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    
    # Get the last exam code
    result = await db.execute(
        select(ExamMaster.exam_code)
        .where(ExamMaster.exam_code.like("EXAM%"))
        .order_by(ExamMaster.exam_code.desc())
        .limit(1)
    )
    last_code = result.scalar()
    
    # Generate new code
    new_number = int(last_code[4:]) + 1 if last_code and last_code[4:].isdigit() else 1
    candidate_code = f"EXAM{new_number:05d}"
    
    # Verify uniqueness
    exists = await db.scalar(select(ExamMaster.id).where(ExamMaster.exam_code == candidate_code))
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generated exam code already exists. Try again."
        )
    
    return candidate_code


async def create_exam(
    db: AsyncSession,
    exam_name: str,
    current_user,
    total_time: Optional[int] = None,
    exam_mode: Optional[str] = None,
    organization_id: Optional[str] = None,
    block_id: Optional[str] = None,
    school_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new exam container.
    
    Args:
        db: Database session
        exam_name: Name of the exam
        current_user: Current authenticated user
        total_time: Total exam duration in minutes (optional)
        exam_mode: Exam mode (optional)
        organization_id: Organization UUID (optional, defaults to user's organization)
        block_id: Block UUID (optional, defaults to user's block)
        school_id: School UUID (optional, defaults to user's school)
        
    Returns:
        Dict containing exam details with empty designs array
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    from app.models.organization import Organization, Block, School
    
    # Generate unique exam code
    exam_code = await generate_unique_exam_code(db)
    
    # Convert UUIDs to integer IDs if provided
    final_organization_id = current_user.organization_id
    final_block_id = current_user.block_id
    final_school_id = current_user.school_id
    
    if organization_id is not None:
        org = await db.scalar(select(Organization.id).where(Organization.uuid == organization_id))
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with UUID {organization_id} not found"
            )
        final_organization_id = org
    
    if block_id is not None:
        block = await db.scalar(select(Block.id).where(Block.uuid == block_id))
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Block with UUID {block_id} not found"
            )
        final_block_id = block
    
    if school_id is not None:
        school = await db.scalar(select(School.id).where(School.uuid == school_id))
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"School with UUID {school_id} not found"
            )
        final_school_id = school
    
    # Create exam record
    new_exam = ExamMaster(
        exam_code=exam_code,
        exam_name=exam_name,
        total_time=total_time,
        exam_mode=exam_mode,
        status="draft",
        organization_id=final_organization_id,
        block_id=final_block_id,
        school_id=final_school_id,
        created_by=current_user.id,
        updated_by=current_user.id,
        is_active=True
    )
    
    try:
        db.add(new_exam)
        await db.commit()
        await db.refresh(new_exam)
    except Exception as e:
        await db.rollback()
        from app.utils.database_error_handler import DatabaseErrorHandler
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        
        if isinstance(e, (IntegrityError, SQLAlchemyError)):
            DatabaseErrorHandler.handle_sqlalchemy_error(
                e,
                table_name="exam_master",
                operation="create",
                context={"exam_code": exam_code, "exam_name": exam_name}
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create exam"
        )
    
    # Fetch the exam with relationships to get UUIDs
    await db.refresh(new_exam, ["organization", "block", "school"])
    
    # Return exam details with empty designs array
    return {
        "exam_code": new_exam.exam_code,
        "exam_name": new_exam.exam_name,
        "total_time": new_exam.total_time,
        "total_questions": 0,  # Sum of total_questions from all designs (0 for new exam)
        "exam_mode": new_exam.exam_mode,
        "status": new_exam.status,
        "organization_id": str(new_exam.organization.uuid) if new_exam.organization else None,
        "block_id": str(new_exam.block.uuid) if new_exam.block else None,
        "school_id": str(new_exam.school.uuid) if new_exam.school else None,
        "designs": [],
        "created_at": new_exam.created_at,
        "updated_at": new_exam.updated_at
    }



async def get_exam_by_code(
    db: AsyncSession,
    exam_code: str,
    current_user
) -> Dict[str, Any]:
    """
    Get exam container with all its designs.
    
    Args:
        db: Database session
        exam_code: Exam code to retrieve
        current_user: Current authenticated user
        
    Returns:
        Dict containing exam details with designs array
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    from app.services.qn_paper_service import get_design_by_exam_code
    
    # Get user role for permission checking
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    
    # Build query with hierarchical scope filtering
    stmt = select(ExamMaster).where(
        ExamMaster.exam_code == exam_code,
        ExamMaster.is_active == True
    )
    
    # Apply hierarchical scope filtering
    if role_obj.role_code == "teacher":
        # Teachers can only see their own exams within their school
        stmt = stmt.where(
            ExamMaster.created_by == current_user.id,
            ExamMaster.school_id == current_user.school_id
        )
    elif role_obj.role_code == "block_admin":
        # Block admins can see exams within their block
        stmt = stmt.where(ExamMaster.block_id == current_user.block_id)
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can see exams within their organization
        stmt = stmt.where(ExamMaster.organization_id == current_user.organization_id)
    # Super admins can see all exams (no additional filtering)
    
    result = await db.execute(stmt)
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found or access denied"
        )
    
    # Fetch all designs associated with this exam
    designs_stmt = select(Design).where(
        Design.exam_id == exam.id,
        Design.is_active == True
    )
    designs_result = await db.execute(designs_stmt)
    designs = designs_result.scalars().all()
    
    # Build design details using existing logic
    designs_list = []
    total_questions_sum = 0
    for design in designs:
        try:
            # Use existing get_design_by_exam_code logic to get full design details
            design_response = await get_design_by_exam_code(
                db=db,
                exam_code=design.dm_design_code,
                current_user=current_user
            )
            # Extract the design data from the response (remove wrapper)
            if "design" in design_response:
                design_data = design_response["design"]
                designs_list.append(design_data)
                # Sum up total_questions from each design
                if design_data.get("total_questions"):
                    total_questions_sum += design_data["total_questions"]
        except HTTPException:
            # Skip designs that user doesn't have access to
            continue
    
    # Fetch relationships to get UUIDs
    await db.refresh(exam, ["organization", "block", "school"])
    
    # Return exam with designs array
    return {
        "exam_code": exam.exam_code,
        "exam_name": exam.exam_name,
        "total_time": exam.total_time,
        "total_questions": total_questions_sum,  # Sum of total_questions from all designs
        "exam_mode": exam.exam_mode,
        "status": exam.status,
        "organization_id": str(exam.organization.uuid) if exam.organization else None,
        "block_id": str(exam.block.uuid) if exam.block else None,
        "school_id": str(exam.school.uuid) if exam.school else None,
        "designs": designs_list,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at
    }



async def list_exams(
    db: AsyncSession,
    current_user,
    page: int = 1,
    page_size: int = 10,
    status_filter: Optional[str] = None,
    standard: Optional[str] = None,
    subject_code: Optional[str] = None,
    exam_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    List exam containers with pagination and filters.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        page: Page number (1-indexed)
        page_size: Number of items per page
        status_filter: Filter by exam status (draft, started, completed)
        standard: Filter by standard (from designs)
        subject_code: Filter by subject code (from designs)
        exam_name: Search by exam name (partial match, case-insensitive)
        
    Returns:
        Dict containing paginated list of exams with design counts
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster, Subject
    
    # Get user role for permission checking
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    
    # Build base query with hierarchical scope filtering
    stmt = select(ExamMaster).where(ExamMaster.is_active == True)
    
    # Apply hierarchical scope filtering
    if role_obj.role_code == "teacher":
        # Teachers can only see their own exams within their school
        stmt = stmt.where(
            ExamMaster.created_by == current_user.id,
            ExamMaster.school_id == current_user.school_id
        )
    elif role_obj.role_code == "block_admin":
        # Block admins can see exams within their block
        stmt = stmt.where(ExamMaster.block_id == current_user.block_id)
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can see exams within their organization
        stmt = stmt.where(ExamMaster.organization_id == current_user.organization_id)
    # Super admins can see all exams (no additional filtering)
    
    # Apply status filter
    if status_filter:
        stmt = stmt.where(ExamMaster.status == status_filter)
    
    # Apply exam name filter (partial match, case-insensitive)
    if exam_name:
        stmt = stmt.where(ExamMaster.exam_name.ilike(f"%{exam_name}%"))
    
    # Apply standard and subject_code filters by joining with designs
    if standard or subject_code:
        stmt = stmt.join(Design, ExamMaster.id == Design.exam_id)
        
        if standard:
            stmt = stmt.where(Design.dm_standard == standard)
        
        if subject_code:
            stmt = stmt.join(Subject, Design.dm_subject_id == Subject.id)
            stmt = stmt.where(Subject.smt_subject_code == subject_code)
        
        # Ensure distinct results when joining
        stmt = stmt.distinct()
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar()
    
    # Apply pagination
    offset = (page - 1) * page_size
    stmt = stmt.order_by(ExamMaster.created_at.desc()).offset(offset).limit(page_size)
    
    # Execute query
    result = await db.execute(stmt)
    exams = result.scalars().all()
    
    # Build response with design counts and aggregated data
    exams_list = []
    for exam in exams:
        # Fetch all designs for this exam to aggregate data
        designs_stmt = select(Design).where(
            Design.exam_id == exam.id,
            Design.is_active == True
        ).options(joinedload(Design.subject))
        designs_result = await db.execute(designs_stmt)
        designs = designs_result.scalars().all()
        
        # Derive board_id, state_id, and standard from first design's first question
        board_id = None
        state_id = None
        standard = None
        
        if designs:
            # Get standard from first design
            standard = designs[0].dm_standard
            
            # Get board_id and state_id from first question of first design
            first_design = designs[0]
            if first_design.dm_total_question_codes:
                first_question_code = first_design.dm_total_question_codes[0] if isinstance(first_design.dm_total_question_codes, list) else None
                if first_question_code:
                    from app.models.master import Questions
                    question_result = await db.execute(
                        select(Questions.board_id, Questions.state_id)
                        .where(Questions.qmt_question_code == first_question_code)
                    )
                    question = question_result.first()
                    if question:
                        board_id = question.board_id
                        state_id = question.state_id
        
        # Get unique subjects from all designs
        subjects = list(set([design.subject.smt_subject_name for design in designs if design.subject])) if designs else []
        
        exams_list.append({
            "exam_code": exam.exam_code,
            "exam_name": exam.exam_name,
            "board_id": board_id,
            "state_id": state_id,
            "standard": standard,
            "status": exam.status,
            "total_designs": len(designs),
            "subjects": subjects,
            "created_at": exam.created_at
        })
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    
    return {
        "data": exams_list,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }



async def update_exam(
    db: AsyncSession,
    exam_code: str,
    current_user,
    exam_name: Optional[str] = None,
    total_time: Optional[int] = None,
    exam_mode: Optional[str] = None,
    status_update: Optional[str] = None,
    organization_id: Optional[str] = None,  # UUID string
    block_id: Optional[str] = None,  # UUID string
    school_id: Optional[str] = None  # UUID string
) -> Dict[str, Any]:
    """
    Update exam container details.
    
    Args:
        db: Database session
        exam_code: Exam code to update
        current_user: Current authenticated user
        exam_name: New exam name (optional)
        total_time: New total time (optional)
        exam_mode: New exam mode (optional)
        status_update: New status (optional)
        organization_id: New organization ID (optional, role-based)
        block_id: New block ID (optional, role-based)
        school_id: New school ID (optional, role-based)
        
    Returns:
        Dict containing updated exam details
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    
    # Get user role for permission checking
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    
    # Fetch exam
    stmt = select(ExamMaster).where(
        ExamMaster.exam_code == exam_code,
        ExamMaster.is_active == True
    )
    result = await db.execute(stmt)
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Check immutability rules:
    # - Completed exams are fully immutable
    # - Started exams can only have status changed to completed
    if exam.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update exam with status 'completed'. Completed exams are immutable."
        )
    
    if exam.status == "started":
        # For started exams, only allow status change to completed
        if status_update and status_update != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Started exams can only be changed to 'completed' status. No other updates allowed."
            )
        # If trying to update other fields (not just status), reject
        if exam_name is not None or total_time is not None or exam_mode is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update exam details once started. Only status can be changed to 'completed'."
            )
    
    # Apply role-based permissions for organizational field updates
    # Convert UUIDs to integer IDs
    from app.models.organization import Organization, Block, School
    
    if organization_id is not None:
        if role_obj.role_code != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_admin can update organization_id"
            )
        # Convert UUID to ID
        org = await db.scalar(select(Organization.id).where(Organization.uuid == organization_id))
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Organization with UUID {organization_id} not found"
            )
        exam.organization_id = org
    
    if block_id is not None:
        if role_obj.role_code not in ["super_admin", "admin", "admin_user"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_admin, admin, or admin_user can update block_id"
            )
        # Convert UUID to ID
        block = await db.scalar(select(Block.id).where(Block.uuid == block_id))
        if not block:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Block with UUID {block_id} not found"
            )
        exam.block_id = block
    
    if school_id is not None:
        if role_obj.role_code not in ["super_admin", "admin", "admin_user", "block_admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only super_admin, admin, admin_user, or block_admin can update school_id"
            )
        # Convert UUID to ID
        school = await db.scalar(select(School.id).where(School.uuid == school_id))
        if not school:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"School with UUID {school_id} not found"
            )
        exam.school_id = school
    
    # Update basic fields (partial updates supported)
    if exam_name is not None:
        exam.exam_name = exam_name
    
    if total_time is not None:
        exam.total_time = total_time
    
    if exam_mode is not None:
        exam.exam_mode = exam_mode
    
    # Handle status update and design synchronization
    if status_update is not None:
        # Validate status transition
        valid_statuses = ["draft", "saved", "started", "completed"]
        if status_update not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        
        exam.status = status_update
        
        # If status changes to "started", update all associated designs to status 2 (closed)
        if status_update == "started":
            designs_stmt = select(Design).where(
                Design.exam_id == exam.id,
                Design.is_active == True
            )
            designs_result = await db.execute(designs_stmt)
            designs = designs_result.scalars().all()
            
            for design in designs:
                design.dm_status = "closed"
    
    # Update audit fields
    exam.updated_by = current_user.id
    exam.updated_at = datetime.utcnow()
    
    try:
        await db.commit()
        await db.refresh(exam)
    except Exception as e:
        await db.rollback()
        from app.utils.database_error_handler import DatabaseErrorHandler
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        
        if isinstance(e, (IntegrityError, SQLAlchemyError)):
            DatabaseErrorHandler.handle_sqlalchemy_error(
                e,
                table_name="exam_master",
                operation="update",
                context={"exam_code": exam_code}
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update exam"
        )
    
    # Calculate total_questions from all designs
    designs_stmt = select(Design).where(
        Design.exam_id == exam.id,
        Design.is_active == True
    )
    designs_result = await db.execute(designs_stmt)
    designs = designs_result.scalars().all()
    
    total_questions_sum = sum(design.dm_total_questions or 0 for design in designs)
    
    # Fetch relationships to get UUIDs
    await db.refresh(exam, ["organization", "block", "school"])
    
    # Return updated exam details
    return {
        "exam_code": exam.exam_code,
        "exam_name": exam.exam_name,
        "total_time": exam.total_time,
        "total_questions": total_questions_sum,  # Sum of total_questions from all designs
        "exam_mode": exam.exam_mode,
        "status": exam.status,
        "organization_id": str(exam.organization.uuid) if exam.organization else None,
        "block_id": str(exam.block.uuid) if exam.block else None,
        "school_id": str(exam.school.uuid) if exam.school else None,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at
    }



async def delete_exam(
    db: AsyncSession,
    exam_code: str,
    current_user
) -> None:
    """
    Delete exam container (cascade deletes designs via FK).
    
    Args:
        db: Database session
        exam_code: Exam code to delete
        current_user: Current authenticated user
        
    Returns:
        None (204 No Content)
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    
    # Get user role for permission checking
    role_obj = await get_user_role(db, current_user.role_id)
    if not role_obj:
        raise HTTPException(status_code=404, detail="User role not found")
    
    # Fetch exam
    stmt = select(ExamMaster).where(
        ExamMaster.exam_code == exam_code,
        ExamMaster.is_active == True
    )
    result = await db.execute(stmt)
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Check hierarchical permissions for deletion
    if role_obj.role_code == "teacher":
        # Teachers can only delete their own exams within their school
        if exam.created_by != current_user.id or exam.school_id != current_user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this exam"
            )
    elif role_obj.role_code == "block_admin":
        # Block admins can delete exams within their block
        if exam.block_id != current_user.block_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this exam"
            )
    elif role_obj.role_code in ["admin", "admin_user"]:
        # Admin and Admin-User can delete exams within their organization
        if exam.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this exam"
            )
    # Super admins can delete all exams (no additional checks)
    
    try:
        # Delete exam (cascade deletes designs via FK constraint)
        await db.delete(exam)
        await db.commit()
    except Exception as e:
        await db.rollback()
        from app.utils.database_error_handler import DatabaseErrorHandler
        from sqlalchemy.exc import IntegrityError, SQLAlchemyError
        
        if isinstance(e, (IntegrityError, SQLAlchemyError)):
            DatabaseErrorHandler.handle_sqlalchemy_error(
                e,
                table_name="exam_master",
                operation="delete",
                context={"exam_code": exam_code}
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete exam"
        )



async def create_design_within_exam(
    db: AsyncSession,
    exam_code: str,
    payload,
    current_user,
    state_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a design within an exam container.
    
    Args:
        db: Database session
        exam_code: Exam code to add design to
        payload: Design creation payload
        current_user: Current authenticated user
        state_id: State ID for question filtering (optional)
        
    Returns:
        Dict containing design details (same response as v1/exams)
    """
    # Import here to avoid circular dependency
    from app.models.master import ExamMaster
    from app.services.design_service import create_exam_design_and_generate_qps
    
    # Validate exam exists
    stmt = select(ExamMaster).where(
        ExamMaster.exam_code == exam_code,
        ExamMaster.is_active == True
    )
    result = await db.execute(stmt)
    exam = result.scalar_one_or_none()
    
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with code '{exam_code}' not found"
        )
    
    # Force status to 1 (draft) for designs within exams
    # Design status is controlled by exam status, not user input
    payload.status = 1
    
    # Call existing create_exam_design_and_generate_qps() from design_service
    design_response = await create_exam_design_and_generate_qps(
        payload=payload,
        current_user=current_user,
        db=db,
        state_id=state_id,
        exam_id=exam.id  # Pass exam_id for uniqueness check within exam
    )
    
    # Extract design code from response
    design_code = design_response.get("data", {}).get("exam_code")
    
    if not design_code:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create design - no design code returned"
        )
    
    # Set design_master.exam_id to exam.id
    design_stmt = select(Design).where(Design.dm_design_code == design_code)
    design_result = await db.execute(design_stmt)
    design = design_result.scalar_one_or_none()
    
    if design:
        design.exam_id = exam.id
        try:
            await db.commit()
            await db.refresh(design)
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to link design to exam: {str(e)}"
            )
    
    # Return same response as v1/exams
    return design_response




