from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any

from app.models.user import User, TeacherClass
from app.models.master import Medium, Subject
from app.schemas.teacher_academic import TeacherAcademicCreate, TeacherAcademicResponse, TeacherAcademicListResponse
from app.services.scope_service import ScopeFilterService


async def create_teacher_academic_assignment(
    db: AsyncSession,
    user_uuid: str,
    assignment_data: TeacherAcademicCreate,
    current_user: User
) -> TeacherAcademicResponse:
    """
    Create a new teacher academic assignment.
    """
    # Get the teacher by UUID
    teacher_result = await db.execute(
        select(User).where(User.uuid == user_uuid)
    )
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )
    
    # Validate scope - only superadmins and users within the same organization can create assignments
    if current_user.role.role_code != "super_admin":
        if teacher.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage teachers within your organization"
            )
    
    # Get medium by code
    medium_result = await db.execute(
        select(Medium).where(Medium.mmt_medium_code == assignment_data.medium_code)
    )
    medium = medium_result.scalar_one_or_none()
    
    if not medium:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Medium with code '{assignment_data.medium_code}' not found"
        )
    
    # Get subjects by codes
    subjects_result = await db.execute(
        select(Subject).where(Subject.smt_subject_code.in_(assignment_data.subject_codes))
    )
    subjects = subjects_result.scalars().all()
    
    if len(subjects) != len(assignment_data.subject_codes):
        found_codes = [s.smt_subject_code for s in subjects]
        missing_codes = [code for code in assignment_data.subject_codes if code not in found_codes]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject codes not found: {missing_codes}"
        )
    
    # Check for duplicate assignment
    existing_assignment = await db.execute(
        select(TeacherClass).where(
            TeacherClass.teacher_id == teacher.id,
            TeacherClass.academic_year == assignment_data.academic_year,
            TeacherClass.standard == assignment_data.standard,
            TeacherClass.division == assignment_data.division,
            TeacherClass.medium_id == medium.id
        )
    )
    
    if existing_assignment.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment already exists for this combination"
        )
    
    # Create the assignment
    subject_ids = [s.id for s in subjects]
    new_assignment = TeacherClass(
        teacher_id=teacher.id,
        academic_year=assignment_data.academic_year,
        standard=assignment_data.standard,
        division=assignment_data.division,
        medium_id=medium.id,
        subjects=subject_ids,
        created_by=current_user.id
    )
    
    db.add(new_assignment)
    await db.commit()
    await db.refresh(new_assignment)
    
    # Build response
    subject_details = [
        {"id": s.id, "name": s.smt_subject_name, "code": s.smt_subject_code}
        for s in subjects
    ]
    
    return TeacherAcademicResponse(
        id=new_assignment.id,
        academic_year=new_assignment.academic_year,
        standard=new_assignment.standard,
        division=new_assignment.division,
        medium_id=medium.id,
        medium_name=medium.mmt_medium_name,
        subjects=subject_details,
        created_at=new_assignment.created_at,
        updated_at=new_assignment.updated_at
    )


async def get_teacher_academic_assignments(
    db: AsyncSession,
    user_uuid: str,
    current_user: User,
    academic_year: Optional[str] = None,
    standard: Optional[str] = None,
    division: Optional[str] = None
) -> TeacherAcademicListResponse:
    """
    Get all academic assignments for a teacher.
    """
    # Get the teacher by UUID
    teacher_result = await db.execute(
        select(User).where(User.uuid == user_uuid)
    )
    teacher = teacher_result.scalar_one_or_none()
    
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found"
        )
    
    # Validate scope - only superadmins and users within the same organization can view assignments
    if current_user.role.role_code != "super_admin":
        if teacher.organization_id != current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view teachers within your organization"
            )
    
    # Build query for assignments
    query = (
        select(TeacherClass)
        .options(
            joinedload(TeacherClass.medium)
        )
        .where(TeacherClass.teacher_id == teacher.id)
    )
    
    # Apply filters
    if academic_year:
        query = query.where(TeacherClass.academic_year == academic_year)
    if standard:
        query = query.where(TeacherClass.standard == standard)
    if division:
        query = query.where(TeacherClass.division == division)
    
    assignments_result = await db.execute(query)
    assignments = assignments_result.scalars().all()
    
    # Get subject details for each assignment
    assignment_responses = []
    for assignment in assignments:
        # Get subjects by IDs
        subjects_result = await db.execute(
            select(Subject).where(Subject.id.in_(assignment.subjects))
        )
        subjects = subjects_result.scalars().all()
        
        subject_details = [
            {"id": s.id, "name": s.smt_subject_name, "code": s.smt_subject_code}
            for s in subjects
        ]
        
        assignment_responses.append(TeacherAcademicResponse(
            id=assignment.id,
            academic_year=assignment.academic_year,
            standard=assignment.standard,
            division=assignment.division,
            medium_id=assignment.medium.id,
            medium_name=assignment.medium.mmt_medium_name,
            subjects=subject_details,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at
        ))
    
    return TeacherAcademicListResponse(
        teacher_uuid=str(teacher.uuid),
        teacher_name=teacher.full_name or teacher.username,
        staff_id=teacher.staff_id,
        academic_assignments=assignment_responses
    )
