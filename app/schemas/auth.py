from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum
import uuid
from app.utils.auth import validate_password_strength

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    role_code: str
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    phone: Optional[str] = Field(None, max_length=15)
    organization_uuid: Optional[uuid.UUID] = None
    block_uuid: Optional[uuid.UUID] = None
    school_uuid: Optional[uuid.UUID] = None
    staff_id: Optional[str] = Field(None, max_length=100, description="Staff ID for teachers")
    boards: Optional[List[int]] = Field(None, description="List of board IDs for teachers")

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not validate_password_strength(v):
            raise ValueError(
                'Password must be at least 8 characters long and contain at least '
                '1 lowercase letter, 1 uppercase letter, and 1 special character'
            )
        return v

    model_config = ConfigDict(from_attributes=True)

class RoleResponse(BaseModel):
    role_code: str
    role_name: str

    class Config:
        from_attributes = True

class RoleListResponse(BaseModel):
    data: List[RoleResponse]

class LoginRequest(BaseModel):
    username: str
    password: str

    class Config:
        from_attributes = True 

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    user_uuid: uuid.UUID
    role_name: str
    role_code: str


from pydantic import BaseModel
from typing import List, Optional

class RoleResponse(BaseModel):
    uuid: uuid.UUID
    role_code: str
    role_name: str


class OrganizationInfo(BaseModel):
    uuid: uuid.UUID
    org_name: str
    org_code: str

    model_config = ConfigDict(from_attributes=True)

class BlockInfo(BaseModel):
    uuid: uuid.UUID
    block_name: str
    block_code: str

    model_config = ConfigDict(from_attributes=True)

class SchoolInfo(BaseModel):
    uuid: uuid.UUID
    school_name: str
    udise_code: str

    model_config = ConfigDict(from_attributes=True)

class UserResponse(BaseModel):
    uuid: uuid.UUID
    username: str
    full_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    role: RoleResponse
    organization: Optional[OrganizationInfo]
    block: Optional[BlockInfo]
    school: Optional[SchoolInfo]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    grandTotal: int = Field(..., description="Total number of all users")

    model_config = ConfigDict(from_attributes=True)

class PasswordUpdateRequest(BaseModel):
    new_password: str = Field(..., min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        if not validate_password_strength(v):
            raise ValueError(
                'Password must be at least 8 characters long and contain at least '
                '1 lowercase letter, 1 uppercase letter, and 1 special character'
            )
        return v

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    role_code: Optional[str] = None
    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    phone: Optional[str] = Field(None, max_length=15)
    is_active: Optional[bool] = None
    organization_uuid: Optional[uuid.UUID] = None
    block_uuid: Optional[uuid.UUID] = None
    school_uuid: Optional[uuid.UUID] = None

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if v and '@' not in v:
            raise ValueError('Invalid email format')
        return v

    model_config = ConfigDict(from_attributes=True)

class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3)
    role_code: Optional[str]
    is_active: Optional[bool]