from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    content: Mapped[str] = mapped_column(String(500))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    couple_id: Mapped[int] = mapped_column(
        ForeignKey("couples.id"),
        index=True,
    )


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
    hashed_password: Mapped[str] = mapped_column(String(255))
    couple_id: Mapped[int | None] = mapped_column(
        ForeignKey("couples.id"),
        nullable=True,
    )

    couple: Mapped[Couple | None] = relationship(back_populates="members")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )

class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    couple_id: Mapped[int] = mapped_column(
        ForeignKey("couples.id"),
        index=True,
    )
    created_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
    )


class DecisionCondition(Base):
    __tablename__ = "decision_conditions"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "user_id",
            name="uq_decision_condition_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    max_budget: Mapped[int] = mapped_column(Integer)
    available_time: Mapped[str] = mapped_column(String(200))
    preferences: Mapped[str] = mapped_column(String(1000))
    avoidances: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class DecisionCandidate(Base):
    __tablename__ = "decision_candidates"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "version",
            name="uq_decision_candidate_version",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id"),
        index=True,
    )
    content: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(default=1)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )


class DecisionApproval(Base):
    __tablename__ = "decision_approvals"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "user_id",
            name="uq_candidate_user_approval",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("decision_candidates.id"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    approved: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )
