from pydantic import BaseModel, ConfigDict


class MessageCreate(BaseModel):
    content: str


class MessageRead(MessageCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)