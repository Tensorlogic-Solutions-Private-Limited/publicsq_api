from pydantic import BaseModel, ConfigDict,Field
from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum
from pydantic import BaseModel, root_validator, validator
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional

class OptionResponseEach(BaseModel):
    id: str
    text: str
    is_correct: Optional[bool] = None

class QuestionResponseEach(BaseModel):
    id: str
    text: str
    options: List[OptionResponseEach]
    format_code: Optional[str] = None
    # Image media fields (for image format questions)
    qmt_question_text_media: Optional[List[str]] = None
    qmt_option1_media: Optional[List[str]] = None
    qmt_option2_media: Optional[List[str]] = None
    qmt_option3_media: Optional[List[str]] = None
    qmt_option4_media: Optional[List[str]] = None

class QuestionPaperResponseEach(BaseModel):
    id: str
    exam_name: str
    exam_code: str
    design_id: int
    number_of_sets: int
    number_of_versions: int
    no_of_qns: int
    total_time: int
    subject: str
    medium: str
    exam_type: str
    standard: str
    qns: List[QuestionResponseEach]

class DesignPaperList(BaseModel):
    exam_name: str
    exam_code: str
    exam_type: str
    exam_mode: str
    standard: str
    subject: str
    medium: str
    status: str
    number_of_sets: int
    number_of_versions: int
    total_questions: int

class DesignPaperListResponse(BaseModel):
    exams: List[DesignPaperList]