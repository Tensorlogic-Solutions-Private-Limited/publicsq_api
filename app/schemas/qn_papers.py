from pydantic import BaseModel, ConfigDict,Field
from typing import Optional, List, Literal, Union
from datetime import datetime
from pydantic import BaseModel
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum
from pydantic import BaseModel, root_validator, validator
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional


######################
# class DesignPaperResponse(BaseModel):
#     exam_name: str
#     exam_code: str
#     exam_type: str
#     exam_mode: str
#     standard: str
#     subject: str
#     medium: str
#     status: str
#     number_of_sets: int
#     number_of_versions: int
#     total_questions: int
#     papers: List[str] = []

# class SingleDesignResponse(BaseModel):
#     design: DesignPaperResponse
############################new design response ################################
class ChapterDetails(BaseModel):
    code: str
    name: str

class TopicDetails(BaseModel):
    code: str
    name: str

class QuestionToExclude(BaseModel):
    code: str
    txt: str
    chapter_details: ChapterDetails
    topic_details: TopicDetails

class ChapterCode(BaseModel):
    code: str
    qn_count: Optional[int] = None
    name: str

class TopicCode(BaseModel):
    code: str
    qn_count: Optional[int] = None
    name: str
    chapter_details: Optional[ChapterDetails] = None  # Only topics have this

class ChapterTopicGroup(BaseModel):
    type: str  # "chapter" or "topic"
    codes: List[Union[ChapterCode, TopicCode]]  # Depending on type

class SingleDesignResponseItem(BaseModel):
    exam_name: Optional[str] = None
    exam_code: Optional[str] = None
    exam_type: Optional[str] = None
    exam_mode: Optional[str] = None
    standard: Optional[str] = None
    division: Optional[str] = None
    subject: Optional[str] = None
    medium: Optional[str] = None
    status: Optional[str] = None
    number_of_sets: Optional[int] = None
    number_of_versions: Optional[int] = None
    total_questions: Optional[int] = None
    board_id: Optional[int] = None
    board_name: Optional[str] = None
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    medium_code: Optional[str] = None
    subject_code: Optional[str] = None
    created_at: Optional[str] = None
    qtn_codes_to_exclude: Optional[List[QuestionToExclude]] = None
    chapters_topics: Optional[List[ChapterTopicGroup]] = None
    papers: List[str]

class SingleDesignResponse(BaseModel):
    design: SingleDesignResponseItem

#################################################################################
# class ChapterDetails(BaseModel):
#     code: str
#     name: str

# class TopicDetails(BaseModel):
#     code: str
#     name: str
# class QuestionToExclude(BaseModel):
#     code: str
#     txt: str
#     chapter_details: ChapterDetails
#     topic_details: TopicDetails
# class ChapterTopicCodes(BaseModel):
#     code: str
#     qn_count: Optional[int] = 0
#     name: Optional[str] = None

# class ChapterTopicGroup(BaseModel):
#     type: str  # "chapter" or "topic"
#     codes: List[ChapterTopicCodes]
# class SingleDesignResponseItem(BaseModel):
#     exam_name: Optional[str] = None
#     exam_code: Optional[str] = None
#     exam_type: Optional[str] = None
#     exam_mode: Optional[str] = None
#     standard: Optional[str] = None
#     subject: Optional[str] = None
#     medium: Optional[str] = None
#     status: Optional[str] = None
#     number_of_sets: Optional[int] = None
#     number_of_versions: Optional[int] = None
#     total_questions: Optional[int] = None
#     qtn_codes_to_exclude: Optional[List[QuestionToExclude]] = None
#     chapters_topics: Optional[List[ChapterTopicGroup]] = None
#     papers: List[str]
# class SingleDesignResponse(BaseModel):
#     design: SingleDesignResponseItem

######################## exams #############################
class DesignPaperListResponseItem(BaseModel):
    exam_name: str
    exam_code: str
    exam_type: Optional[str] = None
    exam_mode: Optional[str] = None
    standard: Optional[str] = None
    division: Optional[str] = None
    subject: Optional[str] = None
    medium: Optional[str] = None
    subject_code: Optional[str] = None
    medium_code: Optional[str] = None
    status: str
    number_of_sets: Optional[int] = None
    number_of_versions: Optional[int] = None
    total_questions: Optional[int] = None
    board_id: Optional[int] = None
    board_name: Optional[str] = None
    state_id: Optional[int] = None
    state_name: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None

class DesignPaperListResponse(BaseModel):
    exams: List[DesignPaperListResponseItem]

class DesignPaperListResponsePaginated(BaseModel):
    total: int
    page: int
    limit: int
    exams: List[DesignPaperListResponseItem]