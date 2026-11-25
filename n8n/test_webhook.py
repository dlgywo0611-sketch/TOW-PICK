"""One-shot local n8n Webhook smoke test using an isolated synthetic SQLite DB."""

import argparse
import hashlib
import secrets
from dataclasses import replace
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from database import Base
from notification_logic import KST, POLICY_VERSION, prepare_mock_payload
from n8n.webhook_client import WebhookConfig, WebhookError, send_test_webhook

EXPECTED_STATUS = {
    "valid": 200,
    "missing-field": 400,
    "unexpected-field": 400,
    "missing-auth": 403,
    "wrong-auth": 403,
}


def build_synthetic_payload() -> dict:
    """Never touches the repository's tow_pick.db or a real email address."""
    with TemporaryDirectory(prefix="two-pick-n8n-") as directory:
        engine = create_engine(f"sqlite:///{(Path(directory) / 'test.db').as_posix()}")
        try:
            Base.metadata.create_all(engine)
            now = datetime.now(timezone.utc)
            due_at = now - timedelta(seconds=30)
            occurrence = due_at.astimezone(KST).date() + timedelta(days=1)
            with Session(engine) as db:
                couple = models.Couple(invite_code="N8NTEST1")
                db.add(couple)
                db.flush()
                user = models.User(email="n8n-smoke@example.test", nickname="test",
                                   hashed_password="synthetic-unused", couple_id=couple.id)
                db.add(user)
                db.flush()
                schedule = models.CoupleSchedule(
                    couple_id=couple.id, created_by_id=user.id,
                    title="가상 일정", kind="schedule", local_date=occurrence,
                    local_time=None, repeat_rule="none", revision=1,
                )
                db.add(schedule)
                db.flush()
                setting = models.NotificationSetting(
                    user_id=user.id, consent=True, d1_enabled=True,
                    day_of_enabled=False, send_time=time(9),
                    policy_version=POLICY_VERSION, consented_at=now,
                )
                db.add(setting)
                key_source = f"{schedule.id}:1:{user.id}:d1:{occurrence.isoformat()}"
                job = models.NotificationJob(
                    schedule_id=schedule.id, schedule_revision=1,
                    recipient_user_id=user.id, notification_type="d1",
                    occurrence_date=occurrence,
                    send_at=due_at.replace(tzinfo=None),
                    dedupe_key=hashlib.sha256(key_source.encode()).hexdigest(),
                    status="pending", attempt_count=0,
                )
                db.add(job)
                db.flush()
                return prepare_mock_payload(db, job.id, now=now)
        finally:
            engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=EXPECTED_STATUS, default="valid")
    parser.add_argument("--live", action="store_true",
                        help="Send one request to the local n8n test listener")
    args = parser.parse_args()
    payload = build_synthetic_payload()
    if args.case == "missing-field":
        payload.pop("schedule_id")
    elif args.case == "unexpected-field":
        payload["unexpected_test_field"] = "synthetic"
    if not args.live:
        print(f"DRY RUN: synthetic payload ready for {args.case}; no HTTP request sent")
        return 0

    load_dotenv()
    try:
        config = WebhookConfig.from_environment()
        if args.case == "missing-auth":
            config = replace(config, secret=None)
        elif args.case == "wrong-auth":
            config = replace(config, secret=secrets.token_urlsafe(32))
        result = send_test_webhook(payload, config)
    except (ValueError, WebhookError) as error:
        print(f"FAIL {args.case}: {type(error).__name__}: {error}")
        return 1
    passed = result.status_code == EXPECTED_STATUS[args.case]
    print(f"{'PASS' if passed else 'FAIL'} {args.case}: HTTP {result.status_code}; "
          f"expected {EXPECTED_STATUS[args.case]}; success={result.success}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
