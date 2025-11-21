from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from typing import Optional, List, Literal, Dict, Union
from datetime import datetime
import uuid
from enum import Enum

############## questions/quesiton_service ################
class SubtopicQuestionCount(BaseModel):
    code: str = Field(..., description="Subtopic code")
    name: str = Field(..., description="Subtopic name")
    question_count: int = Field(..., description="Number of questions under the subtopic")

class TopicQuestionCount(BaseModel):
    code: str = Field(..., description="Topic code")
    name: str = Field(..., description="Topic name")
    question_count: int = Field(..., description="Number of questions under the topic")
    subtopics: List[SubtopicQuestionCount] = Field(default_factory=list, description="List of subtopics")

class ChapterQuestionCount(BaseModel):
    code: str = Field(..., description="Chapter code")
    name: str = Field(..., description="Chapter name")
    question_count: int = Field(..., description="Number of questions under the chapter")
    topics: List[TopicQuestionCount] = Field(default_factory=list, description="List of topics under the chapter")

class ChapterCountResponse(BaseModel):
    data: List[ChapterQuestionCount] = Field(..., description="List of chapters with topic and question count")

class ChapterTopicQuestionCountResponse(ChapterCountResponse):
    pass  # Alias for clarity and flexibility in routing

###get questions #############
class ExamQuestionGroupResponse(BaseModel):
    type: str
    type_codes: List[str]
    type_names: List[str]
    no_of_qns: int

class ExamQuestionResponse(BaseModel):
    code: str
    type: str
    marks: int
    difficulty_level: str
    grp_type: str
    grp_type_name: str
    grp_type_code: str
    text: str
    option1: str
    option2: str
    option3: str
    option4: str
    correct_answer: str
    format_code: Optional[str] = None
    type_code: Optional[str] = None




class ExamQuestionsResponse(BaseModel):
    qn_groups: List[ExamQuestionGroupResponse]
    qns: List[ExamQuestionResponse]
    total: int = Field(..., description="Total number of questions matching the criteria")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of questions per page")
    total_pages: int = Field(..., description="Total number of pages")
    grandTotal: int = Field(..., description="Total count (same as total)")

class ExamQuestionsV2Response(BaseModel):
    qn_groups: List[ExamQuestionGroupResponse]
    qns: List[ExamQuestionResponse]
    total: int = Field(..., description="Total number of questions matching the criteria")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of questions per page")


############## V3 Unified Response Schemas ################

# Text question schemas (no media fields)
class TextQuestionText(BaseModel):
    """Schema for text question content without media."""
    text: str

class TextQuestionOption(BaseModel):
    """Schema for text question option without media."""
    text: str

class TextQuestionResponse(BaseModel):
    """Response schema for text questions with unified nested structure."""
    code: str
    type: str
    marks: int
    difficulty_level: str
    grp_type: str
    grp_type_name: str
    grp_type_code: str
    format_code: str
    type_code: str
    correct_answer: str
    qn: TextQuestionText
    option1: TextQuestionOption
    option2: TextQuestionOption
    option3: TextQuestionOption
    option4: TextQuestionOption

# V3 unified response
class ExamQuestionsV3Response(BaseModel):
    qn_groups: List[ExamQuestionGroupResponse]
    qns: List[TextQuestionResponse]
    total: int = Field(..., description="Total number of questions matching the criteria")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of questions per page")
    total_pages: int = Field(..., description="Total number of pages")
    grandTotal: int = Field(..., description="Total count (same as total)")


############## New Question Management Schemas ################

class QuestionCreateRequest(BaseModel):
    question_text: str = Field(..., description="The question text")
    option1: str = Field(..., description="First answer option")
    option2: str = Field(..., description="Second answer option")
    option3: str = Field(..., description="Third answer option")
    option4: str = Field(..., description="Fourth answer option")
    correct_answer: str = Field(..., description="Correct answer option")
    marks: int = Field(1, description="Question marks")
    format_code: str = Field(..., description="Question format code (e.g., '5000')")
    type_code: str = Field(..., description="Question type code (e.g., '1000')")
    chapter_code: str = Field(..., description="Chapter code (mandatory)")
    topic_code: Optional[str] = Field(None, description="Topic code (optional)")
    subtopic_code: Optional[str] = Field(None, description="Subtopic code (optional)")
    standard: str = Field(..., description="Class/standard (mandatory, e.g., '10', '12')")
    subject_code: str = Field(..., description="Subject code (mandatory)")
    medium_code: str = Field(..., description="Medium code (mandatory)")
    board_id: int = Field(..., description="Board ID (mandatory)")
    state_id: int = Field(..., description="State ID (mandatory)")
    cognitive_learning_id: int = Field(..., description="Cognitive learning ID")
    difficulty_id: int = Field(..., description="Difficulty ID")


class QuestionUpdateRequest(BaseModel):
    question_text: Optional[str] = Field(None, description="The question text")
    option1: Optional[str] = Field(None, description="First answer option")
    option2: Optional[str] = Field(None, description="Second answer option")
    option3: Optional[str] = Field(None, description="Third answer option")
    option4: Optional[str] = Field(None, description="Fourth answer option")
    correct_answer: Optional[str] = Field(None, description="Correct answer option")
    marks: Optional[int] = Field(None, description="Question marks")
    format_code: Optional[str] = Field(None, description="Question format code (e.g., '5000')")
    type_code: Optional[str] = Field(None, description="Question type code (e.g., '1000')")
    chapter_code: Optional[str] = Field(None, description="Chapter code")
    topic_code: Optional[str] = Field(None, description="Topic code")
    subtopic_code: Optional[str] = Field(None, description="Subtopic code")
    subject_code: Optional[str] = Field(None, description="Subject code")
    medium_code: Optional[str] = Field(None, description="Medium code")
    standard: Optional[str] = Field(None, description="Class/standard (e.g., '10', '12')")
    board_id: Optional[int] = Field(None, description="Board ID")
    state_id: Optional[int] = Field(None, description="State ID")
    cognitive_learning_id: Optional[int] = Field(None, description="Cognitive learning ID")
    difficulty_id: Optional[int] = Field(None, description="Difficulty ID")




class OrganizationInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    org_name: Optional[str] = None
    org_code: Optional[str] = None


class BlockInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    block_name: Optional[str] = None
    block_code: Optional[str] = None


class SchoolInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    school_name: Optional[str] = None
    udise_code: Optional[str] = None


class BoardInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    board_name: Optional[str] = None


class StateInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    state_name: Optional[str] = None
    iso_code: Optional[str] = None


class CognitiveLearningInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    cognitive_learning_name: Optional[str] = None


class DifficultyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    difficulty_name: Optional[str] = None


class SubjectInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    smt_subject_code: Optional[str] = None
    smt_subject_name: Optional[str] = None
    smt_standard: Optional[str] = None


class MediumInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: Optional[int] = None
    mmt_medium_code: Optional[str] = None
    mmt_medium_name: Optional[str] = None


class TaxonomyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    stm_taxonomy_code: str
    stm_chapter_code: str
    stm_chapter_name: str
    stm_topic_code: str
    stm_topic_name: str
    stm_standard: str


class QuestionTypeInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    qtm_type_code: str
    qtm_type_name: str


class QuestionFormatInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    qfm_format_code: str
    qfm_format_name: str


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    qmt_question_code: str
    qmt_question_text: str
    qmt_option1: str
    qmt_option2: str
    qmt_option3: str
    qmt_option4: str
    qmt_correct_answer: str
    qmt_marks: int
    qmt_taxonomy_code: str
    qmt_is_active: bool
    
    # Master data IDs
    subject_id: int
    medium_id: int
    board_id: int
    state_id: int
    cognitive_learning_id: int
    difficulty_id: int
    
    # Organizational context
    organization_uuid: Optional[uuid.UUID] = None
    block_uuid: Optional[uuid.UUID] = None
    school_uuid: Optional[uuid.UUID] = None
    
    # Relationships
    organization: Optional[OrganizationInfo] = None
    block: Optional[BlockInfo] = None
    school: Optional[SchoolInfo] = None
    taxonomy: Optional[TaxonomyInfo] = None
    type: Optional[QuestionTypeInfo] = None
    format: Optional[QuestionFormatInfo] = None
    subject: Optional[SubjectInfo] = None
    medium: Optional[MediumInfo] = None
    board: Optional[BoardInfo] = None
    state: Optional[StateInfo] = None
    cognitive_learning: Optional[CognitiveLearningInfo] = None
    difficulty: Optional[DifficultyInfo] = None
    

    
    # Audit fields
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None