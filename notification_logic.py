"""Local, unsent notification planning. No n8n or email request occurs here."""

import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from schedule_logic import occurrence_on_or_after

try:
    KST = ZoneInfo("Asia/Seoul")
except ZoneInfoNotFoundError:
    # Windows development images may lack tzdata. This fallback is valid for
    # the contemporary MVP schedule range, but historical DST is not modeled.
    KST = timezone(timedelta(hours=9), "Asia/Seoul")
POLICY_VERSION = "care_reminder_v1"


def cancel_pending(db: Session, *, schedule_id: int | None = None,
                   recipient_user_id: int | None = None) -> None:
    query = select(models.NotificationJob).where(models.NotificationJob.status == "pending")
    if schedule_id is not None:
        query = query.where(models.NotificationJob.schedule_id == schedule_id)
    if recipient_user_id is not None:
        query = query.where(models.NotificationJob.recipient_user_id == recipient_user_id)
    for job in db.scalars(query):
        job.status = "canceled"


def plan_next_jobs(db: Session, schedule: models.CoupleSchedule,
                   now: datetime | None = None) -> None:
    """Plan the next eligible D-1/day-of occurrence for each consenting member."""
    now = now or datetime.now(timezone.utc)
    local_today = now.astimezone(KST).date()
    users = db.scalars(select(models.User).where(
        models.User.couple_id == schedule.couple_id,
    )).all()
    for user in users:
        setting = db.get(models.NotificationSetting, user.id)
        if setting is None or not setting.consent or not user.email:
            continue
        for kind, enabled, offset in (
            ("d1", setting.d1_enabled, 1),
            ("day_of", setting.day_of_enabled, 0),
        ):
            if not enabled:
                continue
            if (kind == "day_of" and schedule.local_time is not None
                    and setting.send_time > schedule.local_time):
                continue
            # At most the next occurrence is planned. A future dispatcher must
            # advance recurring jobs after successful delivery.
            target = local_today + timedelta(days=offset)
            occurrence = occurrence_on_or_after(schedule.local_date,
                                               schedule.repeat_rule, target)
            if occurrence is None:
                continue
            local_send = datetime.combine(occurrence - timedelta(days=offset),
                                          setting.send_time, tzinfo=KST)
            send_at = local_send.astimezone(timezone.utc).replace(tzinfo=None)
            if send_at <= now.astimezone(timezone.utc).replace(tzinfo=None):
                continue
            raw_key = (f"{schedule.id}:{schedule.revision}:{user.id}:"
                       f"{kind}:{occurrence.isoformat()}")
            key = hashlib.sha256(raw_key.encode()).hexdigest()
            existing = db.scalar(select(models.NotificationJob).where(
                models.NotificationJob.dedupe_key == key,
            ))
            if existing is not None:
                if existing.status == "canceled":
                    existing.status = "pending"
                    existing.send_at = send_at
                continue
            db.add(models.NotificationJob(
                schedule_id=schedule.id, schedule_revision=schedule.revision,
                recipient_user_id=user.id, notification_type=kind,
                occurrence_date=occurrence, send_at=send_at,
                dedupe_key=key, status="pending", attempt_count=0,
            ))
    db.flush()


def prepare_mock_payload(db: Session, job_id: int,
                         now: datetime | None = None) -> dict:
    """Recheck consent and revision immediately before a future n8n handoff."""
    job = db.get(models.NotificationJob, job_id)
    if job is None or job.status != "pending":
        raise ValueError("Job is not pending")
    schedule = db.get(models.CoupleSchedule, job.schedule_id)
    user = db.get(models.User, job.recipient_user_id)
    setting = db.get(models.NotificationSetting, job.recipient_user_id)
    if (schedule is None or schedule.deleted_at is not None
            or user is None or setting is None
            or not setting.consent or not user.email
            or user.couple_id != schedule.couple_id
            or schedule.revision != job.schedule_revision
            or (job.notification_type == "d1" and not setting.d1_enabled)
            or (job.notification_type == "day_of" and not setting.day_of_enabled)):
        raise ValueError("Consent, recipient, or schedule changed")
    now = now or datetime.now(timezone.utc)
    utc_now = now.astimezone(timezone.utc).replace(tzinfo=None)
    if not job.send_at <= utc_now <= job.send_at + timedelta(minutes=10):
        raise ValueError("Job is outside its send window")
    return {
        "job_id": job.id,
        "schedule_id": job.schedule_id,
        "notification_type": job.notification_type,
        "occurrence_date": job.occurrence_date.isoformat(),
        "send_at": job.send_at.isoformat() + "Z",
        "recipient_email": user.email,
        "dedupe_key": job.dedupe_key,
        "message": "등록한 일정 알림입니다.",
    }
