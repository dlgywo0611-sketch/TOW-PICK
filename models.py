from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Time,
    UniqueConstraint,
    text,
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


class CoupleInvite(Base):
    __tablename__ = "couple_invites"

    couple_id: Mapped[int] = mapped_column(
        ForeignKey("couples.id"), primary_key=True,
    )
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


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


class DecisionRecommendationAttempt(Base):
    """One recommendation evaluation per Decision, even if none matches.

    Do not persist user-supplied option pools, individual preference scores,
    private conditions or specific rejection reasons here.
    """

    __tablename__ = "decision_recommendation_attempts"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            name="uq_decision_recommendation_attempt",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id"),
        nullable=False,
        index=True,
    )
    requested_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("decision_candidates.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class DecisionCandidate(Base):
    __tablename__ = "decision_candidates"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "version",
            name="uq_decision_candidate_version",
        ),
        Index(
            "uq_decision_current_candidate", "decision_id", unique=True,
            sqlite_where=text("is_current = 1"),
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


class DecisionConfirmation(Base):
    __tablename__ = "decision_confirmations"

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(
        ForeignKey("decisions.id"), unique=True, nullable=False, index=True,
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("decision_candidates.id"), nullable=False,
    )
    candidate_version: Mapped[int] = mapped_column(nullable=False)
    content_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False,
    )


class DecisionFeedback(Base):
    __tablename__ = "decision_feedback"
    __table_args__ = (UniqueConstraint("decision_id", "user_id",
                                      name="uq_decision_feedback_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now,
    )


class CoupleSchedule(Base):
    __tablename__ = "couple_schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    local_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    repeat_rule: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    d1_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    day_of_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    send_time: Mapped[time] = mapped_column(Time, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationJob(Base):
    __tablename__ = "notification_jobs"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_job_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("couple_schedules.id"), index=True)
    schedule_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    notification_type: Mapped[str] = mapped_column(String(10), nullable=False)
    occurrence_date: Mapped[date] = mapped_column(Date, nullable=False)
    send_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDispatchAttempt(Base):
    """Durable claim/result ledger; new table preserves existing job rows."""

    __tablename__ = "notification_dispatch_attempts"
    __table_args__ = (UniqueConstraint("job_id", "number",
                                      name="uq_notification_dispatch_attempt"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("notification_jobs.id"), index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
