from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


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


class DecisionConfirmationRead(BaseModel):
    id: int
    decision_id: int
    candidate_id: int
    candidate_version: int
    content_snapshot: str
    confirmed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DecisionFeedbackUpsert(BaseModel):
    score: StrictInt = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DecisionFeedbackRead(DecisionFeedbackUpsert):
    id: int
    decision_id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CoupleScheduleInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: Literal["schedule", "anniversary"]
    local_date: date
    local_time: time | None = None
    repeat_rule: Literal["none", "weekly", "monthly", "yearly"] | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_schedule(self):
        if not self.title.strip():
            raise ValueError("Title cannot be blank")
        if self.local_time is not None and self.local_time.tzinfo is not None:
            raise ValueError("Use a local Asia/Seoul time without offset")
        if self.repeat_rule is None:
            self.repeat_rule = "yearly" if self.kind == "anniversary" else "none"
        if self.kind == "anniversary" and self.repeat_rule not in ("none", "yearly"):
            raise ValueError("Anniversary repeat must be none or yearly")
        return self


class CoupleScheduleRead(CoupleScheduleInput):
    id: int
    couple_id: int
    created_by_id: int
    revision: int
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingInput(BaseModel):
    consent: bool
    d1_enabled: bool = False
    day_of_enabled: bool = False
    send_time: time = time(9, 0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("send_time")
    @classmethod
    def local_time_only(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("Use a local Asia/Seoul time without offset")
        return value


class NotificationSettingRead(NotificationSettingInput):
    user_id: int
    policy_version: str
    consented_at: datetime | None = None
    withdrawn_at: datetime | None = None
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"


class NotificationDispatchResultInput(BaseModel):
    attempt: int = Field(ge=1)
    result: Literal["simulated", "sent", "failed", "canceled"]
    error_code: Literal[
        "connection_error", "http_error", "timeout", "auth_error",
        "delivery_failed", "result_unknown",
    ] | None = None
    provider_message_id: str | None = Field(default=None, min_length=1, max_length=255)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_error_code(self):
        if (self.result == "failed") != (self.error_code is not None):
            raise ValueError("error_code is required only for failed results")
        if (self.result == "sent") != (self.provider_message_id is not None):
            raise ValueError("provider_message_id is required only for sent results")
        return self


class NotificationClaimInput(BaseModel):
    mode: Literal["mock", "test_email"] = "mock"

    model_config = ConfigDict(extra="forbid")
