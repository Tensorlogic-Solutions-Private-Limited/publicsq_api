from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, Enum, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, foreign
from app.database import Base
from app.models.audit_mixin import AuditMixin
from sqlalchemy import JSON
import enum

class Board(Base, AuditMixin):
    __tablename__ = "board_master"

    id = Column(Integer, primary_key=True, index=True)
    board_name = Column(String, unique=True, nullable=False)

    # Relationships
    taxonomies = relationship("Taxonomy", back_populates="board")
    questions = relationship("Questions", back_populates="board")
    school_boards = relationship("SchoolBoard", back_populates="board")


class State(Base, AuditMixin):
    __tablename__ = "state_master"

    id = Column(Integer, primary_key=True, index=True)
    state_name = Column(String, unique=True, nullable=False)
    iso_code = Column(String, nullable=True)

    # Relationships
    blocks = relationship("Block", back_populates="state")
    taxonomies = relationship("Taxonomy", back_populates="state")
    questions = relationship("Questions", back_populates="state")
    schools = relationship("School", back_populates="state")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(State.created_by) == User.id", back_populates="created_states")
    updated_by_user = relationship("User", primaryjoin="foreign(State.updated_by) == User.id", back_populates="updated_states")


class CognitiveLearning(Base, AuditMixin):
    __tablename__ = "cognitive_learning_master"

    id = Column(Integer, primary_key=True, index=True)
    cognitive_learning_name = Column(String, unique=True, nullable=False)

    # Relationships
    questions = relationship("Questions", back_populates="cognitive_learning")


class Difficulty(Base, AuditMixin):
    __tablename__ = "difficulty_master"

    id = Column(Integer, primary_key=True, index=True)
    difficulty_name = Column(String, unique=True, nullable=False)

    # Relationships
    questions = relationship("Questions", back_populates="difficulty")


class QuestionSequence(Base):
    __tablename__ = "question_sequence"

    id = Column(Integer, primary_key=True, index=True)
    last_question_id = Column(Integer, default=0, nullable=False)


class Question_Type(Base, AuditMixin):
    __tablename__ = "question_type_master"

    id = Column(Integer, primary_key=True, index=True)
    qtm_type_code = Column(String, unique=True, nullable=False)
    qtm_type_name = Column(String, unique=True, nullable=False)

    questions = relationship("Questions", back_populates="type")
    designs = relationship("Design", back_populates="type")


class Question_Format(Base, AuditMixin):
    __tablename__ = "question_format_master"

    id = Column(Integer, primary_key=True, index=True)
    qfm_format_code = Column(String, unique=True, nullable=False)
    qfm_format_name = Column(String, unique=True, nullable=False)

    questions = relationship("Questions", back_populates="format")


class Medium(Base, AuditMixin):
    __tablename__ = "medium_master_table"

    id = Column(Integer, primary_key=True, index=True)
    mmt_medium_code = Column(String, unique=True, nullable=False)
    mmt_medium_name = Column(String, unique=True, nullable=False)

    # Relationships
    subjects = relationship("Subject", back_populates="medium", cascade="all, delete-orphan")
    designs = relationship("Design", back_populates="medium", cascade="all, delete-orphan")
    taxonomies = relationship("Taxonomy", back_populates="medium", cascade="all, delete-orphan")
    questions = relationship("Questions", back_populates="medium")
    teacher_classes = relationship("TeacherClass", back_populates="medium")


class Criteria(Base, AuditMixin):
    __tablename__ = "selection_criteria_master"

    id = Column(Integer, primary_key=True, index=True)
    scm_criteria_code = Column(String, unique=True, nullable=False)
    scm_criteria_name = Column(String, unique=True, nullable=False)


class Subject(Base, AuditMixin):
    __tablename__ = "subject_master_table"

    id = Column(Integer, primary_key=True, index=True)
    smt_subject_code = Column(String, unique=True, nullable=False)
    smt_subject_name = Column(String, unique=True, nullable=False)
    smt_standard = Column(String, nullable=False)

    smt_medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="SET NULL"), nullable=False)

    # Relationships
    medium = relationship("Medium", back_populates="subjects")
    designs = relationship("Design", back_populates="subject", cascade="all, delete-orphan")
    taxonomies = relationship("Taxonomy", back_populates="subject", cascade="all, delete-orphan")
    questions = relationship("Questions", back_populates="subject")


class Taxonomy(Base, AuditMixin):
    __tablename__ = "subject_taxonomy_master"

    id = Column(Integer, primary_key=True, index=True)
    stm_taxonomy_code = Column(String, nullable=False)
    stm_subject_id = Column(Integer, ForeignKey("subject_master_table.id", ondelete="SET NULL"), nullable=False)
    stm_medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="SET NULL"), nullable=False)
    stm_standard = Column(String, nullable=False)
    stm_chapter_code = Column(String, nullable=False)
    stm_chapter_name = Column(String, nullable=False)
    stm_topic_code = Column(String, nullable=False)
    stm_topic_name = Column(String, nullable=False)
    stm_subtopic_code = Column(String, nullable=False)
    stm_subtopic_name = Column(String, nullable=False)
    board_id = Column(Integer, ForeignKey("board_master.id", ondelete="SET NULL"), nullable=False)
    state_id = Column(Integer, ForeignKey("state_master.id", ondelete="SET NULL"), nullable=False)

    # Composite unique constraint to prevent taxonomy collisions
    __table_args__ = (
        UniqueConstraint(
            'stm_chapter_code', 'stm_topic_code', 'stm_subtopic_code', 
            'stm_subject_id', 'stm_medium_id', 'stm_standard', 'board_id', 'state_id',
            name='unique_taxonomy_context'
        ),
    )

    # Relationships
    questions = relationship("Questions", back_populates="taxonomy")
    subject = relationship("Subject", back_populates="taxonomies")
    medium = relationship("Medium", back_populates="taxonomies")
    board = relationship("Board", back_populates="taxonomies")
    state = relationship("State", back_populates="taxonomies")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(Taxonomy.created_by) == User.id", back_populates="created_taxonomies")
    updated_by_user = relationship("User", primaryjoin="foreign(Taxonomy.updated_by) == User.id", back_populates="updated_taxonomies")

    @property
    def created_by_username(self):
        """Get the username of the user who created this taxonomy."""
        return self.created_by_user.username if self.created_by_user else None
    
    @property
    def updated_by_username(self):
        """Get the username of the user who last updated this taxonomy."""
        return self.updated_by_user.username if self.updated_by_user else None

    def __repr__(self):
        return f"<Taxonomy(id={self.id}, stm_taxonomy_code='{self.stm_taxonomy_code}', chapter='{self.stm_chapter_name}', topic='{self.stm_topic_name}', subtopic='{self.stm_subtopic_name}')>"


class Questions(Base, AuditMixin):
    __tablename__ = "question_master_table"

    id = Column(Integer, primary_key=True, index=True)
    qmt_question_code = Column(String, unique=True, nullable=False)
    qmt_question_text = Column(Text, nullable=False)
    qmt_option1 = Column(String, nullable=False)
    qmt_option2 = Column(String, nullable=False)
    qmt_option3 = Column(String, nullable=False)
    qmt_option4 = Column(String, nullable=False)
    qmt_correct_answer = Column(String, nullable=False)
    qmt_marks = Column(Integer, nullable=False)
    qmt_format_id = Column(Integer, ForeignKey("question_format_master.id", ondelete="SET NULL"), nullable=False)
    qmt_type_id = Column(Integer, ForeignKey("question_type_master.id", ondelete="SET NULL"), nullable=False)
    qmt_taxonomy_id = Column(Integer, ForeignKey("subject_taxonomy_master.id", ondelete="SET NULL"), nullable=False)
    qmt_taxonomy_code = Column(String, nullable=False)
    qmt_is_active = Column(Boolean, default=True)
    status = Column(String(50), nullable=False, default="Approved")
    cognitive_learning_id = Column(Integer, ForeignKey("cognitive_learning_master.id", ondelete="SET NULL"), nullable=False)
    difficulty_id = Column(Integer, ForeignKey("difficulty_master.id", ondelete="SET NULL"), nullable=False)
    
    # Direct master data references
    subject_id = Column(Integer, ForeignKey("subject_master_table.id", ondelete="SET NULL"), nullable=False)
    medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="SET NULL"), nullable=False)
    board_id = Column(Integer, ForeignKey("board_master.id", ondelete="SET NULL"), nullable=False)
    state_id = Column(Integer, ForeignKey("state_master.id", ondelete="SET NULL"), nullable=False)
    
    # Organizational hierarchy fields
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    block_id = Column(Integer, ForeignKey("blocks.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    
    # Media fields for image-based questions
    qmt_question_text_media = Column(JSON, nullable=True)
    qmt_option1_media = Column(JSON, nullable=True)
    qmt_option2_media = Column(JSON, nullable=True)
    qmt_option3_media = Column(JSON, nullable=True)
    qmt_option4_media = Column(JSON, nullable=True)
    
    # Image order mapping for position-based image management
    qmt_image_order_mapping = Column(JSON, nullable=True)

    # Relationships
    format = relationship("Question_Format", back_populates="questions")
    type = relationship("Question_Type", back_populates="questions")
    taxonomy = relationship("Taxonomy", back_populates="questions")
    cognitive_learning = relationship("CognitiveLearning", back_populates="questions")
    difficulty = relationship("Difficulty", back_populates="questions")
    subject = relationship("Subject", back_populates="questions")
    medium = relationship("Medium", back_populates="questions")
    board = relationship("Board", back_populates="questions")
    state = relationship("State", back_populates="questions")
    organization = relationship("Organization", back_populates="questions")
    block = relationship("Block", back_populates="questions")
    school = relationship("School", back_populates="questions")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(Questions.created_by) == User.id", back_populates="created_questions")
    updated_by_user = relationship("User", primaryjoin="foreign(Questions.updated_by) == User.id", back_populates="updated_questions")




# class Design(Base, AuditMixin):
#     __tablename__ = "design_master"

#     id = Column(Integer, primary_key=True, index=True)
#     dm_design_name = Column(String, unique=True, nullable=False)
#     dm_design_code = Column(String, unique=True, nullable=False)
#     dm_exam_type_id = Column(Integer, ForeignKey("question_type_master.id", ondelete="CASCADE"), nullable=False)
#     dm_exam_mode = Column(String, nullable=False)

#     dm_total_time = Column(Integer, nullable=False, comment="Total duration of the exam in minutes")
#     dm_total_questions = Column(Integer, nullable=False, comment="Total number of questions")
#     dm_no_of_versions = Column(Integer, nullable=False, comment="Number of versions")
#     dm_no_of_sets = Column(Integer, nullable=False, comment="Number of sets")

#     dm_subject_id = Column(Integer, ForeignKey("subject_master_table.id", ondelete="CASCADE"), nullable=False)
#     dm_medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="CASCADE"), nullable=False)
#     dm_standard = Column(String, nullable=False)
#     dm_status = Column(Enum("draft", "closed", name="dm_status_enum"), nullable=False, server_default="draft")
#     dm_total_question_codes = Column(JSON, nullable=False)

#     dm_chapter_topics = Column(JSON, nullable=True)
#     dm_questions_to_exclude = Column(JSON, nullable=True)

#     # Relationships
#     subject = relationship("Subject", back_populates="designs")
#     medium = relationship("Medium", back_populates="designs")
#     type = relationship("Question_Type", back_populates="designs")
#     question_papers = relationship("QuestionPaperDetails", back_populates="design", cascade="all, delete-orphan")

class ExamMaster(Base, AuditMixin):
    __tablename__ = "exam_master"

    id = Column(Integer, primary_key=True, index=True)
    exam_code = Column(String, unique=True, nullable=False)
    exam_name = Column(String, nullable=False)
    total_time = Column(Integer, nullable=True)
    exam_mode = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    
    # Organizational hierarchy fields
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    block_id = Column(Integer, ForeignKey("blocks.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    
    # Soft delete flag
    is_active = Column(Boolean, default=True)

    # Relationships
    designs = relationship("Design", back_populates="exam", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="exams")
    block = relationship("Block", back_populates="exams")
    school = relationship("School", back_populates="exams")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(ExamMaster.created_by) == User.id", back_populates="created_exams")
    updated_by_user = relationship("User", primaryjoin="foreign(ExamMaster.updated_by) == User.id", back_populates="updated_exams")


class Design(Base, AuditMixin):
    __tablename__ = "design_master"
    
    __table_args__ = (
        # Allow same design name as long as they're not in the same exam
        # NULL exam_id values are treated as distinct, so standalone designs can have duplicate names
        UniqueConstraint('dm_design_name', 'exam_id', name='unique_design_name_per_exam'),
    )

    id = Column(Integer, primary_key=True, index=True)
    dm_design_name = Column(String, nullable=False)
    dm_design_code = Column(String, unique=True, nullable=False)
    dm_exam_type_id = Column(Integer, ForeignKey("question_type_master.id", ondelete="SET NULL"), nullable=True)  # Draft-friendly
    dm_exam_mode = Column(String, nullable=True)  #  Draft-friendly

    dm_total_time = Column(Integer, nullable=True, comment="Total duration of the exam in minutes")  # Draft-friendly
    dm_total_questions = Column(Integer, nullable=True, comment="Total number of questions")  # Draft-friendly
    dm_no_of_versions = Column(Integer, nullable=True, comment="Number of versions")  # Draft-friendly
    dm_no_of_sets = Column(Integer, nullable=True, comment="Number of sets")  # Draft-friendly

    dm_subject_id = Column(Integer, ForeignKey("subject_master_table.id", ondelete="SET NULL"), nullable=True)  # Draft-friendly
    dm_medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="SET NULL"), nullable=True)  # Draft-friendly
    dm_standard = Column(String, nullable=True)  # Draft-friendly
    division = Column(String(100), nullable=True)  # Division field
    
    dm_status = Column(Enum("draft", "closed", name="dm_status_enum"), nullable=False, server_default="draft")
    dm_total_question_codes = Column(JSON, nullable=True)  # Draft: No questions yet

    dm_chapter_topics = Column(JSON, nullable=True)
    dm_questions_to_exclude = Column(JSON, nullable=True)
    
    # Organizational hierarchy fields
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    block_id = Column(Integer, ForeignKey("blocks.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    
    # Exam hierarchy field (nullable - designs can exist without exam)
    exam_id = Column(Integer, ForeignKey("exam_master.id", ondelete="CASCADE"), nullable=True)
    
    # Soft delete flag
    is_active = Column(Boolean, default=True)

    # Relationships
    subject = relationship("Subject", back_populates="designs")
    medium = relationship("Medium", back_populates="designs")
    type = relationship("Question_Type", back_populates="designs")
    question_papers = relationship("QuestionPaperDetails", back_populates="design", cascade="all, delete-orphan")
    organization = relationship("Organization", back_populates="designs")
    block = relationship("Block", back_populates="designs")
    school = relationship("School", back_populates="designs")
    exam = relationship("ExamMaster", back_populates="designs")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(Design.created_by) == User.id", back_populates="created_designs")
    updated_by_user = relationship("User", primaryjoin="foreign(Design.updated_by) == User.id", back_populates="updated_designs")


class QuestionPaperDetails(Base, AuditMixin):
    __tablename__ = "question_paper_details"

    id = Column(Integer, primary_key=True, index=True) # primary key
    qpd_paper_id = Column(Text, nullable=False) # paper code for each questionpaper
    qpd_q_codes = Column(JSON, nullable=False) #question codes of each questionpaper
    qpd_total_time = Column(Integer,nullable=False)
    qpd_total_questions = Column(Integer,nullable=False)# total no of questions for each qustion paper
    qpd_design_name = Column(Text,nullable=False) #design name form Design table
    qpd_design_id = Column(Integer, ForeignKey("design_master.id", ondelete="CASCADE"), nullable=False)# primary key from the design table

    # Relationships
    design = relationship("Design", back_populates="question_papers")


class JobStatusEnum(enum.Enum):
    """Enum for upload job status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadJob(Base, AuditMixin):
    """Model for tracking async upload job processing"""
    __tablename__ = "upload_jobs"

    id = Column(String, primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    status = Column(Enum(JobStatusEnum), nullable=False, default=JobStatusEnum.PENDING)
    total_rows = Column(Integer, nullable=True)
    processed_rows = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    error_details = Column(JSON, nullable=True)
    result_message = Column(Text, nullable=True)
    result_loc = Column(String, nullable=True)  # S3 URL for result file
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="upload_jobs")






    



    

