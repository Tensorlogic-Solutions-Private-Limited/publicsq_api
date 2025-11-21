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

# === Medium ===
class MediumBase(BaseModel):
    medium_code: str
    medium_name: str

class MediumResponse(BaseModel):
    data: List[MediumBase]

# === Subject ===

class SubjectBase(BaseModel):
    subject_code: str
    subject_name: str
    medium_code: str
    standard: str

    class Config:
        from_attributes = True
class SubjectListResponse(BaseModel):
    data: List[SubjectBase]

# === Format ===

class FormatBase(BaseModel):
    qfm_format_code: str
    qfm_format_name: str

    class Config:
        from_attributes = True
class FormatResponse(BaseModel):
    data: List[FormatBase] 

# === QuestionType ===

class QuestionTypeBase(BaseModel):
    type_code: str
    type_name: str

    class Config:
        from_attributes = True

class QuestionTypeListResponse(BaseModel):
    data: List[QuestionTypeBase]

# === Board ===

class BoardBase(BaseModel):
    board_id: int
    board_name: str

    class Config:
        from_attributes = True

class BoardResponse(BaseModel):
    data: List[BoardBase]

# === State ===

class StateBase(BaseModel):
    id: int
    state_name: str
    iso_code: Optional[str] = None

    class Config:
        from_attributes = True

class StateResponse(BaseModel):
    data: List[StateBase]