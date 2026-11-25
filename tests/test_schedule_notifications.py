"""Schedule and consent tests use an isolated database and real JWT logins."""

import unittest
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import models
import notification_logic
from auth import hash_password
from database import Base
from schedule_logic import occurrence_on_or_after


class ScheduleNotificationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            couples = [models.Couple(invite_code="SCHAAAA1"),
                       models.Couple(invite_code="SCHBBBB2")]
            db.add_all(couples)
            db.flush()
            for email, couple in (("a@example.test", couples[0]),
                                  ("b@example.test", couples[0]),
                                  ("c@example.test", couples[1])):
                db.add(models.User(email=email, nickname=email[0],
                                   hashed_password=hash_password("schedule-test-password"),
                                   couple_id=couple.id))
            db.commit()

        def db_override():
            with self.sessions() as db:
                yield db

        main.app.dependency_overrides[main.get_db] = db_override
        self.client = TestClient(main.app)
        self.headers = {}
        for key in "abc":
            token = self.client.post("/token", data={"username": f"{key}@example.test",
                                                      "password": "schedule-test-password"})
            self.assertEqual(token.status_code, 200, token.text)
            self.headers[key] = {"Authorization": "Bearer " + token.json()["access_token"]}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()

    def schedule(self, key="a", **overrides):
        data = {"title": "기념일", "kind": "anniversary",
                "local_date": "2030-02-28", "local_time": None}
        data.update(overrides)
        return self.client.post("/schedules", json=data, headers=self.headers[key])

    def setting(self, key, consent):
        return self.client.put("/notifications/settings/me", json={
            "consent": consent, "d1_enabled": True, "day_of_enabled": True,
            "send_time": "09:00:00",
        }, headers=self.headers[key])

    def test_schedule_crud_and_couple_isolation(self):
        created = self.schedule()
        self.assertEqual(created.status_code, 201, created.text)
        item = created.json()
        self.assertEqual((item["repeat_rule"], item["revision"], item["timezone"]),
                         ("yearly", 1, "Asia/Seoul"))
        sid = item["id"]
        self.assertEqual(self.client.get(f"/schedules/{sid}", headers=self.headers["b"]).status_code, 200)
        self.assertEqual(self.client.get(f"/schedules/{sid}", headers=self.headers["c"]).status_code, 403)
        self.assertEqual(self.client.put(f"/schedules/{sid}", json={
            "title": "bad", "kind": "schedule", "local_date": "2031-01-01",
        }, headers=self.headers["c"]).status_code, 403)
        self.assertEqual(self.client.get("/schedules", headers=self.headers["c"]).json(), [])
        updated = self.client.put(f"/schedules/{sid}", json={
            "title": "변경", "kind": "schedule", "local_date": "2030-03-01",
            "repeat_rule": "monthly", "local_time": "18:30:00",
        }, headers=self.headers["b"])
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["revision"], 2)
        self.assertEqual(self.client.delete(f"/schedules/{sid}", headers=self.headers["a"]).status_code, 204)
        self.assertEqual(self.client.get(f"/schedules/{sid}", headers=self.headers["b"]).status_code, 404)

    def test_schedule_validation_and_recurrence_boundaries(self):
        self.assertEqual(self.schedule(kind="anniversary", repeat_rule="weekly").status_code, 422)
        self.assertEqual(self.schedule(local_date="2030-02-30").status_code, 422)
        self.assertEqual(self.schedule(title=" ").status_code, 422)
        self.assertEqual(occurrence_on_or_after(date(2028, 1, 31), "monthly",
                                                 date(2028, 2, 1)), date(2028, 2, 29))
        self.assertEqual(occurrence_on_or_after(date(2028, 1, 31), "monthly",
                                                 date(2028, 3, 1)), date(2028, 3, 31))
        self.assertEqual(occurrence_on_or_after(date(2028, 2, 29), "yearly",
                                                 date(2029, 1, 1)), date(2029, 2, 28))

    def test_consent_default_independent_jobs_and_minimal_mock_payload(self):
        a = self.client.get("/notifications/settings/me", headers=self.headers["a"])
        self.assertFalse(a.json()["consent"])
        self.assertFalse(a.json()["d1_enabled"])
        self.assertFalse(a.json()["day_of_enabled"])
        self.assertEqual(self.client.put("/notifications/settings/me", json={
            "consent": True, "user_id": 2,
        }, headers=self.headers["a"]).status_code, 422)
        self.assertEqual(self.setting("a", True).status_code, 200)
        created = self.schedule(local_date="2030-02-28")
        self.assertEqual(created.status_code, 201, created.text)
        sid = created.json()["id"]
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob).where(
                models.NotificationJob.schedule_id == sid)).all()
            self.assertEqual(len(jobs), 2)
            self.assertEqual({job.recipient_user_id for job in jobs}, {1})
            due = jobs[0].send_at.replace(tzinfo=timezone.utc)
            payload = notification_logic.prepare_mock_payload(db, jobs[0].id, now=due)
            self.assertEqual(payload["recipient_email"], "a@example.test")
            self.assertFalse(set(payload) & {"password", "jwt", "secret_key",
                                             "private_conditions", "partner_email"})
            notification_logic.plan_next_jobs(db, db.get(models.CoupleSchedule, sid))
            db.commit()
            self.assertEqual(len(db.scalars(select(models.NotificationJob)).all()), 2)
        self.assertEqual(self.setting("b", True).status_code, 200)
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob).where(
                models.NotificationJob.schedule_id == sid)).all()
            self.assertEqual(len(jobs), 4)

    def test_withdrawal_schedule_change_and_delete_cancel_jobs(self):
        consented = self.setting("a", True)
        self.assertIsNotNone(consented.json()["consented_at"])
        created = self.schedule()
        sid = created.json()["id"]
        withdrawn = self.setting("a", False)
        self.assertIsNotNone(withdrawn.json()["withdrawn_at"])
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob)).all()
            self.assertTrue(jobs)
            self.assertTrue(all(job.status == "canceled" for job in jobs))
            with self.assertRaises(ValueError):
                notification_logic.prepare_mock_payload(db, jobs[0].id)
        reconsented = self.setting("a", True)
        self.assertEqual(reconsented.json()["withdrawn_at"],
                         withdrawn.json()["withdrawn_at"])
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob)).all()
            self.assertEqual(len(jobs), 2)
            self.assertTrue(all(job.status == "pending" for job in jobs))
        self.client.put(f"/schedules/{sid}", json={
            "title": "변경", "kind": "anniversary", "local_date": "2031-02-28",
        }, headers=self.headers["a"])
        with self.sessions() as db:
            jobs = db.scalars(select(models.NotificationJob)).all()
            self.assertEqual(len(jobs), 4)
            self.assertEqual(sum(job.status == "pending" for job in jobs), 2)
        self.client.delete(f"/schedules/{sid}", headers=self.headers["a"])
        with self.sessions() as db:
            self.assertEqual(sum(job.status == "pending" for job in
                                 db.scalars(select(models.NotificationJob))), 0)


if __name__ == "__main__":
    unittest.main()
