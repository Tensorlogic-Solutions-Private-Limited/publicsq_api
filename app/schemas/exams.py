from pydantic import BaseModel, ConfigDict,Field, root_validator
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum
from pydantic import BaseModel, root_validator, validator
from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional, Union
from uuid import UUID

############# Design Create #############
from pydantic import BaseModel, model_validator
from typing import List, Optional, Literal

class CodeSelection(BaseModel):
    code: str
    qn_count: Optional[int] = None

class QuestionSelection(BaseModel):
    type: str
    codes: List[CodeSelection]

from app.constants.status_codes import DESIGN_STATUS

class DesignBase(BaseModel):
    status: int
    is_ai_selected: bool
    exam_name: str
    exam_type_code: Optional[str] = None
    subject_code: Optional[str] = None
    medium_code: Optional[str] = None
    board_id: Optional[int] = None
    state_id: Optional[int] = None
    exam_mode: Optional[str] = None
    total_time: Optional[int] = None
    total_questions: Optional[int] = None
    no_of_versions: Optional[int] = None
    no_of_sets: Optional[int] = None
    standard: Optional[str] = None
    division: Optional[str] = None
    qtn_codes_to_exclude: List[str] = []
    chapters_topics: List[QuestionSelection] = []

    @model_validator(mode="after")
    def validate_based_on_status(self):
        status_label = DESIGN_STATUS.get(self.status)

        if status_label == "closed":
            # Validate required fields for finalization
            required_fields = [
                "exam_type_code", "subject_code", "medium_code", "board_id", "exam_mode",
                "total_time", "total_questions", "no_of_versions", "no_of_sets"
            ]
            for field in required_fields:
                if getattr(self, field) is None:
                    raise ValueError(f"{field} is required when status is 'closed'")

            # Validate question count rules
            if self.is_ai_selected:
                for q in self.chapters_topics:
                    for code in q.codes:
                        if code.qn_count is not None:
                            raise ValueError("When 'is_ai_selected' is True, 'qn_count' must be null or omitted.")
            else:
                for q in self.chapters_topics:
                    for code in q.codes:
                        if code.qn_count is None:
                            raise ValueError("When 'is_ai_selected' is False, each 'qn_count' must be provided.")

        return self

class DesignCreate(BaseModel):
    is_ai_selected: bool
    exam_name: str
    exam_type_code: str
    subject_code: str
    medium_code: str
    board_id: int
    state_id: Optional[int] = None
    exam_mode: str
    total_time: int
    total_questions: int
    no_of_versions: int
    no_of_sets: int
    standard: Optional[str]
    qtn_codes_to_exclude: List[str] = []
    chapters_topics: List[QuestionSelection]

    @model_validator(mode="after")
    def validate_qn_count(self) -> 'DesignCreate':
        if self.is_ai_selected:
            for q in self.chapters_topics:
                for code in q.codes:
                    if code.qn_count is not None:
                        raise ValueError("When 'is_ai_selected' is True, 'qn_count' must be null or omitted.")
        else:
            for q in self.chapters_topics:
                for code in q.codes:
                    if code.qn_count is None:
                        raise ValueError("When 'is_ai_selected' is False, each 'qn_count' must be provided.")
        return self


class DesignPaperListResponseItem(BaseModel):
    exam_name: str
    exam_code: str
    exam_type: Optional[str] = None
    exam_mode: Optional[str] = None  
    standard: Optional[str] = None
    division: Optional[str] = None
    subject: Optional[str] = None
    medium: Optional[str] = None
    status: str
    number_of_sets: Optional[int] = None 
    number_of_versions: Optional[int] = None 
    total_questions: Optional[int] = None 
    board_id: Optional[int] = None
    state_id: Optional[int] = None
    created_at: str
    created_by: Optional[str] = None

class DesignUpdate(BaseModel):
    exam_name: Optional[str]
    exam_type_code: Optional[str]
    exam_mode: Optional[str]
    total_time: Optional[int]
    total_questions: Optional[int]
    no_of_versions: Optional[int]
    no_of_sets: Optional[int]
    subject_code: Optional[str]
    medium_code: Optional[str]
    board_id: Optional[int]
    state_id: Optional[int] = None
    standard: Optional[str]
    division: Optional[str]
    is_ai_selected: Optional[bool] = False
    qtn_codes_to_exclude: Optional[List[str]] = []
    chapters_topics: Optional[List[QuestionSelection]] = None
    status: Optional[int]  # 1=draft, 2=finalized

class DesignStatusUpdate(BaseModel):
    status: int  # 1=draft, 2=finalized
    
    @field_validator('status')
    def validate_status(cls, v):
        if v not in [1, 2]:
            raise ValueError('Status must be 1 (draft) or 2 (finalized)')
        return v

class DesignPaperResponse(BaseModel):
    exam_name: str
    exam_code: str
    exam_type: Optional[str] = None
    exam_mode: Optional[str] = None
    standard: Optional[str] = None
    division: Optional[str] = None
    subject: Optional[str] = None
    medium: Optional[str] = None
    status: str
    number_of_sets: Optional[int] = None
    number_of_versions: Optional[int] = None
    total_questions: Optional[int] = None
    board_id: Optional[int] = None
    state_id: Optional[int] = None
    papers: List[str] = []

class SingleDesignResponse(BaseModel):
    design: DesignPaperResponse

class DesignPaperListResponse(BaseModel):
    exams: List[DesignPaperListResponseItem]


############# Exam Container Schemas #############

class ExamCreate(BaseModel):
    """
    Schema for creating an exam container.
    
    Required fields:
    - exam_name: Name of the exam
    
    Optional fields:
    - total_time: Total time for the exam in minutes
    - exam_mode: Mode of the exam (e.g., 'online', 'offline')
    - organization_id: Organization UUID (auto-populated from user profile if not provided)
    - block_id: Block UUID (auto-populated from user profile if not provided)
    - school_id: School UUID (auto-populated from user profile if not provided)
    
    Note: If organization_id, block_id, or school_id are not provided in the request,
    they will be automatically populated from the current user's profile.
    Role-based permissions apply when explicitly providing these values.
    """
    exam_name: str
    total_time: Optional[int] = None
    exam_mode: Optional[str] = None
    organization_id: Optional[UUID] = None
    block_id: Optional[UUID] = None
    school_id: Optional[UUID] = None


class ExamUpdate(BaseModel):
    """
    Schema for updating an exam container.
    
    All fields are optional for partial updates.
    
    Status values:
    - 'draft': Exam is being prepared
    - 'saved': Exam is saved but not started
    - 'started': Exam has started (immutable after this)
    - 'completed': Exam is completed (immutable)
    
    Note: Once status is 'started' or 'completed', the exam becomes immutable.
    
    Organizational fields (role-based permissions apply):
    - organization_id: Organization UUID (super_admin only)
    - block_id: Block UUID (super_admin, admin, admin_user)
    - school_id: School UUID (super_admin, admin, admin_user, block_admin)
    """
    exam_name: Optional[str] = None
    total_time: Optional[int] = None
    exam_mode: Optional[str] = None
    status: Optional[Literal['draft', 'saved', 'started', 'completed']] = None
    organization_id: Optional[UUID] = None
    block_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    
    @field_validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['draft', 'saved', 'started', 'completed']:
            raise ValueError("Status must be one of: 'draft', 'saved', 'started', 'completed'")
        return v


class ExamResponse(BaseModel):
    """
    Schema for exam container response with all associated designs.
    """
    exam_code: str
    exam_name: str
    total_time: Optional[int] = None
    total_questions: Optional[int] = None  # Sum of total_questions from all designs
    exam_mode: Optional[str] = None
    status: str
    organization_id: Optional[UUID] = None
    block_id: Optional[UUID] = None
    school_id: Optional[UUID] = None
    designs: List[dict] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class ExamListItem(BaseModel):
    """
    Schema for individual exam item in list response.
    """
    exam_code: str
    exam_name: str
    board_id: Optional[int] = None
    state_id: Optional[int] = None
    standard: Optional[str] = None
    status: str
    total_designs: int
    subjects: List[str] = []
    created_at: datetime


class ExamListResponse(BaseModel):
    """
    Schema for paginated exam list response.
    """
    data: List[ExamListItem]
    total: int
    page: int
    page_size: int
    total_pages: int

