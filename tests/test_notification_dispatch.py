"""Isolated SQLite checks for internal notification claim and result handling."""

import os
import tempfile
import unittest
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

import main
import models
import notification_dispatch as dispatch
import notification_logic
from database import Base, ensure_notification_attempt_columns


class NotificationDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            "sqlite:///" + str(Path(self.temp.name) / "dispatch.db"),
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def sqlite_settings(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=5000")

        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.key = "synthetic-test-only-internal-key"
        self.env = patch.dict(os.environ, {"TWO_PICK_N8N_INTERNAL_SECRET": self.key})
        self.env.start()

        def db_override():
            with self.sessions() as db:
                yield db

        main.app.dependency_overrides[main.get_db] = db_override
        self.client = TestClient(main.app)
        self.headers = {"X-Two-Pick-Internal-Secret": self.key}
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.sessions() as db:
            couple = models.Couple(invite_code="DISP0001")
            db.add(couple)
            db.flush()
            user = models.User(email="dispatch@example.test", nickname="test",
                               hashed_password="unused", couple_id=couple.id)
            db.add(user)
            db.flush()
            setting = models.NotificationSetting(
                user_id=user.id, consent=True, d1_enabled=True,
                day_of_enabled=True, send_time=self.now.time(),
                policy_version="care_reminder_v1",
            )
            schedule = models.CoupleSchedule(
                couple_id=couple.id, created_by_id=user.id, title="가상 일정",
                kind="schedule", local_date=date.today(), local_time=None,
                repeat_rule="none", revision=1,
            )
            db.add_all([setting, schedule])
            db.flush()
            job = models.NotificationJob(
                schedule_id=schedule.id, schedule_revision=1,
                recipient_user_id=user.id, notification_type="day_of",
                occurrence_date=date.today(),
                send_at=self.now - timedelta(seconds=30),
                dedupe_key="a" * 64, status="pending", attempt_count=0,
            )
            db.add(job)
            db.commit()
            self.job_id = job.id
            self.schedule_id = schedule.id
            self.user_id = user.id

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.env.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def test_auth_due_claim_verify_and_idempotent_mock_result(self):
        path = "/internal/notifications/due"
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.get(path, headers={
            "X-Two-Pick-Internal-Secret": "wrong"}).status_code, 403)
        due = self.client.get(path, headers=self.headers)
        self.assertEqual(due.status_code, 200, due.text)
        self.assertEqual(due.json(), {"job_ids": [self.job_id]})
        self.assertNotIn("dispatch@example.test", due.text)
        claim_path = f"/internal/notifications/{self.job_id}/claim"
        claim = self.client.post(claim_path, headers=self.headers)
        self.assertEqual(claim.status_code, 200, claim.text)
        self.assertEqual(claim.json()["mode"], "mock")
        self.assertEqual(claim.json()["notification_type"], "day_of")
        self.assertNotIn("dispatch@example.test", claim.text)
        self.assertEqual(self.client.post(claim_path, headers=self.headers).status_code, 409)
        verify = self.client.post(f"/internal/notifications/{self.job_id}/verify",
                                  headers=self.headers)
        self.assertTrue(verify.json()["eligible"])
        result_path = f"/internal/notifications/{self.job_id}/result"
        body = {"attempt": 1, "result": "simulated"}
        result = self.client.post(result_path, json=body, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["status"], "simulated")
        duplicate = self.client.post(result_path, json=body, headers=self.headers)
        self.assertTrue(duplicate.json()["idempotent"])
        self.assertEqual(self.client.get(path, headers=self.headers).json()["job_ids"], [])
        with self.sessions() as db:
            job = db.get(models.NotificationJob, self.job_id)
            self.assertIsNone(job.succeeded_at)
            self.assertEqual(job.attempt_count, 1)
            self.assertEqual(db.scalar(select(func.count(models.NotificationDispatchAttempt.id))), 1)

    def test_concurrent_claim_only_one_wins(self):
        path = f"/internal/notifications/{self.job_id}/claim"

        def call():
            with TestClient(main.app) as client:
                return client.post(path, headers=self.headers).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(lambda _: call(), range(2)))
        self.assertEqual(sorted(codes), [200, 409])
        with self.sessions() as db:
            self.assertEqual(db.get(models.NotificationJob, self.job_id).attempt_count, 1)
            self.assertEqual(db.scalar(select(func.count(models.NotificationDispatchAttempt.id))), 1)

    def test_withdrawal_or_schedule_change_blocks_completion(self):
        claim = self.client.post(f"/internal/notifications/{self.job_id}/claim",
                                 headers=self.headers)
        self.assertEqual(claim.status_code, 200)
        with self.sessions() as db:
            db.get(models.NotificationSetting, self.user_id).consent = False
            db.commit()
        verify = self.client.post(f"/internal/notifications/{self.job_id}/verify",
                                  headers=self.headers)
        self.assertFalse(verify.json()["eligible"])
        result = self.client.post(f"/internal/notifications/{self.job_id}/result",
                                  json={"attempt": 1, "result": "simulated"},
                                  headers=self.headers)
        self.assertEqual(result.json()["status"], "canceled")
        with self.sessions() as db:
            self.assertEqual(db.get(models.NotificationJob, self.job_id).status, "canceled")

    def test_retry_and_unknown_are_not_automatically_resent(self):
        with self.sessions() as db:
            first = dispatch.claim_job(db, self.job_id,
                                       now=self.now.replace(tzinfo=timezone.utc))
            failed = dispatch.finish_job(
                db, self.job_id, attempt_number=first["attempt"],
                result="failed", error_code="delivery_failed",
                now=self.now.replace(tzinfo=timezone.utc))
            self.assertEqual(failed["status"], "pending")
            self.assertEqual(dispatch.due_job_ids(db, now=(self.now + timedelta(seconds=30)).replace(
                tzinfo=timezone.utc)), [])
            self.assertEqual(dispatch.due_job_ids(db, now=(self.now + timedelta(seconds=61)).replace(
                tzinfo=timezone.utc)), [self.job_id])
            second = dispatch.claim_job(db, self.job_id,
                                        now=(self.now + timedelta(seconds=61)).replace(
                                            tzinfo=timezone.utc))
            unknown = dispatch.finish_job(
                db, self.job_id, attempt_number=second["attempt"],
                result="failed", error_code="timeout",
                now=(self.now + timedelta(seconds=61)).replace(tzinfo=timezone.utc))
            self.assertEqual(unknown["status"], "unknown")
            db.commit()
        self.assertEqual(self.client.get("/internal/notifications/due",
                                         headers=self.headers).json()["job_ids"], [])

    def test_stale_claim_is_unknown_and_real_recipient_is_rejected(self):
        with self.sessions() as db:
            dispatch.claim_job(db, self.job_id, now=self.now.replace(tzinfo=timezone.utc))
            dispatch.refresh_stale(db, now=(self.now + timedelta(minutes=3)).replace(
                tzinfo=timezone.utc))
            self.assertEqual(db.get(models.NotificationJob, self.job_id).status, "unknown")
            db.commit()
        with self.sessions() as db:
            db.get(models.NotificationJob, self.job_id).status = "pending"
            db.get(models.User, self.user_id).email = "real@invalid.example"
            db.commit()
        self.assertEqual(self.client.get("/internal/notifications/due",
                                         headers=self.headers).json()["job_ids"], [])
        self.assertEqual(self.client.post(f"/internal/notifications/{self.job_id}/claim",
                                          headers=self.headers).status_code, 409)

    def test_send_window_and_schedule_revision(self):
        with self.sessions() as db:
            job = db.get(models.NotificationJob, self.job_id)
            job.send_at = self.now + timedelta(minutes=1)
            db.commit()
        self.assertEqual(self.client.get("/internal/notifications/due",
                                         headers=self.headers).json()["job_ids"], [])
        with self.sessions() as db:
            self.assertEqual(dispatch.due_job_ids(db, now=(self.now + timedelta(minutes=1)).replace(
                tzinfo=timezone.utc)), [self.job_id])
            db.get(models.CoupleSchedule, self.schedule_id).revision += 1
            self.assertEqual(dispatch.due_job_ids(db, now=(self.now + timedelta(minutes=1)).replace(
                tzinfo=timezone.utc)), [])
            self.assertEqual(db.get(models.NotificationJob, self.job_id).status, "canceled")
            db.commit()

    def test_expired_job_and_maximum_retry_count(self):
        with self.sessions() as db:
            job = db.get(models.NotificationJob, self.job_id)
            job.send_at = self.now - timedelta(minutes=11)
            self.assertEqual(dispatch.due_job_ids(db, now=self.now.replace(
                tzinfo=timezone.utc)), [])
            self.assertEqual(job.status, "expired")
            job.status = "pending"
            job.send_at = self.now - timedelta(seconds=30)
            job.attempt_count = dispatch.MAX_ATTEMPTS
            with self.assertRaises(dispatch.DispatchConflict):
                dispatch.claim_job(db, self.job_id,
                                   now=self.now.replace(tzinfo=timezone.utc))

    def test_simulated_recurring_job_plans_next_occurrence_once(self):
        with self.sessions() as db:
            schedule = db.get(models.CoupleSchedule, self.schedule_id)
            schedule.repeat_rule = "weekly"
            job = db.get(models.NotificationJob, self.job_id)
            raw = (f"{schedule.id}:{schedule.revision}:{self.user_id}:"
                   f"day_of:{job.occurrence_date.isoformat()}")
            job.dedupe_key = hashlib.sha256(raw.encode()).hexdigest()
            db.commit()
        claim = self.client.post(f"/internal/notifications/{self.job_id}/claim",
                                 headers=self.headers)
        self.assertEqual(claim.status_code, 200, claim.text)
        result = self.client.post(f"/internal/notifications/{self.job_id}/result",
                                  json={"attempt": 1, "result": "simulated"},
                                  headers=self.headers)
        self.assertEqual(result.json()["status"], "simulated")
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob).where(
                models.NotificationJob.notification_type == "day_of").order_by(
                models.NotificationJob.id)).all()
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[1].status, "pending")
            self.assertGreater(jobs[1].send_at, self.now)
            count = db.scalar(select(func.count(models.NotificationJob.id)))
            notification_logic.plan_next_jobs(db, db.get(models.CoupleSchedule, self.schedule_id))
            self.assertEqual(db.scalar(select(func.count(models.NotificationJob.id))), count)

    def test_failure_retries_stop_after_three_attempts(self):
        with self.sessions() as db:
            for number, seconds in enumerate((0, 61, 183), start=1):
                instant = (self.now + timedelta(seconds=seconds)).replace(
                    tzinfo=timezone.utc)
                claim = dispatch.claim_job(db, self.job_id, now=instant)
                self.assertEqual(claim["attempt"], number)
                result = dispatch.finish_job(
                    db, self.job_id, attempt_number=number, result="failed",
                    error_code="connection_error", now=instant)
                self.assertEqual(result["status"], "failed" if number == 3 else "pending")
            self.assertEqual(dispatch.due_job_ids(db, now=(self.now + timedelta(
                seconds=250)).replace(tzinfo=timezone.utc)), [])
            self.assertEqual(db.scalar(select(func.count(
                models.NotificationDispatchAttempt.id))), 3)

    def test_deleted_schedule_and_disabled_kind_are_not_dispatched(self):
        with self.sessions() as db:
            db.get(models.NotificationSetting, self.user_id).day_of_enabled = False
            self.assertEqual(dispatch.due_job_ids(db,
                now=self.now.replace(tzinfo=timezone.utc)), [])
            job = db.get(models.NotificationJob, self.job_id)
            self.assertEqual(job.status, "canceled")
            job.status = "pending"
            db.get(models.NotificationSetting, self.user_id).day_of_enabled = True
            db.get(models.CoupleSchedule, self.schedule_id).deleted_at = self.now
            self.assertEqual(dispatch.due_job_ids(db,
                now=self.now.replace(tzinfo=timezone.utc)), [])
            self.assertEqual(job.status, "canceled")

    def test_result_schema_rejects_unclassified_or_invalid_failure(self):
        claim = self.client.post(f"/internal/notifications/{self.job_id}/claim",
                                 headers=self.headers)
        self.assertEqual(claim.status_code, 200)
        path = f"/internal/notifications/{self.job_id}/result"
        for body in (
            {"attempt": 1, "result": "failed"},
            {"attempt": 1, "result": "simulated", "error_code": "timeout"},
            {"attempt": 1, "result": "sent"},
            {"attempt": 1, "result": "failed", "error_code": "password"},
        ):
            self.assertEqual(self.client.post(path, json=body,
                                              headers=self.headers).status_code, 422)

    def test_test_email_requires_explicit_gate_and_receipt(self):
        path = f"/internal/notifications/{self.job_id}/claim"
        with patch.dict(os.environ, {"TWO_PICK_N8N_ENABLE_TEST_EMAIL": "0"}):
            self.assertEqual(self.client.post(path, json={"mode": "test_email"},
                                              headers=self.headers).status_code, 409)
        with patch.dict(os.environ, {
            "TWO_PICK_N8N_ENABLE_TEST_EMAIL": "1",
            "TWO_PICK_N8N_TEST_RECIPIENT": "approved@example.test",
        }):
            claim = self.client.post(path, json={"mode": "test_email"},
                                     headers=self.headers)
            self.assertEqual(claim.status_code, 200, claim.text)
            self.assertEqual(claim.json()["recipient_email"], "approved@example.test")
            verify = self.client.post(
                f"/internal/notifications/{self.job_id}/verify",
                headers=self.headers)
            self.assertTrue(verify.json()["eligible"])
            self.assertEqual(verify.json()["recipient_email"], "approved@example.test")
            result_path = f"/internal/notifications/{self.job_id}/result"
            self.assertEqual(self.client.post(result_path, json={
                "attempt": 1, "result": "sent"}, headers=self.headers).status_code, 422)
            receipt = {"attempt": 1, "result": "sent",
                       "provider_message_id": "synthetic-message-1"}
            saved = self.client.post(result_path, json=receipt, headers=self.headers)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()["status"], "sent")
            duplicate = self.client.post(result_path, json=receipt,
                                         headers=self.headers)
            self.assertTrue(duplicate.json()["idempotent"])
            with self.sessions() as db:
                job = db.get(models.NotificationJob, self.job_id)
                attempt = dispatch.latest_attempt(db, self.job_id)
                self.assertIsNotNone(job.succeeded_at)
                self.assertEqual(attempt.provider_message_id, "synthetic-message-1")
                self.assertEqual(attempt.mode, "test_email")

    def test_email_claim_cap_counts_failed_claims_too(self):
        with self.sessions() as db:
            for number in (2, 3):
                db.add(models.NotificationJob(
                    schedule_id=self.schedule_id, schedule_revision=1,
                    recipient_user_id=self.user_id, notification_type="day_of",
                    occurrence_date=date.today(),
                    send_at=self.now - timedelta(seconds=30),
                    dedupe_key=f"{number}" * 64, status="pending",
                    attempt_count=0))
            db.commit()
        with patch.dict(os.environ, {
            "TWO_PICK_N8N_ENABLE_TEST_EMAIL": "1",
            "TWO_PICK_N8N_TEST_RECIPIENT": "approved@example.test",
        }):
            for job_id in (self.job_id, self.job_id + 1):
                claim = self.client.post(f"/internal/notifications/{job_id}/claim",
                    json={"mode": "test_email"}, headers=self.headers)
                self.assertEqual(claim.status_code, 200, claim.text)
            self.assertEqual(self.client.post(
                f"/internal/notifications/{self.job_id + 2}/claim",
                json={"mode": "test_email"}, headers=self.headers).status_code, 409)
            failed = self.client.post(
                f"/internal/notifications/{self.job_id}/result",
                json={"attempt": 1, "result": "failed",
                      "error_code": "delivery_failed"}, headers=self.headers)
            self.assertEqual(failed.json()["status"], "failed")
            self.assertEqual(self.client.post(
                f"/internal/notifications/{self.job_id + 2}/claim",
                json={"mode": "test_email"}, headers=self.headers).status_code, 409)

    def test_attempt_ledger_migration_preserves_existing_row(self):
        legacy = create_engine("sqlite:///" + str(Path(self.temp.name) / "legacy.db"))
        try:
            with legacy.begin() as conn:
                conn.exec_driver_sql("CREATE TABLE notification_dispatch_attempts ("
                    "id INTEGER PRIMARY KEY, job_id INTEGER, number INTEGER, "
                    "status VARCHAR(20), claimed_at DATETIME, completed_at DATETIME, "
                    "retry_after DATETIME, error_code VARCHAR(40))")
                conn.exec_driver_sql("INSERT INTO notification_dispatch_attempts "
                    "(id, job_id, number, status, claimed_at) "
                    "VALUES (1, 1, 1, 'simulated', '2026-11-25 00:00:00')")
            ensure_notification_attempt_columns(legacy)
            with legacy.connect() as conn:
                row = conn.exec_driver_sql("SELECT status, mode, "
                    "provider_message_id FROM notification_dispatch_attempts "
                    "WHERE id=1").one()
            self.assertEqual(tuple(row), ("simulated", "mock", None))
        finally:
            legacy.dispose()


if __name__ == "__main__":
    unittest.main()
