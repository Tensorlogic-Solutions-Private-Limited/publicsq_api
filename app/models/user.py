from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, foreign
import uuid
from app.database import Base
from app.models.audit_mixin import AuditMixin


class Role(Base, AuditMixin):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    role_code = Column(String, unique=True, nullable=False)
    role_name = Column(String, unique=True, nullable=False)
    users = relationship("User", back_populates="role", cascade="all, delete")
    role_permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

class User(Base, AuditMixin):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"), nullable=False)
    
    # Organizational hierarchy fields
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    block_id = Column(Integer, ForeignKey("blocks.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    
    # Teacher-specific fields
    staff_id = Column(String(100), nullable=True)
    boards = Column(JSON, nullable=True)
    
    # Relationships
    role = relationship("Role", back_populates="users")
    organization = relationship("Organization", back_populates="users")
    block = relationship("Block", back_populates="users")
    school = relationship("School", back_populates="users")
    upload_jobs = relationship("UploadJob", back_populates="user")
    teacher_classes = relationship("TeacherClass", back_populates="teacher", cascade="all, delete-orphan")
    
    # Audit field relationships
    created_organizations = relationship("Organization", primaryjoin="User.id == foreign(Organization.created_by)")
    updated_organizations = relationship("Organization", primaryjoin="User.id == foreign(Organization.updated_by)")
    created_blocks = relationship("Block", primaryjoin="User.id == foreign(Block.created_by)")
    updated_blocks = relationship("Block", primaryjoin="User.id == foreign(Block.updated_by)")
    created_schools = relationship("School", primaryjoin="User.id == foreign(School.created_by)")
    updated_schools = relationship("School", primaryjoin="User.id == foreign(School.updated_by)")
    created_states = relationship("State", primaryjoin="User.id == foreign(State.created_by)")
    updated_states = relationship("State", primaryjoin="User.id == foreign(State.updated_by)")
    created_questions = relationship("Questions", primaryjoin="User.id == foreign(Questions.created_by)")
    updated_questions = relationship("Questions", primaryjoin="User.id == foreign(Questions.updated_by)")
    created_designs = relationship("Design", primaryjoin="User.id == foreign(Design.created_by)")
    updated_designs = relationship("Design", primaryjoin="User.id == foreign(Design.updated_by)")
    created_exams = relationship("ExamMaster", primaryjoin="User.id == foreign(ExamMaster.created_by)")
    updated_exams = relationship("ExamMaster", primaryjoin="User.id == foreign(ExamMaster.updated_by)")
    created_taxonomies = relationship("Taxonomy", primaryjoin="User.id == foreign(Taxonomy.created_by)")
    updated_taxonomies = relationship("Taxonomy", primaryjoin="User.id == foreign(Taxonomy.updated_by)")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role.role_code if self.role else None}')>"


class TeacherClass(Base, AuditMixin):
    __tablename__ = "teacher_classes"
    
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    academic_year = Column(String(10), nullable=False)
    standard = Column(String(10), nullable=False)
    division = Column(String(10), nullable=False)
    medium_id = Column(Integer, ForeignKey("medium_master_table.id", ondelete="CASCADE"), nullable=False)
    subjects = Column(JSON, nullable=False)
    
    # Relationships
    teacher = relationship("User", back_populates="teacher_classes")
    medium = relationship("Medium", back_populates="teacher_classes")
    
    def __repr__(self):
        return f"<TeacherClass(id={self.id}, teacher_id={self.teacher_id}, academic_year='{self.academic_year}', standard='{self.standard}', division='{self.division}')>"