"""Server-side notification claims and gated test delivery results.

This module makes no email or n8n request. All timestamps stored in SQLite are
UTC without an offset, matching the existing NotificationJob.send_at column.
"""

import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import models
import notification_logic

SEND_WINDOW = timedelta(minutes=10)  # Existing prepare_mock_payload contract.
CLAIM_TIMEOUT = timedelta(minutes=2)
MAX_ATTEMPTS = 3
TEST_EMAIL_CLAIM_LIMIT = 2


class DispatchConflict(ValueError):
    pass


def utc_naive(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def latest_attempt(db: Session, job_id: int) -> models.NotificationDispatchAttempt | None:
    return db.scalar(select(models.NotificationDispatchAttempt).where(
        models.NotificationDispatchAttempt.job_id == job_id,
    ).order_by(models.NotificationDispatchAttempt.number.desc()).limit(1))


def _valid_context(db: Session, job: models.NotificationJob) -> bool:
    schedule = db.get(models.CoupleSchedule, job.schedule_id)
    user = db.get(models.User, job.recipient_user_id)
    setting = db.get(models.NotificationSetting, job.recipient_user_id)
    return bool(
        schedule is not None and schedule.deleted_at is None
        and schedule.revision == job.schedule_revision
        and user is not None and user.couple_id == schedule.couple_id
        and user.email and user.email.lower().endswith("@example.test")
        and setting is not None and setting.consent
        and setting.policy_version == notification_logic.POLICY_VERSION
        and ((job.notification_type == "d1" and setting.d1_enabled)
             or (job.notification_type == "day_of" and setting.day_of_enabled))
    )


def refresh_stale(db: Session, now: datetime | None = None) -> None:
    """Never auto-reclaim a run whose outcome is unknown after interruption."""
    current = utc_naive(now)
    for job in db.scalars(select(models.NotificationJob).where(
        models.NotificationJob.status == "claimed",
    )):
        attempt = latest_attempt(db, job.id)
        if attempt and attempt.claimed_at + CLAIM_TIMEOUT < current:
            attempt.status = "unknown"
            attempt.completed_at = current
            attempt.error_code = "claim_timeout"
            job.status = "unknown"
            job.failed_at = current


def due_job_ids(db: Session, now: datetime | None = None) -> list[int]:
    current = utc_naive(now)
    refresh_stale(db, current.replace(tzinfo=timezone.utc))
    jobs = db.scalars(select(models.NotificationJob).where(
        models.NotificationJob.status == "pending",
        models.NotificationJob.send_at <= current,
    ).order_by(models.NotificationJob.send_at, models.NotificationJob.id).limit(100)).all()
    ready = []
    for job in jobs:
        if current > job.send_at + SEND_WINDOW:
            job.status = "expired"
            job.failed_at = current
            continue
        if not _valid_context(db, job):
            job.status = "canceled"
            continue
        attempt = latest_attempt(db, job.id)
        if attempt is None or attempt.retry_after is None or attempt.retry_after <= current:
            ready.append(job.id)
    return ready


def test_email_target() -> str | None:
    target = os.getenv("TWO_PICK_N8N_TEST_RECIPIENT", "").strip()
    if (os.getenv("TWO_PICK_N8N_ENABLE_TEST_EMAIL") != "1"
            or not target or "@" not in target):
        return None
    return target


def claim_job(db: Session, job_id: int, now: datetime | None = None,
              *, mode: str = "mock") -> dict:
    current = utc_naive(now)
    if mode not in ("mock", "test_email"):
        raise DispatchConflict("Unsupported dispatch mode")
    job = db.get(models.NotificationJob, job_id)
    if job is None or job.status != "pending":
        raise DispatchConflict("Job is not pending")
    if not job.send_at <= current <= job.send_at + SEND_WINDOW:
        raise DispatchConflict("Job is outside the send window")
    attempt = latest_attempt(db, job_id)
    if attempt and attempt.retry_after and attempt.retry_after > current:
        raise DispatchConflict("Retry is not due")
    if job.attempt_count >= MAX_ATTEMPTS or not _valid_context(db, job):
        raise DispatchConflict("Job is no longer eligible")
    if mode == "test_email":
        if test_email_target() is None:
            raise DispatchConflict("Test email delivery is disabled")
        claim_count = db.scalar(select(func.count(models.NotificationDispatchAttempt.id)).where(
            models.NotificationDispatchAttempt.mode == "test_email"))
        if claim_count >= TEST_EMAIL_CLAIM_LIMIT:
            raise DispatchConflict("Test email claim limit reached")
    notification_logic.prepare_mock_payload(
        db, job_id, now=current.replace(tzinfo=timezone.utc))
    job.attempt_count += 1
    job.status = "claimed"
    db.add(models.NotificationDispatchAttempt(
        job_id=job.id, number=job.attempt_count, mode=mode, status="claimed",
        claimed_at=current,
    ))
    db.flush()
    # The mock workflow only needs routing metadata. In the separately gated
    # email test, the approved destination is supplied from the local env.
    response = {"job_id": job.id, "attempt": job.attempt_count,
                "notification_type": job.notification_type, "mode": mode}
    if mode == "test_email":
        response["recipient_email"] = test_email_target()
    return response


def verify_claim(db: Session, job_id: int, now: datetime | None = None) -> bool:
    current = utc_naive(now)
    job = db.get(models.NotificationJob, job_id)
    attempt = latest_attempt(db, job_id) if job else None
    return bool(job and job.status == "claimed" and attempt
                and attempt.status == "claimed"
                and attempt.claimed_at + CLAIM_TIMEOUT >= current
                and current <= job.send_at + SEND_WINDOW
                and _valid_context(db, job)
                and (attempt.mode != "test_email" or test_email_target() is not None))


def finish_job(db: Session, job_id: int, *, attempt_number: int,
               result: str, error_code: str | None = None,
               provider_message_id: str | None = None,
               now: datetime | None = None) -> dict:
    current = utc_naive(now)
    job = db.get(models.NotificationJob, job_id)
    attempt = latest_attempt(db, job_id) if job else None
    if not job or not attempt or attempt.number != attempt_number:
        raise DispatchConflict("Claim does not match the job")
    if (attempt.status == result
            and (result != "failed" or attempt.error_code == error_code)
            and (result != "sent" or attempt.provider_message_id == provider_message_id)):
        return {"job_id": job.id, "status": job.status,
                "attempt": attempt.number, "idempotent": True}
    if job.status != "claimed" or attempt.status != "claimed":
        raise DispatchConflict("Claim is no longer active")
    if result == "sent" and (attempt.mode != "test_email"
                            or not provider_message_id):
        raise DispatchConflict("Sent result requires a claimed test email and receipt")
    if result == "simulated" and attempt.mode != "mock":
        raise DispatchConflict("Mock result requires a mock claim")
    if result == "simulated":
        if not verify_claim(db, job_id, now=current.replace(tzinfo=timezone.utc)):
            attempt.status = "canceled"
            attempt.completed_at = current
            job.status = "canceled"
            db.flush()
            return {"job_id": job.id, "status": job.status,
                    "attempt": attempt.number, "idempotent": False}
        job.status = "simulated"
        attempt.status = "simulated"
        # A mock result must not set succeeded_at or imply an email was sent.
        schedule = db.get(models.CoupleSchedule, job.schedule_id)
        if schedule is not None and schedule.deleted_at is None:
            notification_logic.plan_next_jobs(
                db, schedule, now=current.replace(tzinfo=timezone.utc))
    elif result == "sent":
        job.status = "sent"
        job.succeeded_at = current
        attempt.status = "sent"
        attempt.provider_message_id = provider_message_id
        schedule = db.get(models.CoupleSchedule, job.schedule_id)
        if schedule is not None and schedule.deleted_at is None:
            notification_logic.plan_next_jobs(
                db, schedule, now=current.replace(tzinfo=timezone.utc))
    elif result == "canceled":
        attempt.status = "canceled"
        job.status = "canceled"
    elif result == "failed":
        attempt.status = "failed"
        attempt.error_code = error_code
        job.failed_at = current
        if error_code in {"timeout", "result_unknown"}:
            job.status = "unknown"
        elif error_code == "auth_error":
            job.status = "failed"
        elif (attempt.mode == "mock" and job.attempt_count < MAX_ATTEMPTS
              and current < job.send_at + SEND_WINDOW):
            attempt.retry_after = current + timedelta(seconds=60 * job.attempt_count)
            job.status = "pending"
        else:
            job.status = "failed"
    else:
        raise ValueError("Unsupported dispatch result")
    attempt.completed_at = current
    db.flush()
    return {"job_id": job.id, "status": job.status,
            "attempt": attempt.number, "idempotent": False}
