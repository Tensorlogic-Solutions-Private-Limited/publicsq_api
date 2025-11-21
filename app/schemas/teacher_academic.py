from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TeacherAcademicCreate(BaseModel):
    academic_year: str = Field(..., description="Academic year (e.g., '2025')")
    standard: str = Field(..., description="Standard/class (e.g., '10')")
    division: str = Field(..., description="Division (e.g., 'A', 'B', 'C')")
    medium_code: str = Field(..., description="Medium code from medium_master_table")
    subject_codes: List[str] = Field(..., description="List of subject codes from subject_master_table")


class TeacherAcademicResponse(BaseModel):
    id: int
    academic_year: str
    standard: str
    division: str
    medium_id: int
    medium_name: str
    subjects: List[dict]  # [{"id": 1, "name": "Math", "code": "3000"}]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TeacherAcademicListResponse(BaseModel):
    teacher_uuid: str
    teacher_name: str
    staff_id: Optional[str] = None
    academic_assignments: List[TeacherAcademicResponse]


class TeacherAcademicUpdate(BaseModel):
    academic_year: Optional[str] = None
    standard: Optional[str] = None
    division: Optional[str] = None
    medium_code: Optional[str] = None
    subject_codes: Optional[List[str]] = None
