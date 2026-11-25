"""Competing HTTP requests use separate SQLite file connections."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import main
import models
from auth import hash_password
from database import Base


class DecisionConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        path = Path(self.temporary.name) / "race.db"
        self.engine = create_engine(
            f"sqlite:///{path.as_posix()}",
            connect_args={"check_same_thread": False, "timeout": 5},
        )
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.password = "concurrency-test-password"
        with self.sessions() as db:
            couple = models.Couple(invite_code="DEC-RACE")
            db.add(couple)
            db.flush()
            users = [models.User(
                email=f"race-{name}@example.test", nickname=name,
                hashed_password=hash_password(self.password), couple_id=couple.id,
            ) for name in ("a", "b")]
            db.add_all(users)
            db.flush()
            decision = models.Decision(
                couple_id=couple.id, created_by_id=users[0].id,
                title="Concurrent choice", status="open",
            )
            db.add(decision)
            db.flush()
            db.add_all([models.DecisionCondition(
                decision_id=decision.id, user_id=user.id,
                max_budget=30000, available_time="Saturday",
                preferences="quiet", avoidances="spicy",
            ) for user in users])
            db.commit()
            self.did = decision.id

        def test_db():
            with self.sessions() as db:
                yield db

        main.app.dependency_overrides[main.get_db] = test_db
        self.client = TestClient(main.app)
        self.headers = {}
        for name in ("a", "b"):
            response = self.client.post("/token", data={
                "username": f"race-{name}@example.test",
                "password": self.password,
            })
            self.assertEqual(response.status_code, 200)
            self.headers[name] = {"Authorization": f"Bearer {response.json()['access_token']}"}

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.engine.dispose()
        self.temporary.cleanup()

    def competing(self, first, second):
        gate = Barrier(2)

        def run(action):
            gate.wait()
            return action()

        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(run, first)
            b = pool.submit(run, second)
            return a.result(), b.result()

    def candidate(self, content):
        return self.client.post(
            f"/decisions/{self.did}/candidates", json={"content": content},
            headers=self.headers["a"],
        )

    def test_parallel_candidates_have_unique_versions_and_one_current(self):
        responses = self.competing(lambda: self.candidate("First"),
                                   lambda: self.candidate("Second"))
        self.assertEqual(sorted(reply.status_code for reply in responses), [201, 201])
        with self.sessions() as db:
            candidates = db.scalars(select(models.DecisionCandidate).where(
                models.DecisionCandidate.decision_id == self.did
            )).all()
            self.assertEqual(sorted(c.version for c in candidates), [1, 2])
            self.assertEqual(sum(c.is_current for c in candidates), 1)

    def test_parallel_approvals_confirm_once_and_duplicate_is_rejected(self):
        candidate_id = self.candidate("Shared").json()["id"]

        def approve(name):
            return self.client.post(
                f"/candidates/{candidate_id}/approve", headers=self.headers[name]
            )

        responses = self.competing(lambda: approve("a"), lambda: approve("b"))
        self.assertEqual(sorted(reply.status_code for reply in responses), [201, 201])
        self.assertEqual(approve("a").status_code, 409)
        with self.sessions() as db:
            decision = db.get(models.Decision, self.did)
            self.assertEqual(decision.status, "confirmed")
            self.assertEqual(db.scalar(select(func.count(models.DecisionApproval.id))), 2)
            self.assertEqual(db.scalar(select(func.count(models.DecisionConfirmation.id))), 1)
        self.assertEqual(self.candidate("Late").status_code, 409)

    def test_recommendation_competes_with_manual_candidate(self):
        def recommend():
            return self.client.post(
                f"/decisions/{self.did}/recommendations",
                json={"options": [
                    {"title": "One", "estimated_total_cost_krw": 10000,
                     "time_slot": "Saturday", "tags": ["quiet"]},
                    {"title": "Two", "estimated_total_cost_krw": 12000,
                     "time_slot": "Saturday", "tags": []},
                ]}, headers=self.headers["b"],
            )

        responses = self.competing(recommend, lambda: self.candidate("Manual"))
        self.assertIn(sorted(reply.status_code for reply in responses),
                      ([201, 409], [201, 201]))
        with self.sessions() as db:
            candidates = db.scalars(select(models.DecisionCandidate).where(
                models.DecisionCandidate.decision_id == self.did
            )).all()
            self.assertEqual(len(candidates), sum(r.status_code == 201 for r in responses))
            self.assertEqual(len({c.version for c in candidates}), len(candidates))
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id)).where(
                models.DecisionCandidate.is_current.is_(True)
            )), 1)

    def test_parallel_duplicate_approval_is_stored_once(self):
        candidate_id = self.candidate("Shared").json()["id"]
        approve = lambda: self.client.post(
            f"/candidates/{candidate_id}/approve", headers=self.headers["a"])
        responses = self.competing(approve, approve)
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409])
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionApproval.id))), 1)
            self.assertEqual(db.get(models.Decision, self.did).status, "open")

    def test_condition_edit_and_recommendation_are_serialized(self):
        request = {"options": [
            {"title": "One", "estimated_total_cost_krw": 10000,
             "time_slot": "Saturday", "tags": ["quiet"]},
            {"title": "Two", "estimated_total_cost_krw": 12000,
             "time_slot": "Saturday", "tags": []},
        ]}
        def recommend():
            return self.client.post(f"/decisions/{self.did}/recommendations",
                                    json=request, headers=self.headers["b"])
        def edit():
            return self.client.put(f"/decisions/{self.did}/conditions/me", json={
                "max_budget": 25000, "available_time": "Saturday",
                "preferences": "quiet", "avoidances": "spicy",
            }, headers=self.headers["a"])
        responses = self.competing(recommend, edit)
        self.assertIn(sorted(r.status_code for r in responses), ([200, 201], [201, 409]))
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(models.DecisionRecommendationAttempt.id))), 1)
            self.assertEqual(db.scalar(select(func.count(models.DecisionCandidate.id))), 1)
        self.assertEqual(edit().status_code, 409)

    def test_confirmation_competes_with_new_candidate(self):
        candidate_id = self.candidate("First").json()["id"]
        self.assertEqual(self.client.post(f"/candidates/{candidate_id}/approve",
                                          headers=self.headers["a"]).status_code, 201)
        def confirm():
            return self.client.post(f"/candidates/{candidate_id}/approve",
                                    headers=self.headers["b"])
        responses = self.competing(confirm, lambda: self.candidate("Second"))
        self.assertEqual(sorted(r.status_code for r in responses), [201, 409])
        with self.sessions() as db:
            decision = db.get(models.Decision, self.did)
            confirmations = db.scalars(select(models.DecisionConfirmation)).all()
            current = db.scalars(select(models.DecisionCandidate).where(
                models.DecisionCandidate.is_current.is_(True))).all()
            self.assertEqual(len(current), 1)
            if decision.status == "confirmed":
                self.assertEqual(len(confirmations), 1)
                self.assertEqual(confirmations[0].candidate_id, candidate_id)
            else:
                self.assertEqual(decision.status, "open")
                self.assertEqual(len(confirmations), 0)
                self.assertNotEqual(current[0].id, candidate_id)


if __name__ == "__main__":
    unittest.main()
