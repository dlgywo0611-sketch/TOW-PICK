from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str


class MessageRead(MessageCreate):
    id: int

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