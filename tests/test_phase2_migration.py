"""Existing SQLite rows are preserved when additive phase 2 schema is applied."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import models
from database import Base, ensure_current_candidate_index


class Phase2MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        path = Path(self.temp.name) / "legacy.db"
        self.engine = create_engine(f"sqlite:///{path.as_posix()}")
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("DROP INDEX uq_decision_current_candidate")
            for name in ("notification_jobs", "notification_settings",
                         "couple_schedules", "decision_feedback", "couple_invites"):
                connection.exec_driver_sql(f"DROP TABLE {name}")
        self.sessions = sessionmaker(bind=self.engine)
        with self.sessions() as db:
            couple = models.Couple(invite_code="LEGACY01")
            db.add(couple); db.flush()
            user = models.User(email="old@example.test", nickname="old",
                               hashed_password="never-used", couple_id=couple.id)
            db.add(user); db.flush()
            decision = models.Decision(couple_id=couple.id, created_by_id=user.id,
                                       title="old", status="open")
            db.add(decision); db.flush()
            db.add(models.DecisionCandidate(decision_id=decision.id,
                                            content="old candidate", version=1,
                                            is_current=True))
            db.commit()
            self.decision_id = decision.id

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_additive_schema_preserves_legacy_rows_without_fake_invite_timestamp(self):
        Base.metadata.create_all(self.engine)
        ensure_current_candidate_index(self.engine)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.User.id))), 1)
            self.assertEqual(db.scalar(select(func.count(models.Decision.id))), 1)
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id))), 1)
            self.assertEqual(db.scalar(select(func.count(models.CoupleInvite.couple_id))), 0)
            self.assertEqual(db.scalar(select(func.count(models.NotificationJob.id))), 0)
            self.assertEqual(db.scalar(select(models.DecisionCandidate.content)), "old candidate")

    def test_duplicate_current_candidates_stop_index_migration_without_row_deletion(self):
        with self.sessions() as db:
            db.add(models.DecisionCandidate(decision_id=self.decision_id,
                                            content="second", version=2,
                                            is_current=True))
            db.commit()
        with self.assertRaises(RuntimeError):
            ensure_current_candidate_index(self.engine)
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id))), 2)


if __name__ == "__main__":
    unittest.main()
