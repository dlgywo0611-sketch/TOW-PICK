from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str


class MessageRead(MessageCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str
    nickname: str


class UserRead(UserCreate):
    id: int
    couple_id: int | None

    model_config = ConfigDict(from_attributes=True)


class CoupleCreate(BaseModel):
    user_id: int


class CoupleJoin(BaseModel):
    user_id: int
    invite_code: str


class CoupleRead(BaseModel):
    id: int
    invite_code: str
    members: list[UserRead]

    model_config = ConfigDict(from_attributes=True)