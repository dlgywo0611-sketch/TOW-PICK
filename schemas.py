from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class RecommendationOption(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    estimated_total_cost_krw: int = Field(ge=0, le=1_000_000_000)
    time_slot: str = Field(min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=12)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for value in values:
            text = value.strip()
            if not text or len(text) > 60:
                raise ValueError("Each tag must be 1-60 nonblank characters")
            key = text.casefold()
            if key in seen:
                raise ValueError("Duplicate option tag")
            seen.add(key)
            cleaned.append(text)
        return cleaned

    @model_validator(mode="after")
    def check_text(self):
        if not self.title.strip() or not self.time_slot.strip():
            raise ValueError("Title and time slot must not be blank")
        return self


class RecommendationCreate(BaseModel):
    options: list[RecommendationOption] = Field(min_length=2, max_length=8)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def unique_titles(self):
        keys = [item.title.casefold() for item in self.options]
        if len(keys) != len(set(keys)):
            raise ValueError("Recommendation option titles must be unique")
        return self


class RecommendationRead(BaseModel):
    policy_version: str
    message: str
    candidate: DecisionCandidateRead


class DecisionApprovalRead(BaseModel):
    id: int
    candidate_id: int
    user_id: int
    approved: bool

    model_config = ConfigDict(from_attributes=True)
