from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreate(BaseModel):
    content: str


class MessageRead(MessageCreate):
    id: int
    sender_id: int
    couple_id: int
    
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str
    nickname: str
    password: str


class UserRead(BaseModel):
    id: int
    email: str
    nickname: str
    couple_id: int | None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class CoupleJoin(BaseModel):
    invite_code: str


class CoupleRead(BaseModel):
    id: int
    invite_code: str
    members: list[UserRead]

    model_config = ConfigDict(from_attributes=True)

class DecisionCreate(BaseModel):
    title: str


class DecisionRead(BaseModel):
    id: int
    couple_id: int
    created_by_id: int
    title: str
    status: str

    model_config = ConfigDict(from_attributes=True)


class DecisionMemberApprovalRead(BaseModel):
    user_id: int
    approved: bool


class DecisionCandidateStatusRead(BaseModel):
    id: int
    decision_id: int
    content: str
    version: int
    is_current: bool
    approval_count: int
    member_approvals: list[DecisionMemberApprovalRead]


class DecisionDetailRead(DecisionRead):
    current_candidate: DecisionCandidateStatusRead | None
    confirmed: bool


class DecisionConditionUpsert(BaseModel):
    max_budget: int = Field(ge=0, le=1_000_000_000)
    available_time: str = Field(min_length=1, max_length=200)
    preferences: str = Field(max_length=1000)
    avoidances: str = Field(max_length=1000)

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class DecisionConditionRead(DecisionConditionUpsert):
    id: int
    decision_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionConditionMemberStatusRead(BaseModel):
    user_id: int
    submitted: bool


class DecisionConditionStatusRead(BaseModel):
    decision_id: int
    submitted_count: int
    member_conditions: list[DecisionConditionMemberStatusRead]


class DecisionCandidateCreate(BaseModel):
    content: str


class DecisionCandidateRead(BaseModel):
    id: int
    decision_id: int
    content: str
    version: int
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


class DecisionApprovalRead(BaseModel):
    id: int
    candidate_id: int
    user_id: int
    approved: bool

    model_config = ConfigDict(from_attributes=True)
