"""
Pydantic schemas for organizational hierarchy models.
"""
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid


# Base schemas
class OrganizationBase(BaseModel):
    """Base schema for Organization."""
    org_code: str = Field(..., min_length=1, max_length=50, description="Unique organization code")
    org_name: str = Field(..., min_length=1, max_length=200, description="Organization name")
    org_description: Optional[str] = Field(None, max_length=1000, description="Organization description")
    is_active: bool = Field(True, description="Whether the organization is active")

    @validator('org_code')
    def validate_org_code(cls, v):
        if not v or not v.strip():
            raise ValueError('Organization code cannot be empty')
        return v.strip().upper()

    @validator('org_name')
    def validate_org_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Organization name cannot be empty')
        return v.strip()


class BlockBase(BaseModel):
    """Base schema for Block."""
    block_code: str = Field(..., min_length=1, max_length=50, description="Unique block code")
    block_name: str = Field(..., min_length=1, max_length=200, description="Block name")
    block_description: Optional[str] = Field(None, max_length=1000, description="Block description")
    organization_uuid: uuid.UUID = Field(..., description="Organization UUID this block belongs to")
    state_id: int = Field(..., gt=0, description="State ID this block belongs to")
    is_active: bool = Field(True, description="Whether the block is active")

    @validator('block_code')
    def validate_block_code(cls, v):
        if not v or not v.strip():
            raise ValueError('Block code cannot be empty')
        return v.strip().upper()

    @validator('block_name')
    def validate_block_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Block name cannot be empty')
        return v.strip()


class SchoolBase(BaseModel):
    """Base schema for School."""
    udise_code: str = Field(..., min_length=1, max_length=50, description="Unique UDISE code")
    school_name: str = Field(..., min_length=1, max_length=200, description="School name")
    school_description: Optional[str] = Field(None, max_length=1000, description="School description")
    address: Optional[str] = Field(None, max_length=1000, description="School address")
    local_govt_body_id: Optional[str] = Field(None, max_length=255, description="Local government body ID")
    state_id: Optional[int] = Field(None, description="State ID")
    block_uuid: uuid.UUID = Field(..., description="Block UUID this school belongs to")
    organization_uuid: uuid.UUID = Field(..., description="Organization UUID this school belongs to")
    boards: List[int] = Field(..., min_items=1, description="List of board IDs (at least 1 required)")
    class_levels: Optional[List[int]] = Field(None, description="List of class levels (1-12)")
    is_active: bool = Field(True, description="Whether the school is active")

    @validator('udise_code')
    def validate_udise_code(cls, v):
        if not v or not v.strip():
            raise ValueError('UDISE code cannot be empty')
        return v.strip().upper()

    @validator('school_name')
    def validate_school_name(cls, v):
        if not v or not v.strip():
            raise ValueError('School name cannot be empty')
        return v.strip()

    @validator('class_levels')
    def validate_class_levels(cls, v):
        if v is not None:
            for level in v:
                if level <= 0:
                    raise ValueError('Class levels must be positive integers')
        return v

class SchoolSummary(BaseModel):
    uuid: uuid.UUID
    udise_code: str
    school_name: str


class SchoolCodeResponse(BaseModel):
    """Simple schema for school codes endpoint."""
    uuid: uuid.UUID
    school_name: str
    udise_code: str


class SchoolCodesListResponse(BaseModel):
    """Schema for school codes list response."""
    data: List[SchoolCodeResponse]


# Create schemas
class OrganizationCreate(OrganizationBase):
    """Schema for creating an organization."""
    pass


class BlockCreate(BlockBase):
    """Schema for creating a block."""
    
    @validator('state_id')
    def validate_state_id(cls, v):
        if v is None or v <= 0:
            raise ValueError('State ID must be a positive integer')
        return v


class SchoolCreate(SchoolBase):
    """Schema for creating a school."""
    pass


# Update schemas
class OrganizationUpdate(BaseModel):
    """Schema for updating an organization."""
    org_code: Optional[str] = Field(None, min_length=1, max_length=50)
    org_name: Optional[str] = Field(None, min_length=1, max_length=200)
    org_description: Optional[str] = Field(None, max_length=1000)
    is_active: Optional[bool] = None

    @validator('org_code')
    def validate_org_code(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Organization code cannot be empty')
            return v.strip().upper()
        return v

    @validator('org_name')
    def validate_org_name(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Organization name cannot be empty')
            return v.strip()
        return v


class BlockUpdate(BaseModel):
    """Schema for updating a block."""
    block_code: Optional[str] = Field(None, min_length=1, max_length=50)
    block_name: Optional[str] = Field(None, min_length=1, max_length=200)
    block_description: Optional[str] = Field(None, max_length=1000)
    organization_id: Optional[int] = Field(None, gt=0)
    state_id: Optional[int] = Field(None, gt=0, description="State ID this block belongs to")
    is_active: Optional[bool] = None

    @validator('block_code')
    def validate_block_code(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Block code cannot be empty')
            return v.strip().upper()
        return v

    @validator('block_name')
    def validate_block_name(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('Block name cannot be empty')
            return v.strip()
        return v

    @validator('state_id')
    def validate_state_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError('State ID must be a positive integer')
        return v


class SchoolUpdate(BaseModel):
    """Schema for updating a school."""
    udise_code: Optional[str] = Field(None, min_length=1, max_length=50)
    school_name: Optional[str] = Field(None, min_length=1, max_length=200)
    school_description: Optional[str] = Field(None, max_length=1000)
    address: Optional[str] = Field(None, max_length=1000)
    local_govt_body_id: Optional[str] = Field(None, max_length=255)
    state_id: Optional[int] = Field(None, gt=0)
    block_uuid: Optional[uuid.UUID] = None
    organization_uuid: Optional[uuid.UUID] = None
    boards: Optional[List[int]] = Field(None, min_items=1)
    class_levels: Optional[List[int]] = None
    is_active: Optional[bool] = None

    @validator('udise_code')
    def validate_udise_code(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('UDISE code cannot be empty')
            return v.strip().upper()
        return v

    @validator('school_name')
    def validate_school_name(cls, v):
        if v is not None:
            if not v or not v.strip():
                raise ValueError('School name cannot be empty')
            return v.strip()
        return v

    @validator('class_levels')
    def validate_class_levels(cls, v):
        if v is not None:
            for level in v:
                if level <= 0:
                    raise ValueError('Class levels must be positive integers')
        return v


# Response schemas
class OrganizationResponse(OrganizationBase):
    """Schema for organization response."""
    uuid: uuid.UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    model_config = {"from_attributes": True}


class BlockResponse(BlockBase):
    """Schema for block response."""
    uuid: uuid.UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    # Optional nested schools data
    schools: List[SchoolSummary] = []
    # State information
    state_name: Optional[str] = Field(None, description="Name of the state this block belongs to")
    
    # Optional nested organization data
    organization: Optional[OrganizationResponse] = None

    model_config = {"from_attributes": True}


class SchoolResponse(SchoolBase):
    """Schema for school response."""
    uuid: uuid.UUID
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    # Override boards field to allow empty list for responses (unlike create/update which require min_items=1)
    boards: List[int] = Field(default_factory=list, description="List of board IDs")
    
    # Optional nested organization and block data
    organization: Optional[OrganizationResponse] = None
    block: Optional[BlockResponse] = None

    model_config = {"from_attributes": True}


# List response schemas
class OrganizationListResponse(BaseModel):
    """Schema for organization list response."""
    data: List[OrganizationResponse]
    total: int
    page: int = 1
    page_size: int = 50
    grandTotal: int = Field(..., description="Total number of all organizations")


class BlockListResponse(BaseModel):
    """Schema for block list response."""
    data: List[BlockResponse]
    total: int
    page: int = 1
    page_size: int = 50
    grandTotal: int = Field(..., description="Total number of all blocks")


class SchoolListResponse(BaseModel):
    """Schema for school list response."""
    data: List[SchoolResponse]
    total: int
    page: int = 1
    page_size: int = 50
    grandTotal: int = Field(..., description="Total number of all schools")


# Detailed response schemas with relationships
class OrganizationDetailResponse(OrganizationResponse):
    """Detailed organization response with relationships."""
    blocks: List[BlockResponse] = []
    schools: List[SchoolResponse] = []


class BlockDetailResponse(BlockResponse):
    """Detailed block response with relationships."""
    schools: List[SchoolResponse] = []


class SchoolBoardResponse(BaseModel):
    """Schema for school-board relationship response."""
    id: int
    school_id: int
    board_id: int
    board_name: str
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[int]
    updated_by: Optional[int]


class SchoolBoardClassResponse(BaseModel):
    """Schema for school-board-class relationship response."""
    id: int
    school_board_id: int
    class_level: int
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    created_by: Optional[int]
    updated_by: Optional[int]


class SchoolDetailResponse(SchoolResponse):
    """Detailed school response with relationships."""
    school_boards: List[SchoolBoardResponse] = []
    state_name: Optional[str] = None


class RemoveBoardsRequest(BaseModel):
    """Schema for removing boards from a school."""
    board_ids: List[int] = Field(..., min_items=1, description="List of board IDs to remove from the school")
    
    @validator('board_ids')
    def validate_board_ids(cls, v):
        if not v:
            raise ValueError('At least one board ID must be provided')
        if len(set(v)) != len(v):
            raise ValueError('Duplicate board IDs are not allowed')
        for board_id in v:
            if board_id <= 0:
                raise ValueError('Board IDs must be positive integers')
        return v


class RemoveBoardsResponse(BaseModel):
    """Schema for remove boards response."""
    message: str
    school_uuid: uuid.UUID
    removed_board_ids: List[int]
    remaining_board_ids: List[int]