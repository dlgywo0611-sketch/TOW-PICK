from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(String(500))


class Couple(Base):
    __tablename__ = "couples"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invite_code: Mapped[str] = mapped_column(
        String(8),
        unique=True,
        index=True,
    )

    members: Mapped[list[User]] = relationship(back_populates="couple")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )
    nickname: Mapped[str] = mapped_column(String(50))
    couple_id: Mapped[int | None] = mapped_column(
        ForeignKey("couples.id"),
        nullable=True,
    )

    couple: Mapped[Couple | None] = relationship(back_populates="members")