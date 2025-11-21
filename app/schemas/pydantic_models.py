# from pydantic import BaseModel, ConfigDict,Field
# from typing import Optional, List, Literal
# from datetime import datetime
# from pydantic import BaseModel
# from enum import Enum
# from typing import List, Optional
# from pydantic import BaseModel, ConfigDict
# from enum import Enum
# from pydantic import BaseModel, root_validator, validator
# from pydantic import BaseModel, field_validator, model_validator
# from typing import Optional

# class UserCreate(BaseModel):
#     username: str
#     password: str
#     role_code: str

#     class Config:
#         from_attributes = True

# class RoleResponse(BaseModel):
#     role_code: str
#     role_name: str

#     class Config:
#         from_attributes = True

# class RoleListResponse(BaseModel):
#     data: List[RoleResponse]

# class LoginRequest(BaseModel):
#     username: str
#     password: str

#     class Config:
#         from_attributes = True 

# class LoginResponse(BaseModel):
#     access_token: str
#     token_type: str
#     username: str
#     role_name: str
#     role_code: str



# # === QuestionType ===

# class QuestionTypeBase(BaseModel):
#     type_code: str
#     type_name: str

#     class Config:
#         from_attributes = True

# class QuestionTypeListResponse(BaseModel):
#     data: List[QuestionTypeBase]


# # === Medium ===

# class MediumBase(BaseModel):
#     medium_code: str
#     medium_name: str

# class MediumResponse(BaseModel):
#     data: List[MediumBase]



# # === Subject ===

# class SubjectBase(BaseModel):
#     subject_code: str
#     subject_name: str
#     medium_code: str
#     standard: str

#     class Config:
#         from_attributes = True
# class SubjectListResponse(BaseModel):
#     data: List[SubjectBase]



# # === Criteria ===

# class CriteriaBase(BaseModel):
#     scm_criteria_code: str
#     scm_criteria_name: str

#     class Config:
#         from_attributes = True 


# # === Format ===

# class FormatBase(BaseModel):
#     qfm_format_code: str
#     qfm_format_name: str

#     class Config:
#         from_attributes = True
# class FormatResponse(BaseModel):
#     data: List[FormatBase] 


# # === Taxonomy ===

# class TaxonomyBase(BaseModel):
#     stm_taxonomy_code: str
#     stm_subject_id: int
#     stm_medium_id: int
#     stm_standard: str               
#     stm_chapter_code: str
#     stm_chapter_name: str
#     stm_topic_code: str
#     stm_topic_name: str

#     class Config:
#         from_attributes = True


# class TaxonomyCreate(TaxonomyBase):
#     pass  


# class TaxonomyUpdate(BaseModel):
#     stm_taxonomy_code: Optional[str] = None
#     stm_subject_id: Optional[int] = None
#     stm_medium_id: Optional[int] = None
#     stm_class: Optional[str] = None
#     stm_chapter_code: Optional[str] = None
#     stm_chapter_name: Optional[str] = None
#     stm_topic_code: Optional[str] = None
#     stm_topic_name: Optional[str] = None


# class TaxonomyResponse(TaxonomyBase):
#     id: int

#     class Config:
#         from_attributes = True


# # === Chapter & Topic Counts ===

# class ChapterResponse(BaseModel):
#     chapter_code: str
#     chapter_name: str


# class ChapterQuestionCount(BaseModel):
#     chapter_code: str
#     chapter_name: str
#     question_count: int


# class TopicQuestionCount(BaseModel):
#     chapter_code: str
#     chapter_name: str
#     topic_code: str
#     topic_name: str
#     question_count: int


# class ChapterCountResponse(BaseModel):
#     data: List[ChapterQuestionCount]


# class TopicCountResponse(BaseModel):
#     data: List[TopicQuestionCount]


# # === Design ===

# # class DesignBase(BaseModel):
# #     dm_design_name: str
# #     dm_subject_id: int
# #     dm_medium_id: int
# #     dm_standard: str
# #     dm_status: Literal["draft", "open", "closed"]

# #     class Config:
# #         from_attributes = True


# # class DesignCreate(DesignBase):
# #     dm_status: Literal["draft", "open", "closed"] = "draft"


# # class DesignUpdate(BaseModel):
# #     dm_design_name: Optional[str] = None
# #     dm_subject_id: Optional[int] = None
# #     dm_medium_id: Optional[int] = None
# #     dm_standard: Optional[str] = None
# #     dm_status: Optional[Literal["draft", "open", "closed"]] = "draft"


# # class DesignResponse(BaseModel):
# #     message: str
# #     newly_inserted_design_name: str
# #     newly_inserted_design_id: int

# #     class Config:
# #         from_attributes = True

# class QuestionData(BaseModel):
#     selected_question_id: int
#     question_text: str
#     group: int


# class GroupData(BaseModel):
#     question_set_count_id: int
#     group_number: int
#     total_questions: int
#     questions_to_insert: int

# class GroupResponse(BaseModel):
#     message: str
#     groups: List[GroupData]
#     questions: Optional[List[QuestionData]] = None
#     total_questions: Optional[int] = None

# class VersionCreate(BaseModel):
#     design_id: int
#     version_no: int
#     set_no: int
#     total_time: int

# class VersionResponse(BaseModel):
#     message: str
#     newly_inserted_version_code:str
#     newly_inserted_version_id: int
#     newly_inserted_version_no: int
#     newly_inserted_set_no: int
#     newly_inserted_vm_total_time: int

# class CreateQuestionPaperDetails(BaseModel):
#     version_id: int

# class DesignModel(BaseModel):
#     id: int
#     dm_design_name: str
#     dm_medium_id: int
#     dm_status: str
#     dm_subject_id: int
#     dm_standard: str
#     created_at: datetime
#     updated_at: datetime
#     created_by: Optional[str]
#     updated_by: Optional[str]

#     class Config:
#         from_attributes = True

# class VersionModel(BaseModel):
#     id: int
#     vm_version_code: str
#     vm_version_no: int
#     vm_total_time: int
#     vm_design_id: int
#     vm_set_no: int
#     created_at: datetime
#     updated_at: datetime
#     created_by: Optional[str]
#     updated_by: Optional[str]
#     design: DesignModel

#     class Config:
#         from_attributes = True

# class QuestionPaperDetailsModel(BaseModel):
#     id: int
#     qpd_paper_id: str
#     qpd_q_codes: str
#     qpd_total_questions: int
#     qpd_total_time: int
#     qpd_version_id: int
#     qpd_design_name: str
#     created_at: datetime
#     updated_at: datetime
#     created_by: Optional[str]
#     updated_by: Optional[str]
#     version: VersionModel

#     class Config:
#         from_attributes = True

# class ChapterQuestionCount(BaseModel):
#     chapter_code: str
#     chapter_name: str
#     chapter_question_count: int

# class TopicQuestionCount(BaseModel):
#     chapter_code: str
#     chapter_name: str
#     topic_code: str
#     topic_name: str
#     topic_question_count: int

# class ChapterTopicCountResponse(BaseModel):
#     chapter: List[ChapterQuestionCount]
#     topic: List[TopicQuestionCount]

# class AddGroupsRequest(BaseModel):
#     design_id: int
#     chapter_code: Optional[str] = None
#     topic_code: Optional[str] = None
#     questions_to_insert: int

# # class CreateDesign(BaseModel):
# #     questions_to_exclude: Optional[str] = None
# #     chapter_code: Optional[str] = None
# #     topic_code: Optional[str] = None
# #     exam_title: str
# #     total_time: int
# #     total_questions: int
# #     number_of_sets: int
# #     number_of_versions: int
# #     standard: int
# #     medium: int
# #     subject: int

# #     @model_validator(mode="after")
# #     def check_chapter_or_topic(self) -> 'CreateDesign':
# #         if not self.chapter_code and not self.topic_code:
# #             raise ValueError("At least one of 'chapter_code' or 'topic_code' must be provided.")
# #         return self

# class SubTopicResponse(BaseModel):
#     code: str
#     name: str
#     question_count: int

# class TopicResponse(BaseModel):
#     code: str
#     name: str
#     question_count: int
#     subtopics: List[SubTopicResponse]

# class ChapterResponse(BaseModel):
#     code: str
#     name: str
#     question_count: int
#     topics: List[TopicResponse]

# class ChaptersResponse(BaseModel):
#     chapters: List[ChapterResponse]


# class QuestionGroupResponse(BaseModel):
#     type: str
#     type_codes: List[str]
#     type_names: List[str]
#     no_of_qns: int

# class QuestionResponse(BaseModel):
#     code: str
#     type: str
#     marks: int
#     difficulty_level: str
#     grp_type: str
#     grp_type_name: str
#     grp_type_code: str
#     text: str

# class QuestionsResponse(BaseModel):
#     qn_groups: List[QuestionGroupResponse]
#     qns: List[QuestionResponse]

# class DesignStatus(str, Enum):
#     draft = "draft"
#     open = "open"
#     closed = "closed"

# class QuestionType(str, Enum):
#     chapter = "chapter"
#     topic = "topic"

# class QuestionSelection(BaseModel):
#     type: Literal["chapter", "topic"] = Field(..., description="Selection type: 'chapter' or 'topic'")
#     codes: List[str] = Field(..., description="List of chapter/topic codes")
#     qtn_codes_to_exclude: List[str] = Field(default_factory=list, description="List of question codes to exclude")

# class OptionResponse(BaseModel):
#     id: str
#     text: str
#     is_correct: bool

# class QuestionResponse(BaseModel):
#     id: str
#     text: str
#     options: List[OptionResponse]

# ########################### QuestionPaperResponse #################
# class OptionResponse(BaseModel):
#     id: str
#     text: str
#     is_correct: bool

# class QuestionResponse(BaseModel):
#     id: str
#     text: str
#     options: List[OptionResponse]

# class QuestionPaperResponse(BaseModel):
#     id: str
#     exam_name: str
#     design_id: int
#     number_of_sets: int
#     number_of_versions: int
#     no_of_qns: int
#     subject: str
#     medium: str
#     exam_type: str
#     standard: str
#     # qns: List[QuestionResponse]

# class QuestionPaperListResponse(BaseModel):
#     papers: List[QuestionPaperResponse]

# ################### qp_each ############
# class OptionResponseEach(BaseModel):
#     id: str
#     text: str
#     is_correct: Optional[bool] = None

# class QuestionResponseEach(BaseModel):
#     id: str
#     text: str
#     options: List[OptionResponseEach]

# class QuestionPaperResponseEach(BaseModel):
#     id: str
#     exam_name: str
#     design_id: int
#     number_of_sets: int
#     number_of_versions: int
#     no_of_qns: int
#     subject: str
#     medium: str
#     exam_type: str
#     standard: str
#     qns: List[QuestionResponseEach]

# class DesignPaperList(BaseModel):
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

# class DesignPaperListResponse(BaseModel):
#     exams: List[DesignPaperList]
# ###########  @router.get("/v1/exams/{exam_code}")
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

# ###get questions #############
# class ExamQuestionGroupResponse(BaseModel):
#     type: str
#     type_codes: List[str]
#     type_names: List[str]
#     no_of_qns: int

# class ExamQuestionResponse(BaseModel):
#     code: str
#     type: str
#     marks: int
#     difficulty_level: str
#     grp_type: str
#     grp_type_name: str
#     grp_type_code: str
#     text: str

# class ExamQuestionsResponse(BaseModel):
#     qn_groups: List[ExamQuestionGroupResponse]
#     qns: List[ExamQuestionResponse]

# ############# Design Create #############
# class QuestionSelection(BaseModel):
#     type: str
#     codes: List[str]
#     qtn_codes_to_exclude: Optional[List[str]] = []

# class DesignCreate(BaseModel):
#     exam_name: str
#     exam_type_code: str
#     subject_code: str
#     medium_code: str
#     exam_mode: str
#     total_time: int
#     total_questions: int
#     no_of_versions: int
#     no_of_sets: int
#     standard: Optional[str]
#     qns: List[QuestionSelection]

# ############## questions/quesiton_service ################
# class SubtopicQuestionCount(BaseModel):
#     code: str = Field(..., description="Subtopic code")
#     name: str = Field(..., description="Subtopic name")
#     question_count: int = Field(..., description="Number of questions under the subtopic")

# class TopicQuestionCount(BaseModel):
#     code: str = Field(..., description="Topic code")
#     name: str = Field(..., description="Topic name")
#     question_count: int = Field(..., description="Number of questions under the topic")
#     subtopics: List[SubtopicQuestionCount] = Field(default_factory=list, description="List of subtopics")

# class ChapterQuestionCount(BaseModel):
#     code: str = Field(..., description="Chapter code")
#     name: str = Field(..., description="Chapter name")
#     question_count: int = Field(..., description="Number of questions under the chapter")
#     topics: List[TopicQuestionCount] = Field(default_factory=list, description="List of topics under the chapter")

# class ChapterCountResponse(BaseModel):
#     data: List[ChapterQuestionCount] = Field(..., description="List of chapters with topic and question count")

# class ChapterTopicQuestionCountResponse(ChapterCountResponse):
#     pass  # Alias for clarity and flexibility in routing

# ######################## exams #############################
# class DesignPaperListResponseItem(BaseModel):
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


# class DesignPaperListResponse(BaseModel):
#     exams: List[DesignPaperListResponseItem]

# ##################################################################
# class SingleDesignResponseItem(BaseModel):
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
#     papers: List[str]  # List of paper codes (e.g., ["SET1", "SET2"])

# class SingleDesignResponse(BaseModel):
#     design: SingleDesignResponseItem