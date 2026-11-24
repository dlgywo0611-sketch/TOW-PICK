from pydantic import BaseModel, ConfigDict


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
