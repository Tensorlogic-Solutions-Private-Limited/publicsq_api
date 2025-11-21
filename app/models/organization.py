from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, CheckConstraint, JSON, and_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, foreign
import uuid
from app.database import Base
from app.models.audit_mixin import AuditMixin


class Organization(Base, AuditMixin):
    """Organization model representing the top level of the hierarchy."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    org_code = Column(String, unique=True, nullable=False)
    org_name = Column(String, unique=True, nullable=False)
    org_description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    blocks = relationship("Block", back_populates="organization", cascade="all, delete-orphan")
    schools = relationship("School", back_populates="organization", cascade="all, delete-orphan")
    active_schools = relationship("School", back_populates="organization", 
                                primaryjoin="and_(Organization.id == School.organization_id, School.is_active == True)")
    users = relationship("User", back_populates="organization")
    questions = relationship("Questions", back_populates="organization")
    designs = relationship("Design", back_populates="organization")
    exams = relationship("ExamMaster", back_populates="organization")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(Organization.created_by) == User.id", back_populates="created_organizations")
    updated_by_user = relationship("User", primaryjoin="foreign(Organization.updated_by) == User.id", back_populates="updated_organizations")

    @property
    def created_by_username(self):
        """Get the username of the user who created this organization."""
        return self.created_by_user.username if self.created_by_user else None
    
    @property
    def updated_by_username(self):
        """Get the username of the user who last updated this organization."""
        return self.updated_by_user.username if self.updated_by_user else None

    def __repr__(self):
        return f"<Organization(id={self.id}, org_code='{self.org_code}', org_name='{self.org_name}')>"


class Block(Base, AuditMixin):
    """Block model representing the middle level of the hierarchy."""
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    block_code = Column(String, unique=True, nullable=False)
    block_name = Column(String, nullable=False)
    block_description = Column(Text, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False)
    state_id = Column(Integer, ForeignKey("state_master.id", ondelete="RESTRICT"), nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    organization = relationship("Organization", back_populates="blocks")
    state = relationship("State", back_populates="blocks")
    schools = relationship("School", back_populates="block", cascade="all, delete-orphan")
    active_schools = relationship("School", back_populates="block", 
                                primaryjoin="and_(Block.id == School.block_id, School.is_active == True)")
    users = relationship("User", back_populates="block")
    questions = relationship("Questions", back_populates="block")
    designs = relationship("Design", back_populates="block")
    exams = relationship("ExamMaster", back_populates="block")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(Block.created_by) == User.id", back_populates="created_blocks")
    updated_by_user = relationship("User", primaryjoin="foreign(Block.updated_by) == User.id", back_populates="updated_blocks")

    @property
    def organization_uuid(self):
        """Get the organization UUID for this block."""
        return self.organization.uuid if self.organization else None
    
    @property
    def created_by_username(self):
        """Get the username of the user who created this block."""
        return self.created_by_user.username if self.created_by_user else None
    
    @property
    def updated_by_username(self):
        """Get the username of the user who last updated this block."""
        return self.updated_by_user.username if self.updated_by_user else None

    def __repr__(self):
        return f"<Block(id={self.id}, uuid='{self.uuid}', block_code='{self.block_code}', block_name='{self.block_name}')>"


class School(Base, AuditMixin):
    """School model representing the bottom level of the hierarchy."""
    __tablename__ = "schools"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True)
    udise_code = Column(String, unique=True, nullable=False)
    school_name = Column(String, nullable=False)
    school_description = Column(Text, nullable=True)
    address = Column(Text, nullable=True)  # New field
    local_govt_body_id = Column(String, nullable=True)
    state_id = Column(Integer, ForeignKey("state_master.id", ondelete="SET NULL"), nullable=True) 
    block_id = Column(Integer, ForeignKey("blocks.id", ondelete="SET NULL"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Image storage columns
    logo_image_url = Column(Text, nullable=True)
    other_images_urls = Column(JSON, nullable=True, default=list)

    # Relationships
    organization = relationship("Organization", back_populates="schools")
    block = relationship("Block", back_populates="schools")
    state = relationship("State", back_populates="schools")
    users = relationship("User", back_populates="school")
    questions = relationship("Questions", back_populates="school")
    designs = relationship("Design", back_populates="school")
    exams = relationship("ExamMaster", back_populates="school")
    school_boards = relationship("SchoolBoard", back_populates="school", cascade="all, delete-orphan")
    
    # Audit field relationships
    created_by_user = relationship("User", primaryjoin="foreign(School.created_by) == User.id", back_populates="created_schools")
    updated_by_user = relationship("User", primaryjoin="foreign(School.updated_by) == User.id", back_populates="updated_schools")

    @property
    def block_uuid(self):
        """Get the block UUID for this school."""
        return self.block.uuid if self.block else None
    
    @property
    def organization_uuid(self):
        """Get the organization UUID for this school."""
        return self.organization.uuid if self.organization else None
    
    @property
    def boards(self):
        """Get the list of board IDs for this school."""
        return [sb.board_id for sb in self.school_boards if sb.is_active] if self.school_boards else []
    
    @property
    def created_by_username(self):
        """Get the username of the user who created this school."""
        return self.created_by_user.username if self.created_by_user else None
    
    @property
    def updated_by_username(self):
        """Get the username of the user who last updated this school."""
        return self.updated_by_user.username if self.updated_by_user else None

    def __repr__(self):
        return f"<School(id={self.id}, uuid='{self.uuid}', udise_code='{self.udise_code}', school_name='{self.school_name}')>"


class SchoolBoard(Base, AuditMixin):
    """Many-to-many relationship between schools and boards."""
    __tablename__ = "school_boards"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(Integer, ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    board_id = Column(Integer, ForeignKey("board_master.id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    school = relationship("School", back_populates="school_boards")
    board = relationship("Board", back_populates="school_boards")
    school_board_classes = relationship("SchoolBoardClass", back_populates="school_board", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SchoolBoard(id={self.id}, school_id={self.school_id}, board_id={self.board_id})>"


class SchoolBoardClass(Base, AuditMixin):
    """Class levels for each school-board combination."""
    __tablename__ = "school_board_classes"

    id = Column(Integer, primary_key=True, index=True)
    school_board_id = Column(Integer, ForeignKey("school_boards.id", ondelete="CASCADE"), nullable=False)
    class_level = Column(Integer, nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    school_board = relationship("SchoolBoard", back_populates="school_board_classes")

    def __repr__(self):
        return f"<SchoolBoardClass(id={self.id}, school_board_id={self.school_board_id}, class_level={self.class_level})>"